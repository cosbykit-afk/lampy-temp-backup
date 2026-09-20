# How Lampy is built

This file governs the Lampy forum-stack build: the order work happens in,
how each component is installed, tested, and debugged, and what the status
labels mean. It is the workflow counterpart to the runbook
(`README.md`, the living administrator setup guide). The runbook says *what*
to install; this file says *how the work is controlled*.

Methodology: **rapid application design (RAD)** — short build → test →
refine cycles against a working prototype, not a waterfall. The Flask app
already exists as a prototype (`~/workspace/forum/`); each cycle hardens one
more layer of the stack beneath it until the full system passes the
acceptance checklist.

## 0. Project control

This project is managed under Kit's standing directives, which outrank any
incentive to report convenient progress:

- **Honesty over speed.** Report only what a completed step established.
  A failed install, a timed-out build, a lost background session, or a test
  never run is reported as exactly that — never rounded up to "done".
- **"If the tool runs out of time let me know it was incomplete."**
  Timeouts and session losses are disclosed, not absorbed.
- **Precision.** "Always if we could be more precise or show more complete
  work we should." Status labels (§6) carry the exact evidence: what ran,
  what exited 0, what was verified by read-back.
- **Environment first.** `~/workspace/forum-stack/env.sh` is sourced before
  *every* install/build command. The file's deliberate choices
  (`PGRX_BUILD_FLAGS` unset — not a real pgrx variable; `CARGO_TARGET_DIR`
  under the workspace, not tmpfs) are not to be "fixed" by improvisation.
- **Sources are read-only** (§1). The shared Google Doc is never edited.
- **Credentials.** Never collected in chat; the Secure Vault or the
  connector flow. No PostgreSQL password or Flask secret lives in `env.sh`.
- **Critical path first.** "Follow the critical path and when you have time
  do the side tasks." The critical path is the dependency chain in §4.
- **New issues get flagged.** "If you spot new issues flag them and add
  them to the notation" — here the runbook is the notation: new issues go
  into `README.md` §8 and the bug log (§5).
- **Newly-unblocked work gets done.** "When we find something that we can
  now do, let's do it and add it to the notation log."

Tracked structure (Goals tab):

- Parent: `lampy-forum-stack-build` — build and verify the full stack.
- Child: `Lampy — forum stack full installer` — **queued** until the stack
  is configured and verified. The installer is never built from an
  unverified stack.

Routing: Lampy work happens in the main chat. The `lampy-morning-report`
cron (daily ~08:47 PT, staggered after the 07:47 R Theory report) delivers a
read-only sweep to the iOS side chat: runbook §8, `env.sh`, background
sessions, app compile state, tracked states — failures and incompleteness
reported plainly.

## 1. Sources are read-only

