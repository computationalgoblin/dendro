"""Sanity tests for narrative-architect project."""
import sys

import application
import domain
import infrastructure
import persistence
import ui


class TestPackageImports:
    """Verify all packages import correctly."""

    def test_core_packages_exist(self):
        """All five core packages should be importable."""
        assert domain.__name__ == "domain"
        assert application.__name__ == "application"
        assert infrastructure.__name__ == "infrastructure"
        assert persistence.__name__ == "persistence"
        assert ui.__name__ == "ui"

    def test_python_version(self):
        """Project requires Python 3.12+."""
        assert sys.version_info >= (3, 12), f"Python {sys.version_info} < 3.12"


class TestDomainDependencies:
    """Domain must not depend on higher layers."""

    def test_domain_does_not_import_app_infra_persist_ui(self):
        """Domain package should not import application, infrastructure, persistence, or ui."""
        import ast
        import os

        domain_path = domain.__path__[0]
        illegal = {"application", "infrastructure", "persistence", "ui"}

        for root, _dirs, files in os.walk(domain_path):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(root, fname)
                with open(path) as fh:
                    tree = ast.parse(fh.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top = alias.name.split(".")[0]
                            assert top not in illegal, (
                                f"Illegal import in {path}: {alias.name}"
                            )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            top = node.module.split(".")[0]
                            assert top not in illegal, (
                                f"Illegal import in {path}: from {node.module}"
                            )
