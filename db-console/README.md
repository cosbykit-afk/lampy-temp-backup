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
R_THEORY_DIR=~/workspace/r-theory-rewrite \
FORUM_DB_HOST=127.0.0.1 FORUM_DB_PORT=5432 \
~/workspace/forum/venv/bin/python ~/workspace/forum-stack/db-console/app.py
```

Serves on **127.0.0.1:5001**. Binds localhost only — add authentication
before exposing it anywhere (the future database interface must sit behind
the Musey admin login at minimum).

## Status

Prototype. Not yet exercised against the live database (none exists yet on
this VM). Page scripts are intentionally stripped in v1; live Desmos embeds
will need a revisit if the console ever renders book17–19 interactively.
