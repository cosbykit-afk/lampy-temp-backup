# Lampy bug log

Defects found during build-debug-verify cycles (WORKFLOW.md §5). Each entry:
date, component, symptom, reproduction, root cause, fix, regression check,
status. A fix that unblocks new work is noted as such.

---

## 2026-09-19 — cargo-pgrx — first install session vanished

- **Component:** pgrx toolchain (Rust)
- **Symptom:** background session `proc_7188fe16baba` disappeared; no
  `cargo-pgrx` binary, no log, no exit code.
- **Reproduction:** `cargo install cargo-pgrx` (without `--locked`) in a
  background session with `env.sh` sourced.
- **Root cause:** unknown — session lost before producing output.
- **Fix:** retried as `cargo install cargo-pgrx --locked` in a fresh
  background session; completed exit 0 in ~8 min, installed cargo-pgrx
  0.19.2 (`cargo pgrx --version` verified).
- **Regression check:** `cargo pgrx --version` → 0.19.2. Pending: `cargo pgrx
  init` against PG16 and the template-extension build/test.
- **Status:** install recovered; init not yet run.

## 2026-09-19 — Ollama — install script needs zstd

- **Component:** Ollama (embeddings)
- **Symptom:** `https://ollama.com/install.sh` pipeline reported exit 0 but
  no `ollama` binary appeared.
- **Reproduction:** ran the install script on the reference host.
- **Root cause:** script requires `zstd`, which is not installed; apt is
  unusable (slow mirror), so the dependency could not be fetched.
- **Fix:** none yet — retry after apt works, then verify binary, service/API,
  and pull `nomic-embed-text`.
- **Regression check:** n/a.
- **Status:** [blocked] on apt.

## 2026-09-19 — Ollama — guessed tarball URL 404

- **Component:** Ollama
- **Symptom:** direct tarball download returned a 9-byte HTTP 404.
- **Reproduction:** guessed tarball URL instead of using the vendor script.
- **Root cause:** guessed URL — never guess URLs.
- **Fix:** use `https://ollama.com/install.sh` after `zstd` is available.
- **Regression check:** n/a.
- **Status:** closed (procedure corrected); lesson recorded: no guessed URLs.

## 2026-09-19 — Apache James — wrong zip name 404

- **Component:** Apache James 3.8.2
- **Symptom:** `apache-james-3.8.2.zip` downloaded 196 bytes (404 page).
- **Reproduction:** guessed the artifact name.
- **Root cause:** guessed URL; the real artifact is
  `james-server-jpa-guice.zip`.
- **Fix:** downloaded the correct JPA/Guice zip (91,247,630 bytes),
  extracted to `~/workspace/forum-stack/james/james-server-jpa-guice`;
  bad archive removed (`unzip` had exited 9).
- **Regression check:** archive contains app JAR, libraries, `conf/`;
  defaults Derby + SMTP 25 confirmed by inspection.
- **Status:** download recovered; install/config pending (needs Java → apt).

## 2026-09-19 — apt — update session unresolved

- **Component:** base packages (apt)
- **Symptom:** `apt-get update` moved to background session
  `proc_9387516e1d08` after ~122 s with no completion; earlier session
  `proc_1fa6aeea75ed` lost.
- **Reproduction:** `sudo apt-get update` on the reference host (slow mirror).
- **Root cause:** unknown — mirror slowness vs. stuck lock; session outcome
  never obtained.
- **Fix:** none yet — check session state before launching any duplicate;
  inspect `/var/log/apt/` and lock files before retrying.
- **Regression check:** n/a.
- **Status 2026-09-19 ~15:20:** `apt-get update` COMPLETED (exit 0) with
  warnings — `noble-backports` and `noble-security/multiverse` index files
  failed to download (connection failures via the proxy at 198.19.0.1:3128 /
  IPv6 proxy); those were ignored and old indexes used instead. Main/universe
  indexes appear usable. Apt is now partially functional: proceeding to
  install zstd, Java, and PostgreSQL 16 packages; if a package is missing
  from the stale indexes this entry reopens.
- **Status:** was [blocked]; now partial — installs attempted.

## 2026-09-19 — apt — package install session complete

