"""FileOps: move, rewrite, copy, mkdir, remove, list, read.

Every operation is performed by a generated shell script (see shell.py) —
Python never touches the files directly. All paths must resolve inside
ALLOWED_ROOTS; anything outside is refused before any script is written.
remove() moves to trash; it never deletes.
"""
from __future__ import annotations
import base64
import datetime
import os
import shlex

from . import config
from .shell import ScriptResult, ScriptWriter


class OutsideRootError(ValueError):
    pass


class FileOps:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def _resolve(self, path: str) -> str:
        ap = os.path.abspath(os.path.expanduser(path))
        if not any(ap == r or ap.startswith(r + os.sep) for r in config.ALLOWED_ROOTS):
            raise OutsideRootError(f"refusing to touch {ap}: outside allowed roots")
        return ap

    def _writer(self, purpose: str) -> ScriptWriter:
        return ScriptWriter(purpose=purpose, dry_run=self.dry_run)

    def mkdir(self, path: str) -> ScriptResult:
        path = self._resolve(path)
        return self._writer("mkdir").add("mkdir", "-p", path).run()

    def move(self, src: str, dst: str) -> ScriptResult:
        src, dst = self._resolve(src), self._resolve(dst)
        w = self._writer("move")
        w.add("mkdir", "-p", os.path.dirname(dst))
        w.add("mv", "--", src, dst)
        return w.run()

    def copy(self, src: str, dst: str) -> ScriptResult:
        src, dst = self._resolve(src), self._resolve(dst)
        w = self._writer("copy")
        w.add("mkdir", "-p", os.path.dirname(dst))
        w.add("cp", "-a", "--", src, dst)
        return w.run()

    def rewrite(self, path: str, content: str) -> ScriptResult:
        """Replace (or create) a file with content.

        The content travels as base64 inside a quoted heredoc, so any bytes
        — quotes, backslashes, newlines — survive intact.
        """
        path = self._resolve(path)
        blob = base64.b64encode(content.encode()).decode()
        w = self._writer("rewrite")
        w.add("mkdir", "-p", os.path.dirname(path))
        w.add(f"base64 -d > {shlex.quote(path)} << 'LAMPY_EOF'\n{blob}\nLAMPY_EOF")
        return w.run()

    def remove(self, path: str) -> ScriptResult:
        """Move to the control-plane trash. Never deletes."""
        path = self._resolve(path)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(config.TRASH_DIR, f"{stamp}-{os.path.basename(path)}")
        w = self._writer("remove")
        w.add("mkdir", "-p", config.TRASH_DIR)
        w.add("mv", "--", path, dest)
        return w.run()

    def list_dir(self, path: str) -> ScriptResult:
        path = self._resolve(path)
        return self._writer("list").add("ls", "-la", "--", path).run()

    def read_file(self, path: str) -> ScriptResult:
        path = self._resolve(path)
        return self._writer("read").add("cat", "--", path).run()
