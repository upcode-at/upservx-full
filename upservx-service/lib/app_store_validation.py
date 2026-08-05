"""Mandatory manifest and Docker Compose validation for App Store templates."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator, FormatChecker


FORBIDDEN_IMAGE_TAGS = {"latest", "stable", "release", "main", "lts", "alpine"}
UNSAFE_CREDENTIAL_MARKERS = (
    "changeme",
    "adminpassword",
    "rootpassword",
    "mypassword",
    "passw0rd",
    "harbor12345",
    "redispassword",
)
VARIABLE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)")


class TemplateValidationError(ValueError):
    """Raised when an App Store template is unsafe or malformed."""


def load_manifest(template_dir: str | Path) -> dict[str, Any]:
    path = Path(template_dir) / "app.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TemplateValidationError(f"{path}: invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise TemplateValidationError(f"{path}: manifest must be an object")
    return value


def _format_schema_error(error: Any) -> str:
    location = ".".join(str(item) for item in error.absolute_path) or "manifest"
    return f"{location}: {error.message}"


def validate_manifest(
    manifest: Mapping[str, Any], app_id: str, schema_path: str | Path
) -> None:
    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TemplateValidationError(f"Could not load App Store schema: {error}") from error
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(dict(manifest)), key=lambda item: list(item.path))
    if errors:
        raise TemplateValidationError("; ".join(_format_schema_error(error) for error in errors))
    if manifest["id"] != app_id:
        raise TemplateValidationError(
            f"manifest id {manifest['id']!r} must match directory {app_id!r}"
        )
    variables = manifest["environment"]
    names = [variable["name"] for variable in variables]
    if len(names) != len(set(names)):
        raise TemplateValidationError("environment variable names must be unique")
    for variable in variables:
        if variable.get("managed") and variable["secret"]:
            raise TemplateValidationError(
                f"{variable['name']}: managed variables cannot be secrets"
            )
        if variable["generate"] and not variable["secret"]:
            raise TemplateValidationError(
                f"{variable['name']}: generated values must be marked secret"
            )
        if variable["secret"] and variable["default"]:
            raise TemplateValidationError(
                f"{variable['name']}: secret variables cannot have manifest defaults"
            )
        if variable["generate"] and not variable["required"]:
            raise TemplateValidationError(
                f"{variable['name']}: generated values must be required"
            )


def _image_tag(image: str) -> str | None:
    if "@sha256:" in image:
        return None
    final_component = image.rsplit("/", 1)[-1]
    if ":" not in final_component:
        return ""
    return final_component.rsplit(":", 1)[-1]


def compose_environment(manifest: Mapping[str, Any], *, validation: bool) -> dict[str, str]:
    values: dict[str, str] = {}
    for variable in manifest["environment"]:
        value = variable["default"]
        if variable.get("managed") and validation:
            value = "/tmp/upservx-app-validation"
        if not value and validation:
            length = max(16, int(variable.get("min_length", 32)))
            value = ("validation-value-" + variable["name"].lower())[:length]
            value = value.ljust(length, "x")
        if value:
            values[variable["name"]] = value
    return values


def validate_compose_structure(
    compose_path: str | Path, manifest: Mapping[str, Any]
) -> None:
    path = Path(compose_path)
    try:
        raw = path.read_text(encoding="utf-8")
        compose = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as error:
        raise TemplateValidationError(f"{path}: invalid Compose YAML: {error}") from error
    if not isinstance(compose, dict) or not isinstance(compose.get("services"), dict):
        raise TemplateValidationError(f"{path}: Compose must contain a services object")
    if not compose["services"]:
        raise TemplateValidationError(f"{path}: Compose must define at least one service")
    for service_name, service in compose["services"].items():
        if not isinstance(service, dict):
            raise TemplateValidationError(f"{path}: service {service_name!r} must be an object")
        image = service.get("image")
        if not isinstance(image, str) or not image:
            raise TemplateValidationError(
                f"{path}: service {service_name!r} must use a pinned image"
            )
        if "container_name" in service:
            raise TemplateValidationError(
                f"{path}: service {service_name!r} cannot hard-code container_name"
            )
        tag = _image_tag(image)
        if tag == "" or (tag and tag.lower() in FORBIDDEN_IMAGE_TAGS):
            raise TemplateValidationError(
                f"{path}: service {service_name!r} image is not intentionally pinned: {image}"
            )
    lowered = raw.lower()
    for marker in UNSAFE_CREDENTIAL_MARKERS:
        if marker in lowered:
            raise TemplateValidationError(
                f"{path}: unsafe hard-coded credential marker {marker!r}"
            )
    declared = {item["name"] for item in manifest["environment"]}
    referenced = set(VARIABLE_PATTERN.findall(raw))
    undeclared = sorted(referenced - declared)
    if undeclared:
        raise TemplateValidationError(
            f"{path}: Compose references undeclared variables: {', '.join(undeclared)}"
        )


def validate_compose_cli(
    template_dir: str | Path, manifest: Mapping[str, Any], project_name: str
) -> None:
    directory = Path(template_dir)
    environment = os.environ.copy()
    environment.update(compose_environment(manifest, validation=True))
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(directory),
            "-f",
            str(directory / "docker-compose.yml"),
            "-p",
            project_name,
            "config",
            "--quiet",
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise TemplateValidationError(
            result.stderr.strip() or result.stdout.strip() or "docker compose config failed"
        )


def validate_template(
    template_dir: str | Path,
    schema_path: str | Path,
    *,
    compose_cli: bool = False,
) -> dict[str, Any]:
    directory = Path(template_dir)
    app_id = directory.name
    manifest = load_manifest(directory)
    validate_manifest(manifest, app_id, schema_path)
    validate_compose_structure(directory / "docker-compose.yml", manifest)
    if compose_cli:
        validate_compose_cli(directory, manifest, f"validate-{app_id}")
    return manifest