- **Component:** base packages (apt)
- **Symptom:** background session `proc_1100c354cd4b` completed (exit 0) after
  ~203 s; output showed cert setup + `Setting up default-jre-headless`.
- **Caveat recorded:** the command piped apt output through `tail` without
  `set -o pipefail`, so the printed exit code could have been `tail`'s, not
  apt's — exit code alone was not trusted.
- **Fix:** verified every package independently with `dpkg-query -W
  -f='${Status}'` — all 9 report `install ok installed`: `zstd`,
  `default-jre-headless`, `postgresql-16`, `postgresql-contrib`,
  `postgresql-server-dev-16`, `build-essential`, `pkg-config`, `libssl-dev`,
  `libclang-dev`. Binaries confirmed: `zstd` 1.5.5, OpenJDK 21.0.12,
  `pg_config` = PostgreSQL 16.15.
- **Regression check:** Ollama installer and James are now unblocked
  (`zstd` + Java present); `cargo pgrx init --pg16` unblocked
  (server headers present).
- **Status:** [verified] — all requested packages installed; no missing items.

## 2026-09-19 — James — startup defects (all fixed, reference host)

- **Component:** Apache James 3.8.2 (JPA/Guice)
- **Symptom:** server would not start; three successive defects:
  1. `MissingArgumentException: Server needs a working.directory env entry`
     — the README's `java -jar` line was incomplete; the bundled
     `README.adoc` requires `-Dworking.directory=.`
     `-javaagent:.../openjpa-3.2.0.jar` (note: 3.2.0, not 3.1.2)
     `-Djdk.tls.ephemeralDHKeySize=2048`
     `-Dlogback.configurationFile=conf/logback.xml`.
  2. `NoSuchFileException: ./conf/keystore` — no keystore shipped;
     generated per the config's own instructions:
     `keytool -genkeypair -alias james -keyalg RSA -storetype PKCS12
     -keystore conf/keystore -storepass james72laBalle ...`
     (secret `james72laBalle` comes from `imapserver.xml`; self-signed,
     10-year, reference-host dev only).
  3. JMX `Cannot bind to URL [rmi://127.0.0.1:9999/jmxrmi]` —
     `non-JRMP server at remote endpoint`, twice, with no stale process
     and nothing listening on 9999. Cause undetermined (sandbox network?).
     Workaround: `jmx.enabled=false` in `conf/jmx.properties`; admin via
     WebAdmin REST (port 8000) instead of `james-cli.sh`. Production keeps JMX.
- **Also fixed:** `pkill -f james-server-jpa-app` matched the invoking
  shell's own command line and SIGTERM'd it — use `pgrep` + targeted kill.
- **Fix verified:** `JAMES server started`, SMTP `220` banner on 2525,
  `forum.local` domain + `notify@forum.local` user via WebAdmin,
  SMTP send → IMAP (STARTTLS on 1143) retrieval round-trip OK.
- **IMAP note:** plain LOGIN is disabled by default; clients must STARTTLS.
- **Status:** [verified] on reference host.

## 2026-09-19 — forum app — metrics 500 for logged-in users (fixed)

- **Component:** forum Flask app (`/metrics`)
- **Symptom:** `/metrics` returned 500 for logged-in users when the
  `forum_daily` continuous aggregate was missing; anonymous users got 200.
- **Root cause:** the `forum_daily` SELECT failed inside the try/except
  (caught, `rows=[]`), but the failed statement left the per-request
  connection's transaction aborted. The base template's context processor
  calls `current_user()` on every render, which reuses the same poisoned
  connection → `InFailedSqlTransaction` → 500.
- **Fix:** `db().rollback()` in the metrics `except` block before rendering.
- **Regression check:** logged-in `/metrics` → 200 with the
  "metrics unavailable" warning; full flow re-tested.
- **Status:** [verified] fixed.

## 2026-09-19 — forum app — end-to-end on reference host (verified)

- Local PostgreSQL 16.15 started; `forum` role + database created;
  schema loaded from a filtered copy (`/tmp/schema-local.sql`,
  TimescaleDB-only statements dropped — no timescaledb extension on the
  reference host; canonical `schema.sql` unchanged).
- `GRANT ALL` on tables/sequences to the `forum` role (tables were created
  by the postgres superuser).
