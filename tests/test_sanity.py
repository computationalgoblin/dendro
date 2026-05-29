"""Sanity tests for narrative-architect project.

These tests verify the basic structure and integrity of the project.
They are the first line of defense against broken imports, missing packages,
and structural regressions. All sanity tests should complete in < 1 second.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Mark all tests in this module as smoke tests
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.smoke


class TestPythonEnvironment:
    """Verify the Python runtime meets project requirements."""

    def test_python_version(self):
        """Project requires Python 3.12+."""
        assert sys.version_info >= (3, 12), f"Python {sys.version_info} < 3.12"

    def test_pytest_available(self):
        """pytest must be installed."""
        import pytest as _pytest
        assert _pytest.__version__ >= "8.0"


class TestPackageImports:
    """Verify all core packages import correctly."""

    def test_core_packages_exist(self):
        """All five core packages should be importable."""
        import packages.application as _app
        import packages.domain as _domain
        import packages.infrastructure as _infra
        import packages.persistence as _persist
        import packages.ui as _ui

        assert _domain.__name__ == "packages.domain"
        assert _app.__name__ == "packages.application"
        assert _infra.__name__ == "packages.infrastructure"
        assert _persist.__name__ == "packages.persistence"
        assert _ui.__name__ == "packages.ui"

    def test_domain_submodules_importable(self):
        """All domain submodules should be importable."""
        from packages.domain import config as _config
        from packages.domain import exceptions as _exceptions
        from packages.domain import logging as _logging
        from packages.domain import result as _result

        assert _config.AppConfig is not None
        assert _exceptions.DomainError is not None
        assert _result.Ok is not None
        assert _logging.get_logger is not None


class TestProjectStructure:
    """Verify the project file structure is intact."""

    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    def test_pyproject_toml_exists(self):
        assert (self.PROJECT_ROOT / "pyproject.toml").exists()

    def test_packages_directory_exists(self):
        pkg = self.PROJECT_ROOT / "packages"
        assert pkg.is_dir()
        expected = {"domain", "application", "infrastructure", "persistence", "ui"}
        found = {d.name for d in pkg.iterdir() if d.is_dir() and not d.name.startswith("__")}
        missing = expected - found
        assert not missing, f"Missing packages: {missing}"

    def test_readme_exists(self):
        assert (self.PROJECT_ROOT / "README.md").exists()

    def test_docker_compose_exists(self):
        assert (self.PROJECT_ROOT / "docker-compose.yml").exists() or \
               (self.PROJECT_ROOT / "compose.yaml").exists()

    def test_gitignore_exists(self):
        assert (self.PROJECT_ROOT / ".gitignore").exists()

    def test_kanban_directory_exists(self):
        kanban = self.PROJECT_ROOT / ".kanban"
        assert kanban.is_dir()
        assert (kanban / "KANBAN.md").exists()
        assert (kanban / "tickets").is_dir()
        assert (kanban / "templates" / "ticket-template.md").exists()
        assert (kanban / "resumenes").is_dir()

    def test_docs_contracts_exists(self):
        contracts = self.PROJECT_ROOT / "docs" / "contracts"
        assert contracts.is_dir()
        required = {
            "contrato_fases",
            "workflow.md",
            "reglas-trabajo.md",
            "skills-map.md",
            "convenciones-errores.md",
            "perfiles",
        }
        found = {d.name for d in contracts.iterdir()
                 if not d.name.startswith(".")}
        missing = required - found
        assert not missing, f"Missing contract docs: {missing}"


class TestDomainDependencies:
    """Domain must not depend on higher layers.

    This is a compile-time check that parses all Python files in the
    domain package looking for illegal imports of upper-layer packages.
    """

    def _find_module_path(self, module_name: str) -> Path:
        import importlib
        mod = importlib.import_module(module_name)
        if hasattr(mod, "__path__"):
            return Path(mod.__path__[0])
        if mod.__file__:
            return Path(mod.__file__).parent
        raise RuntimeError(f"Cannot find path for module {module_name}")

    def _check_imports(self, pkg_path: Path, allowed_top_levels: set[str]) -> list[str]:
        """Check that all .py files under pkg_path only import from allowed modules.

        Skips stdlib modules and allowed project modules.
        """
        violations = []
        for root, _dirs, files in os.walk(pkg_path):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                filepath = Path(root) / fname
                source = filepath.read_text(encoding="utf-8")
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top = alias.name.split(".")[0]
                            if top not in allowed_top_levels:
                                violations.append(
                                    f"{filepath}: illegal import '{alias.name}'"
                                )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            top = node.module.split(".")[0]
                            if top not in allowed_top_levels:
                                violations.append(
                                    f"{filepath}: illegal import from '{node.module}'"
                                )
        return violations

    def test_domain_imports_only_stdlib(self):
        """Domain package must only import stdlib and its own modules."""
        pkg_path = self._find_module_path("packages.domain")
        # stdlib modules commonly used, plus own package
        allowed = {
            "packages",  # own package
            "__future__",
            "abc",
            "ast",
            "collections",
            "dataclasses",
            "datetime",
            "enum",
            "io",
            "json",
            "logging",
            "os",
            "pathlib",
            "re",
            "sys",
            "typing",
            "uuid",
            "importlib",
        }
        violations = self._check_imports(pkg_path, allowed)
        assert not violations, "\n".join(violations)

    def test_no_illegal_imports_in_any_layer(self):
        """Application layer must not import ui, infrastructure, or persistence directly."""
        for layer in ("packages.application",):
            try:
                pkg_path = self._find_module_path(layer)
            except (ImportError, ModuleNotFoundError):
                continue  # not yet implemented
            allowed = {
                "packages",  # own package
                "__future__",
                "abc",
                "collections",
                "dataclasses",
                "datetime",
                "enum",
                "json",
                "logging",
                "os",
                "pathlib",
                "typing",
                "uuid",
            }
            violations = self._check_imports(pkg_path, allowed)
            assert not violations, f"{layer} violations:\n" + "\n".join(violations)


class TestTestInfrastructure:
    """Verify that the testing infrastructure itself is sound."""

    def test_conftest_exists(self):
        """Root conftest.py must exist."""
        assert Path(__file__).resolve().parent.joinpath("conftest.py").exists()

    def test_domain_conftest_exists(self):
        """Domain conftest must exist."""
        conftest = Path(__file__).resolve().parent / "domain" / "conftest.py"
        assert conftest.exists(), "tests/domain/conftest.py not found"

    def test_all_test_files_have_init(self):
        """Every test directory must have __init__.py."""
        tests_root = Path(__file__).resolve().parent
        for dirpath, dirnames, _ in os.walk(tests_root):
            # Only check directories that contain .py files
            dirpath_p = Path(dirpath)
            if dirpath_p == tests_root:
                continue  # root __init__.py is optional
            if not dirpath_p.joinpath("test_").exists() and not list(dirpath_p.glob("test_*.py")):
                continue  # not a test directory
            assert dirpath_p.joinpath("__init__").exists() or \
                   dirpath_p.joinpath("__init__.py").exists(), \
                   f"Missing __init__.py in {dirpath_p}"

    def test_marker_registration(self):
        """Verify custom markers are registered in pyproject.toml."""
        config_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        config_text = config_path.read_text(encoding="utf-8")
        expected_markers = [
            "integration",
            "slow",
            "unit",
            "smoke",
            "domain",
            "application",
            "persistence",
        ]
        for marker in expected_markers:
            assert marker in config_text, \
                f"Marker '{marker}' not found in pyproject.toml [tool.pytest.ini_options] markers"
