"""Cross-platform test helpers for CLI subprocess invocation.

The key problem: shlex.split() in POSIX mode treats backslash as escape,
which breaks Windows paths like C:\\Users\\... in f-string command args.
"""
from __future__ import annotations

import os
import shlex


def _split_cli(args: str) -> list[str]:
    """Split CLI args string; Windows-safe (backslash paths).

    On Windows, converts backslashes to forward slashes before splitting.
    Windows Python accepts forward slashes in paths, so this is safe.
    """
    if os.name == "nt":
        return shlex.split(args.replace("\\", "/"))
    return shlex.split(args)
