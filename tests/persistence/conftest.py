"""
Pytest fixtures for persistence tests.

Provides temporary directories and sample data for testing
save/load operations without touching the real filesystem.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from packages.domain.project import Project
from packages.persistence.schema import CURRENT_SCHEMA_VERSION


@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """A temporary directory for project files.

    Each test gets a clean, isolated directory.
    """
    return tmp_path / "projects"


@pytest.fixture
def project_file(tmp_project_dir: Path) -> Path:
    """Path to a project file in the temp directory."""
    tmp_project_dir.mkdir(parents=True, exist_ok=True)
    return tmp_project_dir / "test-project.json"


@pytest.fixture
def sample_project() -> Project:
    """Create a sample project for testing."""
    return Project(
        id=uuid.uuid4().hex[:12],
        name="Test Project",
    )


@pytest.fixture
def sample_project_data() -> dict[str, Any]:
    """Create sample raw project data (as loaded from JSON)."""
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "id": "abc123def456",
        "name": "Test Project",
        "created_at": "2026-05-29T10:00:00+00:00",
        "updated_at": "2026-05-29T10:00:00+00:00",
        "metadata": {"author": "tester"},
    }


def write_raw_json(path: Path, data: dict[str, Any]) -> None:
    """Write raw JSON data to a file (for test setup)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@pytest.fixture
def corrupt_project_file(project_file: Path) -> Path:
    """Create a corrupt project file for testing error handling."""
    project_file.parent.mkdir(parents=True, exist_ok=True)
    project_file.write_text("this is not json", encoding="utf-8")
    return project_file
