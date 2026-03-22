"""
CLI Configuration – reads /etc/upservx-cli.conf or environment variables.
"""

import json
import os

CONFIG_FILE = "/etc/upservx-cli.conf"
DEFAULT_API_URL = "http://127.0.0.1:9500"


def load_config() -> dict:
    """Load config from file, fall back to env / defaults."""
    cfg = {
        "api_url": os.environ.get("UPSERVX_API_URL", DEFAULT_API_URL),
        "token": os.environ.get("UPSERVX_TOKEN", ""),
    }

    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                file_cfg = json.load(f)
            cfg.update({k: v for k, v in file_cfg.items() if v})
        except Exception:
            pass

    return cfg


def save_config(cfg: dict) -> None:
    """Persist config to /etc/upservx-cli.conf (requires root or write permission)."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
        os.chmod(CONFIG_FILE, 0o600)
    except PermissionError:
        # Fall back to user home
        user_conf = os.path.expanduser("~/.upservx-cli.conf")
        with open(user_conf, "w") as f:
            json.dump(cfg, f, indent=2)
        os.chmod(user_conf, 0o600)
