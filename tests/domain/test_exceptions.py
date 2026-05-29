"""Tests for domain exception hierarchy."""

from packages.domain.exceptions import (
    ApplicationError,
    ConfigurationError,
    DomainError,
    NarrativeArchitectError,
    PersistenceError,
)


class TestBaseException:
    """Test the base NarrativeArchitectError."""

    def test_default_code(self):
        exc = NarrativeArchitectError("test message")
        assert exc.message == "test message"
        assert exc.code == "UNKNOWN_ERROR"
        assert exc.error_code == "UNKNOWN_ERROR"

    def test_custom_code(self):
        exc = NarrativeArchitectError("test", code="TEST_001")
        assert exc.code == "TEST_001"
        assert exc.error_code == "TEST_001"

    def test_message_format(self):
        exc = NarrativeArchitectError("something failed", code="FAIL_001")
        msg = str(exc)
        assert "[FAIL_001]" in msg
        assert "something failed" in msg

    def test_is_exception(self):
        exc = NarrativeArchitectError("test")
        assert isinstance(exc, Exception)
        assert isinstance(exc, BaseException)


class TestDomainError:
    """Test DomainError class."""

    def test_is_domain_error(self):
        exc = DomainError("invalid entity name", code="DOMAIN_001")
        assert isinstance(exc, DomainError)
        assert isinstance(exc, NarrativeArchitectError)
        assert exc.code == "DOMAIN_001"

    def test_default_code(self):
        exc = DomainError("test")
        assert exc.code == "UNKNOWN_ERROR"
        assert "UNKNOWN_ERROR" in str(exc)

    def test_catch_domain_error(self):
        try:
            raise DomainError("domain violation", code="DOMAIN_042")
        except DomainError as e:
            assert e.code == "DOMAIN_042"
        except NarrativeArchitectError:
            assert False, "Should have caught DomainError first"


class TestApplicationError:
    """Test ApplicationError class."""

    def test_is_application_error(self):
        exc = ApplicationError("command rejected", code="APP_001")
        assert isinstance(exc, ApplicationError)
        assert isinstance(exc, NarrativeArchitectError)
        assert exc.code == "APP_001"


class TestConfigurationError:
    """Test ConfigurationError class."""

    def test_is_config_error(self):
        exc = ConfigurationError("invalid config", code="CONFIG_001")
        assert isinstance(exc, ConfigurationError)
        assert isinstance(exc, NarrativeArchitectError)


class TestPersistenceError:
    """Test PersistenceError class."""

    def test_is_persistence_error(self):
        exc = PersistenceError("file not found", code="PERSIST_001")
        assert isinstance(exc, PersistenceError)
        assert isinstance(exc, NarrativeArchitectError)


class TestExceptionHierarchy:
    """Test the complete exception hierarchy."""

    def test_catch_base_class(self):
        errors = [
            DomainError("d"),
            ApplicationError("a"),
            ConfigurationError("c"),
            PersistenceError("p"),
        ]
        for exc in errors:
            assert isinstance(exc, NarrativeArchitectError)
            assert isinstance(exc, Exception)

    def test_domain_not_app(self):
        d = DomainError("test", code="DOMAIN_001")
        assert not isinstance(d, ApplicationError)
        assert not isinstance(d, ConfigurationError)
        assert not isinstance(d, PersistenceError)

    def test_raise_and_catch_hierarchy(self):
        """Verify that catching NarrativeArchitectError catches all subtypes."""
        caught_types = []

        def raise_error(exc):
            try:
                raise exc
            except NarrativeArchitectError:
                caught_types.append(type(exc).__name__)

        raise_error(DomainError("d"))
        raise_error(ApplicationError("a"))
        raise_error(ConfigurationError("c"))
        raise_error(PersistenceError("p"))

        expected = [
            "DomainError",
            "ApplicationError",
            "ConfigurationError",
            "PersistenceError",
        ]
        assert caught_types == expected
