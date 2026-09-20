# Forum Stack — Network Administrator Setup Guide

**Project name: Lampy.**

**Living document.** Built alongside the stack itself; each section is marked
with its verification status on the reference host. Do not treat
`[pending]` sections as tested.

Core files: `env.sh` (source before any install/build), `WORKFLOW.md`
(process governor), `BUGLOG.md` (defect log), `NOTATION_LEDGER.md`
(terms, env vars, ports, paths, version pins, open items).

## 1. What this is

A self-hosted discussion-forum stack ("LAMP"-style, Python variant):

> **Target deployment (production), 2026-09-19 (Kit): Windows-only first
> build — no WSL2 Ubuntu.** The whole stack (database, Python/Flask app,
> Apache James, Apache HTTPD, pgrx toolchain, pgAI vectorizer worker,
> Ollama) runs on Windows: Linux containers via Docker Desktop
> (`timescale/timescaledb-ha:pg16` for the database — Kit's decision
> 2026-09-19 — plus httpd, ollama, james, ide, pgai-worker images; see
> `docker-compose.yml`). Docker Desktop's internal WSL2 backend is Docker's
> own machinery, not a Ubuntu environment we manage. The earlier
> Windows+WSL2 split (§3.6) is superseded for the first build and retained
> for reference only. The reference build in §8 is all-Linux and prototypes
> the same components in one box.

| Layer | Component | Role |
|---|---|---|
| OS | Linux (Ubuntu 24.04 LTS, reference host) | base |
| Mail | Apache James 3.8.2 (`apache/james:demo-3.8.2`), Kit's port remap 2525/2465/2587/1143/1993/1110 | SMTP/IMAP mail server for forum notifications |
| Database | PostgreSQL 16 + TimescaleDB + pgvector/pgvectorscale + pgAI — in a Docker Desktop Linux container on Windows in production (§3.6); on Linux in the reference build (§8) | forum data, time-series metrics, scalable vector search, AI semantic search |
| Extensions SDK | pgrx (Rust) | toolchain for building custom PostgreSQL extensions |
| App | Python 3.12 + Flask (`~/workspace/forum/`) | the forum web application |

> **Design decision (Kit 2026-09-19):** Python scripts are the AI-operated
> control plane for the stack — the AI uses them to manage every layer down
> to root. The lightweight Python IDE + pip below serve that control plane.

> **Design decision (Kit 2026-09-19):** Apache HTTPD is the web server / TLS
> terminator (replaces nginx; fits the "Lampy"/LAMP naming). Kit's own 2025-02-23
> Docker sketch (his Facebook "Docker progress" post) already specified an
> `httpd` service — this decision matches his original design. 2026-09-19 evening:
> Kit first removed Apache James, then re-added it as the mail server with his
> port remap (SMTP 2525, SMTPS 2465, submission 2587, IMAP 1143, IMAPS 1993,
> POP3 1110 — see `james/james-server-jpa-guice/conf/`). httpd is web/TLS only.

Text architecture:

```
                     ┌──────────────┐
  users ──HTTPS──►   │ Apache HTTPD (TLS) │──► gunicorn/Flask :8000  (forum app)
                     └────────────────────┘         │
                                              ├─► PostgreSQL :5432
                                              │     ├─ forum tables
                                              │     ├─ TimescaleDB hypertable (metrics)
                                              │     └─ pgAI vectorizer (semantic search)
                                              └─► James SMTP :2525/2587 (outbound mail)
                                                        │
  mailboxes ◄──IMAP :1993── Apache James ◄── local delivery
```

Port table (production defaults; build-host deviations noted in §8):

| Port | Service | Expose to |
|---|---|---|
| 80/443 | Apache HTTPD (forum site) | internet |
| 5432 | PostgreSQL | app host only (never internet) |
| 2525 | James SMTP (MX + relay) | internet (2525) / app (2587 submission) |
| 2587 | James SMTP submission | app host / authenticated users |
| 1143/1993 | James IMAP | users (1993 preferred) |
| 1110 | James POP3 | users |
| 8000 | gunicorn | localhost only (behind Apache HTTPD) |

## 2. Prerequisites

- Ubuntu 24.04 LTS (or Debian 12), 2+ vCPU, 4+ GB RAM, 20+ GB disk.
  - Reference build host: 2 vCPU / 7 GB RAM / 7.5 GB disk — workable but tight;
    allow more disk if hosting the mail store long-term.
