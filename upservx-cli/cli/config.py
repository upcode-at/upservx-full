"""
CLI Configuration – reads /etc/upservx-cli.conf, ~/.upservx-cli.conf or env vars.

Stored fields:
  api_url      – backend base URL
    username     – last logged-in username (display only)
    token        – Bearer session/API token
"""

import json
import os

# System-wide config (written by install.sh / root)
SYSTEM_CONFIG_FILE = "/etc/upservx-cli.conf"
# Per-user config (used when system file is not writable)
USER_CONFIG_FILE = os.path.expanduser("~/.upservx-cli.conf")
DEFAULT_API_URL = "http://127.0.0.1:9500"


def _config_path() -> str:
    """Return the config file path that exists or the preferred write target."""
    if os.path.isfile(USER_CONFIG_FILE):
        return USER_CONFIG_FILE
    if os.path.isfile(SYSTEM_CONFIG_FILE):
        return SYSTEM_CONFIG_FILE
    # Prefer user file for new writes
    return USER_CONFIG_FILE


def load_config() -> dict:
    """Load config from file(s) + environment variables."""
    cfg: dict = {
        "api_url": DEFAULT_API_URL,
        "username": "",
        "token": "",
    }

    # System config first, then user config overrides
    for path in (SYSTEM_CONFIG_FILE, USER_CONFIG_FILE):
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    file_cfg = json.load(f)
                cfg.update({k: v for k, v in file_cfg.items() if v})
            except Exception:
                pass

    # Environment variables take highest priority
    if os.environ.get("UPSERVX_API_URL"):
        cfg["api_url"] = os.environ["UPSERVX_API_URL"]
    if os.environ.get("UPSERVX_TOKEN"):
        cfg["token"] = os.environ["UPSERVX_TOKEN"]
    if os.environ.get("UPSERVX_USERNAME"):
        cfg["username"] = os.environ["UPSERVX_USERNAME"]

    return cfg


def save_config(cfg: dict) -> None:
    """Persist config to user config file."""
    path = USER_CONFIG_FILE
    # Try system-wide if it already exists and is writable
    if os.path.isfile(SYSTEM_CONFIG_FILE) and os.access(SYSTEM_CONFIG_FILE, os.W_OK):
        path = SYSTEM_CONFIG_FILE
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(path, 0o600)


def get_username_from_config() -> str:
    """Return stored username (display only)."""
    return load_config().get("username", "")
