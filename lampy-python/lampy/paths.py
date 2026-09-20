"""Canonical Lampy filesystem layout.

The Windows target anchors everything at ``C:\\Lampy``. On this Linux dev VM
the same logical tree is mirrored under a configurable root (default
``~/lampy-dev``) so the same code can be developed here and deployed there.

Nothing here touches the disk; it only computes paths.
"""
from __future__ import annotations

import os
import sys

#: Windows anchor — the one true root on the target machine.
WINDOWS_ROOT = r"C:\Lampy"

#: Logical subdirectories under the anchor, shared by both platforms.
SUBDIRS = {
    "data": "data",            # persistent volumes live here
    "pgdata": r"data\pgdata",  # PostgreSQL/TimescaleDB data dir
    "ollama": r"data\ollama",  # OLLAMA_MODELS on Windows
    "james": r"data\james",    # James mail store (provisional)
    "logs": "logs",
    "config": "config",
    "xapp": "xapp",            # the Python forum app
}


def windows_path(*parts: str) -> str:
    """Join *parts* under the Windows anchor with backslashes.

    Always uses ``\\`` regardless of host OS, since the result is a
    Windows path even when generated on this Linux dev VM.
    """
    return "\\".join([WINDOWS_ROOT, *parts])


def dev_root() -> str:
    """POSIX mirror root for development on Linux.

    Overridable with the ``LAMPY_DEV_ROOT`` environment variable.
    """
    return os.environ.get("LAMPY_DEV_ROOT",
                          os.path.expanduser("~/lampy-dev"))


def dev_path(logical: str) -> str:
    """Map a logical subdir name (see :data:`SUBDIRS`) to the dev-VM path."""
    rel = SUBDIRS[logical].replace("\\", os.sep)
    return os.path.join(dev_root(), rel)


def is_windows_target() -> bool:
    """True when actually running on the Windows target."""
    return sys.platform == "win32"
