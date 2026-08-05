"""Servicio de riego del jardín narrativo (BETA2-FOCO).

Estados del ciclo (``WateringStatus``) DERIVADOS perezosamente — nunca
persistidos por entidad — a partir de:

- ``Project.watering_paused_entity_ids`` (Secadas: fuera del ciclo, jamás se
  invalidan solas; vuelven con ``resume``/Cultivar pasando a Falta regar);
- el último ``WateringDiagnostic`` exitoso frente a los ``updated_at`` de la
  propia entidad, sus relaciones, sus vecinas directas (incluida la rama
  contenedora, que es vecina por ``contiene``) y las de 2º grado con relevancia
  alta (CRITICO/ALTO); más la firma de vecindario guardada en
  ``context_manifest["neighbor_ids"]``, que detecta altas y bajas de vecinas
  que los timestamps no pueden ver.

Derivar (en lugar de enganchar hooks en cada mutación) hace que la invalidación
funcione igual desde cualquier host (desktop, CLI, tests) y que la "lectura
antigua atenuada" salga gratis: si el diagnóstico quedó obsoleto se conserva en
``latest`` con ``stale=True``. Secar y Cultivar NUNCA consumen IA.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.application.ai_privacy import REDACTED_NAME, is_withheld_from_ai
from packages.application.foco_zones import (
    classify_containers,
    classify_milestones,
    classify_neighbors,
)
from packages.domain.entity import CanonState, NarrativeEntity, NarrativeImportance
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.project import Project
from packages.domain.relation import RelationType
from packages.domain.project_chronology import format_year_with_era
from packages.domain.result import Error, Ok, Result
from packages.domain.watering import WateringCostClass, WateringDiagnostic, WateringStatus

#: BETA-AUDIT-11 — cuántos diagnósticos de riego se conservan POR ENTIDAD.
#:
#: Antes no había techo y los diagnósticos eran el 41 % del proyecto de ejemplo (el
#: canon real ocupaba el 16 %). Cinco es un compromiso: la pestaña Cultivo enseña
#: evolución —no solo el último riego— y el estado del jardín únicamente mira el
#: último éxito y el último fallo, así que podar más atrás no cambia nada visible.
MAX_DIAGNOSTICS_PER_ENTITY = 5

_EXCLUDED_CANON = frozenset({CanonState.ARCHIVADO, CanonState.DESCARTADO})
# BETA-MULTIAGENT2-FIX-05: `_HIGH_IMPORTANCE` se retiró con la caducidad de 2º grado
# de `_is_stale` (ver su docstring). La relevancia narrativa sigue viva en
# `_IMPORTANCE_SCORE` y ahora también ordena la cola de sed (watering_attention).

# BETA-MULTIAGENT2-FIX-05 (G2-05): vías de dependencia por las que Regar propaga
# «Falta regar». Regar NO cambia canon (reescribe una página de wiki), así que solo
# se marca a quien depende de ella DE VERDAD: quien la @menciona y quien la cita en su
# propia página. La vía `relacion` —una manta topológica sobre todo el vecindario— se
# reserva a los cambios de CANON (update_entity/update_relation/accept_candidate…),
# que son los emisores legítimos del motor de impacto.
_ONLY_VIA_REGAR = frozenset({"mencion", "cita_memoria"})

# Misma aproximación que prompt_budget (~3.5 chars/token).
_CHARS_PER_TOKEN = 3.5
# Umbrales de clase de coste por tokens estimados de entrada (centralizados aquí
# para recalibrar en un solo sitio; el coste real no se mide — es ESTIMADO).
_TOKENS_BAJO_MAX = 6_000
_TOKENS_MEDIO_MAX = 15_000
# Un lote grande eleva la clase aunque cada entidad sea barata.
_BATCH_MEDIO_MIN = 20
_BATCH_ALTO_MIN = 60

# Relevancia (0-100) derivada de la importancia narrativa que FIJA EL USUARIO.
_IMPORTANCE_SCORE = {
    NarrativeImportance.CRITICO.value: 95,
    NarrativeImportance.ALTO.value: 75,
    NarrativeImportance.MEDIO.value: 50,
    NarrativeImportance.BAJO.value: 30,
    NarrativeImportance.MENOR.value: 15,
}

_ZONE_HEADERS = (("raices", "RAÍCES"), ("entorno", "ENTORNO"), ("brotes", "BROTES"))

_UNCONFIGURED_AI_MESSAGE = (
    "IA no configurada: define las variables de entorno NARRATIVE_AI_PROVIDER, "
    "NARRATIVE_AI_BASE_URL, NARRATIVE_AI_API_KEY y NARRATIVE_AI_MODEL (y reinicia "
    "la app). No se genera contenido simulado."
)

# BETA2-WIKI-13: métricas cuyas Sugerencias pasan por un ANÁLISIS DE INTENCIÓN previo que
# decide el mix de output (hojas/ramas/relaciones/hitos/ediciones). El resto (nutrida,
# calidad) mantiene el job fijo por métrica (edit_entities).
_INTENT_METRICS = frozenset({"arraigo", "iluminada"})

# Sugerir X → job existente + zona donde germina la Semilla (decisión de producto).
# El hint viaja en context_scope y ai_jobs lo copia a candidate.metadata.
_SUGGEST_SPECS: dict[str, dict[str, str]] = {
    "arraigo": {
        "job": "suggest_relations",
        "zone": "raices",
        "bias": (
            "Sugiere ARRAIGO para la entidad en foco: relaciones, causas, contextos "
            "superiores o vínculos con hitos y ramas que hagan verosímil su existencia."
        ),
    },
    "nutrida": {
        "job": "edit_entities",
        "zone": "drawer",
        "bias": (
            "Sugiere NUTRICIÓN: ediciones del cuerpo/campos de la entidad en foco que "
            "desarrollen su interior y la integren mejor en su Entorno."
        ),
    },
    "iluminada": {
        "job": "generate_entities",
        "zone": "brotes",
        "bias": (
            "Sugiere ILUMINACIÓN: entidades o desarrollos derivados (Brotes) que nazcan "
            "de la entidad en foco y proyecten sus consecuencias."
        ),
    },
    "calidad": {
        "job": "edit_entities",
        "zone": "drawer",
        "bias": (
            "Sugiere CALIDAD NARRATIVA: ediciones de texto que mejoren claridad, tono y "
            "fuerza narrativa de la entidad en foco."
        ),
    },
}


@dataclass(frozen=True)
class WateringEstimate:
    """Estimación previa a la autorización: nº de entidades, tokens y clase de coste."""

    entity_count: int
    estimated_input_tokens: int
    cost_class: str


@dataclass(frozen=True)
class WateringStatusReport:
    """Estado derivado de una entidad en el ciclo de riego.

    ``stale=True`` = hubo diagnóstico pero quedó obsoleto; la última lectura se
    conserva en ``latest`` para mostrarla atenuada. ``last_error`` = último
    fallo de riego trazable (lotes) posterior al último éxito.
    """

    status: str
    latest: WateringDiagnostic | None
    stale: bool = False
    last_error: str = ""


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _newer(candidate: datetime, reference: datetime) -> bool:
    return _aware(candidate) > _aware(reference)


class WateringService:
    """Riego sin IA: estados derivados, ciclo Secar/Cultivar e historial.

    ``ai_job_service`` queda inyectado para el riego con IA (FOCO-05/07); todo
    lo de este módulo funciona con él a ``None`` — la app sin proveedor puede
    ver estados, secar y cultivar, pero no regar.
    """

    def __init__(
        self,
        project_service: Any,
        ai_job_service: Any = None,
        history_service: Any = None,
        memory_ai_service: Any = None,
        impact_service: Any = None,
        navigator: Any = None,
        intent_service: Any = None,
        memory_service: Any = None,
    ) -> None:
        self.project_service = project_service
        self.ai_job_service = ai_job_service
        self.history_service = history_service
        # BETA2-WIKI-13: unificación de frescura — el estado de riego refleja también la
        # frescura de la PÁGINA de Memoria (si una relacionada la marcó Falta regar, el chip
        # del jardín también lo muestra: se mueven juntos). Opcional: sin él, riego normal.
        self.memory_service = memory_service
        # BETA2-MEM-07: Regar v2 — al regar, el mismo flujo autorizado actualiza la
        # Memoria editorial de la entidad (auto-aplica). Opcional: sin él, riego normal.
        self.memory_ai_service = memory_ai_service
        # BETA2-WIKI-06: tras reescribir la página, propaga Falta regar a las páginas
        # RELACIONADAS (potencialidad causal). Opcional: sin él, no hay propagación.
        self.impact_service = impact_service
        # BETA2-WIKI-08: las Sugerencias navegan la wiki (WikiNavigator) para armar
        # contexto coherente a partir de la petición del usuario. Opcional.
        self.navigator = navigator
        # BETA2-WIKI-13: análisis de intención previo (arraigo/iluminada) que decide el
        # mix de output. Opcional: sin él, esas métricas caen a su job por defecto.
        self.intent_service = intent_service
        self._cache_key: tuple[str, int] | None = None
        self._cache: dict[str, WateringStatusReport] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_project(self) -> Result[Project, str]:
        service = self.project_service
        project = getattr(service, "active_project", None) if service is not None else None
        if project is None:
            return Error("No active project")
        return Ok(project)

    def _ensure_cache(self, project: Project) -> None:
        key = (project.id, getattr(project, "_index_revision", 0))
        if key != self._cache_key:
            self._cache_key = key
            self._cache = {}

    def _record_history(
        self,
        event_type: str,
        entity_id: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self.history_service is None:
            return
        entry = self.history_service.make_entry(
            event_type,
            affected_entity_id=entity_id,
            description=description,
            change_origin="jardin_riego",
            operation=event_type,
            metadata=metadata or {},
        )
        self.history_service.record(entry)

    @staticmethod
    def _diagnostics_for(project: Project, entity_id: str) -> list[WateringDiagnostic]:
        entries = [d for d in project.watering_diagnostics if d.entity_id == entity_id]
        entries.sort(key=lambda d: _aware(d.created_at))
        return entries

    @staticmethod
    def _direct_neighbor_ids(project: Project, entity_id: str) -> set[str]:
        neighbors: set[str] = set()
        for relation in project.relations_for(entity_id):
            other_id = relation.target_id if relation.source_id == entity_id else relation.source_id
            if other_id != entity_id:
                neighbors.add(other_id)
        return neighbors

    def _is_stale(
        self, project: Project, entity: NarrativeEntity, diagnostic: WateringDiagnostic
    ) -> bool:
        """Caduca el diagnóstico cuando cambió el canon PROPIO de la entidad.

        BETA-MULTIAGENT2-FIX-05 (G2-05, tercera vía de invalidación). Hasta aquí,
        editar la ficha de CUALQUIER vecina —o de una de 2º grado de relevancia alta—
        caducaba un diagnóstico recién pagado. Era el mecanismo que mantenía sediento
        el mundo real del beta (las 4 entidades regadas de la directora de arte, incluida
        la única cuya página seguía `Regada`) y el que hace que «el contador de trabajo
        pendiente suba cuando trabajo» (TDA-07). Ya no invalida.

        Lo que SÍ sigue caducando, porque es canon de esta entidad:
        - su propia ficha se editó después del riego,
        - una relación SUYA se editó después (la relación es canon compartido),
        - su vecindario cambió de FORMA (altas/bajas respecto al manifiesto del riego,
          o una vecina borrada): el contexto que se envió a la IA ya no existe.

        Lo que ya NO caduca aquí: el CONTENIDO de una vecina. Esa señal no se pierde —
        viaja por el camino honesto: un cambio de canon en la vecina dispara
        ``NarrativeImpactService``, que marca `Falta regar` la PÁGINA de quien depende
        de ella, y la unificación de frescura (WIKI-13, ``_memory_falta_regar``) lo
        refleja en el jardín. La diferencia es que ahí se marca a quien depende de
        verdad, no a todo el vecindario topológico.
        """
        watered_at = diagnostic.created_at
        if _newer(entity.updated_at, watered_at):
            return True
        direct: set[str] = set()
        for relation in project.relations_for(entity.id):
            if _newer(relation.updated_at, watered_at):
                return True
            other_id = relation.target_id if relation.source_id == entity.id else relation.source_id
            if other_id != entity.id:
                direct.add(other_id)
        manifest_ids = diagnostic.context_manifest.get("neighbor_ids")
        if isinstance(manifest_ids, list) and {str(v) for v in manifest_ids} != direct:
            return True  # altas o bajas de vecinas desde el último riego
        for other_id in direct:
            if project.entity_by_id(other_id) is None:
                return True  # vecina borrada sin dejar rastro comparable
        return False

    def _compute_status(self, project: Project, entity: NarrativeEntity) -> WateringStatusReport:
        entries = self._diagnostics_for(project, entity.id)
        successes = [d for d in entries if not d.error]
        failures = [d for d in entries if d.error]
        latest = successes[-1] if successes else None
        last_error = ""
        if failures:
            last_failure = failures[-1]
            if latest is None or _newer(last_failure.created_at, latest.created_at):
                last_error = last_failure.error
        if entity.canon_state == CanonState.FANTASMA:
            # Borrador interno: sin métricas ni ciclo de riego.
            return WateringStatusReport(WateringStatus.FALTA_REGAR.value, None, False, "")
        if entity.id in project.watering_paused_entity_ids:
            return WateringStatusReport(WateringStatus.SECADA.value, latest, False, last_error)
        if last_error:
            # Un intento de riego fallido deja la entidad Falta regar con causa
            # trazable; si había lectura previa se conserva atenuada.
            return WateringStatusReport(
                WateringStatus.FALTA_REGAR.value, latest, latest is not None, last_error
            )
        if latest is None:
            return WateringStatusReport(WateringStatus.FALTA_REGAR.value, None, False, "")
        if self._is_stale(project, entity, latest):
            return WateringStatusReport(WateringStatus.FALTA_REGAR.value, latest, True, "")
        # BETA2-WIKI-13: unificación de frescura. El diagnóstico está vigente, pero si la
        # PÁGINA de Memoria quedó Falta regar (p. ej. al regar una entidad relacionada, que
        # propaga por potencialidad causal), el jardín también lo refleja: los dos ejes se
        # mueven juntos y un solo Regar los revive. SECADA/FANTASMA ya salieron arriba.
        if self._memory_falta_regar(entity.id):
            return WateringStatusReport(WateringStatus.FALTA_REGAR.value, latest, True, "")
        return WateringStatusReport(WateringStatus.REGADA.value, latest, False, "")

    def _memory_falta_regar(self, entity_id: str) -> bool:
        """True si la página de Memoria de la entidad está Falta regar (unificación)."""
        svc = self.memory_service
        if svc is None:
            return False
        try:
            got = svc.get_memory(MemoryTargetKind.ENTITY, entity_id)
        except Exception:  # noqa: BLE001 — la Memoria nunca debe romper el estado de riego
            return False
        block = got.value if isinstance(got, Ok) else None
        return block is not None and block.freshness == MemoryFreshness.FALTA_REGAR

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------

    def status_of(self, entity_id: str) -> Result[WateringStatusReport, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        entity = project.entity_by_id(entity_id)
        if entity is None:
            return Error(f"Entidad no encontrada: {entity_id}")
        self._ensure_cache(project)
        cached = self._cache.get(entity_id)
        if cached is None:
            cached = self._compute_status(project, entity)
            self._cache[entity_id] = cached
        return Ok(cached)

    def statuses_for(
        self, entity_ids: list[str] | None = None
    ) -> Result[dict[str, WateringStatusReport], str]:
        """Mapa id→estado en una pasada (Lente Jardín). Ids desconocidos se omiten."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        self._ensure_cache(project)
        targets = (
            [entity.id for entity in project.entities] if entity_ids is None else list(entity_ids)
        )
        report: dict[str, WateringStatusReport] = {}
        for entity_id in targets:
            entity = project.entity_by_id(entity_id)
            if entity is None:
                continue
            cached = self._cache.get(entity_id)
            if cached is None:
                cached = self._compute_status(project, entity)
                self._cache[entity_id] = cached
            report[entity_id] = cached
        return Ok(report)

    @staticmethod
    def prune_diagnostics(project, entity_id: str) -> int:
        """BETA-AUDIT-11: deja solo los ``MAX_DIAGNOSTICS_PER_ENTITY`` más recientes.

        No había ninguna poda: cada riego apilaba una entrada más y el fichero crecía
        sin techo (41 % del proyecto de ejemplo, frente a un 16 % de canon real). Se
        conserva un tramo corto porque la pestaña Cultivo enseña evolución, no solo el
        último diagnóstico.

        Es estático a propósito: la migración de esquema lo reutiliza sin instanciar el
        servicio. Devuelve cuántas entradas se retiraron.
        """
        entradas = [d for d in project.watering_diagnostics if d.entity_id == entity_id]
        if len(entradas) <= MAX_DIAGNOSTICS_PER_ENTITY:
            return 0
        # Ordena por fecha y no por posición: los diagnósticos de la IA pueden llegar
        # fuera de orden si dos riegos en lote terminan cruzados.
        entradas.sort(key=lambda d: str(d.created_at or ""))
        sobran = {id(d) for d in entradas[:-MAX_DIAGNOSTICS_PER_ENTITY]}
        project.watering_diagnostics = [
            d for d in project.watering_diagnostics if id(d) not in sobran
        ]
        return len(sobran)

    @staticmethod
    def drop_orphan_diagnostics(project) -> int:
        """Retira los diagnósticos de entidades que ya no existen.

        Borrar una entidad no se los llevaba: el ejemplo tenía 15 ``entity_id``
        distintos con diagnóstico para 10 entidades vivas. Nadie los ve y viajan en
        cada guardado, cada copia `.bak` y cada instantánea de deshacer.
        """
        vivos = {e.id for e in project.entities}
        antes = len(project.watering_diagnostics)
        project.watering_diagnostics = [
            d for d in project.watering_diagnostics if d.entity_id in vivos
        ]
        return antes - len(project.watering_diagnostics)

    def history_for(self, entity_id: str) -> Result[list[WateringDiagnostic], str]:
        """Historial de riegos (éxitos y fallos), el más reciente primero."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        if project.entity_by_id(entity_id) is None:
            return Error(f"Entidad no encontrada: {entity_id}")
        return Ok(list(reversed(self._diagnostics_for(project, entity_id))))

    # ------------------------------------------------------------------
    # Ciclo Secar / Cultivar (sin IA)
    # ------------------------------------------------------------------

    def pause(self, entity_id: str) -> Result[None, str]:
        """Secar: saca la entidad del ciclo de riego. Conserva la lectura previa."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        entity = project.entity_by_id(entity_id)
        if entity is None:
            return Error(f"Entidad no encontrada: {entity_id}")
        if entity.canon_state == CanonState.FANTASMA:
            return Error("Un nodo fantasma no participa del ciclo de riego")
        if entity_id in project.watering_paused_entity_ids:
            return Ok(None)  # idempotente, sin historial duplicado
        project.watering_paused_entity_ids.append(entity_id)
        project.touch()
        self._record_history(
            "secado_entidad", entity_id, f"Entidad secada (fuera del ciclo de riego): {entity.name}"
        )
        return Ok(None)

    def resume(self, entity_id: str) -> Result[None, str]:
        """Cultivar: devuelve la entidad al ciclo vivo pasando a Falta regar."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        entity = project.entity_by_id(entity_id)
        if entity is None:
            return Error(f"Entidad no encontrada: {entity_id}")
        if entity_id not in project.watering_paused_entity_ids:
            return Error("La entidad no está secada")
        project.watering_paused_entity_ids.remove(entity_id)
        # El contrato de producto exige volver como Falta regar aunque nada
        # cambiara mientras dormía: el touch de la entidad lo garantiza.
        entity.touch()
        project.touch()
        self._record_history(
            "cultivo_entidad", entity_id, f"Entidad cultivada (vuelve al ciclo): {entity.name}"
        )
        return Ok(None)

    # ------------------------------------------------------------------
    # Registro de diagnósticos (lo invoca el riego IA — FOCO-05/07)
    # ------------------------------------------------------------------

    def register_diagnostic(
        self, diagnostic: WateringDiagnostic
    ) -> Result[WateringDiagnostic, str]:
        """Persiste un diagnóstico (éxito o fallo trazable de lote) con historial.

        No toca canon: solo la colección de riego del proyecto. Completa la
        firma de vecindario del manifest si el llamante no la aportó (permite
        detectar luego altas/bajas de vecinas).
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        entity = project.entity_by_id(diagnostic.entity_id)
        if entity is None:
            return Error(f"Entidad no encontrada: {diagnostic.entity_id}")
        if entity.canon_state == CanonState.FANTASMA:
            return Error("Un nodo fantasma no participa del ciclo de riego")
        diagnostic.context_manifest.setdefault(
            "neighbor_ids", sorted(self._direct_neighbor_ids(project, entity.id))
        )
        project.watering_diagnostics.append(diagnostic)
        self.prune_diagnostics(project, diagnostic.entity_id)
        project.touch()
        if diagnostic.error:
            self._record_history(
                "riego_entidad",
                entity.id,
                f"Riego fallido de {entity.name}: {diagnostic.error}",
                {"error": diagnostic.error, "origin": diagnostic.origin},
            )
        else:
            self._record_history(
                "riego_entidad",
                entity.id,
                f"Entidad regada ({diagnostic.origin}): {entity.name}",
                {"scores": dict(diagnostic.scores), "cost_class": diagnostic.cost_class},
            )
        return Ok(diagnostic)

    # ------------------------------------------------------------------
    # Riego con IA (autorizado por la UI antes de llegar aquí) — FOCO-05
    # ------------------------------------------------------------------

    @staticmethod
    def _cost_class_for_tokens(tokens: int) -> str:
        if tokens <= _TOKENS_BAJO_MAX:
            return WateringCostClass.BAJO.value
        if tokens <= _TOKENS_MEDIO_MAX:
            return WateringCostClass.MEDIO.value
        return WateringCostClass.ALTO.value

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        cleaned = " ".join(str(text or "").split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1] + "…"

    def build_watering_context(self, entity_id: str) -> Result[dict[str, Any], str]:
        """Contexto COMPACTO por entidad: ficha + zonas + hitos + última lectura.

        Nunca el proyecto entero (decisión de coste del spec): lo que se envía
        es la ficha de la entidad, sus Raíces/Entorno/Brotes con los fantasmas
        marcados, su anillo/rama y el resumen del último diagnóstico si existe.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        entity = project.entity_by_id(entity_id)
        if entity is None:
            return Error(f"Entidad no encontrada: {entity_id}")
        if entity.canon_state == CanonState.FANTASMA:
            return Error("Un nodo fantasma no participa del ciclo de riego")
        # WS-B: los secretos no se comparten con la IA. Si el foco es reservado, se rehúsa
        # (su contenido nunca sale al proveedor) en vez de enviarlo redactado e inútil.
        if is_withheld_from_ai(entity):
            return Error(
                "Esta entidad es reservada (visibilidad secreta): su contenido no se comparte "
                "con la IA. Cambia su visibilidad para regarla o pedir sugerencias."
            )

        layers_by_id = {layer.id: layer for layer in project.world_layers}
        layer_names = [
            layers_by_id[layer_id].name
            for layer_id in entity.layer_ids or []
            if layer_id in layers_by_id
        ]
        # BETA-MULTIAGENT-FIX-03 (G-03): los años viajan con su traducción a era
        # («año 2140 (Segunda Era, año 940)») para que la IA no compare escalas.
        chrono = getattr(project, "project_chronology", None)
        lines: list[str] = [
            f"ENTIDAD EN FOCO: {entity.name} (tipo: {entity.entity_type.value})",
            f"Relevancia narrativa (fijada por el usuario): {entity.narrative_importance.value}",
            f"Nivel de desarrollo: {entity.development_level.value}",
        ]
        if layer_names:
            lines.append(f"Anillo(s): {', '.join(layer_names)}")
        if entity.birth_year is not None or entity.death_year is not None:
            birth = (
                format_year_with_era(chrono, entity.birth_year)
                if entity.birth_year is not None
                else "abierto"
            )
            death = (
                format_year_with_era(chrono, entity.death_year)
                if entity.death_year is not None
                else "abierto"
            )
            lines.append(f"Lapso: {birth} → {death}")
        if entity.brief_description:
            lines.append(f"Descripción breve: {self._clip(entity.brief_description, 400)}")
        if entity.extended_description:
            lines.append(f"Descripción extendida: {self._clip(entity.extended_description, 900)}")
        if entity.tags:
            lines.append(f"Etiquetas: {', '.join(entity.tags[:10])}")

        zones = classify_neighbors(project, entity_id)
        neighbor_entity_ids: list[str] = []
        # BETA2-FOCO-22: las contenedoras ya no viajan como satélites de zona —
        # se enumeran aparte para que la IA no pierda la pertenencia a rama.
        containers = classify_containers(project, entity_id)
        if containers:
            names = []
            for container in containers:
                other = project.entity_by_id(container.entity_id)
                if other is not None:
                    neighbor_entity_ids.append(other.id)
                    names.append(REDACTED_NAME if is_withheld_from_ai(other) else other.name)
            if names:
                lines.append(f"RAMA CONTENEDORA: {' › '.join(names[:3])}")
        for zone_key, header in _ZONE_HEADERS:
            neighbors = zones.get(zone_key, [])
            lines.append(f"{header}:")
            if not neighbors:
                lines.append("- (vacío)")
                continue
            for neighbor in neighbors:
                other = project.entity_by_id(neighbor.entity_id)
                if other is None:
                    continue
                neighbor_entity_ids.append(other.id)
                if is_withheld_from_ai(other):
                    # WS-B: vecina reservada — no se filtra su nombre ni su contenido a la IA.
                    lines.append("- [entidad reservada]")
                    continue
                ghost_mark = (
                    " [fantasma/no-canon: intención, no sostén]" if neighbor.is_ghost else ""
                )
                brief = self._clip(other.brief_description, 160)
                detail = f" — {brief}" if brief else ""
                lines.append(f"- {other.name} ({other.entity_type.value}){ghost_mark}{detail}")

        milestones_by_id = {milestone.id: milestone for milestone in project.causal_milestones}
        milestone_zones = classify_milestones(project, entity_id)
        milestone_lines: list[str] = []
        for zone_key, header in _ZONE_HEADERS:
            for milestone_id in milestone_zones.get(zone_key, []):
                milestone = milestones_by_id.get(milestone_id)
                if milestone is None:
                    continue
                year = format_year_with_era(chrono, milestone.year)
                milestone_lines.append(f"- [{header.lower()}] {milestone.title} ({year})")
        if milestone_lines:
            lines.append("HITOS VINCULADOS:")
            lines.extend(milestone_lines)

        previous = [d for d in self._diagnostics_for(project, entity_id) if not d.error]
        if previous:
            last = previous[-1]
            # BETA2-WIKI-13: no eco de 'relevancia' en los scores — la fija el usuario y el
            # prompt de riego prohíbe evaluarla (aparecía y contradecía la instrucción).
            echo_scores = {k: v for k, v in last.scores.items() if k != "relevancia"}
            lines.append(
                "ÚLTIMO RIEGO ("
                + last.created_at.date().isoformat()
                + f"): {self._clip(last.summary, 300)} | scores: {echo_scores}"
            )

        text = "\n".join(lines)
        estimated_tokens = max(1, math.ceil(len(text) / _CHARS_PER_TOKEN))
        return Ok(
            {
                "text": text,
                "entity_ids": [entity_id, *neighbor_entity_ids],
                "neighbor_ids": sorted(self._direct_neighbor_ids(project, entity_id)),
                "estimated_tokens": estimated_tokens,
            }
        )

    def estimate(self, entity_ids: list[str]) -> Result[WateringEstimate, str]:
        """Estimación para la autorización previa. Ids no elegibles se omiten."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        total_tokens = 0
        count = 0
        worst = WateringCostClass.BAJO.value
        order = [
            WateringCostClass.BAJO.value,
            WateringCostClass.MEDIO.value,
            WateringCostClass.ALTO.value,
        ]
        for entity_id in entity_ids:
            context = self.build_watering_context(entity_id)
            if isinstance(context, Error):
                continue
            tokens = int(context.value["estimated_tokens"])
            total_tokens += tokens
            count += 1
            entity_class = self._cost_class_for_tokens(tokens)
            if order.index(entity_class) > order.index(worst):
                worst = entity_class
        if count >= _BATCH_ALTO_MIN:
            worst = WateringCostClass.ALTO.value
        elif count >= _BATCH_MEDIO_MIN and worst == WateringCostClass.BAJO.value:
            worst = WateringCostClass.MEDIO.value
        return Ok(WateringEstimate(count, total_tokens, worst))

    def water_entity(
        self,
        entity_id: str,
        *,
        origin: str = "single",
        progress_callback: Any = None,
        batch_ids: list[str] | None = None,
    ) -> Result[WateringDiagnostic, str]:
        """Regar: diagnóstico IA persistente. JAMÁS genera Semillas ni toca canon.

        La autorización visible (qué se envía, coste) es responsabilidad del
        host ANTES de llamar aquí; sin proveedor real este método falla claro.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        entity = project.entity_by_id(entity_id)
        if entity is None:
            return Error(f"Entidad no encontrada: {entity_id}")
        if entity.canon_state == CanonState.FANTASMA:
            return Error("Un nodo fantasma no participa del ciclo de riego")
        if entity_id in project.watering_paused_entity_ids:
            return Error(
                "La entidad está secada: usa Cultivar para devolverla al ciclo antes de regar"
            )
        if self.ai_job_service is None or self.ai_job_service.provider_unconfigured():
            return Error(_UNCONFIGURED_AI_MESSAGE)

        context = self.build_watering_context(entity_id)
        if isinstance(context, Error):
            return context
        ctx = context.value
        prompt = (
            ctx["text"] + "\n\nRiega esta entidad: evalúa arraigo, nutrida e iluminada (0-100) y "
            "devuelve SOLO el JSON del diagnóstico."
        )
        result = self.ai_job_service.run_focused_job(
            "water_entity",
            prompt,
            context_scope={"entity_id": entity_id, "watering": True},
            progress_callback=progress_callback,
        )
        if isinstance(result, Error):
            return result
        staged = getattr(result.value, "result", {}) or {}
        watering = staged.get("watering")
        if not watering:
            return Error(
                str(
                    staged.get("watering_error")
                    or "El modelo no devolvió un diagnóstico de riego válido"
                )
            )

        scores = dict(watering.get("scores") or {})
        # Relevancia: SIEMPRE la del usuario; cualquier valor de la IA fue descartado.
        scores["relevancia"] = _IMPORTANCE_SCORE.get(entity.narrative_importance.value, 50)
        # BETA2-STRUCT-09: la IA atribuye la POTENCIALIDAD DE PROPAGACIÓN CAUSAL de la entidad
        # (semántica, por su naturaleza). Se guarda en custom_metadata (§14 potencia basal); el
        # detector estructural la lee para proponer reubicaciones de anillo. Se persiste con el
        # proyecto (register_diagnostic hace touch). Opcional: si la IA no la devolvió, no toca.
        potencial = watering.get("potencial_causal")
        if potencial is not None:
            from packages.application.causal_potency import set_basal_potency

            set_basal_potency(entity, int(potencial))
        provider = getattr(self.ai_job_service, "provider", None)
        provider_name = str(getattr(provider, "provider_name", "") or "")
        model = str(getattr(provider, "model", "") or os.environ.get("NARRATIVE_AI_MODEL", ""))
        tokens = int(ctx["estimated_tokens"])
        diagnostic = WateringDiagnostic(
            entity_id=entity_id,
            scores=scores,
            summary=str(watering.get("summary", "")),
            metric_explanations=dict(watering.get("metric_explanations") or {}),
            risks=list(watering.get("risks") or []),
            context_manifest={
                "entity_ids": list(ctx["entity_ids"]),
                "neighbor_ids": list(ctx["neighbor_ids"]),
                "estimated_tokens": tokens,
            },
            provider=provider_name,
            model=model,
            cost_class=self._cost_class_for_tokens(tokens),
            origin=origin,
            resulting_status=WateringStatus.REGADA.value,
        )
        registered = self.register_diagnostic(diagnostic)
        # BETA2-MEM-07: Regar v2 — dentro de la MISMA autorización, actualiza la
        # Memoria editorial de la entidad (auto-aplica), solo si hace falta.
        if isinstance(registered, Ok):
            self._update_memory_on_watering(
                entity_id, progress_callback=progress_callback, batch_ids=batch_ids
            )
        return registered

    def _update_memory_on_watering(
        self,
        entity_id: str,
        *,
        progress_callback: Any = None,
        batch_ids: list[str] | None = None,
    ) -> None:
        """Regar v2: genera/actualiza la Memoria del elemento regado (per-entidad).

        Solo corre donde hace falta (sin Memoria o Falta regar/Secada): no regenera
        una Memoria ya vigente. Nunca rompe el riego (efecto derivado, best-effort).
        """
        svc = self.memory_ai_service
        if svc is None:
            return
        try:
            mem_svc = getattr(svc, "memory_service", None)
            if mem_svc is not None:
                got = mem_svc.get_memory(MemoryTargetKind.ENTITY, entity_id)
                block = got.value if isinstance(got, Ok) else None
                if block is not None and block.freshness == MemoryFreshness.REGADA:
                    return  # ya vigente → no re-generar (coste acotado)
            res = svc.update_memory(
                MemoryTargetKind.ENTITY, entity_id, mode="regar", progress_callback=progress_callback
            )
            # BETA2-WIKI-06: reescrita la página, marca Falta regar las que DEPENDEN
            # de ella de verdad (no la propia).
            if isinstance(res, Ok) and self.impact_service is not None:
                # BETA-MULTIAGENT-FIX-01 (G-01): los miembros del lote en curso se
                # excluyen — sin esto se marcaban Falta regar entre sí y el lote
                # nunca acababa verde (4/4 testers del beta multi-agente).
                # BETA-MULTIAGENT2-FIX-05 (G2-05): además, la propagación desde Regar
                # va SOLO por dependencia real (`_ONLY_VIA_REGAR`). Regar no cambia
                # canon: reescribe una página de wiki. Marcar por `relacion` degradaba
                # páginas vigentes de vecinas regadas en otra autorización, así que dos
                # vecinas jamás podían estar verdes a la vez y el jardín no llegaba a su
                # propio estado sano (beta ronda 2, ART-06: 4 riegos → 0 verdes).
                self.impact_service.propagate_change(
                    MemoryTargetKind.ENTITY,
                    entity_id,
                    cause_hint="regar",
                    include_self=False,
                    exclude_ids=frozenset(str(x) for x in (batch_ids or []) if x),
                    only_via=_ONLY_VIA_REGAR,
                )
        except Exception:  # noqa: BLE001 — la Memoria nunca debe romper el riego
            pass

    # ------------------------------------------------------------------
    # Sugerir X → Semillas con hint de zona (FOCO-06)
    # ------------------------------------------------------------------

    def build_suggestion_request(
        self, entity_id: str, metric: str, peticion: str = ""
    ) -> Result[dict[str, Any], str]:
        """Prepara (SIN ejecutar) la petición de Sugerir X: job, prompt y scope.

        El host la usa para mostrar su autorización visible y lanzar después el
        job por el pipeline estándar (worker + staging + germinación SEM04).
        No comprueba proveedor: preparar no consume IA. ``peticion`` es el texto libre
        del usuario (BETA2-WIKI-08): encabeza el prompt (única vía creativa con prompt).
        """
        metric_key = str(metric or "").strip().lower()
        spec = _SUGGEST_SPECS.get(metric_key)
        if spec is None:
            return Error(f"Métrica de sugerencia desconocida: {metric}")
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        entity = project.entity_by_id(entity_id)
        if entity is None:
            return Error(f"Entidad no encontrada: {entity_id}")
        if entity.canon_state == CanonState.FANTASMA:
            return Error("Un nodo fantasma no participa del ciclo de riego")
        if entity_id in project.watering_paused_entity_ids:
            return Error("La entidad está secada: usa Cultivar antes de pedir sugerencias")

        context = self.build_watering_context(entity_id)
        if isinstance(context, Error):
            return context
        peticion = str(peticion or "").strip()
        lines: list[str] = []
        if peticion:
            lines += [f"PETICIÓN DEL USUARIO (prioritaria): {peticion}", ""]
        lines += [context.value["text"], "", spec["bias"]]
        previous = [d for d in self._diagnostics_for(project, entity_id) if not d.error]
        if previous:
            last = previous[-1]
            score = last.scores.get(metric_key)
            explanation = last.metric_explanations.get(metric_key, "")
            if score is not None or explanation:
                lines.append(
                    f"Diagnóstico previo de {metric_key}: puntuación {score}. {explanation}".strip()
                )
        lines.append(
            "Devuelve las propuestas como candidatos revisables (Semillas): "
            "nada se integra al canon sin aceptación humana."
        )
        tokens = int(context.value["estimated_tokens"])
        return Ok(
            {
                "job_type": spec["job"],
                "prompt": "\n".join(lines),
                "peticion": peticion,
                "context_scope": {
                    "selected_entity_ids": [entity_id],
                    "foco_hint": {
                        "zone": spec["zone"],
                        "metric": metric_key,
                        "center_entity_id": entity_id,
                    },
                },
                "entity_name": entity.name,
                "estimated_input_tokens": tokens,
                "cost_class": self._cost_class_for_tokens(tokens),
            }
        )

    def suggest(
        self,
        entity_id: str,
        metric: str,
        *,
        peticion: str = "",
        progress_callback: Any = None,
    ) -> Result[Any, str]:
        """Sugerir X: genera Semillas (candidatos) sesgadas a reparar una métrica.

        Consume IA autorizada (la autorización visible es del host, antes de
        llamar aquí). El hint de zona viaja en ``context_scope["foco_hint"]`` y
        ``ai_jobs`` lo copia a la metadata de cada candidato: la UI de Foco lo
        usa para germinar la Semilla en Raíces/Brotes o como tarjeta del drawer.
        BETA2-WIKI-08: antes de generar, NAVEGA la wiki (si hay navigator) para armar
        ``contexto_wiki`` a partir de la petición del usuario. NUNCA canoniza.
        """
        request = self.build_suggestion_request(entity_id, metric, peticion)
        if isinstance(request, Error):
            return request
        if self.ai_job_service is None or self.ai_job_service.provider_unconfigured():
            return Error(_UNCONFIGURED_AI_MESSAGE)
        payload = request.value
        context_scope = dict(payload["context_scope"])
        self._attach_wiki_context(
            context_scope, payload["job_type"], payload["peticion"], entity_id
        )
        return self.ai_job_service.run_focused_job(
            payload["job_type"],
            payload["prompt"],
            context_scope=context_scope,
            progress_callback=progress_callback,
        )

    def _attach_wiki_context(
        self,
        context_scope: dict,
        job_type: str,
        peticion: str,
        entity_id: str,
        *,
        notice: Any = None,
    ) -> str:
        """Navega la wiki y adjunta ``contexto_wiki`` al scope (best-effort, WIKI-08).

        BETA-MULTIAGENT2-FIX-06 (G2-10): devuelve el motivo por el que NO se navegó
        (hoy: wiki sin una sola página) y lo pasa a ``notice`` para que el host lo diga
        en voz alta. Nada de degradación silenciosa (mismo principio que FIX-02).
        """
        if self.navigator is None:
            return ""
        try:
            from packages.application.wiki_navigator import NavigationRequest

            res = self.navigator.assemble_context(
                NavigationRequest(intent=str(job_type), user_text=peticion, focus_ids=[entity_id])
            )
            bundle = res.value if isinstance(res, Ok) else None
            if bundle is None:
                return ""
            motivo = str(getattr(bundle, "skipped_reason", "") or "")
            if motivo and callable(notice):
                try:
                    notice(motivo)
                except Exception:  # noqa: BLE001 — el aviso nunca rompe la sugerencia
                    pass
            if not bundle.is_empty():
                context_scope["contexto_wiki"] = bundle.as_context_dict()
            return motivo
        except Exception:  # noqa: BLE001 — la navegación nunca rompe la sugerencia
            return ""

    def compose_generation(
        self,
        entity_id: str,
        metric: str,
        peticion: str = "",
        *,
        progress_callback: Any = None,
        cancel_check: Any = None,
    ) -> Result[dict[str, Any], str]:
        """Prepara la generación de una Sugerencia: navega la wiki y, para arraigo/iluminada,
        corre el ANÁLISIS DE INTENCIÓN (plan) y compone el prompt del job compuesto.

        Devuelve un payload listo para ``run_focused_job`` (``job_type``/``prompt``/
        ``context_scope``) más ``plan_summary`` (feedback legible). Está pensado para correr
        FUERA del hilo de UI (encadena hasta 2 llamadas IA: navegación + intención). Para
        nutrida/calidad no analiza intención: mantiene el job por métrica. Consume IA (la
        autorización visible es del host, antes de llamar aquí). NUNCA canoniza.

        BETA-MULTIAGENT-FIX-02 (G-02): ``progress_callback`` recibe el nombre de la
        fase en curso y ``cancel_check`` permite el corte cooperativo ENTRE fases
        (la llamada HTTP en vuelo no se aborta, como en el resto de cancelaciones).
        """

        def _phase(msg: str) -> None:
            if callable(progress_callback):
                try:
                    progress_callback(str(msg))
                except Exception:  # noqa: BLE001 — el feedback nunca rompe la prep
                    pass

        def _cancelled() -> bool:
            try:
                return bool(callable(cancel_check) and cancel_check())
            except Exception:  # noqa: BLE001
                return False

        base = self.build_suggestion_request(entity_id, metric, peticion)
        if isinstance(base, Error):
            return base
        payload = dict(base.value)
        scope = dict(payload["context_scope"])
        metric_key = str(metric or "").strip().lower()
        with_intent = metric_key in _INTENT_METRICS and self.intent_service is not None
        total_phases = 2 if with_intent else 1
        # BETA2-WIKI-08: navega la wiki y adjunta contexto_wiki al scope (best-effort).
        _phase(f"Navegando la wiki (1/{total_phases})…")
        wiki_skipped = self._attach_wiki_context(
            scope,
            payload["job_type"],
            payload.get("peticion", ""),
            entity_id,
            # FIX-06 (G2-10): si la wiki está vacía no se navega — y se DICE.
            notice=lambda _motivo: _phase(
                "La wiki aún no tiene páginas: sin navegación (sin coste). "
                "La Sugerencia sale con el contexto del canon."
            ),
        )
        payload["wiki_skipped"] = wiki_skipped
        if _cancelled():
            return Error("Preparación de la Sugerencia cancelada por el usuario.")

        plan_summary = ""
        if with_intent:
            _phase(f"Analizando la petición (2/{total_phases})…")
            plan_res = self.intent_service.plan(
                entity_id, metric_key, peticion, wiki_context=scope.get("contexto_wiki")
            )
            if _cancelled():
                return Error("Preparación de la Sugerencia cancelada por el usuario.")
            plan = plan_res.value if isinstance(plan_res, Ok) else None
            if plan is not None and not plan.is_empty():
                # Un solo job COMPUESTO produce el mix del plan; stage_results lo estadía todo.
                payload["job_type"] = "suggest_composite"
                payload["prompt"] = payload["prompt"] + "\n\n" + plan.to_generation_directives()
                plan_summary = plan.summary_line()

        payload["context_scope"] = scope
        payload["plan_summary"] = plan_summary
        return Ok(payload)

    # ------------------------------------------------------------------
    # Riego en lote (FOCO-07): pasos persistentes, cancelable ENTRE pasos
    # ------------------------------------------------------------------

    @staticmethod
    def _branch_member_ids(project: Project, branch_id: str) -> list[str]:
        """La rama y todos sus descendientes por contención (BFS determinista)."""
        seen = {branch_id}
        order = [branch_id]
        queue = [branch_id]
        while queue:
            current = queue.pop(0)
            for relation in project.relations_for(current):
                child = None
                contains = relation.relation_type == RelationType.CONTIENE
                if contains and relation.source_id == current:
                    child = relation.target_id
                elif (
                    relation.relation_type == RelationType.PERTENECE_A
                    and relation.target_id == current
                ):
                    child = relation.source_id
                if child and child not in seen:
                    seen.add(child)
                    order.append(child)
                    queue.append(child)
        return order

    def entities_in_scope(self, scope: dict[str, Any] | None) -> Result[list[str], str]:
        """Entidades elegibles para regar en un ámbito.

        Ámbitos: ``{"selection": [ids]}`` · ``{"ring_id": id}`` (miembros
        directos del anillo) · ``{"branch_id": id}`` (la rama y sus
        descendientes por contención) · ``{"graph": True}``. Excluye SIEMPRE
        fantasmas, Secadas y archivadas/descartadas. Orden estable por nombre.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        scope = scope or {}

        candidates: list[NarrativeEntity]
        if scope.get("graph"):
            candidates = list(project.entities)
        elif "selection" in scope:
            wanted = [str(value) for value in (scope.get("selection") or [])]
            candidates = [
                entity
                for entity in (project.entity_by_id(entity_id) for entity_id in wanted)
                if entity is not None
            ]
        elif scope.get("ring_id"):
            ring_id = str(scope["ring_id"])
            candidates = [e for e in project.entities if ring_id in (e.layer_ids or [])]
        elif scope.get("branch_id"):
            branch_id = str(scope["branch_id"])
            if project.entity_by_id(branch_id) is None:
                return Error(f"Entidad no encontrada: {branch_id}")
            member_ids = self._branch_member_ids(project, branch_id)
            candidates = [
                entity
                for entity in (project.entity_by_id(member_id) for member_id in member_ids)
                if entity is not None
            ]
        else:
            return Error("Ámbito de riego no reconocido")

        paused = set(project.watering_paused_entity_ids)
        eligible = [
            entity
            for entity in candidates
            if entity.canon_state not in _EXCLUDED_CANON
            and entity.canon_state != CanonState.FANTASMA
            and entity.id not in paused
        ]
        eligible.sort(key=lambda entity: (entity.name.casefold(), entity.id))
        return Ok([entity.id for entity in eligible])

    def record_failure(self, entity_id: str, error: str) -> Result[WateringDiagnostic, str]:
        """Fallo trazable de lote: la entidad queda Falta regar con causa en su historial."""
        failure = WateringDiagnostic(
            entity_id=entity_id,
            origin="batch",
            error=str(error or "fallo de riego"),
            resulting_status=WateringStatus.FALTA_REGAR.value,
        )
        return self.register_diagnostic(failure)

    def water_batch_step(
        self,
        entity_id: str,
        *,
        batch_ids: list[str] | None = None,
        progress_callback: Any = None,
    ) -> Result[WateringDiagnostic, str]:
        """Un paso del lote: riega o deja fallo trazable y sigue.

        El host itera la lista de ``entities_in_scope`` y puede cancelar ENTRE
        pasos: cada paso persiste su diagnóstico (o su fallo) al completarse,
        así una cancelación nunca deja estado corrupto ni pierde parciales.
        ``batch_ids`` (FIX-01): los miembros del lote no se invalidan entre sí.

        ``progress_callback`` (BETA-MULTIAGENT2-FIX-06, G2-08): las fases del pipeline
        de jobs (BUILDING_CONTEXT / PLANNING / WAITING_FOR_MODEL) que ``water_entity``
        ya sabía reenviar. El cable estaba tendido y desconectado en los dos últimos
        metros: el lote regaba 269 s en silencio absoluto.
        """
        result = self.water_entity(
            entity_id,
            origin="batch",
            batch_ids=batch_ids,
            progress_callback=progress_callback,
        )
        if isinstance(result, Ok):
            return result
        # Best-effort: para fantasmas/desconocidas el registro también fallará
        # y basta con propagar el error original.
        self.record_failure(entity_id, result.error)
        return result