- A public DNS name for the forum (e.g. `forum.example.com`) and an MX record
  pointing at the James host if receiving external mail.
- Root/sudo on the box.

## 3. Base packages [in progress on reference host]

```bash
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib \
  python3 python3-venv python3-pip \
  default-jre-headless \
  build-essential pkg-config libssl-dev
```

## 3.6 Target topology: Windows + WSL2 (SUPERSEDED for first build — reference only)

> 2026-09-19 (Kit): the first build is **Windows-only, no WSL2 Ubuntu**.
> This section is retained for reference; nothing new is built against it.

The production split Kit specified:

- **Windows (native):** PostgreSQL 16 + TimescaleDB + pgvector + pgvectorscale
  + pgAI. Runs on the Windows platform so the database can take advantage of
  Windows hardware tooling (Task Manager / Performance Monitor / services or
  Docker Desktop).
- **WSL2 Ubuntu:** everything else — Python/Flask app + gunicorn, Apache James,
  Apache HTTPD (TLS termination), pgrx/Rust toolchain, pgAI vectorizer worker, Ollama
  (local embeddings).

> [documented from vendor docs — not yet executed on a Windows host]
> **Decision (Kit 2026-09-19): Docker it is.** The Windows database layer runs
> in Docker Desktop via `timescale/timescaledb-ha:pg16` (§3.6.1). Kit's Docker
> Desktop version and container prefs to be collected when the Windows-side
> setup begins.

### 3.6.1 Database on Windows (Docker Desktop — recommended)

Docker Desktop for Windows plus the TimescaleDB HA image is Timescale's own
documented path for Windows. The image is *expected* to ship PostgreSQL 16
with TimescaleDB, pgvector, pgvectorscale, and pgAI extension files
preinstalled — **verify with `\dx` inside the running container before
relying on it** (extension inventory not yet confirmed; no Docker on the
reference host to check):

```powershell
docker pull timescale/timescaledb-ha:pg16
docker run -d --name timescaledb --restart unless-stopped `
  -p 5432:5432 `
  -v pgdata:/home/postgres/pgdata/data `
  -e POSTGRES_PASSWORD='<strong-password>' `
  timescale/timescaledb-ha:pg16
```

Create the database as UTF-8 — Windows PostgreSQL defaults to the WIN1252
locale, which breaks pgAI on non-ASCII API messages:

```sql
CREATE DATABASE forum ENCODING 'UTF8'
  LOCALE_PROVIDER icu ICU_LOCALE 'und' TEMPLATE template0;
\c forum
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale;
CREATE EXTENSION IF NOT EXISTS ai CASCADE;  -- CASCADE pulls in plpython3u + pgvector
```

Then, from WSL2, install pgAI's database objects (the `ai` schema catalog
tables/functions the vectorizer worker needs) — per the official pgai docs:

```bash
pip install "pgai[vectorizer-worker]"
python -m pgai install -d "postgresql://forum:<password>@$WIN_IP:5432/forum"
```

(`$WIN_IP` from §3.6.2. No Python needed on Windows itself.)

The `ai` extension components install from the WSL side (§3.6.3) via the
`pgai` pip package — no Python needed on Windows itself. Schema and seed data:
run `~/workspace/forum/schema.sql` from WSL against the Windows database.

### 3.6.2 WSL2 → Windows networking

From inside WSL2, the Windows host is reached at its vEthernet (WSL) address:

```bash
# Windows host IP as seen from WSL2
WIN_IP=$(ip route show | grep -i default | awk '{ print $3 }')
echo "$WIN_IP"
```

- The app connects with `FORUM_DB_HOST=$WIN_IP`, port 5432.
- Docker Desktop publishes the container port on the Windows host, so the
  database is reachable from WSL2 at `$WIN_IP:5432`.
