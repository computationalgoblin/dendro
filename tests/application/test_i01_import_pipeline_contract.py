from pathlib import Path


CONTRACT_PATH = Path("docs/architecture/I01_import_pipeline_contract.md")


def test_i01_contract_exists_and_names_existing_core_models():
    text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "ImportBasket" in text
    assert "ImportCandidate" in text
    assert "DocumentSegment" in text
    assert "SourceType.DOCUMENTO_IMPORTADO" in text
    assert "Candidate" in text


def test_i01_contract_forbids_direct_canon_mutation():
    text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "no modifica canon directamente" in text
    assert "La UI no escribe directamente en persistencia." in text
    assert "La aceptacion canonica delega en servicios de aplicacion existentes." in text
    assert "No hay fallback de IA simulado." in text


def test_i01_contract_requires_traceable_source_references_and_rag_states():
    text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "SourceReference" in text
    assert "source_references" in text
    assert "raw_import" in text
    assert "reviewed" in text
    assert "accepted" in text
    assert "include_unaccepted_imports=True" in text

