"""lampy_control — the start of Lampy's AI-operated control plane.

The model: Python never touches files directly. Every operation is composed
as shell commands, written out as a real .sh script (the audit trail),
then executed. What ran is always on disk in scripts/ and logs/.
"""
from .shell import ScriptWriter, ScriptResult
from .files import FileOps

__all__ = ["ScriptWriter", "ScriptResult", "FileOps"]
