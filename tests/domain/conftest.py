"""
Domain-specific pytest fixtures for narrative-architect.

Fixtures here are available to all tests under tests/domain/.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def domain_config():
    """Return a minimal AppConfig suitable for domain tests."""
    from packages.domain.config import AppConfig
    return AppConfig(debug=False)


@pytest.fixture
def sample_ok_result():
    """Return a sample Ok(42) result for testing."""
    from packages.domain.result import Ok
    return Ok(42)


@pytest.fixture
def sample_error_result():
    """Return a sample Error('fail') result for testing."""
    from packages.domain.result import Error
    return Error("fail")
