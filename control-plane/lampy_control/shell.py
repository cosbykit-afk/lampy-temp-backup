"""ScriptWriter: compose shell scripts, write them to disk, execute, log.

The control plane runs with administrative privileges — root on this host.
That is exactly why every command goes through here: nothing executes
without first being written to a script file (the audit trail) and logged
afterward. Privilege without a paper trail is how systems get destroyed;
this module is the paper trail.
"""
from __future__ import annotations
import datetime
import os
import shlex
import subprocess
from dataclasses import dataclass

from . import config


@dataclass
class ScriptResult:
    script_path: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class ScriptWriter:
    """Accumulate shell commands, write the .sh file, run it, log the result."""

    def __init__(self, purpose: str = "ops", dry_run: bool = False):
        self.purpose = purpose
        self.dry_run = dry_run
        self.commands: list[str] = []
        os.makedirs(config.SCRIPTS_DIR, exist_ok=True)
        os.makedirs(config.LOGS_DIR, exist_ok=True)

    def add(self, *args) -> "ScriptWriter":
        """One command: either a verbatim string, or argv parts (auto-quoted)."""
        if len(args) == 1 and isinstance(args[0], str):
            self.commands.append(args[0])
        else:
            self.commands.append(shlex.join(str(a) for a in args))
        return self

    def script_text(self) -> str:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "#!/bin/bash",
            f"# lampy_control — {self.purpose} — {stamp}",
            "# runs with administrative privileges; every command below is the audit trail",
            "set -euo pipefail",
            "",
        ]
        lines.extend(self.commands)
        return "\n".join(lines) + "\n"

    def write(self) -> str:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        n = 0
        while True:
            path = os.path.join(config.SCRIPTS_DIR, f"{stamp}-{self.purpose}-{n}.sh")
            if not os.path.exists(path):
                break
            n += 1
        with open(path, "w") as f:
            f.write(self.script_text())
        os.chmod(path, 0o755)
        return path

    def run(self) -> ScriptResult:
        path = self.write()
        if self.dry_run:
            return ScriptResult(path, 0, "", "dry-run: not executed")
        proc = subprocess.run(["bash", path], capture_output=True, text=True)
        result = ScriptResult(path, proc.returncode, proc.stdout, proc.stderr)
        self._log(result)
        return result

    def _log(self, result: ScriptResult) -> None:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(config.LOGS_DIR, "exec.log"), "a") as f:
            f.write(f"[{stamp}] {result.script_path} exit={result.returncode}\n")
            if result.stdout:
                f.write(f"  stdout: {result.stdout[:2000]}\n")
            if result.stderr:
                f.write(f"  stderr: {result.stderr[:2000]}\n")
