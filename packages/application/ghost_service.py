"""Nodos fantasma: placeholders manuales persistentes, borrador interno no-canon (BETA2-FOCO).

Un fantasma es una entidad normal con ``canon_state = fantasma``: tiene los
mismos campos, persiste, puede relacionarse (relaciones fantasma) y vive en el
lienzo translúcido, pero NO cuenta ni exporta como canon pleno: el RAG
(``corpus_indexer``), las exportaciones (``export_service``) y el contexto de
audiencias no-gm lo excluyen; en audiencia gm entra con su ``canon_state``
visible y los prompts lo tratan como intención, no como sostén.

La conversión a entidad real es SIEMPRE una acción explícita del usuario —
nunca ocurre por rellenar campos — y toda operación queda trazada en historial.
"""

from __future__ import annotations

from typing import Any

from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.result import Error, Ok, Result
from packages.domain.source_history import HistoryEventType


class GhostService:
    """Ciclo de vida de nodos y relaciones fantasma (crear/convertir/vincular/descartar)."""

    def __init__(
        self,
        project_service: Any,
        entity_service: Any,
        relation_service: Any,
        history_service: Any = None,
    ) -> None:
        self.project_service = project_service
        self.entity_service = entity_service
        self.relation_service = relation_service
        self.history_service = history_service

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_ghost(obj: Any) -> bool:
        """True para entidades o relaciones con canon fantasma."""
        return getattr(obj, "canon_state", None) == CanonState.FANTASMA

    def _active_project(self):
        project = getattr(self.project_service, "active_project", None)
        if project is None:
            return Error("No active project")
        return Ok(project)

    def _record(
        self,
        event_type: HistoryEventType,
        *,
        entity_id: str | None = None,
        relation_id: str | None = None,
        previous: Any = None,
        new: Any = None,
        operation: str = "",
        description: str = "",
    ) -> None:
        if self.history_service is None:
            return
        entry = self.history_service.make_entry(
            event_type,
            affected_entity_id=entity_id,
            affected_relation_id=relation_id,
            previous_value=previous,
            new_value=new,
            change_origin="ghost_service",
            operation=operation,
            description=description,
        )
        self.history_service.record(entry)

    def _require_ghost(self, ghost_id: str):
        proj = self._active_project()
        if isinstance(proj, Error):
            return proj
        project = proj.value
        entity = project.entity_by_id(ghost_id)
        if entity is None:
            return Error(f"Entidad no encontrada: {ghost_id}")
        if not self.is_ghost(entity):
            return Error("La entidad no es un nodo fantasma")
        return Ok((project, entity))

    # ------------------------------------------------------------------
    # Operaciones
    # ------------------------------------------------------------------

    def create_ghost(self, data: dict[str, Any]) -> Result[NarrativeEntity, str]:
        """Crea un placeholder persistente con indicación vaga de lo que pretende ser."""
        payload = dict(data or {})
        payload["canon_state"] = CanonState.FANTASMA.value
        return self.entity_service.create_entity(payload, history_service=self.history_service)

    def create_ghost_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: Any = None,
        description: str = "",
    ) -> Result[Any, str]:
        """Relación fantasma (vínculo pendiente). Ambos extremos deben existir."""
        data: dict[str, Any] = {"canon_state": CanonState.FANTASMA.value}
        if description:
            data["description"] = description
        result = self.relation_service.create_relation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type or "esta_relacionado_con",
            data=data,
            history_service=self.history_service,
        )
        if isinstance(result, Error):
            return result
        relation = result.value
        if relation.canon_state != CanonState.FANTASMA:
            # Blindaje: si create_relation normalizara el canon al default,
            # la relación fantasma debe seguir siendo fantasma.
            relation.canon_state = CanonState.FANTASMA
            relation.touch()
        return Ok(relation)

    def convert_to_entity(self, ghost_id: str) -> Result[NarrativeEntity, str]:
        """Convierte el fantasma en entidad real (BORRADOR). Acción explícita, trazada.

        Las relaciones fantasma cuyo otro extremo ya es real maduran a BORRADOR;
        las que apuntan a otro fantasma siguen fantasma.
        """
        checked = self._require_ghost(ghost_id)
        if isinstance(checked, Error):
            return checked
        project, entity = checked.value
        entity.canon_state = CanonState.BORRADOR
        entity.touch()
        for relation in project.relations_for(ghost_id):
            if relation.canon_state != CanonState.FANTASMA:
                continue
            other_id = relation.target_id if relation.source_id == ghost_id else relation.source_id
            other = project.entity_by_id(other_id)
            if other is not None and not self.is_ghost(other):
                relation.canon_state = CanonState.BORRADOR
                relation.touch()
        project.touch()
        self._record(
            HistoryEventType.CAMBIO_CANON,
            entity_id=ghost_id,
            previous=CanonState.FANTASMA.value,
            new=CanonState.BORRADOR.value,
            operation="convertir_fantasma",
            description=f"Nodo fantasma convertido en entidad: {entity.name}",
        )
        return Ok(entity)

    def link_to_existing(self, ghost_id: str, entity_id: str) -> Result[NarrativeEntity, str]:
        """Vincula el fantasma con una entidad existente: re-apunta sus relaciones y lo descarta."""
        checked = self._require_ghost(ghost_id)
        if isinstance(checked, Error):
            return checked
        project, ghost = checked.value
        if ghost_id == entity_id:
            return Error("No se puede vincular un fantasma consigo mismo")
        target = project.entity_by_id(entity_id)
        if target is None:
            return Error(f"Entidad no encontrada: {entity_id}")
        if self.is_ghost(target):
            return Error("El destino del vínculo debe ser una entidad real, no otro fantasma")

        ghost_name = ghost.name
        for relation in list(project.relations_for(ghost_id)):
            other_id = relation.target_id if relation.source_id == ghost_id else relation.source_id
            if other_id == entity_id or other_id == ghost_id:
                # Re-apuntarla crearía un self-loop: el vínculo ya existe de facto.
                project.relations.remove(relation)
                continue
            if relation.source_id == ghost_id:
                relation.source_id = entity_id
            if relation.target_id == ghost_id:
                relation.target_id = entity_id
            other = project.entity_by_id(other_id)
            if (
                relation.canon_state == CanonState.FANTASMA
                and other is not None
                and not self.is_ghost(other)
            ):
                relation.canon_state = CanonState.BORRADOR
            relation.touch()
        project.entities.remove(ghost)
        if project.metadata.get("last_worked_entity_id") == ghost_id:
            project.metadata["last_worked_entity_id"] = entity_id
        project.touch()
        self._record(
            HistoryEventType.FUSION_ENTIDADES,
            entity_id=entity_id,
            previous=ghost_name,
            new=target.name,
            operation="vincular_fantasma",
            description=f"Fantasma '{ghost_name}' vinculado a la entidad existente '{target.name}'",
        )
        return Ok(target)

    def discard(self, ghost_id: str) -> Result[None, str]:
        """Descarta el fantasma (borrado real: es un borrador interno, no canon)."""
        checked = self._require_ghost(ghost_id)
        if isinstance(checked, Error):
            return checked
        project, entity = checked.value
        name = entity.name
        for relation in list(project.relations_for(ghost_id)):
            project.relations.remove(relation)
        project.entities.remove(entity)
        if project.metadata.get("last_worked_entity_id") == ghost_id:
            project.metadata.pop("last_worked_entity_id", None)
        project.touch()
        self._record(
            HistoryEventType.DESCARTE_FANTASMA,
            entity_id=ghost_id,
            previous=name,
            operation="descartar_fantasma",
            description=f"Nodo fantasma descartado: {name}",
        )
        return Ok(None)
