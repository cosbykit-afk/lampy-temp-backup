"""Thin Ollama client for the Lampy stack — embeddings and chat.

Stdlib only (urllib). Errors are surfaced verbatim as ``OllamaError``; the
caller decides what a failure means. Nothing is retried silently.

Default models follow the Lampy plan: ``nomic-embed-text`` for embeddings,
``musey`` for chat.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, List, Optional


class OllamaError(RuntimeError):
    """The Ollama server answered with an error or was unreachable."""


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434",
                 timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(self.base_url + path, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                if r.status != 200:
                    raise OllamaError(f"{path} -> HTTP {r.status}: "
                                      f"{r.read(500)!r}")
                return json.loads(r.read().decode())
        except OllamaError:
            raise
        except Exception as e:  # noqa: BLE001 - caller gets the exact cause
            raise OllamaError(f"{path} failed: {e!r}") from e

    def list_models(self) -> List[str]:
        req = urllib.request.Request(self.base_url + "/api/tags")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.loads(r.read().decode())
            return [m.get("name", "?") for m in payload.get("models", [])]
        except Exception as e:  # noqa: BLE001
            raise OllamaError(f"/api/tags failed: {e!r}") from e

    def embed(self, text: str,
              model: str = "nomic-embed-text") -> List[float]:
        """Return the embedding vector for *text*.

        Raises OllamaError if the model is missing or the server fails —
        the caller must not treat a missing vector as a zero vector.
        """
        out = self._post("/api/embed", {"model": model, "input": text})
        try:
            return list(out["embeddings"][0])
        except (KeyError, IndexError, TypeError) as e:
            raise OllamaError(f"bad /api/embed payload: {out!r}") from e

    def chat(self, prompt: str, model: str = "musey",
             system: Optional[str] = None) -> str:
        """Single-turn chat; returns the exact response text."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        out = self._post("/api/chat",
                         {"model": model, "messages": messages,
                          "stream": False})
        try:
            return str(out["message"]["content"])
        except (KeyError, TypeError) as e:
            raise OllamaError(f"bad /api/chat payload: {out!r}") from e
