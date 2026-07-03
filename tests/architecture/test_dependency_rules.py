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
import os
import sys
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

# ---------------------------------------------------------------------------
# Deuda de capas CONGELADA (BETA1-AUDIT-03).
#
# El guard histórico era vacuo (trataba `packages` entero como stdlib), así que
# estas violaciones se acumularon sin aviso. Se congelan aquí como baseline
# explícita —igual que EXPECTED_PARENTLESS_WIDGETS en desktop—: cualquier
# violación NUEVA rompe el test; al resolver una entrada hay que retirarla
# (la metaprueba de vigencia lo exige). El desacople real (puerto AIProvider,
# raíz de composición para ProjectStore) es DC-AUDIT-03 en product_debt_map.
# ---------------------------------------------------------------------------
DOCUMENTED_LAYER_DEBT: frozenset[str] = frozenset({
    # application → infrastructure: el puerto AIProvider vive en infrastructure
    # y lo consume application (inversión pendiente, DC-AUDIT-03).
    "packages/application/ai_context_actions.py: illegal import from 'packages.infrastructure.ai_provider'",
    "packages/application/ai_jobs.py: illegal import from 'packages.infrastructure.ai_provider'",
    "packages/application/ai_request_gateway.py: illegal import from 'packages.infrastructure.ai_provider'",
    "packages/application/command_bar_planner.py: illegal import from 'packages.infrastructure.ai_provider'",
    "packages/application/orchestrator_service.py: illegal import from 'packages.infrastructure.ai_provider'",
    # application → persistence: los servicios construyen/usan ProjectStore
    # directamente; falta un puerto de repositorio + raíz de composición.
    "packages/application/bootstrap.py: illegal import from 'packages.persistence.store'",
    "packages/application/entity_service.py: illegal import from 'packages.persistence.store'",
    "packages/application/project_maintenance_service.py: illegal import from 'packages.persistence.store'",
    "packages/application/project_service.py: illegal import from 'packages.persistence.schema'",
    "packages/application/project_service.py: illegal import from 'packages.persistence.store'",
    "packages/application/relation_service.py: illegal import from 'packages.persistence.store'",
    "packages/application/source_service.py: illegal import from 'packages.persistence.store'",
})

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
    """Check if a top-level module name is stdlib/allowed (non-project imports).

    Project imports (``packages.*``) NO pasan por aquí: se comparan por capa
    (``packages.<capa>``) en ``_check_package_imports``. Antes este helper
    devolvía True para ``packages`` entero, lo que vaciaba el guard: ningún
    import entre capas se comparaba de verdad (BETA1-AUDIT-03).
    """
    return modname in ALWAYS_ALLOWED or modname in sys.stdlib_module_names


def _iter_py_files(package_path: Path) -> Iterator[Path]:
    """Yield all .py file paths under package_path."""
    package_path = Path(package_path)
    if not package_path.is_dir():
        return
    for root, _dirs, files in os.walk(package_path):
        for fname in files:
            if fname.endswith(".py"):
                yield Path(root) / fname


def _type_checking_import_linenos(tree: ast.AST) -> set[int]:
    """Líneas de imports dentro de ``if TYPE_CHECKING:`` (permitidos: el
    contrato admite dependencias de solo tipo para anotaciones)."""
    linenos: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if not is_tc:
            continue
        for child in ast.walk(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                linenos.add(child.lineno)
    return linenos


def _import_violation(module_name: str, allowed_imports: set[str]) -> bool:
    """True si importar ``module_name`` viola la capa dada.

    Los imports del proyecto se comparan por prefijo de DOS niveles
    (``packages.<capa>``); el resto por su primer nivel contra stdlib/allowed.
    """
    if module_name == "packages" or module_name.startswith("packages."):
        layer = ".".join(module_name.split(".")[:2])
        return layer not in allowed_imports
    top = module_name.split(".")[0]
    return not _is_stdlib(top) and top not in allowed_imports


def _check_package_imports(
    package_path: Path,
    allowed_imports: set[str],
    *,
    include_documented_debt: bool = False,
) -> list[str]:
    """Check all .py files under package_path for illegal imports.

    Returns a list of violation strings. Empty list = clean. Las violaciones
    presentes en ``DOCUMENTED_LAYER_DEBT`` se omiten salvo que se pida lo
    contrario (sirven a la metaprueba de vigencia de la deuda).
    """
    violations: list[str] = []
    for filepath in _iter_py_files(package_path):
        rel = Path(filepath).as_posix()
        source = filepath.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            violations.append(f"{rel}: syntax error in file")
            continue

        type_checking_lines = _type_checking_import_linenos(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if node.lineno in type_checking_lines:
                    continue
                for alias in node.names:
                    if _import_violation(alias.name, allowed_imports):
                        violations.append(f"{rel}: illegal import '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.lineno not in type_checking_lines:
                    if _import_violation(node.module, allowed_imports):
                        violations.append(f"{rel}: illegal import from '{node.module}'")
    if not include_documented_debt:
        violations = [v for v in violations if v not in DOCUMENTED_LAYER_DEBT]
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
            own_package = pkg_path_str.replace("/", ".")
            violations = _check_package_imports(
                pkg_path,
                allowed_imports | {own_package} | ALWAYS_ALLOWED,
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

    def test_project_imports_are_layer_checked(self):
        """El namespace del proyecto no es stdlib: se compara por capa."""
        assert not _is_stdlib("packages")
        assert _import_violation("packages.persistence.store", {"packages.domain"})
        assert not _import_violation("packages.domain.result", {"packages.domain"})

    def test_documented_layer_debt_is_current(self):
        """Cada entrada de la deuda congelada debe seguir existiendo: al resolver
        una violación hay que retirar su línea (baseline solo-mengua)."""
        raw: set[str] = set()
        for pkg_path_str, _description, allowed_imports in LAYER_RULES:
            pkg_path = _find_package_dir(pkg_path_str)
            if pkg_path is None:
                continue
            own_package = pkg_path_str.replace("/", ".")
            raw.update(_check_package_imports(
                pkg_path,
                allowed_imports | {own_package} | ALWAYS_ALLOWED,
                include_documented_debt=True,
            ))
        stale = sorted(DOCUMENTED_LAYER_DEBT - raw)
        assert not stale, (
            "Deuda de capas resuelta; retira estas entradas de DOCUMENTED_LAYER_DEBT: "
            + "; ".join(stale)
        )
