"""Architecture dependency tests."""
import ast
import os


def _get_all_modules_under(package_path):
    """Yield (filepath, modname) for .py files under package_path."""
    for root, _dirs, files in os.walk(package_path):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, package_path)
            if rel == "__init__.py":
                continue
            yield full, rel


class TestDependencyRules:
    """Verify layer dependency rules are respected."""

    # Each entry: (package_name, allowed_imports)
    # allowed_imports = set of top-level package names this layer CAN import
    RULES = [
        ("domain", {"domain", "typing", "abc", "dataclasses", "enum",
                     "datetime", "uuid", "__future__", "collections",
                     "json", "pathlib", "os", "io"}),
    ]

    def _check_package(self, package_name, allowed):
        """Check that package only imports from allowed modules."""
        import importlib
        mod = importlib.import_module(package_name)
        pkg_path = mod.__path__[0] if hasattr(mod, "__path__") else mod.__file__

        for filepath, _rel in _get_all_modules_under(pkg_path):
            with open(filepath) as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top not in allowed:
                            # Skip stdlib modules
                            import importlib.util
                            if importlib.util.find_spec(top) is None:
                                yield f"{filepath}: illegal import '{alias.name}'"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top = node.module.split(".")[0]
                        if top not in allowed:
                            import importlib.util
                            if importlib.util.find_spec(top) is None:
                                yield f"{filepath}: illegal import from '{node.module}'"

    def test_domain_dependencies(self):
        """Domain must only import pure Python stdlib and its own modules."""
        violations = list(self._check_package("domain",
                                              {"domain", "typing", "abc",
                                               "dataclasses", "enum",
                                               "datetime", "uuid",
                                               "__future__", "collections",
                                               "json", "pathlib", "os", "io"}))
        assert not violations, "\n".join(violations)
