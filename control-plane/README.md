# Lampy control plane — core (begun 2026-09-19)

The AI-operated control plane, down to the root. Python never touches files
directly: every operation is composed as shell commands, written out as a
real `.sh` script, then executed. The script files are the audit trail.

## Layout

- `lampy_control/` — the package
  - `shell.py` — `ScriptWriter`: accumulate commands → write timestamped
    `.sh` → execute → log. `dry_run=True` writes without executing.
  - `files.py` — `FileOps`: `mkdir`, `move`, `copy`, `rewrite`, `remove`,
    `list_dir`, `read_file`. All run through generated scripts.
  - `config.py` — allowed roots, script/log/trash dirs.
- `scripts/` — every generated script, kept. This is the audit trail.
- `logs/exec.log` — every execution with exit code and output.
- `trash/` — `remove()` moves here; nothing is ever deleted.
- `demo.py` — smoke test (also the usage example).

## Privilege model

Runs with administrative privileges (root on the reference host; admin on
Windows/WSL2 prod, per the Lampy guide). Privilege is why the audit trail
exists: no command runs without being written to `scripts/` first and
logged in `logs/exec.log` afterward.

## Safety rails (deliberate, not optional)

1. **Root-scoped**: any path resolving outside `ALLOWED_ROOTS`
   (`~/workspace/forum-stack`) raises `OutsideRootError` before any script
   is written.
2. **Trash, not delete**: `remove()` moves to `trash/` with a timestamp.
3. **Dry run**: `FileOps(dry_run=True)` writes the script but does not run it.
4. **Passwords**: never stored in scripts, logs, or config — deploy-time only.

## Usage

```python
from lampy_control import FileOps
ops = FileOps()
ops.rewrite("/home/hatch/workspace/forum-stack/control-plane/notes.txt", "hello")
ops.move("a.txt", "archive/a.txt")
```

## Status

Core file-ops begun 2026-09-19 at Kit's direction (`demo.py` passes).
Not yet: service control (httpd/postgres/ollama), Docker orchestration,
pgAI vectorizer calls, installer logic. Those come after component
verification, per WORKFLOW.md.
