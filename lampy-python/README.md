# lampy — Python utilities for the Lampy forum stack

Stdlib-only helpers for operating the Lampy stack (X = Windows host,
Apache HTTPD, PostgreSQL/TimescaleDB, Python xapp, James mail, Ollama
embeddings):

- `lampy.paths` — the `C:\Lampy` layout constants plus POSIX dev equivalents,
  so the same code runs on the Windows target and this Linux dev VM.
- `lampy.health` — per-service TCP/HTTP health checks with exact failure
  reasons (no boolean-only "healthy" claims).
- `lampy.ollama_client` — thin Ollama client: embeddings (`nomic-embed-text`)
  and chat (`musey`). Surfaces API errors verbatim.
- `lampy.config_gen` — deterministic config-file generators (Apache vhost,
  etc.). Generated files are byte-stable: same inputs, same bytes.
- `lampy.james_admin` — Apache James webadmin helpers (domains, users).

Status: scaffolded 2026-09-20 on Linux. **Not yet exercised against the real
Windows container** — treat every module as untested-on-target until the
~Sept 23 Windows acceptance runs pass.

## Quick start

```python
from lampy import health, ollama_client

print(health.check_all("127.0.0.1"))          # dict of per-service results
emb = ollama_client.embed("hello world")      # list[float]
```

## Layout

```
lampy-python/
  pyproject.toml
  lampy/
    __init__.py
    paths.py
    health.py
    ollama_client.py
    config_gen.py
    james_admin.py
```
