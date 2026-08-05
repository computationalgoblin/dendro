"""Application service for causal milestones — B41-T02."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.application import causal_links
from packages.application.candidate_service import CandidateService
from packages.application.milestone_promotion import now_iso as _now_iso, promote_milestone
from packages.application.temporal_dating import normalize_milestone_dating
from packages.domain.candidate_issue import CandidateState
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok, Result


@dataclass
class CausalMilestoneService:
    """Use-case service for Hitos.

    Mutating methods update the active project in memory only. Persistence stays
    explicit through ProjectService.save(), matching the application-layer policy.
    """

    project_service: Any
    candidate_service: CandidateService | None = None
    history_service: Any = None

    def _proj(self):
        project = getattr(self.project_service, "active_project", None)
        if project is None:
            return Error("No active project")
        return Ok(project)

    def _get_hito(self, hito_id: str) -> Result[CausalMilestone, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        for hito in proj.value.causal_milestones:
            if hito.id == hito_id:
                return Ok(hito)
        return Error(f"Hito '{hito_id[:8]}' not found")

    def _record(self, event_type: str, description: str, hito: CausalMilestone) -> None:
        if not self.history_service:
            return
        payload = {
            "event_type": event_type,
            "description": description,
            "metadata": {"hito_id": hito.id, "hito_title": hito.title},
        }
        try:
            if hasattr(self.history_service, "add_entry"):
                self.history_service.add_entry(payload)
            elif hasattr(self.history_service, "record"):
                self.history_service.record(payload)
        except Exception:
            pass

    def _apply_default_year(self, hito: CausalMilestone) -> None:
        """BETA1-J04: ya NO se asume present_year. Un hito sin año queda 'por
        datar' (su ``temporality`` se marca pendiente); nunca un presente falso.
        La obligatoriedad es del write path de producto (``enforce_dating``).
        """
        normalize_milestone_dating(hito)

    def create_hito_candidate(
        self,
        data: dict[str, Any],
        source: str = "ia",
        confidence: float = 0.5,
    ):
        if self.candidate_service is None:
            return Error("CandidateService not available")
        hito = CausalMilestone.from_dict(data)
        hito.status = CausalMilestoneStatus.CANDIDATE
        self._apply_default_year(hito)
        return self.candidate_service.create_causal_milestone_candidate(
            hito,
            source=source,
            confidence=confidence,
            justification=hito.rationale,
        )

    def create_hito_manual(
        self, data: dict[str, Any], *, enforce_dating: bool = False
    ) -> Result[CausalMilestone, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        hito = CausalMilestone.from_dict(data)
        # BETA-MULTIAGENT2-FIX-03: misma promoción que las rutas de aceptación
        # (esta ya la hacía bien a mano; ahora no hay dos copias de la regla).
        promote_milestone(hito)
        if enforce_dating and not hito.as_temporal_span().is_dated():
            return Error(
                "El hito requiere un año antes de guardar "
                "(un año concreto o una precisión explícita)."
            )
        proj.value.causal_milestones.append(hito)
        # BETA-MULTIAGENT2-FIX-09: el hito puede nacer declarando padres; el espejo
        # del padre se reconstruye aquí (punto único), así que A sabe que tiene a B
        # como consecuencia sin que esta ruta escriba el enlace inverso a mano.
        causal_links.sync_children_mirror(proj.value)
        if hasattr(proj.value, "touch"):
            proj.value.touch()
        self._record("hito_creado", f"Hito '{hito.title}' creado manualmente", hito)
        return Ok(hito)

    def approve_hito(self, hito_or_candidate_id: str) -> Result[CausalMilestone, str]:
        existing = self._get_hito(hito_or_candidate_id)
        if isinstance(existing, Ok):
            existing.value.status = CausalMilestoneStatus.CANON
            existing.value.updated_at = _now_iso()
            self._record("hito_aprobado", f"Hito '{existing.value.title}' aprobado", existing.value)
            return existing

        if self.candidate_service is None:
            return existing
        candidate_result = self.candidate_service.get_candidate(hito_or_candidate_id)
        if isinstance(candidate_result, Error):
            return existing
        candidate = candidate_result.value
        proposed = candidate.proposed_data if isinstance(candidate.proposed_data, dict) else {}
        if proposed.get("kind") != "causal_milestone" or not isinstance(proposed.get("milestone"), dict):
            return Error("Candidate is not a causal milestone")

        hito = CausalMilestone.from_dict(proposed["milestone"])
        # BETA-MULTIAGENT2-FIX-03: la promoción (canon + datación honesta +
        # sellos + trazabilidad) vive en un único sitio y las tres rutas de
        # aceptación la comparten. Aquí estaba escrita a mano y era la ÚNICA
        # correcta; ahora es la referencia extraída.
        promote_milestone(hito, candidate_id=candidate.id)
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        proj.value.causal_milestones.append(hito)
        causal_links.sync_children_mirror(proj.value)  # FIX-09: reciprocidad
        if hasattr(proj.value, "touch"):
            proj.value.touch()
        candidate.state = CandidateState.ACEPTADO
        candidate.final_action = "aceptado"
        candidate.reviewed_at = datetime.now(timezone.utc)
        self._record("hito_aprobado", f"Hito '{hito.title}' aprobado desde candidato", hito)
        return Ok(hito)

    def reject_hito(self, hito_or_candidate_id: str) -> Result[CausalMilestone, str]:
        existing = self._get_hito(hito_or_candidate_id)
        if isinstance(existing, Ok):
            existing.value.status = CausalMilestoneStatus.REJECTED
            existing.value.updated_at = _now_iso()
            self._record("hito_rechazado", f"Hito '{existing.value.title}' rechazado", existing.value)
            return existing
        if self.candidate_service is not None:
            candidate_result = self.candidate_service.get_candidate(hito_or_candidate_id)
            if isinstance(candidate_result, Ok):
                self.candidate_service.reject_candidate(hito_or_candidate_id)
        return existing

    def update_hito(
        self, hito_id: str, data: dict[str, Any], impact_service: Any = None
    ) -> Result[CausalMilestone, str]:
        current = self._get_hito(hito_id)
        if isinstance(current, Error):
            return current
        # FIX-09: editar `causal_parent_hito_ids` puede QUITAR causas; el espejo del
        # padre que se va se limpia antes de reconciliar (si no, la adopción de
        # enlaces legados lo leería como una declaración y lo resucitaría).
        padres_previos = list(current.value.causal_parent_hito_ids or [])
        merged = current.value.to_dict()
        merged.update(data)
        updated = CausalMilestone.from_dict(merged)
        updated.updated_at = _now_iso()
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        for index, hito in enumerate(proj.value.causal_milestones):
            if hito.id == hito_id:
                hito.__dict__.update(updated.__dict__)
                padres_nuevos = set(hito.causal_parent_hito_ids or [])
                for retirado in padres_previos:
                    if retirado not in padres_nuevos:
                        causal_links.forget_child(proj.value, retirado, hito.id)
                causal_links.sync_children_mirror(proj.value)
                if hasattr(proj.value, "touch"):
                    proj.value.touch()
                self._record("hito_actualizado", f"Hito '{hito.title}' actualizado", hito)
                # BETA2-MEM-04: propaga impacto (Falta regar), sin romper el guardado.
                if impact_service is not None:
                    try:
                        impact_service.propagate_change("milestone", hito.id)
                    except Exception:  # noqa: BLE001
                        pass
                return Ok(hito)
        return Error(f"Hito '{hito_id[:8]}' not found")

    def delete_hito(self, hito_id: str) -> Result[CausalMilestone, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        normalized = str(hito_id or "").strip()
        if not normalized:
            return Error("Hito id required")
        for index, hito in enumerate(list(proj.value.causal_milestones)):
            if str(getattr(hito, "id", "")) != normalized:
                continue
            removed = proj.value.causal_milestones.pop(index)
            chronology = getattr(proj.value, "project_chronology", None)
            if chronology is not None and hasattr(chronology, "unlink_milestone"):
                chronology.unlink_milestone(normalized)
            for other in proj.value.causal_milestones:
                other.causal_parent_hito_ids = [
                    mid for mid in (other.causal_parent_hito_ids or []) if str(mid) != normalized
                ]
                other.causal_child_hito_ids = [
                    mid for mid in (other.causal_child_hito_ids or []) if str(mid) != normalized
                ]
                # BETA2-SUB-01: los subhitos del marco borrado quedan huérfanos
                # (nunca se borran en cascada).
                if str(getattr(other, "parent_milestone_id", "") or "") == normalized:
                    other.parent_milestone_id = None
            # FIX-09: tras limpiar ambos lados, el espejo se re-deriva (los hitos que
            # colgaban del borrado quedan sin punteros muertos en ninguna dirección).
            causal_links.sync_children_mirror(proj.value)
            if hasattr(proj.value, "touch"):
                proj.value.touch()
            self._record("hito_eliminado", f"Hito '{removed.title}' eliminado", removed)
            return Ok(removed)
        return Error(f"Hito '{normalized[:8]}' not found")

    # ── Subhitos: contención temporal de 1 nivel (BETA2-SUB-01) ──────────────

    def set_milestone_parent(self, child_id: str, parent_id: str) -> Result[CausalMilestone, str]:
        """Declara ``child_id`` como subhito de ``parent_id`` (hito-marco).

        Reglas de 1 nivel: existencia, sin auto-referencia, el marco no puede
        ser a su vez subhito, y el hijo no puede tener subhitos propios.
        """
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        child_id = str(child_id or "").strip()
        parent_id = str(parent_id or "").strip()
        if not child_id or not parent_id:
            return Error("Se requieren el subhito y el hito-marco")
        if child_id == parent_id:
            return Error("Un hito no puede contenerse a sí mismo")
        child = self._get_hito(child_id)
        if isinstance(child, Error):
            return child
        parent = self._get_hito(parent_id)
        if isinstance(parent, Error):
            return parent
        if parent.value.parent_milestone_id:
            return Error("El marco ya es un subhito: no se admite más de un nivel")
        if any(
            str(getattr(h, "parent_milestone_id", "") or "") == child_id
            for h in proj.value.causal_milestones
        ):
            return Error("Este hito ya contiene subhitos: no puede ser subhito de otro")
        child.value.parent_milestone_id = parent_id
        child.value.updated_at = _now_iso()
        if hasattr(proj.value, "touch"):
            proj.value.touch()
        self._record(
            "subhito_vinculado",
            f"Hito '{child.value.title}' contenido en '{parent.value.title}'",
            child.value,
        )
        return Ok(child.value)

    def clear_milestone_parent(self, child_id: str) -> Result[CausalMilestone, str]:
        """Saca a un subhito de su marco (queda de primer nivel)."""
        child = self._get_hito(child_id)
        if isinstance(child, Error):
            return child
        child.value.parent_milestone_id = None
        child.value.updated_at = _now_iso()
        proj = self._proj()
        if isinstance(proj, Ok) and hasattr(proj.value, "touch"):
            proj.value.touch()
        self._record(
            "subhito_desvinculado",
            f"Hito '{child.value.title}' ya no está contenido",
            child.value,
        )
        return Ok(child.value)

    def list_subhitos(self, parent_id: str) -> Result[list[CausalMilestone], str]:
        """Subhitos contenidos en ``parent_id`` (ordenados por año)."""
        parent_id = str(parent_id or "").strip()
        result = self._filter(
            lambda h: str(getattr(h, "parent_milestone_id", "") or "") == parent_id
        )
        if isinstance(result, Ok):
            result.value.sort(key=lambda h: h.year if isinstance(h.year, int) else 0)
        return result

    def create_subhito(
        self, parent_id: str, data: dict[str, Any], *, enforce_dating: bool = False
    ) -> Result[CausalMilestone, str]:
        """Crea un hito nuevo y lo contiene en el marco ``parent_id``."""
        parent = self._get_hito(str(parent_id or "").strip())
        if isinstance(parent, Error):
            return parent
        if parent.value.parent_milestone_id:
            return Error("El marco ya es un subhito: no se admite más de un nivel")
        created = self.create_hito_manual(data, enforce_dating=enforce_dating)
        if isinstance(created, Error):
            return created
        linked = self.set_milestone_parent(created.value.id, parent.value.id)
        if isinstance(linked, Error):
            # revertir el hito recién creado para no dejar basura suelta
            self.delete_hito(created.value.id)
            return linked
        return Ok(created.value)

    def list_hitos_for_leaf(self, leaf_id: str) -> Result[list[CausalMilestone], str]:
        return self._filter(lambda h: leaf_id in h.affected_entity_ids)

    def list_hitos_for_branch(self, branch_id: str) -> Result[list[CausalMilestone], str]:
        return self._filter(lambda h: branch_id in h.affected_branch_ids)

    def list_hitos_for_ring(self, ring_id: str) -> Result[list[CausalMilestone], str]:
        return self._filter(lambda h: ring_id in h.affected_layer_ids or ring_id in h.layer_ids)

    def list_hitos_for_relation(self, relation_id: str) -> Result[list[CausalMilestone], str]:
        return self._filter(lambda h: relation_id in h.caused_relation_ids)

    def _filter(self, predicate) -> Result[list[CausalMilestone], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        return Ok([hito for hito in proj.value.causal_milestones if predicate(hito)])

    # ── Hilo causal setup→payoff (BETA-MULTIAGENT2-FIX-09) ───────────────────

    def list_causal_parents(self, hito_id: str) -> Result[list[CausalMilestone], str]:
        """Hitos que este recoge (sus causas declaradas), en orden cronológico."""
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        existing = self._get_hito(str(hito_id or ""))
        if isinstance(existing, Error):
            return existing
        return Ok(causal_links.parents_of(proj.value, existing.value.id))

    def list_causal_children(self, hito_id: str) -> Result[list[CausalMilestone], str]:
        """Consecuencias declaradas de este hito, en orden cronológico.

        Derivadas de ``causal_parent_hito_ids`` (fuente de verdad): es la ÚNICA
        respuesta a «hijos de un hito» del repo.
        """
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        existing = self._get_hito(str(hito_id or ""))
        if isinstance(existing, Error):
            return existing
        return Ok(causal_links.children_of(proj.value, existing.value.id))

    def link_causal(self, child_id: str, parent_id: str) -> Result[CausalMilestone, str]:
        """Declara que ``child_id`` recoge lo que plantó ``parent_id``.

        Validaciones: ambos existen, sin auto-referencia, sin ciclos y sin
        duplicados (declararlo dos veces es idempotente, no duplica ids).
        """
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        child_id = str(child_id or "").strip()
        parent_id = str(parent_id or "").strip()
        if not child_id or not parent_id:
            return Error("Se requieren el hito y su causa")
        if child_id == parent_id:
            return Error("Un hito no puede ser consecuencia de sí mismo")
        child = self._get_hito(child_id)
        if isinstance(child, Error):
            return child
        parent = self._get_hito(parent_id)
        if isinstance(parent, Error):
            return parent
        if parent_id in (child.value.causal_parent_hito_ids or []):
            return Ok(child.value)  # ya declarado: idempotente
        # Sin ciclos: la causa no puede ser ya una consecuencia (directa o no)
        # del hito que se pretende colgar de ella.
        descendientes = {h.id for h in causal_links.causal_chain(proj.value, child_id)}
        if parent_id in descendientes:
            return Error("Ese hito ya es consecuencia de este: el hilo causal daría una vuelta")
        child.value.causal_parent_hito_ids = [
            *(child.value.causal_parent_hito_ids or []),
            parent_id,
        ]
        child.value.updated_at = _now_iso()
        causal_links.sync_children_mirror(proj.value)
        if hasattr(proj.value, "touch"):
            proj.value.touch()
        self._record(
            "hito_enlace_causal",
            f"Hito '{child.value.title}' recoge lo que plantó '{parent.value.title}'",
            child.value,
        )
        return Ok(child.value)

    def unlink_causal(self, child_id: str, parent_id: str) -> Result[CausalMilestone, str]:
        """Deshace el enlace causal ``parent_id`` → ``child_id`` por los dos lados."""
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        child_id = str(child_id or "").strip()
        parent_id = str(parent_id or "").strip()
        child = self._get_hito(child_id)
        if isinstance(child, Error):
            return child
        child.value.causal_parent_hito_ids = [
            pid for pid in (child.value.causal_parent_hito_ids or []) if str(pid) != parent_id
        ]
        child.value.updated_at = _now_iso()
        causal_links.forget_child(proj.value, parent_id, child_id)
        causal_links.sync_children_mirror(proj.value)
        if hasattr(proj.value, "touch"):
            proj.value.touch()
        self._record(
            "hito_desenlace_causal",
            f"Hito '{child.value.title}' deja de recoger un hito anterior",
            child.value,
        )
        return Ok(child.value)

    def reconcile_causal_links(self) -> Result[bool, str]:
        """Normaliza el hilo causal del proyecto activo (idempotente).

        Adopta los enlaces que un proyecto viejo trajera escritos SOLO en el
        espejo ``causal_child_hito_ids`` y reconstruye el espejo desde los
        padres. Es el punto ÚNICO de reconciliación; la lectura no depende de
        él (deriva siempre de los padres), así que abrir un v40 ya enseña la
        cadena completa aunque nadie lo llame.
        """
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        return Ok(causal_links.reconcile_causal_links(proj.value))

    def list_causal_chain(self, hito_id: str) -> Result[list[CausalMilestone], str]:
        """El hito + todas sus consecuencias, en orden CRONOLÓGICO.

        Antes recorría en ANCHURA una lista (`causal_child_hito_ids`) que no
        escribía nadie: devolvía un solo elemento, y con los inversos reparados a
        mano devolvía la cadena barajada.
        """
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        if not any(hito.id == hito_id for hito in proj.value.causal_milestones):
            return Error(f"Hito '{hito_id[:8]}' not found")
        return Ok(causal_links.causal_chain(proj.value, hito_id))

    def find_relations_without_hito(self) -> Result[list[NarrativeRelation], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        explained_ids = set()
        for hito in proj.value.causal_milestones:
            explained_ids.update(hito.caused_relation_ids)
        causal_types = {
            RelationType.CAUSO,
            RelationType.FUE_CAUSADO_POR,
            RelationType.DERIVA_DE,
            RelationType.CONDICIONA,
            RelationType.EXPLICA,
            RelationType.CONTRADICE,
            RelationType.PRODUCE_CONSECUENCIA_EN,
        }
        missing = [
            relation for relation in proj.value.relations
            if relation.relation_type in causal_types and relation.id not in explained_ids
        ]
        return Ok(missing)

    def find_hitos_without_consequences(self) -> Result[list[CausalMilestone], str]:
        """«Plantado sin recoger»: hitos que ningún hito posterior recoge.

        FIX-09: medía ``caused_relation_ids`` —relaciones causadas, otra cosa—, así
        que sobre el mundo del tester devolvía 20 de 20 y seguía dando 20/20 tras
        reparar toda la cadena a mano. Ahora mide **hijos causales** con la única
        implementación del repo (``causal_links.loose_threads``), que
        ``status_quo_explainer`` también consume en vez de repetirla.
        """
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        return Ok(causal_links.loose_threads(proj.value))
