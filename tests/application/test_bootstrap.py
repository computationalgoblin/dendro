"""
Test suite for application bootstrap module.

Covers:
- Successful initialization with default configuration
- Successful initialization with overrides
- Result type correctness (Ok vs Error)
- Error handling on simulated failures (invalid data directory)
- Smoke-level verification that the module is importable
"""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.application.bootstrap import AppContext, initialize
from packages.domain.result import Error, Ok, is_error, is_ok, unwrap, unwrap_error

# ---------------------------------------------------------------------------
# Smoke tests — module importable, types exist
# ---------------------------------------------------------------------------


class TestBootstrapSmoke:
    """Minimal smoke tests verifying module structure."""

    def test_module_importable(self) -> None:
        """The bootstrap module can be imported without errors."""
        from packages.application import bootstrap  # noqa: F811
        assert bootstrap.initialize is not None

    def test_app_context_type(self) -> None:
        """AppContext dataclass exists with expected fields."""
        from packages.domain.config import AppConfig

        ctx = AppContext.__dataclass_fields__
        assert "config" in ctx
        assert "logger" in ctx
        assert "project_store" in ctx

        # Ensure we can create an AppContext (logger is required)
        import logging
        ctx = AppContext(config=AppConfig(), logger=logging.getLogger("test"))
        assert ctx.data_dir == Path(ctx.config.data_dir)

    def test_data_dir_property(self) -> None:
        """AppContext.data_dir returns a Path pointing to config.data_dir."""
        from packages.domain.config import AppConfig

        import logging
        ctx = AppContext(config=AppConfig(data_dir="/tmp/test-na"), logger=logging.getLogger("test"))
        assert ctx.data_dir == Path("/tmp/test-na")


# ---------------------------------------------------------------------------
# initialize() — success cases
# ---------------------------------------------------------------------------


class TestInitializeSuccess:
    """Happy-path tests for bootstrap initialization."""

    def test_returns_ok_with_default_config(self) -> None:
        """initialize() returns Ok(AppContext) with no overrides."""
        result = initialize()
        assert is_ok(result), f"Expected Ok, got {result}"
        ctx = unwrap(result)
        assert isinstance(ctx, AppContext)
        assert ctx.config.app_name == "narrative-architect"
        assert ctx.project_store is not None

    def test_returns_ok_with_overrides(self) -> None:
        """initialize() accepts config overrides."""
        result = initialize({"app_name": "test-override", "debug": True})
        assert is_ok(result), f"Expected Ok, got {result}"
        ctx = unwrap(result)
        assert ctx.config.app_name == "test-override"
        assert ctx.config.debug is True

    def test_logger_is_configured(self) -> None:
        """Logger returned in context is functional (can log without error)."""
        result = initialize()
        assert is_ok(result)
        ctx = unwrap(result)
        # Logging should not raise
        ctx.logger.info("Test log message from bootstrap test")
        ctx.logger.debug("Debug test message")

    def test_project_store_is_ready(self) -> None:
        """ProjectStore is instantiated and usable."""
        result = initialize()
        assert is_ok(result)
        ctx = unwrap(result)
        from packages.persistence.store import ProjectStore
        assert isinstance(ctx.project_store, ProjectStore)
        # ProjectStore has the expected methods
        assert hasattr(ctx.project_store, "save")
        assert hasattr(ctx.project_store, "load")
        assert hasattr(ctx.project_store, "exists")

    def test_initialize_is_idempotent(self) -> None:
        """Calling initialize() multiple times does not crash."""
        r1 = initialize()
        r2 = initialize()
        r3 = initialize()
        assert is_ok(r1)
        assert is_ok(r2)
        assert is_ok(r3)

    def test_data_dir_is_created(self, tmp_path: Path) -> None:
        """If data_dir doesn't exist, it gets created."""
        custom_dir = tmp_path / "should-be-created"
        assert not custom_dir.exists()
        result = initialize({"data_dir": str(custom_dir)})
        assert is_ok(result), f"Expected Ok, got {result}"
        assert custom_dir.is_dir()


# ---------------------------------------------------------------------------
# initialize() — error cases
# ---------------------------------------------------------------------------


class TestInitializeErrors:
    """Error-path tests for bootstrap initialization."""

    def test_invalid_data_dir_returns_error(self) -> None:
        """When data_dir is an invalid path (e.g., a file), Error is returned."""
        import tempfile
        with tempfile.NamedTemporaryFile() as f:
            result = initialize({"data_dir": f.name})
        assert is_error(result), f"Expected Error, got {result}"
        error_msg = unwrap_error(result)
        assert isinstance(error_msg, str)
        assert len(error_msg) > 0

    def test_error_result_contains_meaningful_message(self) -> None:
        """Error messages should be descriptive, not empty."""
        import tempfile
        with tempfile.NamedTemporaryFile() as f:
            result = initialize({"data_dir": f.name})
        assert is_error(result)
        msg = unwrap_error(result)
        # Message should reference the problematic path or the operation
        assert "Cannot create data directory" in msg or "File exists" in msg

    def test_result_type_is_union(self) -> None:
        """initialize() always returns Ok | Error, never raw value."""
        result = initialize()
        assert isinstance(result, (Ok, Error))

    def test_initialize_error_on_file_as_datadir(self) -> None:
        """When data_dir is an existing file (not a dir), error is returned."""
        import tempfile
        with tempfile.NamedTemporaryFile() as f:
            result = initialize({"data_dir": f.name})
        assert is_error(result), f"Expected Error, got {result}"
        msg = unwrap_error(result)
        assert len(msg) > 0
        assert "Cannot create data directory" in msg


# ---------------------------------------------------------------------------
# Docker smoke — verifiable as 'python -m pytest tests/application/'
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """Allow running this file directly as a smoke check in Docker."""
    import sys
    result = initialize()
    if is_ok(result):
        ctx = unwrap(result)
        print(f"OK: Bootstrap initialized ({ctx.config.app_name} v{ctx.config.app_version})")
        sys.exit(0)
    else:
        print(f"FAIL: {unwrap_error(result)}")
        sys.exit(1)
