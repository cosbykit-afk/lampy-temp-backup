# Lampy Windows path-stability design

DRAFT 2026-09-19 — Kit's directive: "Windows only, no WSL/Ubuntu, first build."
Not yet executed on a Windows host.

## The problem

Three components have hardcoded data paths:

- **Ollama** — model store defaults to `%USERPROFILE%\.ollama`.
- **PostgreSQL** — `PGDATA`; move it and the server won't start.
- **TimescaleDB** — the extension is linked into the Postgres install
  (`lib`/`share` dirs); move the install and `CREATE EXTENSION timescaledb`
  breaks — "the link between timescale and database".

Move any folder and the relative positions change, and those links break.
Separately, Google Drive's virtual mount litters junk folders from
unmounted/disconnected drives, and database files must never live under
Drive sync anyway (sync + live database files = corruption).

## The solution: PGDATA anchor + junction armor

1. **The PGDATA folder is the anchor** (Kit 2026-09-19). It is chosen first
   (`bootstrap-paths.ps1 -PgData`), and every other program's data directory
   is positioned relative to it — siblings under the anchor's parent tree.
   The marker file (`lampy-anchor.marker`) records the anchor path, so a
   previous install is found by its anchor, never by a parallel junk chain.

2. **NTFS junctions at the hardcoded locations.** The data lives in the
   anchor's tree; a junction (`mklink /J`) sits at the path the component
   insists on. The app always sees its fixed path; the bytes can be anywhere.
   Moving the install = re-pointing the junctions — one command, no
   per-app reconfiguration. This is the "command line magic".

3. **One chain per install, outside Drive.** The bootstrap refuses anchors
   inside Google Drive's virtual mount or synced folders (database files
   under sync = corruption, plus the junk-folder clutter).

## Fixed layout (never renamed between versions)

The tree is derived from the anchor — nothing is positioned absolutely
except PGDATA itself:

```
C:\Lampy\                  <- install home (anchor's grandparent)
  bin\              launcher scripts
  compose\          docker-compose.yml + .env (PGDATA_DIR=..., LAMPY_DATA=...)
  conf\            httpd.conf, James overrides
  htdocs\          static web root
  logs\
  data\                    <- the anchor's tree (anchor's parent)
    pgdata\                <- THE ANCHOR (chosen first, recorded)
    ollama\                <- siblings: relative positions extend
    james\                    off the anchor's tree
    lampy-anchor.marker
```

`docker-compose.yml` uses `${PGDATA_DIR}` for the db bind mount and
`${LAMPY_DATA}` (the anchor's parent) for the siblings' bind mounts.

## Docker carries the TimescaleDB link

PG + TimescaleDB run in the `timescale/timescaledb-ha:pg16` image — the
extension↔database link lives *inside the immutable image* and cannot
break from host moves. The only host-side path is the PGDATA bind mount,
which is the anchor itself.

## Junctions planted by the bootstrap

| Hardcoded path (link)              | Target (real data)                        |
|------------------------------------|-------------------------------------------|
| `%USERPROFILE%\.ollama`            | `<anchor-parent>\ollama` (sibling of PGDATA)|

(`OLLAMA_MODELS` is also set as a user env var; the junction is
belt-and-braces for anything that ignores the variable. A native-Postgres
fallback junction would go here only if we ever go native — the container
path needs none.)

## Moving an install

```
bootstrap-paths.ps1 -MoveFrom C:\Lampy\data\pgdata -PgData D:\Lampy\data\pgdata
```

robocopies `pgdata ollama james`, re-points the junctions, rewrites
`compose\.env` with the new anchor. Container-side paths are unchanged,
so the stack comes up identical.

## Drive-letter-proofing (optional)

If the data should live on another volume but the path must never change,
mount the volume at `%LAMPY_ROOT%\data` (Disk Management → Change Drive
Letter and Paths → "Mount in the following empty NTFS folder"). Drive
letters can then change freely underneath it.