- Test-client: register 200 → login 302 → new thread 302 → reply 302 →
  reply visible on thread page → index/search/metrics 200.
- App → James mail: registration welcome email
  (`notify@forum.local` → `inboxtest@forum.local`) delivered and read back
  via IMAP.
- venv rebuilt (`~/workspace/forum/venv`, Flask 3.1.3); `py_compile` clean.
- **Status:** [verified] on reference host (Timescale/pgAI/semantic search
  still pending — needs the Docker image / pgAI bring-up).

## 2026-09-19 — env config — Kit confirmation

- Kit confirmed the full env-var configuration from his 2025-02-26 post is
  tested and correct as written.
- `PGDATA=C:\Postres\data` — the "Postres" spelling is intentional, NOT a
  typo (earlier typo flag retracted).
- `PGRX_BUILD_FLAGS=TRUE` restored in `env.sh` per Kit's tested config
  (previous "deliberately unset" decision reversed by Kit).
- `RUSTUP_HOME=C:\.rustup\bin`, empty `POSTGRES_USER`/`POSTGRES_PASSWORD`,
  `OLLAMA_MODELS`/`OPENSSL_CONF` empty — all confirmed correct as in the post.
- **Status:** [verified] by Kit.

## 2026-09-19 — Ollama official installer — completed

- Session `proc_d562bdeeb21a` (`curl -fsSL https://ollama.com/install.sh | sh`)
  finished with exit 0 after ~9.8 min. Created the `ollama` user and a systemd
  service unit. The manually started `ollama serve` on 127.0.0.1:11434
  (binary 0.34.2) was already serving; model pull still in flight separately.
- **Status:** [verified] installer completed; no action taken on the systemd
  unit (reference host has no running systemd).

## 2026-09-19 — pgAI venv install — first attempt FAILED (disk)

- Session `proc_9b5bac43810f` failed after ~8.8 min: pip
  `OSError: [Errno 28] No space left on device` while installing
  `pgai[vectorizer-worker]`. At failure time the disk was likely under
  transient pressure (pgrx test compiling 2.2G+ into cargo-target, Ollama
  model downloading); `df` afterward showed 4.8G free, so the shortage was
  transient. /tmp is a 512M tmpfs — pip temp builds could also have hit that.
- Fix: retried as `proc_da434ffe3f2d` with TMPDIR pointed at
  `~/workspace/forum-stack/build/pip-tmp` (bypasses the 512M /tmp).
- **Status:** [in progress] retry running.

## 2026-09-19 — Ollama model pull — FAILED (egress approval)

- Session `proc_758db3472100` (`ollama pull nomic-embed-text`) ran ~10 min,
  then failed: `Error: pull model manifest: 403:
  {"detail":"egress approval timed out; the action was not performed.",
  "error":"policy_denied","policy":"sentinel-policy",
  "rule":"GET /v2/token?...&service=ollama..."}`. The registry token request
  to ollama.com was denied by egress policy. (PULL_EXIT printed 0 because the
  pipe through `tail` swallowed ollama's real exit — same pipefail trap as
  before.)
- `ollama list` is empty; `~/.ollama/models/{blobs,manifests}` are empty.
- A pending egress approval exists (approval_id
  13c630d5-a441-46d0-b01a-bc4778fc6d2b, "Access ollama.com", requested
  2026-09-19 15:35 PDT). Kit must approve it before the pull can be retried.
- **Status:** [blocked] on Kit's approval.

## 2026-09-19 — pgrx template test — PASS (after two real defects fixed)

- Session `proc_13c93735c2f9` (`cargo pgrx test pg16`, correct syntax,
  pipefail) FAILED the template test `tests::pg_test_hello_lampy_smoke`.
