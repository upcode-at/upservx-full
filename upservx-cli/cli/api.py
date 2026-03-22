"""
HTTP client for the UpservX API – uses only stdlib (urllib + json).
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from cli.config import load_config


class APIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"HTTP {status}: {message}")


class APIClient:
    def __init__(self):
        cfg = load_config()
        self.base_url = cfg["api_url"].rstrip("/")
        self.token = cfg.get("token", "")

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            try:
                detail = json.loads(body_text).get("detail", body_text)
            except Exception:
                detail = body_text
            raise APIError(e.code, detail) from e
        except urllib.error.URLError as e:
            raise APIError(0, f"Cannot reach API at {self.base_url}: {e.reason}") from e

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, body: Optional[dict] = None) -> Any:
        return self._request("POST", path, body)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)


def get_client() -> APIClient:
    return APIClient()
