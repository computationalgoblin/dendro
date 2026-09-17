"""BETA2-FIX-13 · TANDA E (application) — el vocabulario interno no
se imprime (G2-20).

De `ai_jobs` salía literalmente el botón «Editar Marta Iriarte: birth_year» que
fotografió la diseñadora en Play, y de `structural_analysis_service` salía
«(contrato §16)» dentro de la justificación que se le enseña a una novelista.

En los dos casos el DATO no cambia: cambian las etiquetas y el texto.
"""
from __future__ import annotations

from packages.application.candidate_service import (
    AI_EDITABLE_ENTITY_FIELDS,
    FIELD_LABELS,
    field_label,
    field_labels,
)


class TestEtiquetasDeCampo:
    def test_beta_m2fix13_todo_campo_editable_por_ia_tiene_etiqueta(self):
        sin_etiqueta = sorted(AI_EDITABLE_ENTITY_FIELDS - set(FIELD_LABELS))
        assert not sin_etiqueta, f"campos sin etiqueta legible: {sin_etiqueta}"

    def test_beta_m2fix13_ninguna_etiqueta_es_la_clave_interna(self):
        for clave, etiqueta in FIELD_LABELS.items():
            assert etiqueta != clave, clave
            assert "_" not in etiqueta, f"«{etiqueta}» sigue oliendo a clave interna"

    def test_beta_m2fix13_una_clave_desconocida_degrada_sin_romper(self):
        assert field_label("campo_raro_del_futuro") == "campo raro del futuro"
        assert field_label("") == "campo"
        assert field_label(None) == "campo"

    def test_beta_m2fix13_field_labels_une_en_castellano(self):
        assert field_labels(["birth_year", "entity_type"]) == "año de nacimiento, tipo"


class TestTituloDelCandidato:
    def _job(self):
        from packages.application.ai_jobs import AIJob, AIJobType

        return AIJob(type=AIJobType.EDIT_ENTITIES, prompt="lo que sea")

    def test_beta_m2fix13_titulo_de_candidato_no_filtra_claves_internas(self):
        from packages.application.ai_jobs import stage_results

        payload = {
            "entity_edits": [
                {
                    "entity_name": "Marta Iriarte",
                    "edit_fields": {"birth_year": 1931, "brief_description": "Modista."},
                    "rationale": "Consta en el registro civil citado.",
                }
            ]
        }
        # `stage_results` devuelve un dict con la lista de candidatos (dicts);
        # además del de edición añade el informe general del job.
        candidatos = stage_results(payload, self._job())["candidates"]
        candidato = next(c for c in candidatos if c["title"].startswith("Editar "))

        # Lo que se LEE: en castellano, sin claves.
        assert candidato["title"] == "Editar Marta Iriarte: año de nacimiento, descripción breve"
        assert "birth_year" not in candidato["title"]
        texto_visible = " ".join(
            str(v)
            for k, v in candidato["proposed_data"].items()
            if k in ("report",) and isinstance(v, str)
        )
        assert "birth_year" not in texto_visible
        assert "año de nacimiento" in texto_visible

        # Lo que se GUARDA: las claves internas, intactas.
        assert candidato["proposed_data"]["edit_fields"] == {
            "birth_year": 1931,
            "brief_description": "Modista.",
        }

    def test_beta_m2fix13_el_hito_tampoco_filtra_claves(self):
        from packages.application.ai_jobs import stage_results

        payload = {
            "milestone_edits": [
                {"target_name": "La riada", "edit_fields": {"year": 1956, "rationale": "x"}}
            ]
        }
        candidatos = stage_results(payload, self._job())["candidates"]
        candidato = next(c for c in candidatos if c["title"].startswith("Editar hito"))
        assert "rationale" not in candidato["title"]
        assert "justificación" in candidato["title"]
        assert set(candidato["proposed_data"]["edit_fields"]) == {"year", "rationale"}


class TestSalidaDelProveedor:
    def test_beta_m2fix13_el_markdown_se_limpia_al_estadiar(self):
        from packages.application.ai_jobs import AIJob, AIJobType, stage_results

        job = AIJob(type=AIJobType.EDIT_ENTITIES, prompt="x")
        payload = {
            "entity_edits": [
                {
                    "entity_name": "Marta",
                    "edit_fields": {"brief_description": "Una **modista** de *Cádiz*."},
                }
            ]
        }
        candidatos = stage_results(payload, job)["candidates"]
        candidato = next(c for c in candidatos if c["title"].startswith("Editar "))
        guardado = candidato["proposed_data"]["edit_fields"]["brief_description"]
        assert guardado == "Una modista de Cádiz."


class TestJustificacionEstructural:
    """Mismo montaje que `tests/application/test_structural_analysis.py`."""

    def _servicio_con_excepcion(self):
        from dataclasses import dataclass

        from packages.application.causal_potency import set_basal_potency
        from packages.application.structural_analysis_service import StructuralAnalysisService
        from packages.application.world_layer_causal import set_causal_rank
        from packages.domain.entity import NarrativeEntity
        from packages.domain.project import Project
        from packages.domain.relation import NarrativeRelation, RelationType
        from packages.domain.world_layer import WorldLayer

        @dataclass
        class _FakePS:
            active_project: Project

        proyecto = Project(id="p", name="P")
        anillos = []
        for i, rank in enumerate((1, 2, 3), start=1):
            capa = WorldLayer(id=f"r{i}", name=f"Anillo{i}")
            set_causal_rank(capa, rank)
            proyecto.world_layers.append(capa)
            anillos.append(capa.id)

        abajo = NarrativeEntity(id="sierva", name="La imprenta clandestina")
        abajo.layer_ids = [anillos[2]]
        set_basal_potency(abajo, 90)
        arriba = NarrativeEntity(id="reina", name="El Concilio")
        arriba.layer_ids = [anillos[0]]
        proyecto.entities.extend([abajo, arriba])
        proyecto.relations.append(
            NarrativeRelation(
                id="rel1",
                source_id="sierva",
                target_id="reina",
                relation_type=RelationType.GOBIERNA,  # no causal
            )
        )
        proyecto.touch()
        return StructuralAnalysisService(_FakePS(active_project=proyecto))

    def test_beta_m2fix13_justificacion_estructural_no_cita_el_contrato(self):
        servicio = self._servicio_con_excepcion()
        hallazgos = [
            f for f in servicio.analyze().value if f.kind == "ascending_exception"
        ]
        assert hallazgos, "el detector dejó de encontrar la excepción ascendente"
        hallazgo = hallazgos[0]

        texto = " ".join(hallazgo.reasons())
        assert "§" not in texto, "sigue citando la especificación por número de sección"
        assert "contrato" not in texto.lower()
        # «Apalancamiento» puede aparecer, pero EXPLICADO — nunca a pelo.
        if "apalancamiento" in texto.lower():
            assert "algo pequeño que mueve algo grande" in texto.lower()

        # El DATO no cambia: lo consume `candidate_service` y lo fijan otros tests.
        assert hallazgo.proposed_data["exception_kind"] == "apalancamiento"