- Defect 1 (build): with `PGRX_BUILD_FLAGS=TRUE` exported (from Kit's
  confirmed env config), every build failed:
  `error: multiple input filenames provided (src/lib.rs, TRUE)`.
  Root cause PROVEN from cargo-pgrx 0.19.2 source, src/cargo.rs:156:
    let flags = env::var("PGRX_BUILD_FLAGS").unwrap_or_default();
    for arg in flags.split_ascii_whitespace() { cmd.arg(arg); }
  The value is passed VERBATIM as cargo/rustc args, so TRUE became a bogus
  input filename. Same read exists in src/command/install.rs:307 (it also
  broke `cargo pgrx install`). Kit's Feb-2025 config was tested against
  pgrx 0.12.x-era behavior; the installed 0.19.2 honors the variable, so
  the value is version-dependent. Fix: `unset PGRX_BUILD_FLAGS` in env.sh
  with this evidence in the comment. Windows/WSL2 prod must re-check
  against its own installed pgrx version — do NOT blindly inherit either
  value.
- Defect 2 (test framework): `initdb: error: cannot be run as root`. This
  sandbox runs everything as root; the pgrx test framework always initdbs
  a throwaway cluster. Non-root users are sandbox-blocked from /home/hatch
  entirely (even 777 dirs deny them), and user namespaces can't map
  outer-root, so the usual workarounds failed. Fix (reference-host only):
  `build/fakeuid-shim/fakeuid.c` — a small LD_PRELOAD shim that reports
  uid/gid 1000 from getuid/geteuid/getgid/getegid and rewrites st_uid/
  st_gid 0->1000 in stat-family results so postgres's data-dir ownership
  check passes. The process stays really root, so all file access works.
  Test run: `LD_PRELOAD=.../fakeuid.so USER=lampybuild cargo pgrx test
  pg16`. (Note: CARGO_PGRX_TEST_RUNAS must NOT be used — it makes the
  framework add --sudo to the install step; plain USER= works.)
- Result: `test tests::pg_test_hello_lampy_smoke ... ok`,
  `test result: ok. 1 passed; 0 failed`, exit 0. The shim is documented
  in fakeuid-shim/fakeuid.c and is reference-host-only; WSL2 prod runs as
  a normal user and must NOT use it.
- **Status:** [verified] pgrx toolchain end-to-end (init, build, install,
  live #[pg_test]).

## 2026-09-19 ~16:35 PDT — VM replacement wiped system-level installs
- Reference host was replaced: everything outside ~ is gone. Lost: PostgreSQL 16
  (binaries + clusters), OpenJDK 21, Ollama 0.34.2 (binary + ollama user +
  systemd service), all apt base packages.
- Survived in ~: ~/workspace (forum app, venvs incl. pgai-venv, James
  extraction, build dirs), ~/.cargo (cargo + cargo-pgrx 0.19.2), ~/.rustup,
  ~/.pgrx/config.toml, ~/.ollama/models (empty — pull never completed).
- Rebuild started: apt reinstall of base packages in background; Ollama
  official installer to follow (needs fresh ollama.com egress approval);
  then PG cluster + forum role/DB + filtered schema, James restart +
  re-verify, pgAI install retry.
- Lesson: reference-host system installs are ephemeral; the runbook must treat
  them as reinstallable steps, not one-time setup.

## 2026-09-19 ~16:50 PDT — Docker on the reference host (sandbox workarounds)
- docker.io installed from Ubuntu repos (had to drop the hanging
  mirror.cogentco.com apt mirror; azure.archive.ubuntu.com works).
- dockerd CANNOT manage networking here: no iptables/nftables kernel support.
  Running with `--iptables=false --bridge=none`; containers must use
  `--network host` (fine here; on prod Docker Desktop networking is normal).
- overlayfs mounts rejected by the sandbox kernel ("invalid argument" even
  with userxattr). Running with `--storage-driver=vfs` (slower, disk-hungry,
  but works). /var/lib/docker is ephemeral anyway (VM replacement wipes it).
- Daemon honors the egress proxy env for pulls. Proxy is FLAKY: intermittent
  TLS handshake timeouts / EOFs to registry-1.docker.io, auth.docker.io,
  production.cloudfront.docker.com — but curl through the same proxy works
  and one full hello-world pull succeeded. Retries eventually succeed.
- Kit reports having a working image already; awaiting its name/location.
  Kit's Docker Hub login is in the Secure Vault (first entry was the wrong
  password; fresh card sent 16:51 PDT). Vault cannot do CLI `docker login`;
  Kit declined the transient handoff ("keep it in the vault") — pulls stay
  anonymous unless rate limits force the issue.

