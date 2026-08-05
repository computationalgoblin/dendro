"""BETA-MULTIAGENT-FIX-05: idempotencia del panel de estructura (G-05).

- Un hallazgo aplicado no vuelve a listarse (analyze/structure_proposals) ni el
  parseo de la IA lo re-propone.
- `_parse_structure` deduplica por fingerprint y no propone anillos ya existentes.
- `count()` cuenta lo mismo que muestra el panel (deterministas + propuestas IA).
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.application.structural_analysis_service import (
    StructuralAnalysisService,
    StructuralFinding,
)
from packages.domain.project import Project
from packages.domain.world_layer import WorldLayer


@dataclass
class _PS:
    active_project: Project = None


def _service() -> tuple[StructuralAnalysisService, Project]:
    proj = Project(name="Estructura FIX-05")
    proj.world_layers.append(WorldLayer(id="layer_mar", name="Las Mareas", order=1))
    return StructuralAnalysisService(project_service=_PS(proj)), proj


def _proposal(name: str) -> StructuralFinding:
    return StructuralFinding(
        kind="ring_create",
        target_id="",
        proposed_data={"kind": "ring_template", "ring_name": name},
        confidence=0.7,
        fingerprint=f"ring_create:{name}",
        title=f"Crear anillo «{name}»",
    )


def test_mark_applied_retira_la_propuesta_y_no_se_reacepta():
    svc, _ = _service()
    svc._structure_proposals = [_proposal("Las Resonancias")]
    assert len(svc.structure_proposals()) == 1
    svc.mark_applied("ring_create:Las Resonancias")
    assert svc.structure_proposals() == []
    assert svc.is_applied("ring_create:Las Resonancias")


def test_parse_structure_deduplica_por_fingerprint():
    svc, proj = _service()
    data = {
        "crear": [
            {"nombre": "Los Fragmentos", "rank": 2},
            {"nombre": "Los Fragmentos", "rank": 3},  # repetido en la MISMA respuesta
        ],
        "fusionar": [
            {"origen_id": "a", "destino_id": "b", "motivo": "casi vacío"},
            {"origen_id": "a", "destino_id": "b", "motivo": "repetido"},
        ],
    }
    out = svc._parse_structure(proj, data)
    assert [f.fingerprint for f in out] == ["ring_create:Los Fragmentos", "ring_merge:a->b"]


def test_parse_structure_no_repropone_aplicados_ni_anillos_existentes():
    svc, proj = _service()
    svc.mark_applied("ring_create:Los Fragmentos")
    data = {
        "crear": [
            {"nombre": "Los Fragmentos", "rank": 2},  # ya aplicado en la sesión
            {"nombre": "Las Mareas", "rank": 1},  # ya existe como anillo del proyecto
            {"nombre": "El Silencio", "rank": 4},  # legítimo
        ]
    }
    out = svc._parse_structure(proj, data)
    assert [f.fingerprint for f in out] == ["ring_create:El Silencio"]


def test_count_incluye_propuestas_ia_vigentes():
    svc, _ = _service()
    # Proyecto sin entidades → cero hallazgos deterministas.
    assert svc.count() == 0
    svc._structure_proposals = [_proposal("Uno"), _proposal("Dos")]
    assert svc.count() == 2  # el badge cuadra con las tarjetas del panel
    svc.mark_applied("ring_create:Uno")
    assert svc.count() == 1


def test_analyze_filtra_aplicados_incluso_con_cache():
    svc, _ = _service()
    first = svc.analyze()
    assert first.value == []
    # Inyecta un hallazgo en la caché viva (simula un ring_move vigente) y séllalo.
    finding = _proposal("ring-move-simulado")
    svc._cache = [finding]
    assert [f.fingerprint for f in svc.analyze().value] == [finding.fingerprint]
    svc.mark_applied(finding.fingerprint)
    assert svc.analyze().value == []