The starting outline is Kit's "Lampy" Google Doc ("LAMP_AI Stack Setup Guide
(LAMP_AI Stack Setup Guide (Windows + WSL2)", v1.1, 2025-08-01). It is never
edited by this workflow. The working copy is the local read-only reference:

`~/workspace/goals/forum-stack-full-installer/files/LAMP_AI-Stack-Setup-Guide-v1.1.md`

with deltas-vs-current-build noted alongside it. All adaptation (Linux
reference build, Docker Desktop topology, pgAI Ollama procedure) happens in
this repo's `README.md`, never in the Doc.

## 2. Environment first

Before any install/build command, on any host:

```bash
source ~/workspace/forum-stack/env.sh
```

`env.sh` holds the build environment: `CARGO_HOME`, `RUSTUP_HOME`,
`CARGO_TARGET_DIR`, `PGRX_HOME`, `PGRX_BUILD_VERBOSE`,
`PGRX_IGNORE_RUST_VERSIONS=1`, `PGDATA`, `OLLAMA_MODELS`, `OLLAMA_HOST`,
plus the local reference-host DB/SMTP variables. `bash -n` must pass after
any edit. Variables are thought through *before* installs begin (Kit's
directive), not invented mid-command.

## 3. RAD phases

The build runs in four overlapping phases. Phases overlap deliberately —
RAD refines the prototype while the layers beneath it are still being built —
but a phase's **exit gate** must be met before the next phase's work is
called done.

### Phase 0 — Requirements planning [done 2026-09-19]

Stack components, topology, and decisions recorded: Python/Flask forum,
PostgreSQL 16, TimescaleDB, pgvector, pgvectorscale, pgAI + vectorizer
worker, Ollama (`nomic-embed-text`, 768-dim), pgrx/Rust tooling,
Apache HTTPD/gunicorn (web + mail — James removed 2026-09-19 per Kit). Production topology (2026-09-19, Kit): **Windows-only first build — no WSL2
Ubuntu.** Docker Desktop on Windows runs the Linux container images (db,
httpd, ollama, ide, pgai-worker per `docker-compose.yml`); Docker
Desktop's internal WSL2 backend is Docker's own machinery, not a Ubuntu
environment we manage. The earlier Windows+WSL2 split (runbook §3.6) is
superseded for the first build and retained for reference only.
Name collision with the Showtec "LAMPY" console noted; Kit kept the name.

Exit gate: every component has an owner, a host, and a documented install
path in the runbook.

### Phase 1 — Prototype [done 2026-09-19, hardening ongoing]

The Flask app (`~/workspace/forum/`): registration/login/logout,
categories/boards/threads/replies/pagination, parameterized psycopg SQL,
Werkzeug hashing, Jinja autoescaping, HMAC-compared session CSRF tokens,
session clearing on login/logout, same-origin redirects, input-length
validation, SMTP notifications, TimescaleDB event logging, `/metrics`,
`/search` (keyword fallback, explicitly labelled as such). Nine Jinja
templates; legacy PHP prototype preserved under `forum/legacy-php/`.
Python venv built; Flask 3.1.3 + psycopg import verified; gunicorn installed.

Exit gate: `py_compile` clean, imports clean, Flask test-client exercises
register → login → thread → reply, templates render. **Not yet run.**

### Phase 2 — Construction [in progress]

Install the stack in dependency order (§4), one component per build-debug
cycle (§5): base packages → Rust → cargo-pgrx → Java → PostgreSQL 16 +
TimescaleDB + pgvector + pgvectorscale + pgAI → Ollama →
vectorizer worker → schema → mail (httpd) → Apache HTTPD/gunicorn wiring.

Reference host (this machine) prototypes everything all-Linux first; the
first build targets native Windows (Docker Desktop, no WSL2 Ubuntu distro)
and is executed on a real Windows host when one is available. Kit's Docker
Desktop version/preferences to be collected then.

Exit gate: every component [verified] in runbook §8 and the §9 checklist
green on the reference host.

### Phase 3 — Cutover [queued]

Deploy the Windows-only topology on the Windows host, re-run the full
acceptance checklist against it, then — and only then — build the full
installer (child goal). The first-build installer covers the Windows-only
layout.

Exit gate: installer reproduces a verified stack from scratch on a clean
host.

## 4. Dependency chain and build order

Canonical chain (Kit 2026-09-19):

**pgrx (Rust toolchain) → TimescaleDB → pgvectorscale → pgAI**

i.e. `timescaledb` first, then `vector` → `vectorscale` (pgvectorscale needs
the base pgvector type), then `ai` CASCADE (pgAI needs pgvector +
plpython3u, pulled in automatically). pgrx heads the chain as the
extension-building toolchain — not a runtime dependency of the others, but
installed first so custom extensions can build against any of them.

Rules:

1. **Build follows the chain.** A component is installed only after the
   layer beneath it is [verified]. Skipping ahead creates debugging debt.
2. **Failures propagate downward.** If a component's bring-up fails and the
   root cause traces to a lower layer, that layer's build-debug cycle (§5)
   reopens — the upper layer does not get a workaround that hides it.
3. **Versions are pinned at bring-up.** The pgAI vectorizer call, the
   TimescaleDB image tag, the mail implementation — each is pinned to the
   exact release verified, and the pin is recorded in the runbook.

## 5. Build-debug-verify cycles

Every component goes through the same cycle. This is the "bugging cycle"
discipline: no component is declared working on the basis of a successful
install alone.

```
install → smoke test → integration test → [bug?] → debug loop → re-verify
```

### 5.1 The cycle steps

1. **Install** per the runbook, with `env.sh` sourced. Record the exact
   version installed (e.g. cargo-pgrx 0.19.2, 2026-09-19).
2. **Smoke test** — the component's own minimal proof of life (e.g.
   `cargo pgrx --version`, `ollama --version`, mail banner on the
   test port, `SELECT * FROM timescaledb_information.hypertables`).
3. **Integration test** — the component doing its real job inside the
   stack (e.g. vectorizer worker embeds a new post; the mail side delivers a
   reply-notification email; `/metrics` reads the hypertable).
