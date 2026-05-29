"""Tests for structured logging module."""

import logging
import tempfile
from pathlib import Path

from packages.domain.config import AppConfig, LoggingConfig
from packages.domain.logging import (
    configure_logging,
    get_logger,
    shutdown_logging,
)


class TestGetLogger:
    """Test logger creation and configuration."""

    def test_get_logger_basic(self):
        config = AppConfig(logging=LoggingConfig(level="DEBUG"))
        logger = get_logger("test_basic", config)
        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.DEBUG
        assert logger.name == "test_basic"

    def test_get_logger_default_level(self):
        config = AppConfig()
        logger = get_logger("test_default", config)
        assert logger.level == logging.INFO

    def test_get_logger_caches(self):
        config = AppConfig()
        logger1 = get_logger("test_cache", config)
        logger2 = get_logger("test_cache", config)
        assert logger1 is logger2

    def test_get_logger_different_names(self):
        config = AppConfig()
        logger1 = get_logger("test_diff1", config)
        logger2 = get_logger("test_diff2", config)
        assert logger1 is not logger2

    def test_logger_writes_to_stderr(self, capsys):
        config = AppConfig(logging=LoggingConfig(level="DEBUG"))
        logger = get_logger("test_stream", config)
        logger.info("hello from test")
        stderr = capsys.readouterr().err
        assert "hello from test" in stderr
        assert "test_stream" in stderr

    def test_logger_writes_to_file(self):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            log_path = f.name

        try:
            config = AppConfig(logging=LoggingConfig(level="DEBUG", output_file=log_path))
            logger = get_logger("test_file", config)
            logger.info("file log message")
            shutdown_logging()

            content = Path(log_path).read_text()
            assert "file log message" in content
            assert "test_file" in content
        finally:
            Path(log_path).unlink(missing_ok=True)


class TestLoggerLevels:
    """Test all log levels work."""

    def test_debug_level(self, capsys):
        config = AppConfig(logging=LoggingConfig(level="DEBUG"))
        logger = get_logger("test_levels_debug", config)
        logger.debug("debug message")
        logger.info("info message")
        output = capsys.readouterr().err
        assert "debug message" in output
        assert "info message" in output

    def test_info_level_filters_debug(self, capsys):
        config = AppConfig(logging=LoggingConfig(level="INFO"))
        logger = get_logger("test_levels_info", config)
        logger.debug("debug message")
        logger.info("info message")
        output = capsys.readouterr().err
        assert "debug message" not in output
        assert "info message" in output

    def test_warning_level(self, capsys):
        config = AppConfig(logging=LoggingConfig(level="WARNING"))
        logger = get_logger("test_levels_warn", config)
        logger.info("info message")
        logger.warning("warning message")
        output = capsys.readouterr().err
        assert "info message" not in output
        assert "warning message" in output


class TestLoggerFormat:
    """Test log format options."""

    def test_structured_format(self, capsys):
        config = AppConfig(logging=LoggingConfig(level="INFO", structured=True))
        logger = get_logger("test_format_struct", config)
        logger.info("structured test")
        output = capsys.readouterr().err
        # Should have timestamp and logger name
        assert "test_format_struct" in output
        assert "structured test" in output
        # Timestamp format: [YYYY-MM-DD HH:MM:SS]
        assert output.startswith("[")

    def test_simple_format(self, capsys):
        config = AppConfig(logging=LoggingConfig(level="INFO", structured=False))
        logger = get_logger("test_format_simple", config)
        logger.info("simple test")
        output = capsys.readouterr().err
        # Should NOT have timestamp brackets
        assert "simple test" in output
        assert output.startswith("INFO")


class TestConfigureLogging:
    """Test configure_logging function."""

    def test_configure_root(self):
        config = AppConfig(logging=LoggingConfig(level="DEBUG"))
        configure_logging(config)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) > 0

    def test_configure_resets_cache(self):
        config1 = AppConfig(logging=LoggingConfig(level="INFO"))
        config2 = AppConfig(logging=LoggingConfig(level="DEBUG"))

        logger = get_logger("test_configure_reset", config1)
        assert logger.level == logging.INFO

        configure_logging(config2)
        logger2 = get_logger("test_configure_reset", config2)
        assert logger2.level == logging.DEBUG


class TestLoggerEdgeCases:
    """Test edge cases for logging."""

    def test_empty_message(self, capsys):
        config = AppConfig(logging=LoggingConfig(level="INFO"))
        logger = get_logger("test_empty", config)
        logger.info("")
        output = capsys.readouterr().err
        # Should handle empty message without error
        assert "test_empty" in output

    def test_special_characters(self, capsys):
        config = AppConfig(logging=LoggingConfig(level="INFO"))
        logger = get_logger("test_special", config)
        logger.info("line1\nline2\ttab")
        output = capsys.readouterr().err
        assert "line1" in output
        assert "tab" in output

    def test_shutdown_cleanup(self):
        config = AppConfig(logging=LoggingConfig(level="DEBUG"))
        logger = get_logger("test_shutdown", config)
        assert logger is not None
        shutdown_logging()
        # After shutdown, loggers should be re-creatable
        logger2 = get_logger("test_shutdown_after", config)
        assert logger2 is not None
        assert logger2.level == logging.DEBUG
