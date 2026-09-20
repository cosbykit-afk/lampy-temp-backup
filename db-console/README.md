# Lampy console (prototype)

A DigitalOcean-docs-style web UI for the Lampy stack, built 2026-09-20 at
Kit's direction.

## What it is

- **Docs section** — the R Theory rewrite site used as mock content,
  rendered *dynamically*: at startup the app walks the rewrite tree and
  extracts each page's title, headings, body HTML, and embedded CSS. The
  CSS is selector-scoped to the article column so it can't leak into the
  console chrome; the injected site nav is replaced by the console's own
  side panel; page scripts are dropped (PNG fallbacks remain); relative
  links are rewritten to console routes or the local static mount.
- **Layout** — top bar with a Google-style search box, left side-panel
  navigation (volumes → books, tutorial-series style), right "On this page"
  table of contents built from each page's h2/h3 headings.
- **Search** — server-side, over titles + headings + page text, with
  highlighted snippets. No external search service.
- **Database section** — probes `FORUM_DB_HOST:FORUM_DB_PORT` and shows a
  *pending* panel until the database is provisioned at Windows bring-up
  (~Sept 23, Docker Desktop + `timescale/timescaledb-ha:pg16` +
  `forum/schema.sql`). When the port answers it flips to *reachable*;
  the table browser / row counts / read-only query runner land here next.

## Run

```bash
CONSOLE_DEV=1 R_THEORY_DIR=~/workspace/r-theory-rewrite \
FORUM_DB_HOST=127.0.0.1 FORUM_DB_PORT=5432 \
~/workspace/forum/venv/bin/python ~/workspace/forum-stack/db-console/app.py
```

Serves on **127.0.0.1:5001**. Binds localhost only.

## Authentication & hardening

The console has a logon module (`auth.py`): credentials are verified
against the forum database's `users` table (Werkzeug hashes, created by
the forum's `/register`), and the signed session keeps only the user id,
username, and `is_admin` flag. The moderation queue and Musey review
endpoint require an admin account.

`security.py` hardens it further:

- **Secret key**: the app *refuses to start* without `FORUM_SECRET_KEY`
  (exit 1), so a hardcoded fallback can never sign sessions in
  production. `CONSOLE_DEV=1` allows local runs with a random per-process
  key. The real secret comes from the Secure Vault at deploy.
- **Session cookies**: `HttpOnly`, `SameSite=Lax`, and `Secure` in
  production (off in dev, which serves plain HTTP on localhost).
- **CSRF**: per-session token on the login form and on the JSON
  moderation endpoint (via the `X-CSRF-Token` header).
- **Rate limiting**: 5 failed logins per IP per 5 minutes → 15-minute
  lockout (429 + `Retry-After`); a successful login resets the counter.
  In-memory — a multi-worker deployment should use a shared store.
- **Logout is POST-only** (a GET link could be triggered by a
  third-party page); `next=` redirects are restricted to relative paths.
- Failed logins return 401; an unreachable account database returns 503
  with an honest message instead of failing open.

Tests: `tests/test_auth_hardening.py` — 18 tests, no live database
needed (the DB-down paths are exercised for real against the refused
connection).

## Status

Prototype. Not yet exercised against the live database (none exists yet on
this VM). Page scripts are intentionally stripped in v1; live Desmos embeds
will need a revisit if the console ever renders book17–19 interactively.
