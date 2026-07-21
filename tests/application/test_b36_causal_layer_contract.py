from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.application.world_layer_causal import (
    apply_default_causal_metadata,
    get_causal_aliases,
    get_causal_notes,
    get_causal_parent_layer_ids,
    get_causal_rank,
    get_causal_role,
    is_causally_above,
    is_causally_below,
    set_causal_aliases,
    set_causal_notes,
    set_causal_parent_layer_ids,
    set_causal_rank,
    set_causal_role,
    sort_layers_by_causal_rank,
    validate_causal_metadata,
)
from packages.domain.project import Project
from packages.domain.world_layer import WorldLayer, default_world_layers


@pytest.mark.application
def test_default_causal_metadata_exists_for_existing_world_layers() -> None:
    layers = default_world_layers()

    assert len(layers) == 16
    by_id = {layer.id: layer for layer in layers}
    assert get_causal_role(by_id["layer_premisa"]) == "meta_context"
    assert get_causal_rank(by_id["layer_premisa"]) is None
    assert get_causal_rank(by_id["layer_metafisica"]) == 1
    assert get_causal_role(by_id["layer_metafisica"]) == "root_cause"
    assert "causas primeras" in get_causal_aliases(by_id["layer_metafisica"])
    assert get_causal_rank(by_id["layer_campaña"]) == 15


@pytest.mark.application
def test_get_set_causal_rank_and_role_use_serialized_metadata() -> None:
    layer = WorldLayer(id="custom", name="Custom")

    assert get_causal_rank(layer) is None
    assert get_causal_role(layer) is None

    set_causal_rank(layer, 42)
    set_causal_role(layer, "custom_role")

    assert layer.metadata["causal_rank"] == "42"
    assert get_causal_rank(layer) == 42
    assert get_causal_role(layer) == "custom_role"

    set_causal_rank(layer, None)
    set_causal_role(layer, None)
    assert get_causal_rank(layer) is None
    assert get_causal_role(layer) is None
    assert "causal_rank" not in layer.metadata
    assert "causal_role" not in layer.metadata


@pytest.mark.application
def test_aliases_parent_layer_ids_and_notes_helpers() -> None:
    layer = WorldLayer(id="custom", name="Custom")

    set_causal_aliases(layer, ["metafísica", " causas primeras ", ""])
    set_causal_parent_layer_ids(layer, ["layer_a", "layer_b"])
    set_causal_notes(layer, "Nota causal")

    assert get_causal_aliases(layer) == ["metafísica", "causas primeras"]
    assert get_causal_parent_layer_ids(layer) == ["layer_a", "layer_b"]
    assert get_causal_notes(layer) == "Nota causal"
    assert layer.metadata["causal_aliases"] == "metafísica,causas primeras"
    assert layer.metadata["causal_parent_layer_ids"] == "layer_a,layer_b"


@pytest.mark.application
def test_sort_and_above_below_by_causal_rank() -> None:
    low = WorldLayer(id="low", name="Low")
    high = WorldLayer(id="high", name="High")
    meta = WorldLayer(id="meta", name="Meta")
    set_causal_rank(low, 10)
    set_causal_rank(high, 1)

    assert sort_layers_by_causal_rank([low, meta, high]) == [high, low, meta]
    assert is_causally_above(high, low) is True
    assert is_causally_below(low, high) is True
    assert is_causally_above(meta, low) is False
    assert is_causally_below(meta, high) is False


@pytest.mark.application
def test_validate_causal_metadata_accepts_defaults_and_reports_errors() -> None:
    default_issues = validate_causal_metadata(default_world_layers())
    assert default_issues == []

    a = WorldLayer(id="a", name="A", metadata={"causal_rank": "x", "causal_parent_layer_ids": "missing"})
    b = WorldLayer(id="b", name="B", metadata={"causal_rank": "2"})
    c = WorldLayer(id="c", name="C", metadata={"causal_rank": "2", "causal_role": "bad role"})

    issues = validate_causal_metadata([a, b, c])
    fields = {(issue.layer_id, issue.field) for issue in issues}
    assert ("a", "causal_rank") in fields
    assert ("a", "causal_parent_layer_ids") in fields
    assert ("b", "causal_role") in fields
    assert ("c", "causal_rank") in fields
    assert ("c", "causal_role") in fields


@pytest.mark.application
def test_apply_default_causal_metadata_preserves_custom_values_by_default() -> None:
    layer = WorldLayer(id="layer_metafisica", name="Metafísica", metadata={"causal_rank": "99"})

    apply_default_causal_metadata([layer])
    assert get_causal_rank(layer) == 99
    assert get_causal_role(layer) == "root_cause"

    apply_default_causal_metadata([layer], overwrite=True)
    assert get_causal_rank(layer) == 1


@pytest.mark.application
def test_project_save_load_roundtrip_conserves_causal_metadata() -> None:
    now = datetime.now(timezone.utc)
    project = Project(id="proj_b36", name="B36", created_at=now, updated_at=now)
    # Project() ya no auto-puebla las capas por defecto (las siembra el servicio
    # de creación); el contrato que se prueba es el roundtrip del metadata causal.
    project.world_layers = default_world_layers()
    layer = next(layer for layer in project.world_layers if layer.id == "layer_metafisica")
    set_causal_rank(layer, 7)
    set_causal_role(layer, "custom_root")
    set_causal_parent_layer_ids(layer, ["layer_premisa"])

    restored = Project.from_dict(project.to_dict())
    restored_layer = next(layer for layer in restored.world_layers if layer.id == "layer_metafisica")

    assert get_causal_rank(restored_layer) == 7
    assert get_causal_role(restored_layer) == "custom_root"
    assert get_causal_parent_layer_ids(restored_layer) == ["layer_premisa"]


@pytest.mark.application
def test_narrative_context_builder_exposes_causal_summary_via_helper() -> None:
    now = datetime.now(timezone.utc)
    project = Project(id="proj_b36", name="B36", created_at=now, updated_at=now, worldbuilding_active=True)
    project.world_layers = default_world_layers()

    class ProjectServiceStub:
        active_project = project

    context = NarrativeContextBuilder(ProjectServiceStub()).build_context("project", None)
    metafisica = next(layer for layer in context["project"]["world_layers"] if layer["id"] == "layer_metafisica")

    assert metafisica["causal"]["causal_rank"] == 1
    assert metafisica["causal"]["causal_role"] == "root_cause"
    assert "causas primeras" in metafisica["causal"]["causal_aliases"]
    assert "metadata" not in metafisica


@pytest.mark.application
def test_ui_and_ai_do_not_access_causal_metadata_directly() -> None:
    root = Path(__file__).resolve().parents[2]
    audited_paths = [
        root / "hosts" / "DesktopHostPySide",
        root / "packages" / "infrastructure",
    ]
    forbidden = [
        'metadata["causal_rank"]',
        "metadata['causal_rank']",
        'metadata["causal_role"]',
        "metadata['causal_role']",
        'metadata["causal_aliases"]',
        "metadata['causal_aliases']",
        '.metadata.get("causal_rank"',
        ".metadata.get('causal_rank'",
        '.metadata.get("causal_role"',
        ".metadata.get('causal_role'",
        '.metadata.get("causal_aliases"',
        ".metadata.get('causal_aliases'",
    ]

    offenders: list[str] = []
    for audited_path in audited_paths:
        files = [audited_path] if audited_path.is_file() else sorted(audited_path.rglob("*.py"))
        for path in files:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                if token in text:
                    offenders.append(f"{path.relative_to(root)}: {token}")

    assert offenders == []
