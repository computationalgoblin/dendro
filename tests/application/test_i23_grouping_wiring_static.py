"""I23 — chequeos estáticos del cableado de agrupación + cuerpo.

Confirma que el prompt de extracción exige cuerpo (v3), que la intención de
agrupación existe en el registry, en los parámetros del gateway y en el validador,
y que la vista de importación aplica entidades/ramas antes que relaciones.
"""

from pathlib import Path

from packages.application.ai_request_gateway import INTENT_PARAMS
from packages.application.output_schema_validator import EXPECTED_SCHEMAS
from packages.application.prompt_registry import PromptRegistry, get_prompt

ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "hosts" / "DesktopHostPySide" / "views" / "import_export_view.py"


def test_import_extraction_is_v3_and_requires_body():
    spec = PromptRegistry["import_extraction"]
    assert spec["version"] == 3
    text = get_prompt("import_extraction", "es")
    assert "CUERPO (OBLIGATORIO)" in text
    assert "OBLIGATORIO para entity/branch" in text


def test_import_grouping_prompt_exists():
    assert "import_grouping" in PromptRegistry
    text = get_prompt("import_grouping", "es")
    assert text
    assert '"branches"' in text
    assert '"members"' in text
    assert '"parent"' in text


def test_import_grouping_registered_in_gateway_and_validator():
    assert "import_grouping" in INTENT_PARAMS
    assert INTENT_PARAMS["import_grouping"].max_tokens >= 3000
    assert "import_grouping" in EXPECTED_SCHEMAS
    assert EXPECTED_SCHEMAS["import_grouping"]["container_key"] == "branches"


def test_view_accepts_non_relations_before_relations():
    text = VIEW.read_text(encoding="utf-8")
    assert "_is_relation_candidate" in text
    # El batch ordena de modo que las relaciones se aplican al final.
    assert "rows.sort(key=lambda bc: self._is_relation_candidate(bc[1]))" in text
