"""Central tracing utilities for DesktopHostPySide."""

import functools
import sys
from datetime import datetime


def _apptrace(message: str) -> None:
    """Print a trace message to stdout with APPTRACE prefix and timestamp."""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # milliseconds only
    print(f"APPTRACE {ts} {message}", flush=True)


def traced(action_name: str):
    """Decorator that logs function entry with action name and first few args."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            parts = [action_name]
            for i, a in enumerate(args):
                if i >= 3:
                    break
                parts.append(str(a)[:100])
            _apptrace("ENTER " + " ".join(parts))
            return func(*args, **kwargs)

        return wrapper

    return decorator
