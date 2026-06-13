from __future__ import annotations

import tomllib
from pathlib import Path


def test_desktop_extra_declares_pdf_extractor_dependency():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    desktop_deps = pyproject["project"]["optional-dependencies"]["desktop"]

    assert any(dep.lower().startswith("pymupdf") for dep in desktop_deps)
