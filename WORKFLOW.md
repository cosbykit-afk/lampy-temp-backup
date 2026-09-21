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
Apache James 3.8.2 (`apache/james:demo-3.8.2`, Kit's port remap),
Apache HTTPD/gunicorn. Production topology (2026-09-19, Kit): **Windows-only first build — no WSL2
Ubuntu.** Docker Desktop on Windows runs the Linux container images (db,
httpd, ollama, james, ide, pgai-worker per `docker-compose.yml`); Docker
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
vectorizer worker → schema → Apache James (mail) → Apache HTTPD/gunicorn wiring.

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
   TimescaleDB image tag, the James port remap — each is pinned to the
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
   `cargo pgrx --version`, `ollama --version`, James SMTP banner on the
   test port (2525), `SELECT * FROM timescaledb_information.hypertables`).
3. **Integration test** — the component doing its real job inside the
   stack (e.g. vectorizer worker embeds a new post; James delivers a
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

### 6.1 Notation contract (workflow scripts)

Every workflow script that runs checks follows the same result notation,
so runs are greppable and diffable across machines and dates:

- One `RESULT<TAB><PASS|FAIL|SKIP><TAB><check name><TAB><reason>` record
  per check. Check names are single-line and tab-free; the reason field
  may be empty.
- One `SUMMARY<TAB>pass=N<TAB>fail=M<TAB>skip=K` line at the end of the run.
- Exit codes: `0` = clean (no FAIL), `1` = at least one FAIL,
  `2` = the harness itself is broken (missing tool, bad usage).
- `set -o pipefail` (bash) wherever a pipeline feeds a pass/fail decision —
  a failure anywhere in the pipe fails the check; pipes must never mask
  exit codes.
- Build/push scripts end with one `RESULT<TAB>OK<TAB>...` terminal record;
  under `set -e`, reaching it means the operation succeeded.

The control doc (§10 backlog, runbook §8) uses exactly the §6 labels —
no checkbox/mixed notation. (`[x]` beside `[pending]`, or `[done ...]`
beside `[pending]`, describe one item in two vocabularies and disagree
about which is authoritative.)

## 7. Verification and acceptance

The acceptance gate is the runbook §9 checklist: extensions present
(`\dx` shows `timescaledb`, `vector`, `vectorscale`, `ai`), hypertable
listed, vectorizer worker running with a DiskANN index and relevant
semantic results, `cargo pgrx test` green on the template extension,
James SMTP banner (2525) + delivered test mail, full forum flow
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
- [verified 2026-09-19] All five images in `docker images`: `timescale/timescaledb-ha:pg16`,
  `ollama/ollama:latest`, `apache/james:demo-3.8.2`, `python:3.12-slim`,
  `httpd:latest`. (James re-added to the stack 2026-09-19 evening per Kit.)
- [pending] `httpd -t` syntax check on `httpd/httpd.conf` once the httpd image lands.
- [pending] Real container start verified (vfs, no bridge, `--network host`).
- [pending] Docker socket mount vs real `docker:dind` — decision needed (ledger U-10)
  before any nested orchestration.

### IDE (code-server)
- [verified] Tarball extracted, server started, login page answers 200 (2026-09-19).
- [pending] Python extension installed in code-server.
- [pending, needs docker] `ide` image built from `ide/Dockerfile`; browser access tested.

### Configuration
- [pending] TLS certificates for the 443 vhost (written, commented out).
- [pending] Flask `app` service (`app:8000`, gunicorn) added to compose; `/app`
  proxy target live.

### Extensions / AI
- [in progress] `nomic-embed-text` pulled; real 768-dim embedding verified.
- [blocked] pgAI installed in a dedicated env; vectorizer API pinned.
  (`ModuleNotFoundError: No module named 'pgai'` on reference host 2026-09-19)
- [pending] Resolve what `timescaletools` denotes (ledger U-8).
- [pending] Schema / vectorizer worker / DiskANN / semantic-search qualification.
- [pending, needs Windows host] Windows extension inventory (`timescaledb`, `vector`, `vectorscale`,
  `ai`) on the Windows host.

### Windows host
- [pending] Tailscale on Windows + SSH into the Windows host (~2026-09-23; the
  WSL2-sshd leg of the old plan is dropped — Windows-only now).
- [pending] Confirm Windows-side `PROJECT_ROOT` and `PGDATA` without rewriting
  Kit's setup. [pending]
- [pending] "Same GitHub keychain" decision: GHCR vs Docker Hub.

### Control plane (`control-plane/`)
- [verified] Core file-ops (`ScriptWriter` + `FileOps`), demo passes (2026-09-19).
- [pending] Service control: httpd/postgres/ollama start-stop-status.
- [pending] Docker orchestration via generated scripts (compose up/down/ps).
- [pending] pgAI vectorizer calls.
- [pending — after acceptance] Installer logic.

### Acceptance / installer
- [pending] §9 checklist green **twice** on the Windows-only build.
- [pending — until acceptance green twice] Full installer (child goal).
- [pending] Audit permissive chmod changes under surviving build paths.

### Path stability (Windows bootstrap)
- [verified] Design: PGDATA anchor + NTFS junction armor (`installer/PATH_STABILITY.md`,
  2026-09-19). Compose db bind-mounts `${PGDATA_DIR}` (the anchor); siblings
  hang off `${LAMPY_DATA}` (anchor's parent).
- [verified] `installer/bootstrap-paths.ps1` rewritten anchor-first (`-PgData`, derives
  data tree/home, `-MoveFrom` takes old anchor) (2026-09-19).
- [pending] First Windows run of `bootstrap-paths.ps1`: PowerShell syntax unverified
  on the build machine — review before first run.
- [pending, needs Windows host] First Windows run: create anchor, verify junctions, `docker compose up -d`
  with the bind mounts.

### Superseded 2026-09-19 (Windows-only first build — no WSL2 Ubuntu)
- WSL2 Ubuntu app stack (runbook §3.6) — reference only.
- WSL2-side Python venv (U-9 is now Windows-native only).
- Reference-host + Windows+WSL2 double acceptance — now Windows-only twice.

## 11. Critical-path review (2026-09-20)

Dated review of what is on the critical path, what is blocked, and what can
move before Kit's laptop access (~2026-09-23). Status labels per §6.
Mirrors the "Lampy" Google Tasks list created 2026-09-20.

### Spine: image → acceptance → installer
1. Docker Hub CLI auth — [blocked]. Needs Kit's laptop (~Sept 23); the
   Secure Vault cannot release the PAT to the CLI. This is the single
   gating blocker: nothing downstream on the spine can move without it.
2. Rebuild `kitcosby/lampy-single` via Build Cloud + push — [pending — after auth].
3. Independent digest verification + `pressure-test.sh` until 0 FAIL —
   [pending — after rebuild]. (Harness hardened 2026-09-20: `set -o pipefail`,
   `RESULT`/`SUMMARY` records, §6.1 contract.)
4. Runbook §9 acceptance checklist, twice, on the Windows-only build —
   [pending — after clean image + Windows host].
5. Full installer (child goal) — [pending — until acceptance green twice].

### Ollama / Musey (Kit's priority #1)
- Full Ollama v0.34.2 running locally, `/api/tags` OK — [verified].
- `musey` (qwen3:0.6b) smoke test 3/5 — [verified, with known failures]:
  honesty (breakfast confabulation) and failure-handling (Goldbach proof
  bluff) FAIL. v2 prompt hardening did not fix it and regressed identity —
  [verified] decision: v2 NOT promoted.
- Next: larger-model test (qwen3:8b class) on Windows before user exposure —
  [pending, needs Windows host]. Deploy idempotently to `C:\Lampy\data\ollama`;
  seed the Musey admin account on the live DB at bring-up (one command).
- Embeddings: `nomic-embed-text` pull + real 768-dim verification — [in progress].

### Extension chain (§4): pgrx → TimescaleDB → pgvectorscale → pgAI
- cargo-pgrx 0.19.2 installed — [in progress] (`pgrx init` against PG16 not run).
- pgAI install — [blocked] on the reference host (`ModuleNotFoundError`);
  first real attempt belongs on the Windows host.
- Schema / vectorizer worker / DiskANN / semantic-search qualification —
  [pending — after the chain].

### Side work (when the spine is blocked)
- `lampy-python`: self-tested on Linux, pushed — [pending] Windows exercise.
- db-console: table browser + query runner — [pending]; auth hardening — [verified].
- Payments: 26 unit tests pass, no live DB — [pending] live-DB schema apply +
  integration tests at Windows bring-up.

### Decisions needed from Kit (blocking larger work)
- Docker socket mount vs `docker:dind` (ledger U-10) — [pending].
- GHCR vs Docker Hub ("same GitHub keychain") — [pending].
- Delete temporary Docker tag `pat-test` — [pending — awaiting Kit's go-ahead].

### Deferred
- Full pure-Python OS/C/GCC rebuild — feasibility study for a separate,
  multi-year-scale program (GNU Mes/stage0 class). Does not move Lampy on
  the weeks horizon.

### Review findings
- Before ~Sept 23, the only critical-path work runnable on the reference VM
  is workflow/tooling hardening (this review, §6.1, the pressure-test
  notation) and unblocked side work. No component installs should be
  attempted against the reference host to "stay busy" — that is how the
  pgAI `ModuleNotFoundError` dead end was produced.
- Musey: the evidence (v1 + v2 transcripts) says prompt hardening is
  insufficient; further prompt iterations would be speculative. The larger
  base model on the Windows target is the recorded plan.