- Firewall: Docker Desktop normally opens this path itself. If you run
  PostgreSQL natively on Windows instead, allow inbound TCP 5432 from the WSL
  subnet (elevated PowerShell):

  ```powershell
  New-NetFirewallRule -DisplayName "PostgreSQL from WSL" -Direction Inbound `
    -Protocol TCP -LocalPort 5432 -RemoteAddress 172.16.0.0/12 -Action Allow
  ```

  (WSL2's default subnet is 172.16.0.0/12 — confirm with `ip route` in WSL.)

### 3.6.3 App stack in WSL2 Ubuntu

Inside WSL2, follow the normal Linux build (§4–§7) with these changes:

1. Skip the local PostgreSQL/TimescaleDB install — the database lives on
   Windows. Install only the client tools in WSL: `postgresql-client`.
2. Point the app and tooling at Windows:
   ```bash
   export FORUM_DB_HOST="$WIN_IP"   # from §3.6.2
   export FORUM_DB_PORT=5432
   ```
3. pgAI extension + vectorizer worker from WSL (per the official pgai
   vectorizer quick start, Ollama variant):
   ```bash
   pip install "pgai[vectorizer-worker]"
   # one-time: install pgai's ai-schema objects into the forum database
   python -m pgai install -d "postgresql://forum:<password>@$WIN_IP:5432/forum"
   ```
   Create the vectorizer on the posts table (pin the exact call against the
   installed pgai release during bring-up):
   ```sql
   SELECT ai.create_vectorizer(
     'posts'::regclass,
     loading    => ai.loading_column('body'),
     embedding  => ai.embedding_ollama('nomic-embed-text', 768),
     destination => ai.destination_table('posts_body_embeddings')
   );
   ```
   Run the worker as a service in WSL2:
   ```bash
   export PGAI_VECTORIZER_WORKER_DB_URL="postgresql://forum:<password>@$WIN_IP:5432/forum"
   export OLLAMA_HOST="http://127.0.0.1:11434"   # Ollama runs in WSL2 (§4.3)
   pgai-vectorizer-worker --poll-interval 5s
   ```
   Semantic search then looks like:
   ```sql
   SELECT chunk, embedding <=> ai.ollama_embed('nomic-embed-text', '<query>', host => 'http://127.0.0.1:11434')
     FROM posts_body_embeddings ORDER BY 2 LIMIT 10;
   ```
4. Apache James, Apache HTTPD, gunicorn: as in §6–§7, unchanged. James binds to WSL
   interfaces; expose SMTP/IMAP ports through Windows as needed.

### 3.6.4 Backups

`pg_dump` from WSL against `$WIN_IP:5432` works like any remote Postgres.
Keep the Docker named volume (`pgdata`) backed up on the Windows side too.

## 4. PostgreSQL + TimescaleDB + pgAI [pending]

### 4.1 TimescaleDB repo

```bash
# Add TimescaleDB's apt repository (per https://docs.timescale.com/self-hosted/latest/install/)
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main" \
  | sudo tee /etc/apt/sources.list.d/timescaledb.list
wget -qO- https://packagecloud.io/timescale/timescaledb/gpgkey \
  | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/timescaledb.gpg
sudo apt-get update
sudo apt-get install -y timescaledb-2-postgresql-16
sudo timescaledb-tune --quiet --yes   # tunes shared_preload_libraries etc.
sudo systemctl restart postgresql
```

### 4.2 Database, user, extensions

```bash
# pgvector comes from the distro repos; pgvectorscale from the TimescaleDB repo
sudo apt-get install -y postgresql-16-pgvector timescaledb-2-postgresql-16
sudo apt-get install -y pgvectorscale-0.1-postgresql-16 2>/dev/null || \
  echo "pgvectorscale package name differs — see timescaledb repo listing"
