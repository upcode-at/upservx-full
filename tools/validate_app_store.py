#!/usr/bin/env python3
"""Validate every App Store manifest and rendered Docker Compose project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "upservx-service"
TEMPLATES = ROOT / "app-store-templates"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-compose-cli",
        action="store_true",
        help="Skip docker compose config (structural YAML checks still run)",
    )
    args = parser.parse_args()
    sys.path.insert(0, str(SERVICE))
    from lib.app_store_validation import TemplateValidationError, validate_template

    schema = TEMPLATES / "app.schema.json"
    failures: list[str] = []
    validated = 0
    for directory in sorted(path for path in TEMPLATES.iterdir() if path.is_dir()):
        try:
            validate_template(
                directory,
                schema,
                compose_cli=not args.skip_compose_cli,
            )
            validated += 1
        except (TemplateValidationError, OSError) as error:
            failures.append(f"{directory.name}: {error}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Validated {validated} App Store templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
