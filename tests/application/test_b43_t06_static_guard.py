"""Tests for B43-T06: Static guard — no new inline prompts.

Static test that scans all Python files in packages/application/
for long inline prompts (multi-line string constants that look like
system prompts) outside of prompt_registry.py.

Allowlisted files are documented exceptions.
"""
import os
import re
import pytest

# Files that are explicitly allowed to contain inline prompts
ALLOWLIST = {
    "prompt_registry.py",   # The registry itself
}

# Heuristic: a long string constant (>200 chars) that looks like a system prompt
# Patterns: starts with "Eres", "You are", "Act as", "Tu tarea", etc.
PROMPT_PATTERN = re.compile(
    r'("(?:Eres|You are|Act as|Tu tarea|Your task|Actúa|Responde)[^"]{200,}"'
    r"|'(?:Eres|You are|Act as|Tu tarea|Your task|Actúa|Responde)[^']{200,}'"
    r'|(?:Eres|You are|Act as|Tu tarea|Your task|Actúa)[^\n"]{200,})',
    re.IGNORECASE,
)


def _find_inline_prompts(directory: str) -> list[tuple[str, int, str]]:
    """Scan for inline prompts. Returns (file, line_number, snippet)."""
    findings = []
    for root, dirs, files in os.walk(directory):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            if fname in ALLOWLIST:
                continue
            fpath = os.path.join(root, fname)
            with open(fpath, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    # Skip imports and comments
                    stripped = line.strip()
                    if stripped.startswith("#") or stripped.startswith("import ") or stripped.startswith("from "):
                        continue
                    # Skip test assertions that mention prompt text
                    if "assert" in stripped:
                        continue
                    matches = PROMPT_PATTERN.findall(line)
                    if matches:
                        for m in matches:
                            snippet = m[:80] if isinstance(m, str) else m[0][:80]
                            findings.append((fname, lineno, snippet))
    return findings


class TestStaticGuardNoInlinePrompts:
    def test_no_long_inline_prompts_outside_registry(self):
        findings = _find_inline_prompts("packages/application")
        if findings:
            msg = "\n".join(
                f"  {fname}:{lineno}: {snippet!r}..."
                for fname, lineno, snippet in findings
            )
            pytest.fail(
                f"Found {len(findings)} inline prompt(s) outside prompt_registry.py.\n"
                f"Add to ALLOWLIST or migrate to Prompt Registry.\n{msg}"
            )

    def test_allowlist_entries_exist(self):
        """All allowlisted files must exist."""
        for fname in ALLOWLIST:
            fpath = os.path.join("packages/application", fname)
            assert os.path.exists(fpath), f"Allowlisted file not found: {fpath}"

    def test_prompt_registry_has_all_expected_keys(self):
        from packages.application.prompt_registry import PromptRegistry
        expected = {"command_bar", "inline_leaf", "inline_branch",
                    "inline_relation", "coherence", "coherence_repair",
                    "wizard_suggestion"}
        for key in expected:
            assert key in PromptRegistry, f"Missing prompt key: {key}"
