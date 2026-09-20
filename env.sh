# Lampy reference-host environment — SOURCE BEFORE ANY INSTALL OR BUILD STEP
#   source ~/workspace/forum-stack/env.sh
#
# Adapted from the Lampy doc ("LAMP_AI Stack Setup Guide", Kit, v1.1), which
# lists these as Windows machine vars that MUST be set before any Cargo/PGRX
# download, or build caches get poisoned with wrong paths. Same rule applies
# here: no install/build command runs without this file sourced first.
#
# Every variable below is deliberate. Skipped doc vars are explained.

# --- Rust toolchain paths (explicit so nothing resolves by surprise) ---
export CARGO_HOME="$HOME/.cargo"
export RUSTUP_HOME="$HOME/.rustup"
export PATH="$CARGO_HOME/bin:$PATH"
# Doc uses C:\tmp for CARGO_TARGET_DIR. On Linux /tmp may be tmpfs (RAM-backed)
# and this host has 7 GB RAM with multi-GB pgrx target dirs, so use a
# persistent workspace dir instead of /tmp.
export CARGO_TARGET_DIR="$HOME/workspace/forum-stack/build/cargo-target"

# --- pgrx behavior ---
# Doc: PGRX_HOME=C:\Postgres\pgrx — cargo-pgrx's managed PostgreSQL builds.
# We point pgrx at the system PG16 via `cargo pgrx init --pg16=$(pg_config)`
# instead, so pgrx never downloads/compiles its own Postgres (saves GBs of
# disk). PGRX_HOME is still set explicitly for anything that consults it.
export PGRX_HOME="$HOME/.pgrx"
# Doc sets PGRX_BUILD_VERBOSE=TRUE — real pgrx var, keep it: full build logs.
export PGRX_BUILD_VERBOSE=TRUE
# Doc sets PGRX_IGNORE_RUST_VERSIONS=TRUE — REQUIRED here. This host has
# rustc 1.98.1, far newer than what cargo-pgrx 0.12.x officially supports;
# without this, `cargo pgrx init` refuses the toolchain.
export PGRX_IGNORE_RUST_VERSIONS=1
# Doc sets PGRX_BUILD_FLAGS=TRUE — Kit confirmed 2026-09-19 this exact
# configuration was tested and working (Feb 2025, pgrx 0.12.x era). BUT the
# installed toolchain is cargo-pgrx 0.19.2, whose src/cargo.rs:156 does:
#   let flags = env::var("PGRX_BUILD_FLAGS").unwrap_or_default();
#   for arg in flags.split_ascii_whitespace() { cmd.arg(arg); }
# i.e. the value is passed VERBATIM as cargo/rustc arguments. With TRUE set,
# every build fails: "multiple input filenames provided (src/lib.rs, TRUE)".
# Proven by the lampy_smoke test failure 2026-09-19. So it must stay UNSET
# on any host running cargo-pgrx 0.19.x. Windows/WSL2 prod must re-verify
# against its own installed pgrx version before inheriting Kit's value.
unset PGRX_BUILD_FLAGS

# --- PostgreSQL ---
# Reference host uses the Debian apt cluster layout (prod WSL2 topology puts
# the DB on Windows; see README §3.6). PGDATA is set explicitly per the doc's
# env-first rule rather than left implicit.
export PGDATA="/var/lib/postgresql/16/main"
export POSTGRES_USER="postgres"
# Doc sets POSTGRES_PASSWORD as a machine var. Reference host uses peer auth
# over the local socket, so no password is stored in this file, ever.

# --- Ollama (embeddings for the pgAI vectorizer; Kit's choice) ---
# Doc: OLLAMA_MODELS=C:\ollama\models. Linux default is ~/.ollama/models;
# set explicitly per the env-first rule.
export OLLAMA_MODELS="$HOME/.ollama/models"
export OLLAMA_HOST="http://127.0.0.1:11434"

# --- Forum app (reference host: everything local) ---
export FORUM_DB_HOST="127.0.0.1"
export FORUM_DB_PORT="5432"
export FORUM_DB_NAME="forum"
export FORUM_DB_USER="forum"
# FORUM_DB_PASS and FORUM_SECRET_KEY are set per-deploy, never stored here.
export FORUM_SMTP_HOST="127.0.0.1"
export FORUM_SMTP_PORT="587"
