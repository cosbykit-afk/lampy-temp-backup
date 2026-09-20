# Lampy — Notation Ledger

Living record of the project's shared vocabulary: terms, environment
variables, ports, paths, and version pins. When a value changes, the old
row is updated in place with a dated note — this file always shows the
current truth, and `BUGLOG.md` keeps the history of how it got there.
Status labels are defined in `WORKFLOW.md` §6.

## 1. Project terms

| Term | Meaning |
|---|---|
| Lampy | The project name (Kit's choice, 2026-09-19). The full forum-stack build. |
| Reference host | This Linux VM (Ubuntu 24.04). All-Linux single-box validation of every component before Windows+WSL2 work begins. |
| Prod topology | Windows: database layer in Docker Desktop (`timescale/timescaledb-ha:pg16`); WSL2 Ubuntu: Flask/gunicorn, Apache HTTPD, Apache James, Ollama, pgAI worker, pgrx/Rust. |
| Control plane | Python scripts the AI uses to manage every stack layer down to root (Kit's design decision, 2026-09-19). The lightweight IDE + pip serve this. |
| Runbook | `README.md` — the living setup guide; §8 is the state of record. |
| env-first rule | `env.sh` must be sourced before any install/build command (Kit's directive, from the original guide). |
| Full installer | Child goal `goal_7123d9e516ca`; queued until reference-host AND Windows+WSL2 acceptance both pass (runbook §9 twice). |
| pypip | **pip**, the Python package installer (confirmed by Kit 2026-09-19). |
| | pgAI depends on it. **Standing requirement:** the final build MUST leave |
| | a working pip in place — the AI's control plane cannot function without |
| | a window to use pip. |

## 2. Environment variables

`env.sh` is the Linux/reference-host adaptation. "Doc value" is Kit's
tested Windows configuration (2025-02-26 post, confirmed correct by Kit
2026-09-19).

| Variable | Doc value (Windows) | Reference-host value | Notes |
|---|---|---|---|
| CARGO_HOME | `C:\` | `$HOME/.cargo` | |
| RUSTUP_HOME | `C:\.rustup\bin` | `$HOME/.rustup` | Doc value confirmed as-is by Kit |
| CARGO_TARGET_DIR | `C:\tmp` | `$HOME/workspace/forum-stack/build/cargo-target` | /tmp is tmpfs here; workspace dir used instead |
| PGRX_HOME | `Postgres\pgrx` | `$HOME/.pgrx` | We point pgrx at system PG16; it never builds its own Postgres |
| PGRX_BUILD_VERBOSE | TRUE | TRUE | Real pgrx var; full build logs |
| PGRX_IGNORE_RUST_VERSIONS | TRUE | 1 | Required: host rustc 1.98.1 |
| PGRX_BUILD_FLAGS | TRUE | **unset** | Version-dependent: 0.19.2 passes the value verbatim as compiler args, so TRUE broke every build (proven, BUGLOG 2026-09-19). Kit's value was tested on pgrx 0.12.x-era. Prod must check its own pgrx version. |
| PGDATA | `C:\Postres\data` | `/var/lib/postgresql/16/main` | "Postres" spelling is intentional per Kit — NOT a typo |
| PGLOCALEDIR | `C:\Postgres` | (n/a — Debian layout) | |
| POSTGRES_USER | (empty) | `postgres` | Reference host uses peer auth; no password stored |
| POSTGRES_PASSWORD | (empty) | (not stored, ever) | |
| OLLAMA_MODELS | (empty) | `$HOME/.ollama/models` | |
| OPENSSL_CONF | (empty) | (n/a) | |
| OLLAMA_HOST | — | `http://127.0.0.1:11434` | Linux-side addition |
| FORUM_DB_HOST/PORT/NAME/USER | — | `127.0.0.1`/`5432`/`forum`/`forum` | Reference-host app config |
| FORUM_SMTP_HOST/PORT | — | `127.0.0.1`/`587` | James submission port |

## 3. Ports (reference host)

| Port | Service |
|---|---|
| 5432 | PostgreSQL 16 |
| 11434 | Ollama |
| 8008 | James WebAdmin |
| 2525 / 2465 / 2587 | James SMTP / TLS SMTP / submission |
| 1143 / 1993 | James IMAP / IMAPS (plain login disabled; STARTTLS required) |
| 1110 | James POP3 |

## 4. Key paths

| Path | Contents |
|---|---|
| `~/workspace/forum-stack/env.sh` | Env-first file; source before any install/build |
| `~/workspace/forum-stack/README.md` | Runbook (§8 = state of record) |
| `~/workspace/forum-stack/WORKFLOW.md` | Process governor (RAD, dependency chain, labels) |
| `~/workspace/forum-stack/BUGLOG.md` | Defect and finding log |
| `~/workspace/forum-stack/NOTATION_LEDGER.md` | This file |
| `~/workspace/forum-stack/build/` | cargo-target, lampy_smoke, pgai-venv, fakeuid-shim |
| `~/workspace/forum/` | Flask app (venv, app.py, schema.sql, templates) |
| `~/workspace/forum-stack/james/james-server-jpa-guice` | Apache James 3.8.2 |

## 5. Version pins (verified 2026-09-19 unless noted)

| Component | Version |
|---|---|
| PostgreSQL | 16.15 (Debian) |
| cargo-pgrx | 0.19.2 |
| rustc | 1.98.1 (with PGRX_IGNORE_RUST_VERSIONS) |
| Apache James | 3.8.2 (JPA/Guice) |
| OpenJDK | 21.0.12 (default-jre-headless) |
| Ollama | 0.34.2 (binary; official installer completed) |
| nomic-embed-text | [blocked] pull denied by egress policy — U-5 |
| pgAI | [in progress] venv install retry running — U-6 |
| Flask | 3.1.3 |
| Python | 3.12 / pip 24.0 |

## 6. Unresolved log

- **U-1** (2026-09-19): CLOSED — Kit confirmed "pypip" = pip. Standing
  requirement recorded in §1: the final build must leave a working pip in
  place (pgAI depends on it; the AI control plane cannot function without
  a window to use pip).
- **U-2** (2026-09-19): Lightweight Python IDE choice pending — Thonny, Geany,
  or VS Code offered; no display on the reference host (GUI IDEs run on the
  Windows side). UPDATE 2026-09-19: Kit directed the IDE be installed INSIDE
  Docker (download → import file → install in container). Of the three, only
  VS Code has a Docker-native form — code-server (browser-based). Thonny/Geany
  are desktop GUI apps, unusable in a headless container. DECIDED: code-server
  v4.138.0 linux-amd64, tarball cached at
  ~/workspace/forum-stack/downloads/code-server-4.138.0-linux-amd64.tar.gz
  (230 MB, verified). To be COPY'd into the workspace image at build time.
- **U-3** (2026-09-19): `PGRX_BUILD_FLAGS` value for Windows/WSL2 prod is
  version-dependent (TRUE tested on pgrx 0.12.x-era; breaks 0.19.2). Must be
  decided against the pgrx version actually installed there.
- **U-4** (2026-09-19): Windows side not started — Docker Desktop
  version/preferences and the `timescale/timescaledb-ha:pg16` container's
  actual extension inventory (`\dx` for timescaledb, vector, vectorscale, ai)
  still to collect.
- **U-5** (2026-09-19): Ollama model pull blocked — egress approval
  "Access ollama.com" (approval_id 13c630d5-…) timed out and was denied on
  the first attempt. Pull re-triggered 2026-09-19 ~16:35 PDT; fresh approval
  expected on Kit's phone — Kit to approve promptly.
- **U-6** (2026-09-19): pgAI `pgai[vectorizer-worker]` venv install — first
  attempt failed (transient ENOSPC); retry with TMPDIR redirected running.
- **U-7** (2026-09-19): fakeuid LD_PRELOAD shim is reference-host-only
  (sandbox runs as root; initdb refuses root). WSL2 prod runs as a normal
  user and must NOT use it.
- **U-8** (2026-09-19): PENDING TASK FOR KIT — Windows-side access. Install
  Tailscale on the Windows machine and start it inside WSL2 Ubuntu, then
  approve the `muse` device (link: https://login.tailscale.com/a/14359dc018cb4).
  After the join, SSH into WSL2 gets set up as the next step. BLOCKED until
  ~2026-09-23 — Kit is away from his laptop (four days). NOTE 2026-09-19:
  Kit's *desktop* (holds his working Docker images + the successful cargo/pgrx
  setup) is a separate machine he may not reach for a couple of weeks — the
  desktop images and cargo work stay on his side until then; the reference
  build here proceeds with fresh pulls.
- **U-9** (2026-09-19): Python venvs must NOT cross the Windows/WSL2 boundary.
  Kit's 2025-02-27 post shows the failure mode: a venv created by Windows
  Python has `Scripts\activate` (no `bin/activate`), so `source myenv/bin/activate`
  fails under WSL bash; `source myenv/scripts/activate` only works by accident
  from `/mnt/c` and breaks after `cd`. Rule: one venv per side (Windows venv
  for Windows Python, WSL venv for WSL Python), created natively on each side.
- **U-10** (2026-09-19): Docker-in-Docker intent from Kit's 2025-02-23 sketch:
  the alpine container runs `apk add docker.io` ("Install Docker CLI to control
  other Docker containers") with CMD `docker-compose up` — i.e. a container
  that orchestrates sibling containers. As written it is NOT true Docker-in-
  Docker (no dockerd inside, no --privileged) and it does not mount
  /var/run/docker.sock, so it could not work as drafted. When the compose
  topology is built, decide: socket-mounted Docker-out-of-Docker vs true
  docker:dind. Do not silently assume either.
- **U-11** (2026-09-19): Draft cargo-install control files created at
  `~/workspace/forum-stack/control-files/` (README + toml/ x5 + json/ x5 +
  conf/ x2 placeholders) from Kit's 2025-02-23 sketch. Sketch's TOML was not
  valid TOML and its final `>` echo would have wiped pgrx.toml; drafts are
  valid TOML with JSON mirrors generated from them by script. Versions updated
  (pg16, cargo-pgrx 0.19.2); PGRX_BUILD_FLAGS=TRUE kept as Windows-only.
  conf/pgrx.conf + conf/pgai.conf now carry the full environmental
  configuration (sketch ENV block corrected per env.sh). Status DRAFT, not
  consumed by any build script yet; Kit to confirm Windows-side values.
- **U-12** (2026-09-19): Control-plane core BEGUN at Kit's direction
  (`~/workspace/forum-stack/control-plane/`, package `lampy_control`):
  ScriptWriter (compose -> write .sh -> execute -> log) + FileOps
  (mkdir/move/copy/rewrite/remove/list/read), all through generated shell
  scripts; demo.py passes. Runs with administrative privileges (uid 0 on the
  reference host); audit trail (scripts/ + logs/exec.log) is mandatory because
  of that. Safety: root-scoped paths, trash-not-delete, dry-run mode, no
  passwords in files. Service/Docker/pgAI/installer layers still wait for
  component verification per WORKFLOW.md.
- **U-11 update** (2026-09-19): `control-files/yaml/` added at Kit's direction —
  YAML mirrors of all five TOML manifests, generated by parsing the TOML
  (PyYAML 6.0.1) and round-trip verified (YAML parse == TOML parse). Canonical
  rule now recorded in control-files/README.md: toml/ is source of truth;
  json/ and yaml/ are generated mirrors, never hand-edited.
- **U-13** (2026-09-19): Kit: the 2025-02-23 sketch's compose topology "is a
  better configuration." Drafted `~/workspace/forum-stack/docker-compose.yml`
  (DRAFT): httpd, db (timescaledb-ha:pg16), ollama, james, ide (code-server),
  pgai-worker. Sketch defects fixed: one owner per port (sketch mapped 80/443
  on every service), dropped depends_on the nonexistent "cargo" service, no
  passwords in the file (deploy-time env), obsolete version field removed.
  pgrx/pgvectorscale/pgai-extension are build-time/in-db, not services;
  timescaletools still unresolved (U-8), no service yet. `ide/Dockerfile`
  unpacks the cached code-server tarball in-image. pgai-worker is the target
  shape, untested until pgai installs cleanly. Compose is the runtime topology;
  control-files toml/json/yaml remain the build manifests.
- **U-14** (2026-09-19): HTTPD configured at Kit's direction.
  `httpd/httpd.conf` (DRAFT, from official httpd:2.4 defaults): Listen 80,
  mod_proxy/mod_proxy_http enabled, vhost reverse-proxies /app to the Flask
  app at http://app:8000/ (app service does not exist yet — proxy resolves
  per-request so httpd starts clean; /app 503s until then). Static landing
  page at / (`httpd/htdocs/index.html`). TLS 443 vhost present but commented
  — no certificates yet. Compose httpd service mounts the conf + htdocs.
  Syntax check (`httpd -t`) PENDING: httpd image not yet downloaded.
- **U-15** (2026-09-19): Kit: first build is **Windows-only, no WSL/Ubuntu**.
  Docker Desktop on Windows runs the Linux container images (compose file);
  Docker's internal WSL2 backend is not a managed Ubuntu environment. Runbook
  §3.6 (Windows+WSL2 split) superseded for the first build, kept for reference.
  Acceptance is now twice on the Windows-only build; the installer child goal
  covers the Windows-only layout. U-9 venv rule: Windows-native only.
- **U-12 update** (2026-09-19): code-server smoke test VERIFIED — HTTP server
  listening on 127.0.0.1:8080, login page 200, password auth on. Python
  extension + image build still pending.
- **U-16** (2026-09-19): Kit's bootstrap challenge — hardcoded data paths
  (Ollama %USERPROFILE%\.ollama, PGDATA, TimescaleDB extension linkage) break
  when folders move; Drive virtual-mount junk clutters each install.
  Solution: single root %LAMPY_ROOT% (default C:\Lampy, marker file, Drive
  locations refused) + NTFS junction armor at hardcoded paths
  (`installer/PATH_STABILITY.md`, `installer/bootstrap-paths.ps1` with
  -MoveFrom migration). Compose db/ollama now bind-mount under
  ${LAMPY_ROOT}; the timescale<->database link lives inside the immutable
  image. Script DRAFT — PowerShell syntax unverified (no pwsh on build
  machine); review before first Windows run.
- **U-16 refinement** (2026-09-19): Kit — the anchor is the **PGDATA folder**;
  other programs' relative positions extend off its tree. Bootstrap rewritten
  anchor-first (`-PgData`, default C:\Lampy\data\pgdata; derives data tree =
  anchor's parent, home = grandparent; writes PGDATA_DIR + LAMPY_DATA to
  compose/.env; sets PGDATA/LAMPY_DATA/LAMPY_HOME/OLLAMA_MODELS user env).
  Compose: db bind-mounts ${PGDATA_DIR}, ollama ${LAMPY_DATA}/ollama.
  Doc updated. Still DRAFT, PowerShell unverified.
- **Naming convention** (2026-09-19): Kit — when he says "Apache" he means the
  mail server (Apache James), not Apache HTTPD. Stack letters: X=Windows,
  A=Apache HTTPD (web), P=PostgreSQL, P=Python, xapp=forum app
  (Python+Flask; Flask is the PHP replacement, accepted by Kit).
- **U-18** (2026-09-19): Python-based C IDE built at Kit's direction:
  `c-ide/app.py` (Flask) + `c-ide/templates/index.html` (no CDN deps).
  Editor, Compile & Run via system GCC (flags editable, stdin box, 10 s
  limits, 200 KB cap, temp-dir builds), workspace file save/load/list
  confined to c-ide/workspace (traversal unit-checked). Test-client
  verified: good program compiles+runs (CC_WORKS, exit 0), broken program
  returns gcc errors cleanly, index serves 200. Not yet served live or in
  compose.
- **U-19** (2026-09-19): Kit's 2025-02-28 Facebook posts (two, same day) pulled
  at his direction. (1) 07:10 PT "more flushed out OS with tools needed for the
  LampY stack": Python sketch — toy boot loader/Kernel (memory, process, fs,
  device managers), DOS> command loop, plus venv automation WITH MOUNT
  HANDLING (warn on ismount at setup, refuse delete on mount; win32 vs POSIX
  activation paths). Sketch flaw: activate via os.system does not persist.
  Design input for control-plane venv management; pairs with the 2025-02-27
  one-native-venv-per-side rule. (2) 10:56 PT research dump on Python-based C
  compilation (distutils.ccompiler driving gcc; Cython; ShivyC; Cleese). Pasted
  AI-answer style ("Next Steps" a/b). Ancestor of the c-ide build. Correction:
  distutils.ccompiler was removed from the stdlib in Python 3.12, so option 1
  fails as written on modern Python; c-ide shells out to gcc directly instead.
- (U-19 continued): third 2025-02-28 post, 06:34 PT — earliest of the day:
  "finding that i can place pip tools in an unmounted rood got me thinking, i
  will need an os down there... soo...." + the same toy-OS sketch (no venv part
  yet; venv automation was added in the 07:10 revision). PROVENANCE: this is the
  origin of Kit's standing "control scripts manipulate the stack down to the
  root" directive — pip tools on an unmounted root -> need an OS down there ->
  the Python control plane. Day's arc: 06:34 unmounted-root insight + OS sketch
  -> 07:10 venv automation w/ mount guards -> 10:56 Python-C compilation
  research (ancestor of c-ide).

## New issues (2026-09-19)
- (U-20): `apache/james:3.8.2` does not exist on Docker Hub — the repo carries
  only variant-prefixed tags (`demo-3.8.2`, `cassandra-3.8.2`, `distributed-3.8.2`,
  …; 77 tags, no plain `3.8.2`; "manifest unknown" is definitive, not flaky).
  `demo-3.8.2` (531MB) was pulled to hold the pinned version. `docker-compose.yml`
  still references the nonexistent `apache/james:3.8.2`; left unchanged pending
  Kit's Apache clarification (whether James stays in the stack at all).
- Docker 29.8.1 reinstalled durably: static binaries at ~/docker/docker/,
  symlinked into ~/bin/ (survive VM resets), daemon running
  (--storage-driver=vfs --iptables=false --bridge=none). Images verified via
  `docker images`: timescale/timescaledb-ha:pg16 (3.28GB), ollama/ollama:latest
  (5.46GB), apache/james:demo-3.8.2 (531MB), python:3.12-slim (119MB),
  httpd:latest (117MB). Docker-install backup tarball at
  backups/docker-install-backup-2026-09-19.tar.gz (86MB; already in the GitHub
  backup push, remote SHA verified).
- DECISION (Kit 2026-09-19 evening): Apache James REMOVED from the stack —
  httpd serves both web and mail; no separate mail service. compose `james`
  service + `james_data` volume deleted; pull scripts de-jamesed;
  `james/` (99MB) and `downloads/james.zip` moved to recoverable trash.
  README §6 marked REMOVED (retained for history); WORKFLOW acceptance
  criteria reworded to the mail side generically.
- (U-21) OPEN: how the mail side is implemented on httpd. Stock Apache HTTPD
  has no SMTP/IMAP of its own; the mechanism (module, CGI/app-level relay,
  external MTA behind httpd) is undecided. Closes when the mail path is
  specified and the acceptance "mail banner + delivered test mail" has a
  concrete target.
- (U-20 follow-up, Kit 2026-09-19 evening): James files restored from trash
  (both entries, originals back in place). Diff vs pristine zip shows Kit's
  SMTP setup was port remapping ONLY: SMTP 25->2525, SMTPS 465->2465,
  submission 587->2587, IMAP 143->1143, IMAPS 993->1993, POP3 110->1110.
  All other settings (auth, authorizedAddresses 127.0.0.0/8, DB) are stock.
  Service still out of docker-compose.yml pending Kit's decision.
- DECISION REVERSED (Kit 2026-09-19 ~21:28 PT): James RE-ADDED as the mail
  server. compose `james` service restored: image `apache/james:demo-3.8.2`
  (3.8.2 via the demo variant tag; `apache/james:3.8.2` does not exist —
  see U-20), Kit's port remap published (2525/2465/2587/1143/1993/1110),
  `james_data` named volume back. Pull scripts re-jamesed. U-21 CLOSED:
  mail = James; the httpd-does-mail question is moot.
- (U-22) ENVIRONMENT LIMITATION (2026-09-20): `docker run` is BLOCKED in the
  Linux reference sandbox — runc fails with "setns: operation not permitted"
  (mount namespace), even as root and even with --privileged/--userns=host.
  `docker build` RUN steps hang/fail for the same reason (ide image build
  killed after hanging on its RUN tar step). What works here: pull, images,
  COPY/ADD-only builds. Stack launch (`compose up`) and any RUN-step build
  MUST happen on Windows Docker Desktop (~2026-09-23). Daemon itself runs
  fine (29.8.1, vfs/iptables=false/bridge=none); all 5 pulled images intact.
- DECISION (Kit 2026-09-20): single consolidated image. Design at
  lampy-single/: base timescale/timescaledb-ha:pg16 (USER root + ENTRYPOINT []
  reset — base sets USER postgres), Debian apache2 + python3 + openjdk-17 +
  supervisor via apt, ollama binary COPY --from ollama/ollama (/usr/bin/ollama
  verified in image layers), James with Kit's conf, code-server via ADD,
  supervisord runs postgres/apache2/ollama/james/code-server/pgai-worker.
  Trade-off: one container = shared fate for all services; image ~10GB.
  Full build deferred to Windows; COPY/ADD paths validated here.