## 2026-09-19 ~19:33 PDT — trickle fallback for timescaledb-ha pull (Kit's request)
- Kit: "slow down the timescale db, let that download as a trickle, if it fails again."
- Fact: `docker pull` has no bandwidth limit; `trickle` (LD_PRELOAD) cannot hook
  Go's statically-linked binaries — so a true trickle pull is done by hand.
- Built `hidden_files/trickle_pull.sh <repo> <tag> [rate] [--probe]`: registry
  HTTP API (token -> manifest list -> linux/amd64 manifest) + curl
  --limit-rate per blob (resumable, 8 attempts each) -> assemble docker-load
  tarball -> `docker load -i`. Probed OK 2026-09-19: timescaledb-ha:pg16 =
  2 layers, 955,838,565 bytes (~911 MB); at 1M the ETA is ~15 min.
- Policy: the running full-speed pull stays (it was downloading fine on
  attempt 3); the trickle script is ARMED and launches automatically if the
  normal pull exhausts its attempts without landing the image.

## 2026-09-19 ~19:40 PDT — Rust toolchain verified (Kit: "just enough to install rust")
- C compiler: already present — gcc 13.3.0 at /usr/bin/{cc,gcc}; compiled and
  ran a hello-world (CC_WORKS).
- Rust: NOT on PATH but present in persistent home (~/.cargo, survived host
  replacement). Re-ran rustup-init (-y, minimal) to verify/repair; toolchain
  resolves: rustc 1.98.1, cargo 1.98.1, cargo-pgrx 0.19.2 (matches env.sh
  expectations). `cargo new/build/run` hello-world prints OK — rustc -> cc
  link chain works. env.sh already puts $CARGO_HOME/bin on PATH (lines 12-14);
  no edit needed. Verified through `source env.sh`.

## 2026-09-20 ~07:39 PDT — cloud build failed at apt-get: missing /usr/share/man/man1 (FIXED)
- First full `lampy-single` Build Cloud build failed at [stage-2 2/12]
  (Dockerfile:50), exit code 100. Observed root cause, not a guess:
  `update-alternatives: error: error creating symbolic link
  '/usr/share/man/man1/java.1.gz.dpkg-tmp': No such file or directory`
  during openjdk-17-jre-headless postinst -> dpkg error -> apt exit 100.
- The timescale/timescaledb-ha:pg16 base strips man pages, so the directory
  does not exist; java's update-alternatives needs it. ca-certificates-java
  failed only as a dependency consequence.
- Fix: `mkdir -p /usr/share/man/man1` at the start of the same RUN
  (lampy-single/Dockerfile). No other RUN uses dpkg, so no other step needs it.
- Retrying the cloud build; earlier steps (base pulls, ollama COPY) should hit
  the cloud builder cache.

## 2026-09-20 ~07:40 PDT — cloud build failed at pip install: --break-system-packages unknown (FIXED)
- After the man1 fix, build reached [stage-2 3/12] and failed, exit code 2:
  `pip install --no-cache-dir --break-system-packages pgai` ->
  `no such option: --break-system-packages`.
- Observed root cause: the base is Ubuntu jammy, pip 22.0.2+dfsg-1ubuntu0.7;
  the flag (and EXTERNALLY-MANAGED enforcement) arrived in pip 23. Plain
  `pip install --no-cache-dir pgai` is correct here. Comment added to the
  Dockerfile explaining why the flag is absent.

## 2026-09-20 ~07:41 PDT — lampy-single cloud build SUCCEEDED and pushed (BUILD DONE)
- Third attempt: exit 0. All 12 stage-2 steps completed (apt fix + pip fix both
  held; pgai 0.12.1 installed; james COPY, code-server ADD, apache vhost,
  supervisord conf all applied).
- Pushed: kitcosby/lampy-single:latest
  digest sha256:2e2d103715b8cc9e9cdc4242e498df41b0c03825249986d6fba9129469956b03
  (manifest list; linux/amd64 image manifest
  sha256:5ef26953a81c0b621c0dc1ea6dbf625b6932b476d9442738787407370cd8624d).
- Independently verified via `docker buildx imagetools inspect` (no pull):
  registry serves the tag, digest matches build output exactly.