```

```bash
sudo -u postgres psql <<'EOF'
CREATE USER forum WITH PASSWORD '<strong-password>';
CREATE DATABASE forum OWNER forum;
\c forum
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector (base vector type)
CREATE EXTENSION IF NOT EXISTS vectorscale;  -- pgvectorscale (DiskANN index, needs vector)
CREATE EXTENSION IF NOT EXISTS ai;           -- pgAI (see 4.3 if packaged separately)
EOF
```

Install order matters — canonical dependency chain (Kit 2026-09-19):

**pgrx (Rust toolchain) → TimescaleDB → pgvectorscale → pgAI**

i.e. `timescaledb` first, then `vector` → `vectorscale` (pgvectorscale needs
the base pgvector type), then `ai` CASCADE (pgAI needs pgvector +
plpython3u, both pulled in automatically). pgrx heads the chain as the
extension-building toolchain — not a runtime dependency of the others, but
installed first so custom extensions can be built against any of them.

### 4.3 pgAI

pgAI ships as a PostgreSQL extension (`ai`) plus a Python vectorizer worker.
On the all-Linux reference host, install per the pgAI release docs for PG 16,
then:

```sql
-- in the forum database, as the forum owner:
CREATE EXTENSION IF NOT EXISTS ai CASCADE;
-- CASCADE automatically installs plpython3u and pgvector
```

One-time install of pgAI's database objects (the `ai`-schema catalog
tables/functions the vectorizer worker needs):

```bash
pip install "pgai[vectorizer-worker]"
python -m pgai install -d "postgresql://forum:<password>@127.0.0.1:5432/forum"
```

Create the vectorizer on the posts table (pin the exact call against the
installed pgAI release during bring-up — the call below follows the official
pgai Ollama quick start):

```sql
SELECT ai.create_vectorizer(
  'posts'::regclass,
  loading     => ai.loading_column('body'),
  embedding   => ai.embedding_ollama('nomic-embed-text', 768),
  destination => ai.destination_table('posts_body_embeddings')
);
```

Run the worker as a daemon (systemd unit on the reference host; see §3.6.3
for the WSL2 split-topology variant):

```bash
export PGAI_VECTORIZER_WORKER_DB_URL="postgresql://forum:<password>@127.0.0.1:5432/forum"
export OLLAMA_HOST="http://127.0.0.1:11434"
pgai-vectorizer-worker --poll-interval 5s
```

Semantic search (replaces the keyword fallback in `/search`):

```sql
SELECT chunk,
       embedding <=> ai.ollama_embed('nomic-embed-text', '<query>',
                                     host => 'http://127.0.0.1:11434') AS distance
  FROM posts_body_embeddings
 ORDER BY distance
 LIMIT 10;
```

The vectorizer worker (embeds new/changed rows on a schedule) runs as a
separate daemon — see §6.3. Embedding provider: **Ollama (local)** — Kit's
choice. No external API key needed; embeddings never leave the box.

#### Ollama install (WSL2 Ubuntu, or the reference host)

```bash
curl -fsSL https://ollama.com/install.sh | sh
# serves on 127.0.0.1:11434; start on boot via the installed systemd unit
# (or `ollama serve` in the foreground for testing)
ollama pull nomic-embed-text   # 768-dim embeddings, ~274 MB
```

The vectorizer is configured with `ai.embedding_ollama('nomic-embed-text', 768)`
pointing at `OLLAMA_HOST` (default `http://127.0.0.1:11434`). In the WSL2 split
topology Ollama runs in WSL2 alongside the vectorizer worker — both reach the
Windows database at `$WIN_IP:5432` (§3.6).

For scale, the embedding column gets a pgvectorscale DiskANN index
(`USING diskann`), which keeps nearest-neighbor search fast well past what a
flat or IVFFlat index handles — this is what makes semantic search over a
large post table practical.

### 4.4 Schema

```bash
psql -h 127.0.0.1 -U forum -d forum -f ~/workspace/forum/schema.sql
```

Schema contents: `users`, `categories`, `threads`, `posts`, plus
`forum_events` (TimescaleDB hypertable for activity metrics) and the pgAI
vectorizer on `posts` for semantic search. Seed boards are inserted by the
script (re-runnable).

`pg_hba.conf`: keep the default (local peer / host scram-sha-256) and do
**not** expose 5432 beyond the app host. If the app runs on another machine,
add one `hostssl` line for the app host's IP with `scram-sha-256`.

## 5. pgrx toolchain (Rust → PostgreSQL extensions) [in progress]

For building custom PG extensions in Rust later. Not required at runtime.

```bash
# minimal profile keeps disk use down
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
  | sh -s -- -y --profile minimal --default-toolchain stable
source "$HOME/.cargo/env"
cargo install cargo-pgrx --locked
# [verified 2026-09-19 on reference host] installed cargo-pgrx 0.19.2
cargo pgrx init --pg16="$(which pg_config)"   # downloads PG source, compiles sys crate (~10-20 min)
```

Verify with the template extension:

```bash
cargo pgrx new forum_ext && cd forum_ext
cargo pgrx install --release   # installs into the local PostgreSQL
```

Then `CREATE EXTENSION forum_ext;` in psql.

## 6. Apache James 3.8.2 (mail server) [Docker: `apache/james:demo-3.8.2`, Kit's port remap; native-install notes below retained for history]

### 6.1 Install

The JPA/Guice distribution is the standalone server (default storage is
file/JPA-based; no external DB needed for basic operation):

