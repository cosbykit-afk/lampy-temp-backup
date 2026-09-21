# Lampy — license

## Kit Cosby's original code: The Unlicense (public domain)

All original code in this repository authored for Lampy (build scripts,
`lampy-single/` config, `httpd/` vhost and htdocs, `james/` config,
`installer/`, `db-console/`, `payments/`, `lampy-python/`, `musey/`
Modelfiles, `control-plane/`, docs) is dedicated to the public domain by
Kit Cosby under the following terms:

```
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org/>
```

In short: corporations and private individuals alike may use it freely,
and the author is held harmless — the software comes as-is, with no
warranty and no liability.

---

## Third-party products in the lampy-single image

The `kitcosby/lampy-single` image (built from `lampy-single/Dockerfile`)
is a collection of third-party products, each under its own license. The
Unlicense above covers only Kit's original code — not these products.
License texts live with their projects (links below) and, for
Debian/Ubuntu packages, under `/usr/share/doc/*/copyright` in the image.

### Base image: timescale/timescaledb-ha:pg16 (pinned by digest)

- **Ubuntu 22.04 (jammy) userspace** — mixed; each package carries its own
  license, documented at `/usr/share/doc/<package>/copyright` in the image.
- **PostgreSQL 16** — PostgreSQL License (permissive, BSD/MIT-style).
  https://www.postgresql.org/about/licence/
- **TimescaleDB (Community, as shipped in the `-ha` image)** — **Timescale
  License (TSL)**, not Apache 2.0. The `-oss` tags are the Apache-2.0-only
  builds; this image uses the standard `-ha` tag, which contains
  TSL-licensed TimescaleDB features. The TSL permits use for internal
  business purposes and distribution of unmodified binaries, but prohibits
  offering TimescaleDB itself as a hosted database-as-a-service. Read the
  license before relying on it:
  https://github.com/timescale/timescaledb/blob/main/tsl/LICENSE-TIMESCALE
- **Patroni** (HA orchestration inside the `-ha` image) — MIT License.
  https://github.com/patroni/patroni

### Added at build time (lampy-single/Dockerfile)

- **Ollama** (`/usr/bin/ollama` + `/usr/lib/ollama` runners, copied from
  the official `ollama/ollama` image) — MIT License.
  https://github.com/ollama/ollama
- **Apache HTTPD 2.4** (Debian `apache2` package) — Apache License 2.0.
  https://httpd.apache.org/
- **Python 3** (Debian `python3`/`python3-pip`) — Python Software
  Foundation License. https://docs.python.org/3/license.html
- **pgai** (pip package, vectorizer worker dependency) — Apache License 2.0.
  https://github.com/timescale/pgai
- **OpenJDK 17** (`openjdk-17-jre-headless`, runs Apache James) — GNU
  General Public License v2 with the Classpath Exception.
  https://openjdk.org/legal/gplv2+ce.html
- **Apache James** (`james-server-jpa-guice`, mail server) — Apache License 2.0.
  https://james.apache.org/
- **Supervisor** (process control, PID 1) — BSD 3-Clause (Supervisor license).
  http://supervisord.org/
- **code-server 4.138.0** (browser IDE on :8080) — Apache License 2.0.
  https://github.com/coder/code-server

### Fetched at runtime (not baked into the image)

Downloaded into the running container on first boot / on demand:

- **qwen3:0.6b** (base model for the `musey` assistant) — Apache License 2.0.
- **nomic-embed-text** (embeddings model) — Apache License 2.0.

### Pending (not in the image yet)

- **pgvectorscale** / **pgai** database extensions (need the pgrx build) —
  Apache License 2.0.
- **xapp** (forum app, behind the `/app` reverse proxy) — license TBD with
  the app.

### Notes

- The TSL entry above is the one with teeth: it is the only
  non-open-source license in the image. Running a forum whose database
  happens to be TimescaleDB is ordinary internal use; exposing
  TimescaleDB itself to third parties as a database service is what the
  TSL forbids.
- Rebuilt or re-based images should re-check this map: a base-image bump
  (e.g. `-ha` → `-oss`, or a TimescaleDB major version) can change the
  TimescaleDB licensing line.