4. **Debug loop** (only if 2 or 3 fails): reproduce → isolate → minimal
   fix → re-run the failing test → regression-check the tests that passed
   before. A fix that breaks a previously green test is not a fix.
5. **Re-verify and record**: status label updated in runbook §8 with the
   evidence (command, exit code, date).

### 5.2 The bug log

Every defect found in a cycle is entered in `BUGLOG.md` (this directory)
with: date, component, symptom, reproduction, root cause, fix, regression
check, status. The log is the project's memory of what broke and why —
"when we find something that we can now do, let's do it and add it to the
notation log" applies to fixes too: a fix that unblocks new work is
recorded as such.

Seeded entries (2026-09-19, already on record):

- cargo-pgrx first install: background session vanished with no binary and
  no log — root cause unknown; retry with `--locked` succeeded (0.19.2).
- Ollama install script: requires `zstd`, absent without apt — blocked,
  retry after apt.
- James download: guessed `apache-james-3.8.2.zip` 404'd (196 bytes);
  correct artifact is `james-server-jpa-guice.zip`.
- Ollama tarball: guessed URL 404'd — never guess URLs; use the vendor
  install script.

### 5.3 Cycle rules

- **One variable at a time.** Change one thing between test runs; if two
  things changed, the result is inconclusive.
- **No mock passes.** A test that doesn't exercise the real component
  (hardcoded expected output, skipped assertions) is not a pass — this is
  the build-side equivalent of the honesty protocol.
- **Background work reports or it didn't happen.** Long installs run in
  background sessions; a session that vanishes without an exit code is
  [failed]/[incomplete], never assumed done. Check sessions before
  launching duplicates.
- **Timeouts are data.** "If the tool runs out of time let me know it was
  incomplete" — a timed-out test is [incomplete], and the timeout itself
  goes in the bug log.

## 6. Status labels

Runbook §8 is the state of record. Every component carries exactly one:

- **[verified]** — installed, smoke-tested, integration-tested, evidence
  recorded (version, exit code, date).
- **[in progress]** — a cycle is actively running (install or debug loop
  open).
- **[blocked]** — waiting on something outside the cycle (apt mirror,
  Windows host, a lower layer's reopened cycle). The blocker is named.
- **[documented]** — procedure written from vendor docs, not yet executed
  here.
- **[pending]** — not started.
- **[failed]** — a cycle step failed and the debug loop is open or the
  failure is unresolved. Never left unlabeled.

Nothing is called "operational", "done", or "working" until it is
[verified]. The Flask app is not operational; the stack is not operational.

## 7. Verification and acceptance

The acceptance gate is the runbook §9 checklist: extensions present
(`\dx` shows `timescaledb`, `vector`, `vectorscale`, `ai`), hypertable
listed, vectorizer worker running with a DiskANN index and relevant
semantic results, `cargo pgrx test` green on the template extension,
mail banner + delivered test mail, full forum flow
(register → thread → reply → notification email), `/metrics` reading the
hypertable, no admin ports internet-reachable, backups configured and
restore-tested.

Acceptance runs twice on the Windows-only first build (Phase 3). The
installer is built only after both runs are green. (Earlier plan: one
reference-host run + one Windows+WSL2 run — superseded 2026-09-19.)

## 8. Ongoing maintenance

- The `lampy-morning-report` cron (daily ~08:47 PT → iOS side chat) sweeps
  runbook §8, `env.sh`, background sessions, app compile state, and tracked
  states. It reports failures and incompleteness plainly and stays silent
  on nothing it was asked to check.
- Runbook §8 is updated the moment a status changes — a status written
  down only in chat is not recorded.
- When a component's procedure changes (new pgAI release, new vectorizer
  call signature), the runbook is updated first, the cycle re-run, and the
  version pin updated. Procedure and reality never drift.

## 9. Tool inventory

- **Shell.** Everything runs from the shell (`muse.exec`) with `env.sh`
  sourced; long installs run in background sessions and report only on
  completion, with exits, losses, and timeouts disclosed.
- **Runbook.** `README.md` — the living administrator guide; `BUGLOG.md`
  — the defect record; this file — the workflow governor.
- **App.** `~/workspace/forum/` (Flask prototype, venv, gunicorn);
  `~/workspace/forum-stack/env.sh` (build environment).
- **Reference docs.** The read-only Google Doc copy under
  `~/workspace/goals/forum-stack-full-installer/files/`; the official
  pgai vectorizer quick start (Ollama variant) as the pgAI procedure
  source.