```bash
cd /opt
sudo curl -sSL -o james.zip \
  https://dlcdn.apache.org/james/server/3.8.2/james-server-jpa-guice.zip
sudo unzip -q james.zip   # extracts to james-server-jpa-guice/ (no version suffix)
```

> Note: the 3.8.2 download directory also contains cassandra/distributed/spring
> variants — `james-server-jpa-guice.zip` is the one you want for a single box.

Out of the box this distribution stores everything in embedded Apache Derby
(`conf/james-database.properties` → `jdbc:derby:../var/store/derby`) — no
external database needed for basic operation. Run from the app directory:

```bash
cd /opt/james/james-server-jpa-guice
java -jar james-server-jpa-app.jar
```

Default binds: SMTP `0.0.0.0:25`, submission 587, IMAP 143/993, JMX CLI on
localhost:9999. On the reference build host (non-root dev), SMTP is moved to
a non-privileged port — see §8.

### 6.2 Configure domain + users

```bash
cd /opt/james/bin
# add your domain
./james-cli.sh -h 127.0.0.1 -p 9999 AddDomain forum.example.com
# service account the forum app uses to send mail
./james-cli.sh -h 127.0.0.1 -p 9999 AddUser notify@forum.example.com '<password>'
```

(Adjust `conf/` for non-default ports/hostnames; defaults: SMTP 25, submission
587, IMAP 143/993, JMX CLI 9999 on localhost.)

### 6.3 Run as a service

Create `/etc/systemd/system/james.service`:

```ini
[Unit]
Description=Apache James mail server
After=network.target postgresql.service

[Service]
User=james
WorkingDirectory=/opt/james
ExecStart=/opt/james/bin/james start
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo useradd -r -d /opt/james james
sudo chown -R james:james /opt/james
sudo systemctl daemon-reload && sudo systemctl enable --now james
```

### 6.4 DNS for real mail delivery

- `MX` record → James host; `A` record for the MX hostname.
- SPF `TXT`: `v=spf1 mx -all`.
- Reverse DNS (PTR) on the sending IP — many receivers require it.

## 7. Forum app (Python/Flask) [pending]

```bash
cd ~/workspace/forum
python3 -m venv .venv && source .venv/bin/activate
pip install flask psycopg[binary] gunicorn
```

Configuration is via environment variables (see `config.py`):

| Variable | Purpose | Example |
|---|---|---|
| `FORUM_DB_HOST/PORT/NAME/USER/PASS` | PostgreSQL | `127.0.0.1 / 5432 / forum / forum / …` |
| `FORUM_SMTP_HOST/PORT/USER/PASS` | James SMTP | `127.0.0.1 / 587 / notify@forum.example.com / …` |
| `FORUM_SECRET_KEY` | Flask sessions | random 32+ bytes |
| `OLLAMA_HOST` | embeddings for pgAI (optional) | `http://127.0.0.1:11434` |

systemd unit `/etc/systemd/system/forum.service`:

