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

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.domain.entity import CanonState, NarrativeEntity, NarrativeImportance
from packages.domain.project import Project
from packages.domain.result import Error, Ok, Result
from packages.domain.watering import WateringDiagnostic, WateringStatus

_HIGH_IMPORTANCE = frozenset({NarrativeImportance.CRITICO, NarrativeImportance.ALTO})
_EXCLUDED_CANON = frozenset({CanonState.ARCHIVADO, CanonState.DESCARTADO})


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
    ) -> None:
        self.project_service = project_service
        self.ai_job_service = ai_job_service
        self.history_service = history_service
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
            other = project.entity_by_id(other_id)
            if other is None:
                return True  # vecina borrada sin dejar rastro comparable
            if _newer(other.updated_at, watered_at):
                return True
        # 2º grado: solo entidades de relevancia alta invalidan (decisión de producto).
        for other_id in direct:
            for relation in project.relations_for(other_id):
                second_id = (
                    relation.target_id if relation.source_id == other_id else relation.source_id
                )
                if second_id == entity.id or second_id in direct:
                    continue
                second = project.entity_by_id(second_id)
                if second is None or second.canon_state in _EXCLUDED_CANON:
                    continue
                if second.narrative_importance in _HIGH_IMPORTANCE and _newer(
                    second.updated_at, watered_at
                ):
                    return True
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
        return WateringStatusReport(WateringStatus.REGADA.value, latest, False, "")

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
