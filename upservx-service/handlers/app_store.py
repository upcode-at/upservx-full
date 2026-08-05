"""Validated, transactional App Store installation and update workflows."""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from dotenv import dotenv_values

from lib.app_store_validation import (
    TemplateValidationError,
    validate_compose_structure,
    validate_manifest,
    validate_template,
)
from lib.file_lock import InterProcessFileLock
from lib.logger import log_appstore


APP_STORE_DIR = os.getenv("UPSERVX_APP_STORE_DIR", "/var/lib/upservx/app-store")
COMPOSE_BASE_DIR = os.getenv("UPSERVX_COMPOSE_DIR", "/var/lib/upservx/compose")
APP_DATA_BASE_DIR = os.getenv(
    "UPSERVX_APP_DATA_DIR", "/var/lib/upservx/app-data"
)
APP_SCHEMA_PATH = os.getenv(
    "UPSERVX_APP_SCHEMA", os.path.join(APP_STORE_DIR, "app.schema.json")
)
INSTALL_METADATA = ".upservx-installation.json"
PROJECT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
INSTALL_TIMEOUT = int(os.getenv("UPSERVX_APP_INSTALL_TIMEOUT", "900"))


class AppStore:
    """Manage schema-validated Compose templates and installations."""

    def __init__(self) -> None:
        self._lock = InterProcessFileLock(
            os.path.join(COMPOSE_BASE_DIR, ".app-store.lock")
        )

    @staticmethod
    def _safe_child(base: str, name: str) -> Path:
        root = Path(base).resolve()
        candidate = (root / name).resolve()
        if candidate.parent != root:
            raise ValueError("Invalid App Store identifier")
        return candidate

    def _template_dir(self, app_id: str) -> Path:
        if not PROJECT_PATTERN.fullmatch(app_id):
            raise ValueError("Invalid App Store identifier")
        return self._safe_child(APP_STORE_DIR, app_id)

    def _project_name(self, name: str) -> str:
        from handlers.compose_manager import normalize_project_name

        normalized = normalize_project_name(name)
        if not PROJECT_PATTERN.fullmatch(normalized):
            raise ValueError("Project name must contain at most 63 safe characters")
        return normalized

    def _schema_path(self) -> Path:
        return Path(APP_SCHEMA_PATH)

    def _load_template(self, app_id: str) -> tuple[Path, dict[str, Any]]:
        directory = self._template_dir(app_id)
        if not directory.is_dir():
            raise FileNotFoundError("App not found in store")
        manifest = validate_template(directory, self._schema_path())
        return directory, manifest

    @staticmethod
    def _icon(app_id: str, directory: Path, manifest: Mapping[str, Any]) -> str:
        for filename in ("icon.png", "logo.png", "icon.jpg", "logo.jpg"):
            if (directory / filename).is_file():
                return f"/containers/app-store/apps/{app_id}/icon"
        return str(manifest["icon"])

    def _installation_index(self) -> dict[str, list[dict[str, Any]]]:
        from handlers.compose_manager import compose_manager

        index: dict[str, list[dict[str, Any]]] = {}
        base = Path(COMPOSE_BASE_DIR)
        if not base.exists():
            return index
        for project_dir in base.iterdir():
            if not project_dir.is_dir() or project_dir.is_symlink():
                continue
            metadata_path = project_dir / INSTALL_METADATA
            metadata: dict[str, Any] | None = None
            if metadata_path.is_file() and not metadata_path.is_symlink():
                try:
                    loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        metadata = loaded
                except (OSError, json.JSONDecodeError):
                    metadata = None
            elif (project_dir / "app.json").is_file():
                # Compatibility for projects installed by the former copy-only path.
                try:
                    legacy = json.loads(
                        (project_dir / "app.json").read_text(encoding="utf-8")
                    )
                    template_id = str(legacy.get("id") or project_dir.name)
                    metadata = {
                        "template_id": template_id,
                        "project_name": project_dir.name,
                        "version": legacy.get("version", "unknown"),
                        "legacy": True,
                    }
                except (OSError, json.JSONDecodeError):
                    metadata = None
            if not metadata or not PROJECT_PATTERN.fullmatch(
                str(metadata.get("template_id", ""))
            ):
                continue
            project_name = project_dir.name
            record = {
                "project_name": project_name,
                "version": metadata.get("version"),
                "installed_at": metadata.get("installed_at"),
                "updated_at": metadata.get("updated_at"),
                "status": compose_manager._get_project_status(
                    project_name, str(project_dir)
                ),
            }
            index.setdefault(str(metadata["template_id"]), []).append(record)
        return index

    def _public_app(
        self,
        app_id: str,
        directory: Path,
        manifest: Mapping[str, Any],
        installations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            **dict(manifest),
            "icon": self._icon(app_id, directory, manifest),
            "installed": bool(installations),
            "installations": installations,
        }

    def list_apps(self) -> List[Dict[str, Any]]:
        apps: list[dict[str, Any]] = []
        installations = self._installation_index()
        template_root = Path(APP_STORE_DIR)
        if not template_root.is_dir():
            return apps
        for directory in sorted(template_root.iterdir()):
            if not directory.is_dir() or directory.is_symlink():
                continue
            try:
                template_dir, manifest = self._load_template(directory.name)
                apps.append(
                    self._public_app(
                        directory.name,
                        template_dir,
                        manifest,
                        installations.get(directory.name, []),
                    )
                )
            except Exception as error:
                log_appstore(
                    f"Rejected invalid App Store template [{directory.name}]: {error}",
                    error=True,
                )
        return sorted(apps, key=lambda app: str(app["name"]).lower())

    def get_app_details(self, app_id: str) -> Optional[Dict[str, Any]]:
        try:
            directory, manifest = self._load_template(app_id)
            installations = self._installation_index().get(app_id, [])
            result = self._public_app(
                app_id, directory, manifest, installations
            )
            result["compose_content"] = (directory / "docker-compose.yml").read_text(
                encoding="utf-8"
            )
            readme = directory / "README.md"
            result["readme"] = (
                readme.read_text(encoding="utf-8") if readme.is_file() else ""
            )
            return result
        except (FileNotFoundError, ValueError, TemplateValidationError, OSError) as error:
            log_appstore(f"Could not load App Store app [{app_id}]: {error}", error=True)
            return None

    @staticmethod
    def _generate_value(variable: Mapping[str, Any]) -> str:
        if variable.get("generator") == "kafka-cluster-id":
            return base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip("=")
        minimum = max(16, int(variable.get("min_length", 32)))
        while True:
            value = secrets.token_urlsafe(max(18, minimum))
            if len(value) >= minimum:
                return value

    def _resolve_environment(
        self,
        manifest: Mapping[str, Any],
        submitted: Mapping[str, str] | None,
        project_name: str,
    ) -> dict[str, str]:
        supplied = dict(submitted or {})
        descriptors = {item["name"]: item for item in manifest["environment"]}
        managed = {name for name, item in descriptors.items() if item.get("managed")}
        unknown = sorted(set(supplied) - set(descriptors))
        forbidden = sorted(set(supplied) & managed)
        if unknown:
            raise ValueError(f"Unknown environment variables: {', '.join(unknown)}")
        if forbidden:
            raise ValueError(f"Managed environment variables cannot be set: {', '.join(forbidden)}")

        values: dict[str, str] = {}
        for name, descriptor in descriptors.items():
            if descriptor.get("managed"):
                if name == "APP_DATA_DIR":
                    value = str(self._safe_child(APP_DATA_BASE_DIR, project_name))
                else:
                    raise ValueError(f"Unsupported managed variable: {name}")
            elif name in supplied:
                value = supplied[name]
            elif descriptor["default"]:
                value = descriptor["default"]
            elif descriptor["generate"]:
                value = self._generate_value(descriptor)
            else:
                value = ""
            if not isinstance(value, str) or "\x00" in value or "\n" in value or "\r" in value:
                raise ValueError(f"{name} must be a single-line string")
            if descriptor["required"] and not value:
                raise ValueError(f"{name} is required")
            minimum = int(descriptor.get("min_length", 0))
            if value and len(value) < minimum:
                raise ValueError(f"{name} must contain at least {minimum} characters")
            if value:
                values[name] = value
        return values

    @staticmethod
    def _dotenv(values: Mapping[str, str]) -> str:
        lines = []
        for name in sorted(values):
            escaped = values[name].replace("\\", "\\\\").replace("'", "\\'")
            lines.append(f"{name}='{escaped}'")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _write_private(path: Path, content: str) -> None:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            raise

    @classmethod
    def _replace_private(cls, path: Path, content: str) -> None:
        temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}"
        cls._write_private(temporary, content)
        try:
            os.replace(temporary, path)
            os.chmod(path, 0o600)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _compose_command(
        project_dir: Path, project_name: str, *arguments: str
    ) -> list[str]:
        return [
            "docker",
            "compose",
            "--env-file",
            str(project_dir / ".env"),
            "--project-directory",
            str(project_dir),
            "-f",
            str(project_dir / "docker-compose.yml"),
            "-p",
            project_name,
            *arguments,
        ]

    @staticmethod
    def _run(command: list[str], project_dir: Path, timeout: int = INSTALL_TIMEOUT) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=timeout,
            check=False,
        )

    def _run_required(
        self, project_dir: Path, project_name: str, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        result = self._run(
            self._compose_command(project_dir, project_name, *arguments),
            project_dir,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "Docker Compose failed"
            raise RuntimeError(message)
        return result

    def _write_metadata(
        self,
        project_dir: Path,
        *,
        template_id: str,
        project_name: str,
        version: str,
        environment_names: list[str],
        installed_at: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "template_id": template_id,
            "project_name": project_name,
            "version": version,
            "installed_at": installed_at or now,
            "updated_at": now,
            "environment_names": sorted(environment_names),
        }
        path = project_dir / INSTALL_METADATA
        temporary = project_dir / f".{INSTALL_METADATA}.{uuid.uuid4().hex}"
        self._write_private(temporary, json.dumps(payload, indent=2) + "\n")
        os.replace(temporary, path)
        os.chmod(path, 0o600)

    def install_app(
        self,
        app_id: str,
        custom_name: Optional[str] = None,
        environment: Mapping[str, str] | None = None,
    ) -> Dict[str, Any]:
        try:
            template_dir, manifest = self._load_template(app_id)
            project_name = self._project_name(custom_name or app_id)
            project_dir = self._safe_child(COMPOSE_BASE_DIR, project_name)
            data_dir = self._safe_child(APP_DATA_BASE_DIR, project_name)
            with self._lock:
                if project_dir.exists():
                    raise FileExistsError(f"Project '{project_name}' already exists")
                values = self._resolve_environment(
                    manifest, environment, project_name
                )
                project_dir.mkdir(mode=0o700)
                try:
                    if "APP_DATA_DIR" in values:
                        data_dir.mkdir(parents=True, mode=0o750)
                    for source in template_dir.iterdir():
                        if source.is_symlink():
                            raise ValueError("Template files cannot be symbolic links")
                        destination = project_dir / source.name
                        if source.is_dir():
                            if any(path.is_symlink() for path in source.rglob("*")):
                                raise ValueError("Template directories cannot contain symbolic links")
                            shutil.copytree(source, destination, symlinks=False)
                        elif source.is_file():
                            shutil.copy2(source, destination)
                    self._write_private(project_dir / ".env", self._dotenv(values))
                    validate_manifest(manifest, app_id, self._schema_path())
                    validate_compose_structure(
                        project_dir / "docker-compose.yml", manifest
                    )
                    self._run_required(project_dir, project_name, "config", "--quiet")
                    self._run_required(project_dir, project_name, "pull")
                    self._run_required(
                        project_dir,
                        project_name,
                        "up",
                        "-d",
                        "--wait",
                        "--wait-timeout",
                        str(INSTALL_TIMEOUT),
                    )
                    self._write_metadata(
                        project_dir,
                        template_id=app_id,
                        project_name=project_name,
                        version=str(manifest["version"]),
                        environment_names=list(values),
                    )
                except Exception:
                    self._run(
                        self._compose_command(
                            project_dir,
                            project_name,
                            "down",
                            "--volumes",
                            "--remove-orphans",
                        ),
                        project_dir,
                    )
                    shutil.rmtree(project_dir, ignore_errors=True)
                    shutil.rmtree(data_dir, ignore_errors=True)
                    raise
            log_appstore(f"Installed app [{app_id}] as project [{project_name}]")
            return {
                "success": True,
                "message": f"App installed and healthy as '{project_name}'",
                "project_name": project_name,
                "template_id": app_id,
            }
        except Exception as error:
            log_appstore(f"Failed to install app [{app_id}]: {error}", error=True)
            return {"success": False, "message": str(error)}

    def update_app(self, project_name: str) -> Dict[str, Any]:
        try:
            project_name = self._project_name(project_name)
            project_dir = self._safe_child(COMPOSE_BASE_DIR, project_name)
            metadata_path = project_dir / INSTALL_METADATA
            if not metadata_path.is_file() or metadata_path.is_symlink():
                raise FileNotFoundError("Managed App Store installation not found")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            template_id = str(metadata["template_id"])
            template_dir, manifest = self._load_template(template_id)
            if manifest["update"]["strategy"] != "compose-pull-recreate":
                raise ValueError("Unsupported application update strategy")
            saved_environment = {
                key: value
                for key, value in dotenv_values(project_dir / ".env").items()
                if isinstance(value, str)
            }
            descriptors = {item["name"]: item for item in manifest["environment"]}
            submitted_environment = {
                key: value
                for key, value in saved_environment.items()
                if key in descriptors and not descriptors[key].get("managed")
            }
            environment = self._resolve_environment(
                manifest, submitted_environment, project_name
            )
            compose_path = project_dir / "docker-compose.yml"
            app_path = project_dir / "app.json"
            env_path = project_dir / ".env"
            old_compose = compose_path.read_bytes()
            old_app = app_path.read_bytes()
            old_env = env_path.read_text(encoding="utf-8")
            with self._lock:
                try:
                    shutil.copy2(template_dir / "docker-compose.yml", compose_path)
                    shutil.copy2(template_dir / "app.json", app_path)
                    self._replace_private(env_path, self._dotenv(environment))
                    validate_compose_structure(compose_path, manifest)
                    self._run_required(project_dir, project_name, "config", "--quiet")
                    self._run_required(project_dir, project_name, "pull")
                    self._run_required(
                        project_dir,
                        project_name,
                        "up",
                        "-d",
                        "--wait",
                        "--wait-timeout",
                        str(INSTALL_TIMEOUT),
                    )
                except Exception as update_error:
                    compose_path.write_bytes(old_compose)
                    app_path.write_bytes(old_app)
                    self._replace_private(env_path, old_env)
                    rollback = self._run(
                        self._compose_command(
                            project_dir,
                            project_name,
                            "up",
                            "-d",
                            "--wait",
                            "--wait-timeout",
                            str(INSTALL_TIMEOUT),
                        ),
                        project_dir,
                    )
                    if rollback.returncode != 0:
                        raise RuntimeError(
                            f"Update failed and rollback failed: {update_error}; "
                            f"{rollback.stderr.strip()}"
                        ) from update_error
                    raise RuntimeError(f"Update rolled back: {update_error}") from update_error
                for source in template_dir.iterdir():
                    if source.name not in {"docker-compose.yml", "app.json"} and source.is_file():
                        shutil.copy2(source, project_dir / source.name)
                self._write_metadata(
                    project_dir,
                    template_id=template_id,
                    project_name=project_name,
                    version=str(manifest["version"]),
                    environment_names=list(environment),
                    installed_at=metadata.get("installed_at"),
                )
            log_appstore(f"Updated App Store project [{project_name}]")
            return {
                "success": True,
                "message": f"Project '{project_name}' updated and healthy",
                "project_name": project_name,
                "version": manifest["version"],
            }
        except Exception as error:
            log_appstore(f"Failed to update app [{project_name}]: {error}", error=True)
            return {"success": False, "message": str(error)}

    def uninstall_app(self, project_name: str) -> Dict[str, Any]:
        from handlers.compose_manager import compose_manager

        project_name = self._project_name(project_name)
        result = compose_manager.delete_project(project_name, remove_volumes=True)
        if result.get("success"):
            data_dir = Path(APP_DATA_BASE_DIR) / project_name
            try:
                if data_dir.is_symlink():
                    data_dir.unlink()
                elif data_dir.exists():
                    shutil.rmtree(data_dir)
                result["data_removed"] = True
            except OSError as error:
                result = {
                    "success": False,
                    "message": f"Project removed but application data cleanup failed: {error}",
                    "data_removed": False,
                }
        if result.get("success"):
            log_appstore(f"Uninstalled app / project [{project_name}]")
        else:
            log_appstore(
                f"Failed to uninstall app [{project_name}]: {result.get('message', '')}",
                error=True,
            )
        return result

    def _check_if_installed(self, app_id: str) -> bool:
        return bool(self._installation_index().get(app_id))

    def search_apps(self, query: str) -> List[Dict[str, Any]]:
        lowered = query.lower()
        return [
            app
            for app in self.list_apps()
            if lowered in str(app["name"]).lower()
            or lowered in str(app["description"]).lower()
            or lowered in str(app["category"]).lower()
        ]

    def get_categories(self) -> List[str]:
        return sorted({str(app.get("category", "other")) for app in self.list_apps()})

    def get_app_icon(self, app_id: str) -> Optional[str]:
        try:
            directory, _manifest = self._load_template(app_id)
        except Exception:
            return None
        for filename in ("icon.png", "logo.png", "icon.jpg", "logo.jpg"):
            path = directory / filename
            if path.is_file() and not path.is_symlink():
                return str(path)
        return None


app_store = AppStore()