```ini
[Unit]
Description=Forum app (gunicorn)
After=network.target postgresql.service james.service

[Service]
User=forum
WorkingDirectory=/home/forum/forum
Environment="FORUM_DB_PASS=<strong-password>"
Environment="FORUM_SECRET_KEY=<random>"
ExecStart=/home/forum/forum/.venv/bin/gunicorn -w 3 -b 127.0.0.1:8000 app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Put Apache HTTPD in front for TLS (Let's Encrypt) and proxy to `127.0.0.1:8000`.

## 8. Reference build-host status (this machine)

| Item | Status |
|---|---|
| Ubuntu 24.04, Python 3.12 | present |
| `apt-get update` | [verified] completed 2026-09-19 (exit 0; some repo fetches failed through proxy, old indexes used) |
| Base packages | [verified] installed 2026-09-19, all 9 confirmed via `dpkg-query`: `zstd` 1.5.5, `default-jre-headless` (OpenJDK 21.0.12), `postgresql-16` 16.15, `postgresql-contrib`, `postgresql-server-dev-16`, `build-essential`, `pkg-config`, `libssl-dev`, `libclang-dev` |
| Rust toolchain (rustup, minimal) | [verified] installed: rustc/cargo 1.98.1 |
| cargo-pgrx | [verified] 0.19.2 installed 2026-09-19 (`cargo install cargo-pgrx --locked`, exit 0) |
| Python venv (flask, psycopg[binary], gunicorn) | installing in background |
| Apache James 3.8.2 zip | [verified] downloaded (91 MB) + extracted; default store is embedded Derby |
| Apache James 3.8.2 server | [verified] running 2026-09-19 on reference host: SMTP banner `220` on 2525; domain `forum.local` + user `notify@forum.local` created via WebAdmin (port 8000); SMTP→IMAP delivery round-trip verified |
| Java runtime | [verified] OpenJDK 21.0.12 (default-jre-headless) installed 2026-09-19 |
| PostgreSQL / TimescaleDB / pgAI | local PostgreSQL 16.15 + server dev headers installed on reference host 2026-09-19 (dev/test only; production DB remains the `timescale/timescaledb-ha:pg16` Docker image on Windows) — pgAI procedure documented from the official pgai Ollama quick start: `timescale/timescaledb-ha:pg16` image, `CREATE EXTENSION ai CASCADE`, `python -m pgai install`, `ai.create_vectorizer` with `ai.embedding_ollama('nomic-embed-text', 768)` |
| pgrx init/compile/test | [verified] `cargo pgrx init --pg16` done; template extension `cargo pgrx test pg16` PASSES (1 passed, 0 failed, exit 0) — via reference-host-only fakeuid LD_PRELOAD shim, see BUGLOG 2026-09-19 |
| Flask app rewrite (from PHP) | [verified] written: app.py + 9 Jinja2 templates + extended schema (email on users, forum_events hypertable, pgAI placeholder); PHP preserved under forum/legacy-php/ |
| Flask app end-to-end (reference host) | [verified] 2026-09-19: venv rebuilt (Flask 3.1.3), `py_compile` clean, test-client flow register→login→new thread→reply→search→metrics all pass against local PG16 (Timescale statements skipped — no timescaledb extension locally); welcome email sent by the app arrived in the James IMAP inbox |
| Metrics graceful degradation | [verified] bug found + fixed 2026-09-19: failed `forum_daily` query left the per-request txn aborted, so the base template's `current_user()` 500'd for logged-in users — added `db().rollback()` in the metrics handler |
| pgvectorscale | added to stack + README §4.2/§4.3/§9 (install order vector → vectorscale → ai) |
| WSL split topology (Windows DB + WSL2 app) | [superseded 2026-09-19] First build is Windows-only per Kit — no WSL2 Ubuntu. §3.6 retained for reference only; U-9 venv rule now Windows-native only |
| Ollama (embedding provider — Kit's choice) | [in progress] 0.34.2 binary verified (`ollama --version`); server running on 11434; official installer re-downloading tarball in background (slow proxy); pulling `nomic-embed-text` in background |
| Full-stack installer (Windows-only layout) | queued — build after the Windows-only stack passes acceptance twice (Kit 2026-09-19) |
| End-to-end test (register → post → email → search) | not started |

Build-host deviations from production defaults (dev only): James SMTP will run
on a non-privileged port; app served directly by Flask dev server for testing.

## 9. Verification checklist (run before calling it done)

- [ ] `psql -h 127.0.0.1 -U forum -d forum -c '\dx'` shows `timescaledb`, `vector`, `vectorscale`, `ai`
- [ ] `SELECT * FROM timescaledb_information.hypertables;` lists `forum_events`
- [ ] pgAI vectorizer worker running; embedding column has a DiskANN index; semantic search returns a relevant post
- [x] `cargo pgrx test` passes on the template extension (2026-09-19, with fakeuid shim + USER=lampybuild; shim is reference-host-only)
- [ ] James: `telnet 127.0.0.1 25` banners; send test mail; IMAP shows it delivered
- [ ] Forum: register → new thread → reply → reply-notification email arrives
- [ ] `/metrics` page shows TimescaleDB-backed daily counts
- [ ] No PostgreSQL/James admin ports reachable from the internet (nmap from outside)
- [ ] Backups: `pg_basebackup`/WAL archiving configured and restore-tested

## 10. Maintenance

- **PostgreSQL**: nightly `pg_basebackup` + WAL archiving; test restores quarterly.
- **James**: mail store lives under `/opt/james/var` — include in backups.
- **Updates**: `apt-get upgrade` for PG/TimescaleDB; James by replacing `/opt/james`
  (keep `conf/`); `pip install -U` in the venv after testing.
- **Logs**: `journalctl -u forum -u james -u postgresql`.
