"""BETA2-SHIP-04: la versión es UNA — pyproject y AppConfig no pueden divergir."""

from __future__ import annotations

import tomllib
from pathlib import Path

from packages.domain.config import AppConfig


def test_pyproject_and_appconfig_versions_match():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == AppConfig().app_version