- Build Cloud minutes used: ~3.5 min total across 3 attempts (200 free on trial).
- Scope honesty: BUILD success only. The image has NOT been run — this sandbox
  cannot launch containers (setns blocked, U-22). Runtime validation
  (postgres, httpd, ollama, james, code-server, pgai worker) waits for
  Windows Docker Desktop when Kit is back at his laptop (~Sept 23).
- Cleanup done: `docker logout`, config.json holds no credential, relay killed.
- Update 07:43 PDT: Kit keeps the non-expiring PAT in the Secure Vault for
  reuse (revocation superseded). Remaining: remove temporary `pat-test` tag
  (needs Kit's OK); git push still failing on SSH (commits local-only).

## 2026-09-20 ~08:05 PDT — pressure-test workflow built and run; real image bugs found (2 fixed in Dockerfile, rebuild pending)
- New workflow `lampy-single/pressure-test.sh` (Kit's directive: "pressure test
  the configuration to make the best image we can provide"). Six suites, no
  container needed: registry/build provenance, static file/binary/config audit
  (exported rootfs), supervisord/apache/shell config checks, real binary smoke
  tests via chroot+userns, two-tier secret scan, size/hygiene + Dockerfile lint.
  Seven runtime checks explicitly deferred to Windows (needs docker run).
- First run: 48 PASS / 11 FAIL / 7 SKIP. Most FAILs were checker/sandbox
  artifacts (fixed in the script, not the image): rootfs symlink resolution
  (code-server, docker-entrypoint.sh, /var/run/supervisor are absolute
  symlinks — must resolve inside the rootfs, not against the host); java
  needs LD_LIBRARY_PATH inside chroot; apache2 -t needs envvars sourced;
  secret-scan hits were Debian snakeoil + known-benign test material.
- REAL image bugs found (all verified by direct experiment, fixes committed,
  rebuild blocked on Docker Hub push auth — see below):
  1. apache would crash-loop at startup: /var/run/apache2 and /var/lock/apache2
     are missing from the image, so `apache2ctl -D FOREGROUND` (supervisord)
     fails with "DefaultRuntimeDir must be a valid directory". Verified:
     chroot configtest fails without the dirs, "Syntax OK" with them.
     Dockerfile now mkdirs both at build time.
  2. `ollama serve` would fail at startup: Dockerfile copied only /usr/bin/ollama
     (the CLI) from the donor image; the CLI execs the llama-server runner from
     /usr/lib/ollama, which was absent ("llama-server binary not found" when
     attempting inference with the image's binary). Dockerfile now copies
     /usr/lib/ollama too; pressure-test gained a regression check.
  3. /tmp/hsperfdata_root left in image (JVM debris). Dockerfile now removes it.
- Also committed: base-image digest pins (timescale + ollama donors, digests
  from the successful build log), Apache ServerName localhost.
- Latest run: 58 PASS / 2 FAIL / 7 SKIP. The 2 FAILs are exactly the two
  findings above awaiting rebuild (apache configtest, /tmp clean) — both fixed
  in the Dockerfile, verified by experiment to be fixed-by-rebuild.
- Rebuild attempted via Build Cloud with the sandbox relay (procedure now
  documented in build-cloud.sh): got PAST the TLS/proxy issue, then failed
  cleanly on `no credentials found for https://index.docker.io/v1/` — the
  cloud driver needs Docker Hub auth and the Secure Vault cannot release the
  PAT to the CLI. Rebuild+push queued until Kit can provide auth (laptop,
  ~Sept 23, or his direction). Current pushed image is functionally identical
  in content (pins resolve to the same digests); the pending rebuild adds
  only the three fixes above.

## 2026-09-20 ~08:10 PDT — Musey model created (Ollama)
- Kit: "create a Muse-style Ollama model named Musey." Extracted the ollama
  binary from the lampy-single image, ran a local server, pulled qwen3:0.6b
  as the base, created `musey` from ~/workspace/ollama-test/Modelfile.musey.
  The Modelfile states plainly it is NOT Muse's weights — open-weights base
  with a Musey persona (concise, honest about being a small model).
- Inference smoke test pending: the image's ollama binary lacks its runner
  libs (finding #2 above); downloading the full Ollama Linux tarball to run
  the first inference test.
