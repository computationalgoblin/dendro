
"""CandidateService — CRUD, acceptance, merge, history (B14-T02)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.domain.candidate_issue import Candidate, CandidateState, CandidateType
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.world_layer import WorldLayer
from packages.domain.result import Error, Ok, Result
from packages.application.project_chronology_service import ProjectChronologyService


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CandidateService:
    project_service: Any
    entity_service: Any = None
    relation_service: Any = None
    history_service: Any = None

    def _proj(self):
        p = self.project_service.active_project
        if p is None:
            return Error("No active project")
        return Ok(p)

    # ── CRUD ──────────────────────────────────────────────────────────

    def create_candidate(self, data: dict) -> Result[Candidate, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        c = Candidate.from_dict(data)
        proj.value.candidates.append(c)
        return Ok(c)

    def create_causal_milestone_candidate(
        self,
        milestone: CausalMilestone,
        source: str = "ia",
        confidence: float = 0.5,
        justification: str = "",
    ) -> Result[Candidate, str]:
        """Create a review-only candidate for a causal milestone.

        This does not append to project.causal_milestones and therefore never
        canonizes IA output automatically. Acceptance is handled by a later B41
        service/UI ticket.
        """
        data = {
            "title": f"Hito: {milestone.title}",
            "candidate_type": CandidateType.SUGERENCIA_IA.value,
            "state": CandidateState.PENDIENTE.value,
            "proposed_data": {
                "kind": "causal_milestone",
                "milestone": milestone.to_dict(),
            },
            "affected_entity_ids": list(milestone.affected_entity_ids),
            "affected_relation_ids": list(milestone.caused_relation_ids),
            "source": source,
            "confidence": confidence,
            "justification": justification or milestone.rationale,
            "expected_impact": "Propone un hito causal/histórico para revisión; no modifica canon.",
            "metadata": {
                "kind": "causal_milestone",
                "review_required": True,
                "canonizes_automatically": False,
                "layer_ids": list(milestone.layer_ids),
            },
        }
        return self.create_candidate(data)

    def get_candidate(self, cid: str) -> Result[Candidate, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        for c in proj.value.candidates:
            if c.id == cid:
                return Ok(c)
        return Error(f"Candidate '{cid[:8]}' not found")

    def list_candidates(
        self, state: str | None = None, ctype: str | None = None,
    ) -> Result[list[Candidate], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        result = list(proj.value.candidates)
        if state:
            result = [c for c in result if c.state.value == state]
        if ctype:
            result = [c for c in result if c.candidate_type.value == ctype]
        return Ok(result)

    def list_candidates_by_entity(self, eid: str) -> Result[list[Candidate], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        return Ok([c for c in proj.value.candidates if eid in c.affected_entity_ids])

    def list_candidates_by_source(self, source: str) -> Result[list[Candidate], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        return Ok([c for c in proj.value.candidates if c.source == source])

    def update_candidate(self, cid: str, data: dict) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        if "title" in data:
            c.title = data["title"]
        if "proposed_data" in data:
            c.proposed_data = data["proposed_data"]
        if "confidence" in data:
            conf = float(data["confidence"])
            if conf < 0.0 or conf > 1.0:
                return Error("confidence must be 0.0-1.0")
            c.confidence = conf
        if "justification" in data:
            c.justification = data["justification"]
        if "source" in data:
            c.source = data["source"]
        return Ok(c)

    # ── Decisions ─────────────────────────────────────────────────────

    def _add_history(self, proj, event_type: str, entity_id: str = "",
                     note: str = "", candidate_id: str = "") -> None:
        if not self.history_service:
            return
        try:
            self.history_service.add_entry({
                "event_type": event_type,
                "entity_id": entity_id,
                "description": note or f"Candidate {candidate_id[:8]} decision",
                "metadata": {"candidate_id": candidate_id},
            })
        except Exception:
            pass  # history is non-critical

    def _collect_temporal_warnings(
        self, project, entity_id: str, relation_id: str, milestone_id: str
    ) -> list[dict]:
        """BETA1-J04: ejecuta el validador determinista (J02) sobre el canon
        recién creado y sus vecinos directos. Devuelve avisos serializables."""
        from packages.application.temporal_coherence import (
            evaluate_entity,
            evaluate_milestone,
            evaluate_relation,
        )

        chronology = getattr(project, "project_chronology", None)
        entities = {e.id: e for e in project.entities}
        issues = []
        if entity_id and entity_id in entities:
            issues += evaluate_entity(entities[entity_id], chronology=chronology)
        if relation_id:
            rel = next((r for r in project.relations if r.id == relation_id), None)
            if rel is not None:
                issues += evaluate_relation(
                    rel,
                    source=entities.get(rel.source_id),
                    target=entities.get(rel.target_id),
                    chronology=chronology,
                )
        if milestone_id:
            hito = next(
                (h for h in project.causal_milestones if h.id == milestone_id), None
            )
            if hito is not None:
                parent_ids = set(hito.causal_parent_hito_ids)
                parents = [
                    h for h in project.causal_milestones if h.id in parent_ids
                ]
                issues += evaluate_milestone(
                    hito, parent_milestones=parents, chronology=chronology
                )
        return [
            {
                "code": i.code,
                "message": i.message,
                "severity": i.severity,
                "related_ids": list(i.related_ids),
            }
            for i in issues
        ]

    def accept_candidate(self, cid: str) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        proj = self._proj()
        if isinstance(proj, Error):
            return proj

        entity_id = ""
        created_relation_id = ""  # SEM03: id de la arista creada (bloom de relación)
        created_milestone_id = ""  # SEM03: id del hito creado (bloom en cronología)
        edited_stamp: dict[str, str] = {}  # UX4 (C5): elemento editado al aceptar
        if c.candidate_type == CandidateType.ENTIDAD:
            if not self.entity_service:
                return Error("EntityService not available")
            result = self.entity_service.create_entity(c.proposed_data)
            if isinstance(result, Error):
                return result
            entity_id = result.value.id
            # UX4 (C4): una rama-contenedor puede traer hojas hijas. Al aceptarla,
            # se materializa cada hoja y una relación 'contiene' del contenedor a
            # la hoja, para que sea un contenedor REAL (no vacío) en el grafo.
            children = c.proposed_data.get("child_leaves")
            if isinstance(children, list) and children and self.relation_service:
                origin = (c.proposed_data.get("custom_metadata") or {}).get("origin_prompt", "")
                for child in children:
                    if not isinstance(child, dict):
                        continue
                    cname = str(child.get("name") or "").strip()
                    if not cname:
                        continue
                    child_res = self.entity_service.create_entity({
                        "name": cname,
                        "entity_type": child.get("entity_type") or "personaje",
                        "brief_description": str(
                            child.get("brief_description") or child.get("description") or ""
                        ).strip(),
                        "layer_ids": list(c.proposed_data.get("layer_ids") or []),
                        "custom_metadata": {"origin_prompt": origin},
                    })
                    if isinstance(child_res, Error):
                        continue
                    self.relation_service.create_relation(
                        source_id=entity_id, target_id=child_res.value.id,
                        relation_type="contiene", data={},
                    )
            # UX5d: las entidades EXISTENTES seleccionadas al crear la rama se enlazan
            # como miembros (`contiene`), sin duplicarlas. Las @menciones (externas) no
            # llegan aquí. Por defecto, seleccionar entidades = insertarlas en la rama.
            contained = c.proposed_data.get("contained_entity_ids")
            if isinstance(contained, list) and contained and self.relation_service:
                existing_ids = {e.id for e in proj.value.entities}
                for target in contained:
                    tid = str(target).strip()
                    if not tid or tid == entity_id or tid not in existing_ids:
                        continue
                    self.relation_service.create_relation(
                        source_id=entity_id, target_id=tid,
                        relation_type="contiene", data={},
                    )
            # UX5f: crear una HOJA con una RAMA (contenedor) seleccionada la añade
            # DENTRO de la rama (`contiene`) y, si la hoja no traía anillo, hereda el
            # del contenedor para quedar realmente dentro. Por defecto, seleccionar
            # una rama = crear en ella. Las @menciones son referencias externas (no
            # llegan en selected_entity_ids): no insertan. La rama-contenedor recién
            # creada (UX5d) se excluye: gestiona sus propios miembros.
            new_is_container = str(c.proposed_data.get("entity_type") or "") == "contenedor"
            scope = (getattr(c, "metadata", None) or {}).get("context_scope") or {}
            selected_ids = {str(x) for x in (scope.get("selected_entity_ids") or []) if str(x)}
            if not new_is_container and selected_ids and self.relation_service:
                containers = [
                    e for e in proj.value.entities
                    if e.id in selected_ids and e.id != entity_id
                    and getattr(getattr(e, "entity_type", None), "value", "") == "contenedor"
                ]
                if containers:
                    new_entity = result.value
                    if not (getattr(new_entity, "layer_ids", None) or []):
                        host = next(
                            (cont for cont in containers if getattr(cont, "layer_ids", None)),
                            None,
                        )
                        if host is not None and self.entity_service:
                            self.entity_service.update_entity(
                                new_entity.id, {"layer_ids": list(host.layer_ids)}
                            )
                    for container in containers:
                        self.relation_service.create_relation(
                            source_id=container.id, target_id=entity_id,
                            relation_type="contiene", data={},
                        )
        elif c.candidate_type == CandidateType.RELACION:
            if not self.relation_service:
                return Error("RelationService not available")
            # Resolve endpoints: prefer direct IDs, fall back to name lookup
            sid = c.proposed_data.get("source_id", "")
            tid = c.proposed_data.get("target_id", "")
            if not sid or not tid:
                sid, tid = self._resolve_relation_endpoints_by_name(
                    proj.value, c.proposed_data
                )
            if not sid or not tid:
                return Error(
                    "No se pudieron encontrar las entidades para esta relación. "
                    "Asegúrate de que ambas entidades existen en el proyecto."
                )
            found_s = any(e.id == sid for e in proj.value.entities)
            found_t = any(e.id == tid for e in proj.value.entities)
            if not found_s or not found_t:
                return Error(
                    "Relation endpoints not found in project"
                )
            result = self.relation_service.create_relation(
                source_id=sid, target_id=tid,
                relation_type=c.proposed_data.get("relation_type", ""),
                data=c.proposed_data,
            )
            if isinstance(result, Error):
                return result
            created_relation_id = result.value.id
        elif c.proposed_data.get("kind") == "causal_milestone":
            milestone_data = c.proposed_data.get("milestone")
            if not isinstance(milestone_data, dict):
                return Error("Causal milestone candidate has no milestone payload")
            hito = CausalMilestone.from_dict(milestone_data)
            proj.value.causal_milestones.append(hito)
            created_milestone_id = hito.id
            chronology = getattr(proj.value, "project_chronology", None)
            if chronology is not None and hasattr(chronology, "link_milestone"):
                chronology.link_milestone(hito.id)
            if hasattr(proj.value, "touch"):
                proj.value.touch()
        elif c.proposed_data.get("kind") == "ring_template":
            import uuid as _uuid
            data = c.proposed_data
            layer = WorldLayer(
                id=f"layer_{_uuid.uuid4().hex[:10]}",
                name=str(data.get("ring_name") or data.get("name") or "Anillo"),
                description=str(data.get("description") or ""),
                order=int(data.get("order", 0) or 0),
                is_visible=True,
                is_default=False,
                metadata={
                    "origin": "ai_ring_template",
                    "domain": str(data.get("domain") or ""),
                    "derived_from": str(data.get("derived_from") or ""),
                },
            )
            proj.value.world_layers.append(layer)
            if hasattr(proj.value, "touch"):
                proj.value.touch()
            entity_id = layer.id
        elif c.proposed_data.get("kind") == "project_chronology_suggestion":
            result = ProjectChronologyService(self.project_service).apply_candidate(c.proposed_data)
            if isinstance(result, Error):
                return result
        elif self._routes_as_edit(c.proposed_data):
            # UX4 (C5): aceptar una EDICIÓN aplica el cambio a canon (acción humana
            # explícita), en vez de quedarse en "sugerencia" inerte.
            applied = self._apply_edit(proj.value, c)
            if isinstance(applied, Error):
                return applied
            edited_kind, edited_id = applied.value
            edited_stamp = {f"edited_{edited_kind}_id": edited_id}
        else:
            # Other types: just mark accepted without creating entity/relation
            pass

        # Semillas (SEM02/SEM03): expone el id del elemento creado por familia para
        # que la UI pueda «germinar» (foco + glow) lo recién nacido: nodo (entidad),
        # arista (relación), banda (anillo) o marca de cronología (hito). metadata ya
        # se serializa, sin migración de esquema.
        stamps: dict[str, str] = {}
        if c.candidate_type == CandidateType.ENTIDAD and entity_id:
            stamps["created_entity_id"] = entity_id
        if created_relation_id:
            stamps["created_relation_id"] = created_relation_id
        if created_milestone_id:
            stamps["created_milestone_id"] = created_milestone_id
        if c.proposed_data.get("kind") == "ring_template" and entity_id:
            stamps["created_ring_id"] = entity_id
        if edited_stamp:
            stamps.update(edited_stamp)
        if stamps:
            meta = dict(getattr(c, "metadata", None) or {})
            meta.update(stamps)
            c.metadata = meta

        # BETA1-J04: guardia determinista de coherencia temporal. Genera avisos
        # (preguntas abiertas) asociados al candidato; NO bloquea el accept
        # (la IA nunca impone canon; el usuario decide).
        warnings = self._collect_temporal_warnings(
            proj.value, entity_id, created_relation_id, created_milestone_id
        )
        if warnings:
            meta = dict(getattr(c, "metadata", None) or {})
            meta["temporal_warnings"] = warnings
            c.metadata = meta

        c.state = CandidateState.ACEPTADO
        c.final_action = "aceptado"
        c.reviewed_at = _now()
        self._add_history(proj.value, "candidato_aceptado", entity_id,
                          f"Candidate '{c.title}' accepted", c.id)
        return Ok(c)

    # UX4 (C5): mapeo de campo de edición → campo del dominio por tipo de objetivo.
    _ENTITY_FIELD_MAP = {
        "body": "extended_description",
        "extended_description": "extended_description",
        "brief_description": "brief_description",
        "description": "brief_description",
    }

    def _find_entity(self, project, name: str, selected_ids):
        nm = (name or "").strip().lower()
        if nm:
            for e in project.entities:
                if str(e.name).strip().lower() == nm:
                    return e
        for eid in (selected_ids or []):
            for e in project.entities:
                if e.id == eid:
                    return e
        return None

    def _find_relation(self, project, selected_ids):
        for rid in (selected_ids or []):
            for r in project.relations:
                if r.id == rid:
                    return r
        return None

    @staticmethod
    def _routes_as_edit(pd: Any) -> bool:
        """True si el candidato debe aplicarse como EDICIÓN a canon al aceptar.

        Una edición de relación (UX5e) puede cambiar solo el tipo, sin nuevo
        contenido, y se resuelve por la selección — no exige `edit_target_name`.
        """
        if not isinstance(pd, dict):
            return False
        has_value = bool(str(pd.get("edit_proposed_value") or "").strip())
        if pd.get("edit_kind") == "relation_edits":
            return has_value or bool(str(pd.get("edit_relation_type") or "").strip())
        return has_value and bool(str(pd.get("edit_target_name") or "").strip())

    def _apply_edit(self, project, c: Candidate) -> Result[tuple, str]:
        """Aplica una edición staged a canon. Resuelve el objetivo por nombre y,
        de respaldo, por la selección guardada en metadata.context_scope."""
        pd = c.proposed_data or {}
        kind = str(pd.get("edit_kind") or "entity_edits")
        target_name = str(pd.get("edit_target_name") or "").strip()
        field = str(pd.get("edit_field") or "").strip().lower()
        value = str(pd.get("edit_proposed_value") or "")
        scope = (getattr(c, "metadata", None) or {}).get("context_scope") or {}

        if kind in ("entity_edits", "entity"):
            if not self.entity_service:
                return Error("EntityService not available")
            ent = self._find_entity(project, target_name, scope.get("selected_entity_ids"))
            if ent is None:
                return Error(f"No se encontró la entidad a editar: '{target_name}'")
            dom_field = self._ENTITY_FIELD_MAP.get(field, "extended_description")
            res = self.entity_service.update_entity(ent.id, {dom_field: value})
            if isinstance(res, Error):
                return res
            return Ok(("entity", ent.id))

        if kind == "relation_edits":
            if not self.relation_service:
                return Error("RelationService not available")
            rel = self._find_relation(project, scope.get("selected_relation_ids"))
            if rel is None:
                return Error("No se encontró la relación a editar (sin selección).")
            # UX5e: una sola semilla puede traer tipo Y contenido; se aplican juntos.
            updates: dict[str, str] = {}
            new_type = str(pd.get("edit_relation_type") or "").strip()
            if not new_type and field == "relation_type":
                new_type = value.strip()  # compat: formato viejo type-only
            if new_type:
                updates["relation_type"] = new_type
            if value.strip() and field != "relation_type":
                updates["description"] = value
            if not updates:
                return Error("La edición de relación no propone ningún cambio.")
            res = self.relation_service.update_relation(rel.id, updates)
            if isinstance(res, Error):
                return res
            return Ok(("relation", rel.id))

        if kind == "ring_edits":
            nm = target_name.lower()
            layer = next((x for x in project.world_layers if str(x.name).lower() == nm), None)
            if layer is None:
                return Error(f"No se encontró el anillo a editar: '{target_name}'")
            if field == "order":
                try:
                    layer.order = int(value)
                except (TypeError, ValueError):
                    pass
            else:
                layer.description = value
            if hasattr(project, "touch"):
                project.touch()
            return Ok(("ring", layer.id))

        if kind == "milestone_edits":
            # Resolución por ID primero (estable ante renombrados: un edit de título
            # cambia el title, así que un segundo edit por título ya no casaría; el id
            # no cambia). Respaldo por título para compatibilidad.
            target_id = str(pd.get("edit_target_id") or "").strip()
            hito = None
            if target_id:
                hito = next(
                    (m for m in project.causal_milestones
                     if str(getattr(m, "id", "")) == target_id),
                    None,
                )
            if hito is None:
                nm = target_name.lower()
                hito = next((m for m in project.causal_milestones
                             if str(getattr(m, "title", "")).lower() == nm), None)
            if hito is None:
                return Error(f"No se encontró el hito a editar: '{target_name}'")
            attr = {"title": "title", "summary": "description", "description": "description",
                    "body": "rationale", "rationale": "rationale"}.get(field, "description")
            setattr(hito, attr, value)
            if hasattr(project, "touch"):
                project.touch()
            return Ok(("milestone", hito.id))

        return Error(f"Tipo de edición no soportado: {kind}")

    def accept_with_changes(self, cid: str, modified: dict) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        merged = dict(c.proposed_data)
        merged.update(modified)
        c.proposed_data = merged
        result = self.accept_candidate(cid)
        if not isinstance(result, Error):
            result.value.state = CandidateState.EDITADO_ACEPTADO
            result.value.final_action = "editado_aceptado"
        return result

    def partial_accept_candidate(
        self, cid: str, accepted: dict, note: str = "",
    ) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        c.state = CandidateState.PARCIALMENTE_ACEPTADO
        c.final_action = "parcialmente_aceptado"
        c.reviewed_at = _now()
        c.proposed_data = accepted
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._add_history(proj.value, "candidato_parcialmente_aceptado",
                          note=note, candidate_id=c.id)
        return Ok(c)

    def reject_candidate(self, cid: str, note: str = "") -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        c.state = CandidateState.RECHAZADO
        c.final_action = "rechazado"
        c.reviewed_at = _now()
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._add_history(proj.value, "candidato_rechazado",
                          note=note, candidate_id=c.id)
        return Ok(c)

    def postpone_candidate(self, cid: str) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        c.state = CandidateState.POSPUESTO
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._add_history(proj.value, "candidato_pospuesto", candidate_id=c.id)
        return Ok(c)

    def merge_candidate(self, cid: str, entity_id: str) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        target = None
        for e in proj.value.entities:
            if e.id == entity_id:
                target = e
                break
        if not target:
            return Error(f"Entity '{entity_id[:8]}' not found")
        # Merge: set non-empty fields from proposed_data onto target
        for key, val in c.proposed_data.items():
            if val and hasattr(target, key):
                setattr(target, key, val)
        c.state = CandidateState.FUSIONADO
        c.final_action = "fusionado"
        c.reviewed_at = _now()
        self._add_history(proj.value, "candidato_fusionado", entity_id,
                          f"Candidate '{c.title}' merged into entity", c.id)
        return Ok(c)

    def convert_candidate(self, cid: str, new_type: str) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        try:
            c.candidate_type = CandidateType(new_type)
        except ValueError:
            return Error(f"Invalid CandidateType: {new_type}")
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._add_history(proj.value, "candidato_convertido",
                          f"Converted to {new_type}", candidate_id=c.id)
        return Ok(c)

    def archive_candidate(self, cid: str) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        c.state = CandidateState.ARCHIVADO
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._add_history(proj.value, "candidato_archivado", candidate_id=c.id)
        return Ok(c)

    @staticmethod
    def _resolve_relation_endpoints_by_name(project: Any, proposed_data: dict) -> tuple[str, str]:
        """Resolve source_name/target_name to real entity IDs by fuzzy name match."""
        source_name = str(proposed_data.get("source_name") or "").strip().lower()
        target_name = str(proposed_data.get("target_name") or "").strip().lower()
        entities = list(getattr(project, "entities", []) or [])
        sid = ""
        tid = ""
        for entity in entities:
            name = str(getattr(entity, "name", "")).strip().lower()
            if not sid and source_name and name == source_name:
                sid = str(getattr(entity, "id", ""))
            elif not sid and source_name and source_name in name:
                sid = str(getattr(entity, "id", ""))
            if not tid and target_name and name == target_name:
                tid = str(getattr(entity, "id", ""))
            elif not tid and target_name and target_name in name:
                tid = str(getattr(entity, "id", ""))
        return sid, tid


__all__ = ["CandidateService"]