- **Orchestration.** Cron (`lampy-morning-report`); tracked goals
  (`lampy-forum-stack-build` parent, full-installer child); subagents for
  parallelizable build work. The browser is available whenever a step
  needs it (Kit: "You can always use the browser if you have need").
- **Verification discipline.** Every check is a real command with a real
  exit code; status labels from §6 are attached at the point of the check;
  nothing is promoted beyond what the check established.

## 10. Unfinished tasks (backlog)

Added 2026-09-19 at Kit's direction ("add unfinished tasks to the control
document"). Status labels per §6. A task leaves this list only when its
evidence is recorded in runbook §8.

### Docker / images
- [ ] All four images in `docker images`: `timescale/timescaledb-ha:pg16`,
  `ollama/ollama:latest`, `python:3.12-slim`,
  `httpd:latest`. [done 2026-09-19] (James removed from the stack 2026-09-19 per Kit.)
- [ ] `httpd -t` syntax check on `httpd/httpd.conf` once the httpd image lands. [pending]
- [ ] Real container start verified (vfs, no bridge, `--network host`). [pending]
- [ ] Docker socket mount vs real `docker:dind` — decision needed (ledger U-10)
  before any nested orchestration. [pending]

### IDE (code-server)
- [x] Tarball extracted, server started, login page answers 200 (2026-09-19).
- [ ] Python extension installed in code-server. [pending]
- [ ] `ide` image built from `ide/Dockerfile`; browser access tested. [pending, needs docker]

### Configuration
- [ ] TLS certificates for the 443 vhost (written, commented out). [pending]
- [ ] Flask `app` service (`app:8000`, gunicorn) added to compose; `/app`
  proxy target live. [pending]

### Extensions / AI
- [ ] `nomic-embed-text` pulled; real 768-dim embedding verified. [in progress]
- [ ] pgAI installed in a dedicated env; vectorizer API pinned. [blocked]
  (`ModuleNotFoundError: No module named 'pgai'` on reference host 2026-09-19)
- [ ] Resolve what `timescaletools` denotes (ledger U-8). [pending]
- [ ] Schema / vectorizer worker / DiskANN / semantic-search qualification. [pending]
- [ ] Windows extension inventory (`timescaledb`, `vector`, `vectorscale`,
  `ai`) on the Windows host. [pending, needs Windows host]

### Windows host
- [ ] Tailscale on Windows + SSH into the Windows host (~2026-09-23; the
  WSL2-sshd leg of the old plan is dropped — Windows-only now). [pending]
- [ ] Confirm Windows-side `PROJECT_ROOT` and `PGDATA` without rewriting
  Kit's setup. [pending]
- [ ] "Same GitHub keychain" decision: GHCR vs Docker Hub. [pending]

### Control plane (`control-plane/`)
- [x] Core file-ops (`ScriptWriter` + `FileOps`), demo passes (2026-09-19).
- [ ] Service control: httpd/postgres/ollama start-stop-status. [pending]
- [ ] Docker orchestration via generated scripts (compose up/down/ps). [pending]
- [ ] pgAI vectorizer calls. [pending]
- [ ] Installer logic. [queued — after acceptance]

### Acceptance / installer
- [ ] §9 checklist green **twice** on the Windows-only build. [pending]
- [ ] Full installer (child goal) — queued until then.
- [ ] Audit permissive chmod changes under surviving build paths. [pending]

### Path stability (Windows bootstrap)
- [x] Design: PGDATA anchor + NTFS junction armor (`installer/PATH_STABILITY.md`,
  2026-09-19). Compose db bind-mounts `${PGDATA_DIR}` (the anchor); siblings
  hang off `${LAMPY_DATA}` (anchor's parent).
- [x] `installer/bootstrap-paths.ps1` rewritten anchor-first (`-PgData`, derives
  data tree/home, `-MoveFrom` takes old anchor). [pending] not yet run on
  Windows; PowerShell syntax unverified on the build machine — review before
  first run.
- [ ] First Windows run: create anchor, verify junctions, `docker compose up -d`
  with the bind mounts. [pending, needs Windows host]

### Superseded 2026-09-19 (Windows-only first build — no WSL2 Ubuntu)
- WSL2 Ubuntu app stack (runbook §3.6) — reference only.
- WSL2-side Python venv (U-9 is now Windows-native only).
- Reference-host + Windows+WSL2 double acceptance — now Windows-only twice.
