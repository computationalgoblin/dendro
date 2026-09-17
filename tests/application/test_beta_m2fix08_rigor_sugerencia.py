"""BETA2-FIX-08 (G2-13) — rigor de lo que genera la IA.

El camino de DIAGNÓSTICO (Regar/Memoria) es honesto por prompt: pide `risks` e
`issues` con kinds hueco/supuesto. El camino GENERATIVO (Sugerencias) no tenía
dónde declarar incertidumbre, el sistema le autorizaba a inventar «más allá» del
material aunque el usuario pidiera abstención, y las semillas se pintaban con una
`confidence` que era un literal del código (el mismo 0,60/0,62 para una boda
documentada que para una prisión inventada).

Estos tests fijan: marca de BASE por pieza, licencia de invención acotada,
confianza solo si la declara el modelo, tipo narrativo en el contexto de la wiki, y
que el camino honesto (riego/memoria) no cambia.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from packages.application.ai_jobs import (
    BASE_MARK_UNDECLARED,
    AIJob,
    AIJobType,
    stage_results,
)
from packages.application.command_prompts import system_prompt_for_intent
from packages.application.memory_ai_service import MemoryAIService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.narrative_memory import MemoryTargetKind
from packages.domain.project import Project

pytestmark = pytest.mark.application


def _job(job_type: AIJobType = AIJobType.SUGGEST_COMPOSITE) -> AIJob:
    return AIJob(type=job_type, prompt="Si algo no está documentado, dilo explícitamente.")


def _candidatos(payload: dict, job_type: AIJobType = AIJobType.SUGGEST_COMPOSITE) -> list[dict]:
    return stage_results(payload, _job(job_type))["candidates"]


# ── A2 · el prompt pide la marca y no contradice la abstención ────────────────


def test_beta_m2fix08_suggest_composite_pide_marca_de_base():
    p = system_prompt_for_intent("suggest_composite")

    assert "MARCA DE BASE" in p
    assert '"base": "canon|inferido|inventado"' in p
    assert "base_nota" in p
    # …y no permite maquillar una invención de inferencia.
    assert "No maquilles una invención como inferencia" in p


def test_beta_m2fix08_abstencion_del_usuario_no_queda_contradicha():
    p = system_prompt_for_intent("suggest_composite")

    # La licencia vieja era general y sin contrapeso: «plena libertad para inventar
    # más allá de él (NO es un límite)». Ahora está ACOTADA a la ficción del mundo…
    assert "plena libertad para inventar más allá de él (NO es un límite)" not in p
    assert "libertad para inventar FICCIÓN del mundo" in p
    # …y la petición de abstención del usuario deja de estar contradicha.
    assert "LÍMITE DE LA INVENCIÓN" in p
    assert "inventar ficción NO es rellenar datos" in p
    assert "PETICIÓN DEL USUARIO MANDA" in p
    assert "ABSTENTE" in p


def test_beta_m2fix08_riego_y_memoria_conservan_su_esquema():
    riego = system_prompt_for_intent("water_entity")
    memoria = system_prompt_for_intent("update_memory")

    assert '"risks"' in riego
    assert "potencial_causal" in riego
    assert "PROHIBIDO proponer entidades, relaciones, hitos" in riego
    for kind in ("contradiccion", "hueco", "pregunta_abierta", "supuesto"):
        assert kind in memoria
    assert '"issues"' in memoria
    # El recorte WIKI-13 sigue en pie: nada de secciones de CREACIÓN en el camino
    # honesto — tampoco la nueva marca de base ni el nuevo límite de invención.
    for prompt in (riego, memoria):
        assert "DATACIÓN (BETA1-J05)" not in prompt
        assert "CALIDAD Y ABSTENCIÓN" not in prompt
        assert "LÍMITE DE LA INVENCIÓN" not in prompt
        assert "MARCA DE BASE" not in prompt


# ── A1 · la marca del modelo se propaga; sin marca no se inventa nada ─────────


def test_beta_m2fix08_stage_results_propaga_la_marca_del_modelo():
    payload = {
        "hojas": [{
            "name": "Palacio de los Condes",
            "entity_type": "localizacion",
            "base": "inventado",
            "base_nota": "El canon no menciona ningún palacio en Cuéllar.",
            "confidence": "baja",
        }],
        "hitos": [{
            "title": "Boda de Cuéllar",
            "base": "canon",
            "base_nota": "Consta en la crónica del reinado.",
            "confidence": 0.95,
        }],
        "relations": [{
            "source_name": "Pedro I", "target_name": "María de Padilla",
            "base": "inferido", "base_nota": "Se deduce de la descendencia registrada.",
        }],
    }

    candidatos = _candidatos(payload)
    por_base = {c["metadata"]["base"]: c for c in candidatos}

    assert set(por_base) == {"inventado", "canon", "inferido"}
    assert por_base["inventado"]["metadata"]["base_nota"].startswith("El canon no menciona")
    # La confianza declarada SÍ se propaga y discrimina entre piezas.
    assert por_base["inventado"]["metadata"]["confianza_declarada"] is True
    assert por_base["inventado"]["confidence"] == pytest.approx(0.3)
    assert por_base["canon"]["confidence"] == pytest.approx(0.95)
    assert "confianza_declarada" not in por_base["inferido"]["metadata"]


def test_beta_m2fix08_sin_marca_no_se_inventa_confianza():
    payload = {
        "hojas": [{"name": "Alburquerque", "entity_type": "personaje"}],
        "hitos": [{"title": "Muerte en prisión"}],
    }

    candidatos = _candidatos(payload)

    assert candidatos, "el staging debe seguir produciendo semillas"
    for c in candidatos:
        # Sin declaración del modelo: base «no declarada» y CERO señal de confianza
        # (la UI no pinta porcentaje sin esta marca — criterio 6).
        assert c["metadata"]["base"] == BASE_MARK_UNDECLARED
        assert "base_nota" not in c["metadata"]
        assert "confianza_declarada" not in c["metadata"]


def test_beta_m2fix08_marca_fuera_del_vocabulario_es_no_declarada():
    payload = {"hojas": [{"name": "X", "base": "quizás", "confidence": "regular"}]}

    metadata = _candidatos(payload)[0]["metadata"]

    assert metadata["base"] == BASE_MARK_UNDECLARED
    assert "confianza_declarada" not in metadata


def test_beta_m2fix08_la_semilla_no_persiste_un_origen_falso():
    """B5: toda semilla nacía con `source: "ai_command_bar"` — barra retirada."""
    candidatos = _candidatos({"hojas": [{"name": "Alburquerque"}]})

    origen = candidatos[0]["source"]
    assert origen != "ai_command_bar"
    assert origen == f"ai_{AIJobType.SUGGEST_COMPOSITE.value}"


# ── A3 · lo diegético frente a lo meta: el TIPO viaja al contexto ─────────────


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _memoria_context(entity: NarrativeEntity) -> str:
    proj = Project(id="p", name="P")
    proj.entities.append(entity)
    ps = _FakeProjectService(active_project=proj)
    svc = MemoryAIService(ps, ai_job_service=None)
    return svc._build_context(proj, MemoryTargetKind.ENTITY, entity.id, "")


def test_beta_m2fix08_contexto_de_memoria_lleva_el_tipo_del_elemento():
    rama = NarrativeEntity(
        id="c1",
        name="Ciclo: Quién cobra la Concordia",
        entity_type=EntityType.CONTENEDOR,
        custom_metadata={"semantic_type": "arcos"},
    )
    hoja = NarrativeEntity(id="h1", name="La Posada del Ciervo", entity_type=EntityType.OBJETO)

    contexto_rama = _memoria_context(rama)
    contexto_hoja = _memoria_context(hoja)

    assert "tipo_narrativo=contenedor" in contexto_rama
    assert "AGRUPA otros elementos" in contexto_rama
    assert "arcos" in contexto_rama
    assert "tipo_narrativo=objeto" in contexto_hoja
    assert "hoja: elemento individual" in contexto_hoja


def test_beta_m2fix08_prompt_de_memoria_usa_el_tipo_narrativo():
    p = system_prompt_for_intent("update_memory")

    assert "tipo_narrativo" in p
    assert "el ente u objeto denominado" in p  # lo que NO debe volver a escribir
