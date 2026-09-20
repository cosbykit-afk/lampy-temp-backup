"""Apache James webadmin helpers.

James exposes a REST webadmin API (default http://127.0.0.1:8000). These
helpers manage domains and users through it. Every call returns the raw
``(status, body)`` pair so the caller sees exactly what James said.

Not yet exercised against a real James instance — verify on the Windows
target before trusting in production scripts.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Tuple


class JamesError(RuntimeError):
    pass


class JamesAdmin:
    def __init__(self, base_url: str = "http://127.0.0.1:8000",
                 timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _req(self, method: str, path: str,
             payload: dict | None = None) -> Tuple[int, str]:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data,
                                     method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status, r.read().decode(errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(errors="replace")
        except Exception as e:  # noqa: BLE001
            raise JamesError(f"{method} {path} failed: {e!r}") from e

    # -- domains ---------------------------------------------------------
    def add_domain(self, domain: str) -> Tuple[int, str]:
        return self._req("PUT", f"/domains/{domain}")

    def list_domains(self) -> Tuple[int, str]:
        return self._req("GET", "/domains")

    # -- users -----------------------------------------------------------
    def add_user(self, username: str, password: str) -> Tuple[int, str]:
        return self._req("PUT", f"/users/{username}",
                         {"password": password})

    def user_exists(self, username: str) -> bool:
        status, _ = self._req("GET", f"/users/{username}")
        return status == 200
