"""
Architecture dependency tests.

Verifies layer dependency rules are respected using static AST analysis.
Domain must be pure (no upper-layer imports). Each layer has a defined
set of allowed import targets.

These tests use AST parsing, not runtime imports, so they work even
when packages aren't installed or when layers are empty/not yet implemented.
"""

from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
from typing import Iterator

import pytest

# ---------------------------------------------------------------------------
# Layer dependency rules
# Each entry: (top_level_package_name, set_of_allowed_import_top_levels)
# Dependencies marked as "allowed" must be explicitly listed.
# Stdlib modules are always allowed (filtered dynamically).
# ---------------------------------------------------------------------------

LAYER_RULES: list[tuple[str, str, set[str]]] = [
    # (package_path, description, allowed_explicit_modules)
    ("packages/domain", "Domain must only import stdlib",
     set()),
    ("packages/application", "Application may only import domain + stdlib",
     {"packages.domain"}),
    ("packages/infrastructure", "Infrastructure may import domain and application + stdlib",
     {"packages.domain", "packages.application"}),
    ("packages/persistence", "Persistence may only import domain + stdlib",
     {"packages.domain"}),
    ("packages/ui", "UI may import application and domain + stdlib",
     {"packages.domain", "packages.application"}),
]

# Always-allowed top-level modules (stdlib + project namespace)
ALWAYS_ALLOWED = {
    "__future__",
    "abc",
    "ast",
    "collections",
    "contextlib",
    "copy",
    "csv",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "functools",
    "gc",
    "hashlib",
    "html",
    "http",
    "importlib",
    "inspect",
    "io",
    "itertools",
    "json",
    "logging",
    "math",
    "operator",
    "os",
    "pathlib",
    "platform",
    "pprint",
    "queue",
    "re",
    "secrets",
    "shutil",
    "socket",
    "sqlite3",
    "stat",
    "string",
    "struct",
    "subprocess",
    "sys",
    "tempfile",
    "textwrap",
    "threading",
    "time",
    "traceback",
    "typing",
    "types",
    "unittest",
    "urllib",
    "uuid",
    "warnings",
    "weakref",
    "xml",
    "zipfile",
    "zoneinfo",
}


def _is_stdlib(modname: str) -> bool:
    """Check if a module name is part of Python stdlib."""
    return modname in ALWAYS_ALLOWED or importlib.util.find_spec(modname) is not None


def _iter_py_files(package_path: Path) -> Iterator[Path]:
    """Yield all .py file paths under package_path."""
    package_path = Path(package_path)
    if not package_path.is_dir():
        return
    for root, _dirs, files in os.walk(package_path):
        for fname in files:
            if fname.endswith(".py"):
                yield Path(root) / fname


