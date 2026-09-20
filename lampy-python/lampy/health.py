"""Per-service health checks for the Lampy stack.

Each check returns a dict with exactly these keys:

    {"service": str, "ok": bool, "detail": str, "latency_ms": float}

``ok`` is True only when the service answered correctly. ``detail`` carries
the exact evidence (banner text, HTTP status, error repr) — never a bare
boolean claim.

Default ports follow the Lampy remapping (James ports remapped to avoid
clashing with host services):

    postgres 5432 | apache/http 80, https 443 | ollama 11434
    james smtp 2525 | james imap 1143 | code-server 8080 | xapp 8000
"""
from __future__ import annotations

import http.client
import socket
import time
from typing import Callable, Dict, List

DEFAULTS = {
    "postgres": ("tcp", 5432),
    "apache_http": ("tcp", 80),
    "apache_https": ("tcp", 443),
    "ollama": ("http", 11434, "/api/tags"),
    "james_smtp": ("smtp", 2525),
    "james_imap": ("tcp", 1143),
    "code_server": ("http", 8080, "/"),
    "xapp": ("http", 8000, "/"),
}

Result = Dict[str, object]


def _result(service: str, ok: bool, detail: str, t0: float) -> Result:
    return {"service": service, "ok": ok, "detail": detail,
            "latency_ms": round((time.time() - t0) * 1000, 1)}


def check_tcp(service: str, host: str, port: int,
              timeout: float = 5.0) -> Result:
    t0 = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return _result(service, True, f"tcp connect ok {host}:{port}", t0)
    except Exception as e:  # noqa: BLE001 - detail must carry the exact error
        return _result(service, False, f"tcp connect failed: {e!r}", t0)


def check_http(service: str, host: str, port: int, path: str = "/",
               timeout: float = 5.0, expect: int = 200) -> Result:
    t0 = time.time()
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read(200)
        ok = resp.status == expect
        return _result(service, ok,
                       f"GET {path} -> {resp.status} ({body[:80]!r})", t0)
    except Exception as e:  # noqa: BLE001
        return _result(service, False, f"http check failed: {e!r}", t0)


def check_smtp_banner(service: str, host: str, port: int,
                      timeout: float = 5.0) -> Result:
    """James SMTP is only real if it hands us a 220 banner."""
    t0 = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            banner = s.makefile("r", encoding="utf-8",
                                errors="replace").readline().strip()
        ok = banner.startswith("220")
        return _result(service, ok, f"banner: {banner!r}", t0)
    except Exception as e:  # noqa: BLE001
        return _result(service, False, f"smtp banner failed: {e!r}", t0)


def check_ollama(host: str, port: int = 11434,
                 timeout: float = 5.0) -> Result:
    """Ollama is only real if /api/tags answers 200 with a models list."""
    t0 = time.time()
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", "/api/tags")
        resp = conn.getresponse()
        import json
        payload = json.loads(resp.read().decode())
        models = [m.get("name") for m in payload.get("models", [])]
        ok = resp.status == 200 and isinstance(payload.get("models"), list)
        return _result("ollama", ok, f"200, models={models}", t0)
    except Exception as e:  # noqa: BLE001
        return _result("ollama", False, f"ollama check failed: {e!r}", t0)


CHECKS: Dict[str, Callable[[str], Result]] = {
    "postgres": lambda h: check_tcp("postgres", h, 5432),
    "apache_http": lambda h: check_tcp("apache_http", h, 80),
    "apache_https": lambda h: check_tcp("apache_https", h, 443),
    "ollama": check_ollama,
    "james_smtp": lambda h: check_smtp_banner("james_smtp", h, 2525),
    "james_imap": lambda h: check_tcp("james_imap", h, 1143),
    "code_server": lambda h: check_http("code_server", h, 8080, "/"),
    "xapp": lambda h: check_http("xapp", h, 8000, "/"),
}


def check_all(host: str = "127.0.0.1",
              services: List[str] | None = None) -> Dict[str, Result]:
    """Run health checks for *services* (default: all) against *host*."""
    wanted = services or list(CHECKS)
    return {name: CHECKS[name](host) for name in wanted if name in CHECKS}
