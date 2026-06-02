"""
Shared pytest fixtures for narrative-architect.

This conftest provides fixtures available to ALL test files in the project.
Domain-specific fixtures should go in tests/domain/conftest.py.
Application-specific fixtures should go in tests/application/conftest.py, etc.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

# --- Windows compat: monkey-patch shlex.split to handle backslash paths ---
# On Windows, shlex.split() in POSIX mode treats \ as escape character,
# which breaks paths like C:\Users\... in f-string CLI arguments.
# We replace \ with / before splitting (Windows Python accepts forward slashes).
# Also force UTF-8 for subprocess stdout (cp1252 can't encode box-drawing chars).
if os.name == "nt":
    _original_shlex_split = shlex.split

    def _windows_safe_split(s: str, **kwargs: Any) -> list[str]:
        return _original_shlex_split(s.replace("\\", "/"), **kwargs)

    shlex.split = _windows_safe_split
    os.environ["PYTHONUTF8"] = "1"

    # subprocess.run(text=True) decodes with cp1252 on Windows, but the child
    # writes UTF-8 (PYTHONUTF8=1). Default encoding='utf-8' when text=True.
    import subprocess
    _original_run = subprocess.run

    def _utf8_run(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("text") and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
        return _original_run(*args, **kwargs)

    subprocess.run = _utf8_run
# --- end Windows compat ---

from packages.domain.config import AppConfig, LoggingConfig, reset_settings


@pytest.fixture(autouse=True)
def _reset_settings() -> Generator[None, Any, None]:
    """Reset settings singleton before and after each test.

    Ensures test isolation: no test leaks settings state to another.
    """
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def app_config() -> AppConfig:
    """Return a default AppConfig for testing.

    Override with parametrized fixtures or by modifying the returned config
    using dataclasses.replace().
    """
    return AppConfig()


@pytest.fixture
def debug_config() -> AppConfig:
    """Return an AppConfig with debug mode enabled."""
    return AppConfig(debug=True, logging=LoggingConfig(level="DEBUG"))


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Return a temporary directory suitable for use as data_dir.

    Uses pytest's built-in tmp_path fixture for automatic cleanup.
    """
    data_dir = tmp_path / "narrative-architect-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def app_config_with_temp_dir(temp_data_dir: Path) -> AppConfig:
    """Return an AppConfig pointed at a temporary data directory."""
    return AppConfig(data_dir=str(temp_data_dir))


@pytest.fixture
def test_logger_name() -> str:
    """Return a unique logger name for testing.

    Used by logging tests to avoid cross-test pollution.
    """
    import uuid
    return f"test-logger-{uuid.uuid4().hex[:8]}"