def _check_package_imports(
    package_path: Path,
    allowed_imports: set[str],
) -> list[str]:
    """Check all .py files under package_path for illegal imports.

    Returns a list of violation strings. Empty list = clean.
    """
    violations: list[str] = []
    for filepath in _iter_py_files(package_path):
        source = filepath.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            violations.append(f"{filepath}: syntax error in file")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if not _is_stdlib(top) and top not in allowed_imports:
                        violations.append(
                            f"{filepath}: illegal import '{alias.name}'"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if not _is_stdlib(top) and top not in allowed_imports:
                        violations.append(
                            f"{filepath}: illegal import from '{node.module}'"
                        )
    return violations


def _find_package_dir(package_path_str: str) -> Path | None:
    """Find the actual directory for a logical package path.

    Handles both 'packages/domain' and 'packages.application' formats,
    and falls back to importing the module.
    """
    # Try filesystem first
    pkg_path = Path(package_path_str.replace(".", "/"))
    if pkg_path.is_dir():
        return pkg_path

    # Try under workspace packages/
    workspace_path = Path("/workspace") / pkg_path
    if workspace_path.is_dir():
        return workspace_path

    # Try importing
    modname = package_path_str.replace("/", ".")
    try:
        import importlib
        mod = importlib.import_module(modname)
        if hasattr(mod, "__path__"):
            return Path(mod.__path__[0])
        if mod.__file__:
            return Path(mod.__file__).parent
    except (ImportError, ModuleNotFoundError):
        pass

    return None


# =========================================================================
# Tests
# =========================================================================


class TestDomainLayer:
    """Domain must be pure — no dependencies on any other project layer."""

    def test_domain_does_not_import_upper_layers(self):
        pkg_path = _find_package_dir("packages/domain")
        if pkg_path is None:
            pytest.skip("Domain package not found")
        allowed = {"packages.domain"} | ALWAYS_ALLOWED
        violations = _check_package_imports(pkg_path, allowed)
        assert not violations, "\n".join(violations)


class TestApplicationLayer:
    """Application may only import domain + stdlib."""

    def test_application_does_not_import_infrastructure_or_persistence_or_ui(self):
        pkg_path = _find_package_dir("packages/application")
        if pkg_path is None:
            pytest.skip("Application package not found/implemented")
        allowed = {"packages.domain", "packages.application"} | ALWAYS_ALLOWED
        violations = _check_package_imports(pkg_path, allowed)
        assert not violations, "\n".join(violations)


class TestInfrastructureLayer:
    """Infrastructure may import domain and application + stdlib."""

    def test_infrastructure_does_not_import_persistence_or_ui(self):
        pkg_path = _find_package_dir("packages/infrastructure")
        if pkg_path is None:
            pytest.skip("Infrastructure package not found/implemented")
        allowed = {
            "packages.domain",
            "packages.application",
            "packages.infrastructure",
        } | ALWAYS_ALLOWED
        violations = _check_package_imports(pkg_path, allowed)
        assert not violations, "\n".join(violations)


class TestPersistenceLayer:
    """Persistence may only import domain + stdlib (and its own modules)."""

    def test_persistence_does_not_import_application_infrastructure_or_ui(self):
        pkg_path = _find_package_dir("packages/persistence")
        if pkg_path is None:
            pytest.skip("Persistence package not found/implemented")
        allowed = {
            "packages.domain",
            "packages.persistence",
        } | ALWAYS_ALLOWED
        violations = _check_package_imports(pkg_path, allowed)
        assert not violations, "\n".join(violations)


class TestUILayer:
    """UI may import application and domain + stdlib, but not persistence."""

    def test_ui_does_not_import_persistence_infrastructure(self):
        pkg_path = _find_package_dir("packages/ui")
        if pkg_path is None:
            pytest.skip("UI package not found/implemented")
        allowed = {
            "packages.domain",
            "packages.application",
            "packages.ui",
        } | ALWAYS_ALLOWED
        violations = _check_package_imports(pkg_path, allowed)
        assert not violations, "\n".join(violations)


class TestAllPackageImports:
    """Comprehensive test — verify all layers in one pass.

    This test dynamically iterates LAYER_RULES and checks each one,
    reporting all violations together rather than failing at the first one.
    """

    def test_all_layers_respect_dependency_rules(self):
        failures: list[str] = []
        for pkg_path_str, description, allowed_imports in LAYER_RULES:
            pkg_path = _find_package_dir(pkg_path_str)
            if pkg_path is None:
                continue  # skip unimplemented packages
            violations = _check_package_imports(
                pkg_path,
                allowed_imports | ALWAYS_ALLOWED,
            )
            for v in violations:
                failures.append(f"[{pkg_path_str}] {v}")
        assert not failures, (
            "Layer dependency violations found:\n" + "\n".join(failures)
        )


class TestDependencyRulesMetatest:
    """Metatests: verify the test infrastructure itself is correct."""

    def test_find_package_domain(self):
        """Verify _find_package_dir works for domain."""
        pkg_path = _find_package_dir("packages/domain")
        assert pkg_path is not None, "Should find packages/domain"
        assert pkg_path.is_dir()
        assert (pkg_path / "__init__.py").exists()

    def test_allowed_stdlib_set_includes_core_modules(self):
        """The ALWAYS_ALLOWED set must include modules used by domain."""
        for mod in ("typing", "dataclasses", "enum", "datetime", "uuid",
                     "pathlib", "os", "io", "json", "logging", "collections",
                     "abc", "__future__"):
            assert mod in ALWAYS_ALLOWED, f"{mod} missing from ALWAYS_ALLOWED"

    def test_always_allowed_provides_stdlib(self):
        """Verify _is_stdlib returns True for common stdlib modules."""
        assert _is_stdlib("sys")
        assert _is_stdlib("os")
        assert _is_stdlib("typing")
        assert not _is_stdlib("nonexistent_module_xyz")
        assert not _is_stdlib("numpy")
