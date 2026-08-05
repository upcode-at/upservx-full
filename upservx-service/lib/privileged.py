"""Client for the fixed, root-owned UpservX privilege helper."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any


HELPER = os.getenv(
    "UPSERVX_PRIVILEGED_HELPER",
    "/usr/local/libexec/upservx-privileged",
)


def run_privileged(
    action: str,
    *arguments: str,
    input_text: str | None = None,
    timeout: float | None = 30,
) -> subprocess.CompletedProcess[str]:
    """Run one named helper operation without a shell or inherited secrets."""

    command = ["sudo", "-n", HELPER, action, *map(str, arguments)]
    return subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env={
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG": os.getenv("LANG", "C.UTF-8"),
        },
    )


def require_privileged(
    action: str,
    *arguments: str,
    input_text: str | None = None,
    timeout: float | None = 30,
) -> subprocess.CompletedProcess[str]:
    result = run_privileged(
        action,
        *arguments,
        input_text=input_text,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            (result.stderr or result.stdout or "Privileged operation failed").strip()
        )
    return result


def require_privileged_json(action: str, payload: dict[str, Any]) -> None:
    require_privileged(action, input_text=json.dumps(payload), timeout=60)
