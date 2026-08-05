#!/usr/bin/env python3
"""Generate frontend and CLI request types from FastAPI's OpenAPI schema."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "upservx-service"
TS_PATH = ROOT / "upservx" / "lib" / "generated-api-types.ts"
PY_PATH = ROOT / "upservx-cli" / "cli" / "generated_api_types.py"
SELECTED_SCHEMAS = (
    "BackupServerCreate",
    "BackupServerUpdate",
    "BackupJobCreate",
    "BackupJobUpdate",
    "BackupRestoreRequest",
    "SSHKeyGenerateRequest",
    "SSHKeyImportRequest",
    "SSHKeyTestRequest",
)


def _type(schema: dict[str, Any], *, typescript: bool) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in schema:
        values = [_type(value, typescript=typescript) for value in schema["anyOf"]]
        return " | ".join(dict.fromkeys(values))
    if "enum" in schema:
        quote = "'" if typescript else 'Literal['
        if typescript:
            return " | ".join(repr(value) for value in schema["enum"])
        return f"Literal[{', '.join(repr(value) for value in schema['enum'])}]"
    kind = schema.get("type")
    if kind == "array":
        item = _type(schema.get("items", {}), typescript=typescript)
        return f"{item}[]" if typescript else f"list[{item}]"
    if kind == "object":
        return "Record<string, unknown>" if typescript else "dict[str, Any]"
    mapping = {
        "string": "string" if typescript else "str",
        "integer": "number" if typescript else "int",
        "number": "number" if typescript else "float",
        "boolean": "boolean" if typescript else "bool",
        "null": "null" if typescript else "None",
    }
    return mapping.get(kind, "unknown" if typescript else "Any")


def _render_types(schema: dict[str, Any]) -> tuple[str, str]:
    components = schema.get("components", {}).get("schemas", {})
    ts = ["// Generated from the FastAPI OpenAPI schema. Do not edit by hand.", ""]
    py = [
        '"""Generated from the FastAPI OpenAPI schema. Do not edit by hand."""',
        "",
        "from typing import Any, Literal, NotRequired, TypedDict",
        "",
    ]
    for name in SELECTED_SCHEMAS:
        model = components.get(name)
        if not model:
            continue
        required = set(model.get("required", []))
        ts.append(f"export interface {name} {{")
        py.append(f"class {name}(TypedDict):")
        properties = model.get("properties", {})
        if not properties:
            py.append("    pass")
        for field, field_schema in properties.items():
            optional = "" if field in required else "?"
            ts.append(f"  {field}{optional}: {_type(field_schema, typescript=True)}")
            python_type = _type(field_schema, typescript=False)
            if field not in required:
                python_type = f"NotRequired[{python_type}]"
            py.append(f"    {field}: {python_type}")
        ts.extend(["}", ""])
        py.append("")
    return "\n".join(ts), "\n".join(py)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(SERVICE))
    # Schema generation must not touch a developer's or host's live service
    # configuration merely by importing the FastAPI application.
    with tempfile.TemporaryDirectory(prefix="upservx-openapi-") as config_dir:
        os.environ["UPSERVX_CONFIG_DIR"] = config_dir
        os.environ["UPSERVX_STATE_DIR"] = config_dir
        os.environ["UPSERVX_JOB_DB"] = str(Path(config_dir) / "jobs.db")
        from main import app  # noqa: PLC0415

        schema = app.openapi()
    ts_text, py_text = _render_types(schema)
    outputs = ((TS_PATH, ts_text), (PY_PATH, py_text))
    if args.check:
        stale = [str(path.relative_to(ROOT)) for path, content in outputs if not path.exists() or path.read_text() != content]
        if stale:
            print("Generated API contract is stale: " + ", ".join(stale), file=sys.stderr)
            return 1
        return 0
    for path, content in outputs:
        path.write_text(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
