"""NarrativeMemoryService — CRUD de Memoria narrativa viva (BETA2-MEM-02).

Servicio de aplicación que muta la colección ``narrative_memories`` del proyecto
activo y registra trazabilidad. **Sin IA y sin UI**: la generación IA de Memoria
es MEM-05, el motor de impacto es MEM-04 y las superficies (Cultivo/Foco,
visor de Configuración) son MEM-09/10. Aquí solo se modela el mantenimiento
determinista del dato, para que la app funcione sin proveedor IA.

Frontera de capas: la UI nunca escribe persistencia; muta a través de este
servicio, que a su vez opera sobre ``project_service.active_project`` (patrón de
``HistoryService``/``ChronologyWalkService``). El guardado en disco lo decide el
caller (``ProjectService.save``), igual que el resto de servicios.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.domain.narrative_memory import (
    MemoryCitation,
    MemoryFreshness,
    MemoryIssue,
    MemoryIssueStatus,
    MemoryOrigin,
    MemoryRevisionProposal,
    MemoryRevisionStatus,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.result import Error, Ok, Result
from packages.domain.source_history import HistoryEventType


def _as_kind(value: MemoryTargetKind | str) -> MemoryTargetKind:
    if isinstance(value, MemoryTargetKind):
        return value
    return MemoryTargetKind(str(value))


@dataclass
class NarrativeMemoryService:
    """Gestiona los bloques de Memoria del proyecto activo (Result-based)."""

    project_service: Any
    history_service: Any = None

    # ── infraestructura interna ────────────────────────────────────────

    def _proj(self):
        return getattr(self.project_service, "active_project", None)

    def _ensure_memories(self) -> list[NarrativeMemory] | None:
        proj = self._proj()
        if proj is None:
            return None
        if not isinstance(getattr(proj, "narrative_memories", None), list):
            proj.narrative_memories = []
        return proj.narrative_memories

    def _find(
        self, memories: list[NarrativeMemory], kind: MemoryTargetKind, target_id: str, context: str
    ) -> NarrativeMemory | None:
        key = (kind.value, target_id, context)
        for m in memories:
            if m.target_key() == key:
                return m
        return None

    def _record(
        self,
        event: HistoryEventType,
        block: NarrativeMemory,
        *,
        causa: str = "",
        change_origin: str = "",
        previous_value: Any | None = None,
        new_value: Any | None = None,
    ) -> None:
        proj = self._proj()
        if proj is not None and hasattr(proj, "touch"):
            proj.touch()
        if self.history_service is None:
            return
        affected_entity_id = (
            block.target_id if block.target_kind == MemoryTargetKind.ENTITY else None
        )
        self.history_service.record(
            event,
            description=causa,
            affected_entity_id=affected_entity_id,
            change_origin=change_origin,
            previous_value=previous_value,
            new_value=new_value,
            metadata={
                "memory_id": block.id,
                "target_kind": block.target_kind.value,
                "target_id": block.target_id,
                "context": block.context,
            },
        )

    # ── consulta ───────────────────────────────────────────────────────

    def list_memories(
        self,
        target_kind: MemoryTargetKind | str | None = None,
        target_id: str | None = None,
    ) -> Result[list[NarrativeMemory], str]:
        memories = self._ensure_memories()
        if memories is None:
            return Error("No hay proyecto activo")
        result = list(memories)
        if target_kind is not None:
            kind = _as_kind(target_kind)
            result = [m for m in result if m.target_kind == kind]
        if target_id is not None:
            result = [m for m in result if m.target_id == target_id]
        return Ok(result)

    def get_memory(
        self,
        target_kind: MemoryTargetKind | str,
        target_id: str = "",
        context: str = "",
    ) -> Result[NarrativeMemory | None, str]:
        memories = self._ensure_memories()
        if memories is None:
            return Error("No hay proyecto activo")
        return Ok(self._find(memories, _as_kind(target_kind), target_id, context))

    # ── mutación de contenido ──────────────────────────────────────────

    def upsert_memory(
        self,
        target_kind: MemoryTargetKind | str,
        target_id: str = "",
        context: str = "",
        *,
        resumen_editorial: str | None = None,
        estado_actual: str | None = None,
        cuerpo: str | None = None,
        issues: list[MemoryIssue] | None = None,
        notas_causales: list[str] | None = None,
        dependencias: list[MemoryCitation] | None = None,
        citations: list[MemoryCitation] | None = None,
        wikilinks: list[MemoryCitation] | None = None,
        tags: list[str] | None = None,
        freshness: MemoryFreshness | None = None,
        origin: MemoryOrigin = MemoryOrigin.USUARIO,
        causa: str = "",
    ) -> Result[NarrativeMemory, str]:
        """Crea o actualiza el bloque de la clave dada. Solo pisa lo aportado."""
        memories = self._ensure_memories()
        if memories is None:
            return Error("No hay proyecto activo")
        kind = _as_kind(target_kind)
        block = self._find(memories, kind, target_id, context)
        creating = block is None
        if block is None:
            block = NarrativeMemory(
                target_kind=kind, target_id=target_id, context=context, origin=origin
            )
            memories.append(block)

        if resumen_editorial is not None:
            block.resumen_editorial = resumen_editorial
        if estado_actual is not None:
            block.estado_actual = estado_actual
        if cuerpo is not None:
            block.cuerpo = cuerpo
        if issues is not None:
            block.issues = list(issues)
        if notas_causales is not None:
            block.notas_causales = list(notas_causales)
        if dependencias is not None:
            block.dependencias = list(dependencias)
        if citations is not None:
            block.citations = list(citations)
        if wikilinks is not None:
            block.wikilinks = list(wikilinks)
        if tags is not None:
            block.tags = list(tags)
        if origin is not None:
            block.origin = origin
        if freshness is not None:
            block.freshness = freshness
        elif creating:
            # Escribir contenido por primera vez cuenta como Memoria vigente.
            block.freshness = MemoryFreshness.REGADA
        block.touch()

        self._record(
            HistoryEventType.MEMORIA_ACTUALIZADA,
            block,
            causa=causa or ("creación de memoria" if creating else "actualización de memoria"),
            change_origin=origin.value if origin else "",
        )
        return Ok(block)

    def mark_falta_regar(
        self,
        target_kind: MemoryTargetKind | str,
        target_id: str = "",
        context: str = "",
        *,
        causa: str = "",
        change_origin: str = "impacto",
        create_if_missing: bool = True,
    ) -> Result[NarrativeMemory | None, str]:
        """Marca Falta regar SIN borrar contenido previo (criterio 4).

        Si no hay bloque y ``create_if_missing`` es True, crea uno vacío en
        estado Falta regar para persistir la señal del motor de impacto (MEM-04).
        """
        memories = self._ensure_memories()
        if memories is None:
            return Error("No hay proyecto activo")
        kind = _as_kind(target_kind)
        block = self._find(memories, kind, target_id, context)
        if block is None:
            if not create_if_missing:
                return Ok(None)
            block = NarrativeMemory(target_kind=kind, target_id=target_id, context=context)
            memories.append(block)
        block.freshness = MemoryFreshness.FALTA_REGAR
        block.touch()
        self._record(
            HistoryEventType.MEMORIA_FALTA_REGAR,
            block,
            causa=causa or "cambio relacionado detectado",
            change_origin=change_origin,
        )
        return Ok(block)

    def set_freshness(
        self,
        target_kind: MemoryTargetKind | str,
        target_id: str = "",
        context: str = "",
        *,
        freshness: MemoryFreshness,
        causa: str = "",
        change_origin: str = "",
    ) -> Result[NarrativeMemory, str]:
        memories = self._ensure_memories()
        if memories is None:
            return Error("No hay proyecto activo")
        kind = _as_kind(target_kind)
        block = self._find(memories, kind, target_id, context)
        if block is None:
            return Error("No existe Memoria para el elemento indicado")
        block.freshness = freshness
        block.touch()
        event = (
            HistoryEventType.MEMORIA_SECADA
            if freshness == MemoryFreshness.SECADA
            else HistoryEventType.MEMORIA_FALTA_REGAR
            if freshness == MemoryFreshness.FALTA_REGAR
            else HistoryEventType.MEMORIA_ACTUALIZADA
        )
        self._record(event, block, causa=causa, change_origin=change_origin)
        return Ok(block)

    def delete_memory(
        self,
        target_kind: MemoryTargetKind | str,
        target_id: str = "",
        context: str = "",
        *,
        causa: str = "",
    ) -> Result[bool, str]:
        memories = self._ensure_memories()
        if memories is None:
            return Error("No hay proyecto activo")
        kind = _as_kind(target_kind)
        block = self._find(memories, kind, target_id, context)
        if block is None:
            return Ok(False)
        memories.remove(block)
        self._record(HistoryEventType.MEMORIA_BORRADA, block, causa=causa or "borrado de memoria")
        return Ok(True)

    def resolve_issue(
        self,
        target_kind: MemoryTargetKind | str,
        target_id: str,
        context: str = "",
        *,
        issue_id: str,
        status: MemoryIssueStatus | str,
    ) -> Result[MemoryIssue, str]:
        """Marca el estado de una incidencia de Memoria (Cultivo: aceptar/corregir/…)."""
        memories = self._ensure_memories()
        if memories is None:
            return Error("No hay proyecto activo")
        block = self._find(memories, _as_kind(target_kind), target_id, context)
        if block is None:
            return Error("No existe Memoria para el elemento indicado")
        new_status = status if isinstance(status, MemoryIssueStatus) else MemoryIssueStatus(str(status))
        for issue in block.issues:
            if issue.id == issue_id:
                issue.estado = new_status
                block.touch()
                proj = self._proj()
                if proj is not None and hasattr(proj, "touch"):
                    proj.touch()
                return Ok(issue)
        return Error("No existe la incidencia indicada")

    # ── propuestas de revisión (antes/después) ─────────────────────────

    def stage_revision_proposal(
        self,
        target_kind: MemoryTargetKind | str,
        target_id: str = "",
        context: str = "",
        *,
        after: dict[str, Any],
        motivo: str = "",
        origin: MemoryOrigin = MemoryOrigin.IA,
    ) -> Result[MemoryRevisionProposal, str]:
        """Adjunta una propuesta con snapshot antes/después SIN aplicar cambios."""
        memories = self._ensure_memories()
        if memories is None:
            return Error("No hay proyecto activo")
        kind = _as_kind(target_kind)
        block = self._find(memories, kind, target_id, context)
        if block is None:
            return Error("No existe Memoria para proponer un cambio")
        proposal = MemoryRevisionProposal(
            before=block.content_snapshot(),
            after=dict(after),
            origin=origin,
            motivo=motivo,
            estado=MemoryRevisionStatus.PENDIENTE,
        )
        block.pending_revision = proposal
        block.touch()
        self._record(
            HistoryEventType.MEMORIA_PROPUESTA_REVISION,
            block,
            causa=motivo or "propuesta de revisión de memoria",
            change_origin=origin.value,
        )
        return Ok(proposal)

    def apply_revision_proposal(
        self,
        target_kind: MemoryTargetKind | str,
        target_id: str = "",
        context: str = "",
        *,
        causa: str = "",
    ) -> Result[NarrativeMemory, str]:
        """Aplica el ``after`` de la propuesta pendiente al contenido del bloque."""
        memories = self._ensure_memories()
        if memories is None:
            return Error("No hay proyecto activo")
        kind = _as_kind(target_kind)
        block = self._find(memories, kind, target_id, context)
        if block is None:
            return Error("No existe Memoria para el elemento indicado")
        proposal = block.pending_revision
        if proposal is None:
            return Error("No hay propuesta de revisión pendiente")
        previous = block.content_snapshot()
        self._apply_content(block, proposal.after)
        proposal.estado = MemoryRevisionStatus.ACEPTADA
        block.pending_revision = None
        block.freshness = MemoryFreshness.REGADA
        block.touch()
        self._record(
            HistoryEventType.MEMORIA_ACTUALIZADA,
            block,
            causa=causa or "revisión de memoria aplicada",
            change_origin=proposal.origin.value,
            previous_value=previous,
            new_value=block.content_snapshot(),
        )
        return Ok(block)

    def discard_revision_proposal(
        self,
        target_kind: MemoryTargetKind | str,
        target_id: str = "",
        context: str = "",
    ) -> Result[NarrativeMemory, str]:
        memories = self._ensure_memories()
        if memories is None:
            return Error("No hay proyecto activo")
        kind = _as_kind(target_kind)
        block = self._find(memories, kind, target_id, context)
        if block is None:
            return Error("No existe Memoria para el elemento indicado")
        if block.pending_revision is None:
            return Error("No hay propuesta de revisión pendiente")
        block.pending_revision.estado = MemoryRevisionStatus.RECHAZADA
        block.pending_revision = None
        block.touch()
        return Ok(block)

    # ── helpers de contenido ───────────────────────────────────────────

    @staticmethod
    def _apply_content(block: NarrativeMemory, content: dict[str, Any]) -> None:
        """Sustituye solo las secciones editoriales presentes en ``content``."""
        if "resumen_editorial" in content:
            block.resumen_editorial = str(content.get("resumen_editorial", ""))
        if "estado_actual" in content:
            block.estado_actual = str(content.get("estado_actual", ""))
        if "issues" in content:
            raw = content.get("issues") or []
            block.issues = [
                i if isinstance(i, MemoryIssue) else MemoryIssue.from_dict(i)
                for i in raw
                if isinstance(i, (MemoryIssue, dict))
            ]
        if "notas_causales" in content:
            block.notas_causales = [str(n) for n in (content.get("notas_causales") or [])]
        if "dependencias" in content:
            raw = content.get("dependencias") or []
            block.dependencias = [
                c if isinstance(c, MemoryCitation) else MemoryCitation.from_dict(c)
                for c in raw
                if isinstance(c, (MemoryCitation, dict))
            ]
        if "citations" in content:
            raw = content.get("citations") or []
            block.citations = [
                c if isinstance(c, MemoryCitation) else MemoryCitation.from_dict(c)
                for c in raw
                if isinstance(c, (MemoryCitation, dict))
            ]


__all__ = ["NarrativeMemoryService"]
