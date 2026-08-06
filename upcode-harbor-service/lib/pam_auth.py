"""Unprivileged client for Upcode Harbor's root-owned PAM authentication broker."""

from __future__ import annotations

import subprocess

from lib.privileged import run_privileged


PAM_SERVICE = "upcode-harbor"


class PrivilegedPamAuthenticator:
    """Expose a python-pam-like interface backed by the allowlisted helper."""

    code = 0
    reason = "Success"

    def authenticate(self, username: str, password: str, *, service: str) -> bool:
        if service != PAM_SERVICE:
            self.code = 3
            self.reason = "Unsupported PAM service"
            return False
        if any(character in password for character in ("\x00", "\n", "\r")):
            self.code = 7
            self.reason = "Authentication failure"
            return False
        try:
            result = run_privileged(
                "pam-authenticate",
                username,
                input_text=f"{password}\n",
                timeout=25,
            )
        except subprocess.TimeoutExpired:
            self.code = 4
            self.reason = "PAM broker timed out"
            return False
        except OSError:
            self.code = 4
            self.reason = "PAM broker could not be started"
            return False

        if result.returncode == 0:
            self.code = 0
            self.reason = "Success"
            return True
        if result.returncode == 1:
            self.code = 7
            self.reason = "Authentication failure"
            return False

        diagnostic = " ".join((result.stderr or result.stdout or "").split())
        self.code = result.returncode
        self.reason = diagnostic[:160] or "PAM broker failed"
        return False
