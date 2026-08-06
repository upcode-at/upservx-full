"""
HTTP client for the Upcode Harbor API – uses requests.

Auth priority:
    1. UPCODE_HARBOR_TOKEN env / config token  → Bearer <token>
"""

from typing import Any, Optional

import requests
from requests.exceptions import ConnectionError, Timeout

from cli.config import load_config


class APIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"HTTP {status}: {message}")


class APIClient:
    def __init__(self):
        cfg = load_config()
        self.base_url = cfg["api_url"].rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

        token = cfg.get("token", "")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(method, url, json=body, timeout=10)
        except (ConnectionError, Timeout) as e:
            raise APIError(0, f"Cannot reach API at {self.base_url}: {e}") from e

        if not resp.ok:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            if resp.status_code == 401:
                detail = "Not authenticated. Run: upcode-harbor auth login"
            raise APIError(resp.status_code, detail)

        return resp.json() if resp.content else {}

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, body: Optional[dict] = None) -> Any:
        return self._request("POST", path, body)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)


def get_client() -> APIClient:
    return APIClient()
