"""BETA2-FIX-12 (G2-16) — el parentesco llega vivo hasta donde se lee.

Complementa a `tests/domain/test_beta_m2fix12_parentesco.py` (el catálogo) con la
RUTA MANUAL de escritura y las superficies de lectura:

- crear una relación con un tipo de parentesco lo PERSISTE (hasta ahora ninguna
  prueba cubría la ruta manual: la de BETA-FIX-04 de la ronda 1 solo
  cubría `accept_candidate`);
- un tipo fuera del dominio ya no devuelve `Ok` con `esta_relacionado_con`
  dentro (el arreglo del servicio es de BETA2-FIX-03; aquí se guarda
  que sigue cerrado y que NO se cierra sobre los tipos nuevos);
- `_normalize_relation_enums` no revierte un parentesco al actualizar;
- el tipo viaja a la arista del Mapa y al payload que recibe la IA;
- y un parentesco NO se comporta como contención (una madre no es una rama).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.application import foco_rings
from packages.application.command_prompts import system_prompt_for_intent
from packages.application.entity_service import EntityService
from packages.application.graph_service import GraphService
from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.application.project_service import ProjectService
from packages.application.query_service import QueryService
from packages.application.relation_service import RelationService
from packages.application.source_service import SourceService
from packages.application.watering_service import WateringService
from packages.application.wiki_index_service import WikiIndexService
from packages.domain.relation import RelationType
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore

pytestmark = pytest.mark.application


def _setup(tmp_path: Path):
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="La casa de Santa María")
    es = EntityService(project_service=ps, store=store)
    rs = RelationService(project_service=ps, store=store)
    rs._current_path = tmp_path / "proj.json"
    remedios = es.create_entity({"name": "Remedios", "entity_type": "personaje"}).value
    manuel = es.create_entity({"name": "Manuel", "entity_type": "personaje"}).value
    return ps, es, rs, remedios, manuel


# ── ruta manual de escritura ────────────────────────────────────────────────


def test_beta_m2fix12_tipo_valido_se_persiste(tmp_path: Path):
    ps, _es, rs, remedios, manuel = _setup(tmp_path)
    result = rs.create_relation(remedios.id, manuel.id, "es_madre_de")
    assert isinstance(result, Ok), getattr(result, "error", None)
    assert result.value.relation_type is RelationType.ES_MADRE_DE
    # …y lo que queda EN el proyecto, no solo lo devuelto.
    guardada = ps.active_project.relations[0]
    assert guardada.relation_type is RelationType.ES_MADRE_DE
    assert guardada.to_dict()["relation_type"] == "es_madre_de"


def test_beta_m2fix12_tipo_desconocido_no_devuelve_ok_silencioso(tmp_path: Path):
    ps, _es, rs, remedios, manuel = _setup(tmp_path)
    result = rs.create_relation(remedios.id, manuel.id, "mentor_espiritual")
    assert isinstance(result, Error), "un tipo inexistente no puede devolver Ok"
    assert "mentor_espiritual" in result.error
    assert "es_madre_de" in result.error  # el error lista los válidos
    assert not ps.active_project.relations  # y no se guardó nada aplanado


def test_beta_m2fix12_vacio_sigue_siendo_el_default_explicito(tmp_path: Path):
    """Vacío/None = «relación genérica», que es una elección, no un desconocido."""
    _ps, _es, rs, remedios, manuel = _setup(tmp_path)
    for valor in (None, "", "   "):
        r = rs.create_relation(remedios.id, manuel.id, valor)
        if isinstance(r, Ok):
            assert r.value.relation_type is RelationType.ESTA_RELACIONADO_CON
            rs.delete_relation(r.value.id)
        else:  # duplicado: el tipo ya se resolvió al genérico, que es el punto
            assert "misma" in r.error or "same" in r.error


def test_beta_m2fix12_via_data_dict(tmp_path: Path):
    """El mismo tipo dentro de `data` (segunda rama) se comporta igual."""
    ps, _es, rs, remedios, manuel = _setup(tmp_path)
    ok = rs.create_relation(data={
        "source_id": remedios.id, "target_id": manuel.id, "relation_type": "es_madre_de",
    })
    assert isinstance(ok, Ok), getattr(ok, "error", None)
    assert ps.active_project.relations[0].relation_type is RelationType.ES_MADRE_DE

    ko = rs.create_relation(data={
        "source_id": manuel.id, "target_id": remedios.id, "relation_type": "mentor_espiritual",
    })
    assert isinstance(ko, Error)
    assert len(ps.active_project.relations) == 1


def test_beta_m2fix12_update_relation_no_aplana(tmp_path: Path):
    """`_normalize_relation_enums` aplanaba al default lo que no fuera del enum."""
    ps, _es, rs, remedios, manuel = _setup(tmp_path)
    rel = rs.create_relation(remedios.id, manuel.id, "esta_relacionado_con").value
    updated = rs.update_relation(rel.id, {"relation_type": "es_madre_de"})
    assert isinstance(updated, Ok), getattr(updated, "error", None)
    assert updated.value.relation_type is RelationType.ES_MADRE_DE
    assert ps.active_project.relations[0].relation_type is RelationType.ES_MADRE_DE
    # Y sobrevive a una segunda edición que no toca el tipo.
    rs.update_relation(rel.id, {"description": "la madre de Manuel"})
    assert ps.active_project.relations[0].relation_type is RelationType.ES_MADRE_DE


def test_beta_m2fix12_update_relation_rechaza_tipo_desconocido(tmp_path: Path):
    """La puerta gemela de `create_relation`: actualizar tampoco puede aplanar."""
    ps, _es, rs, remedios, manuel = _setup(tmp_path)
    rel = rs.create_relation(remedios.id, manuel.id, "es_madre_de").value
    ko = rs.update_relation(rel.id, {
        "relation_type": "mentor_espiritual", "description": "no debe entrar",
    })
    assert isinstance(ko, Error)
    assert "mentor_espiritual" in ko.error
    guardada = ps.active_project.relations[0]
    assert guardada.relation_type is RelationType.ES_MADRE_DE
    # Rechazo LIMPIO: no se escribió nada a medias.
    assert guardada.description == ""


# ── superficies de lectura ──────────────────────────────────────────────────


def test_beta_m2fix12_parentesco_llega_al_mapa_y_a_la_ia(tmp_path: Path):
    ps, _es, rs, remedios, manuel = _setup(tmp_path)  # noqa: F841 — _es se reusa abajo
    rs.create_relation(remedios.id, manuel.id, "es_madre_de")
    project = ps.active_project

    # 1) Arista del Mapa.
    qs = QueryService(
        entity_service=_es,
        relation_service=rs,
        source_service=SourceService(project_service=ps, store=ProjectStore()),
    )
    grafo = GraphService(
        query_service=qs, relation_service=rs, entity_service=_es
    ).build_graph()
    assert isinstance(grafo, Ok), getattr(grafo, "error", None)
    arista = grafo.value.edges[0]
    assert arista.label == "es_madre_de"
    assert arista.relation_type == "es_madre_de"

    # 2) Payload que recibe la IA — contexto narrativo.
    ctx = NarrativeContextBuilder(ps).build_for_entity(manuel.id)
    texto = str(ctx)
    assert "es_madre_de" in texto
    assert "esta_relacionado_con" not in texto

    # 3) Payload que recibe la IA — índice de la wiki (lo que navega para
    #    decidir qué canon traer).
    indice = WikiIndexService().build_index(project)
    assert isinstance(indice, Ok), getattr(indice, "error", None)
    texto_indice = str(indice.value.to_dict() if hasattr(indice.value, "to_dict") else indice.value)
    assert "es_madre_de" in texto_indice


def test_beta_m2fix12_el_riego_no_ve_un_generico_donde_hay_una_madre(tmp_path: Path):
    """Riego con proveedor falso: la madre viaja y NO como `esta_relacionado_con`.

    HONESTIDAD: el contexto de riego enumera a las vecinas por nombre y tipo de
    ENTIDAD, no por tipo de relación (`watering_service.build_watering_context`);
    eso es una carencia previa a este ticket y su fichero queda fuera de su
    alcance. Lo que aquí se garantiza es que la vecina llega y que el genérico
    aplanado ya no se cuela en el prompt.
    """
    ps, _es, rs, remedios, manuel = _setup(tmp_path)
    rs.create_relation(remedios.id, manuel.id, "es_madre_de")
    capturado: dict[str, str] = {}

    class _FakeAI:
        provider = SimpleNamespace(provider_name="test", model="m")

        def provider_unconfigured(self) -> bool:
            return False

        def run_focused_job(self, job_type, prompt, context_scope=None, progress_callback=None):
            capturado["prompt"] = prompt
            return Ok(SimpleNamespace(result={"watering": {
                "scores": {"arraigo": 50, "nutrida": 50, "iluminada": 50},
                "summary": "ok",
                "metric_explanations": {},
                "risks": [],
            }}))

    svc = WateringService(ps, ai_job_service=_FakeAI())
    assert isinstance(svc.water_entity(manuel.id), Ok)
    prompt = capturado["prompt"]
    assert "Remedios" in prompt
    assert "esta_relacionado_con" not in prompt


def test_beta_m2fix12_parentesco_no_es_contencion_en_el_grafo(tmp_path: Path):
    """Criterio 5: «Remedios es_madre_de Manuel» no la hace rama contenedora."""
    ps, _es, rs, remedios, manuel = _setup(tmp_path)
    anillo_antes = foco_rings.ring_id_for(ps.active_project, manuel.id)
    rs.create_relation(remedios.id, manuel.id, "es_madre_de")
    project = ps.active_project
    assert foco_rings.direct_containments(project, manuel.id) == []
    assert foco_rings.branch_members(project, remedios.id) == []
    assert foco_rings.contained_descendant_ids(project, remedios.id) == []
    assert foco_rings.ring_id_for(project, manuel.id) == anillo_antes


# ── vocabulario en el prompt ────────────────────────────────────────────────


def test_beta_m2fix12_el_prompt_enumera_los_tipos_validos():
    """La IA proponía `valido` porque nunca se le dijo qué valores existen."""
    for intent in ("suggest_relations", "edit_relation", "suggest_composite",
                   "chronology_walk_step"):
        prompt = system_prompt_for_intent(intent)
        assert "TIPOS DE RELACIÓN VÁLIDOS" in prompt, intent
        assert "es_madre_de" in prompt, intent
        assert "esta_casado_con" in prompt, intent
        # Los tipos OCULTOS (familia de conocimiento) no se ofrecen al modelo.
        assert "ha_recibido_pista" not in prompt, intent
