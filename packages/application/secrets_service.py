"""SecretsService — CRUD, revelation, clues, knowledge queries, issue detection (B21-T03).

Knowledge is modeled via RelationService + KnowledgeRelationType.
who_knows_* fields are manual auxiliary lists, NOT auto-synced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from packages.domain.secrets_models import (
    Secreto,
    Pista,
    RevelationState,
    DeliveryState,
    ClueForm,
    _now,
)
from packages.domain.candidate_issue import StructuredIssue
from packages.domain.project import Project
from packages.domain.result import Error, Ok, Result


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── KnowledgeRelationType ────────────────────────────────────────────


class KnowledgeRelationType(str, Enum):
    """Knowledge relation types — independent of core RelationType."""
    SABE = "sabe"
    CREE = "cree"
    SOSPECHA = "sospecha"
    IGNORA = "ignora"
    MALINTERPRETA = "malinterpreta"
    OCULTA = "oculta"
    HA_OIDO = "ha_oido"
    HA_VISTO = "ha_visto"
    HA_RECIBIDO_PISTA = "ha_recibido_pista"
    CONOCE_PARCIALMENTE = "conoce_parcialmente"
    CONOCE_FALSAMENTE = "conoce_falsamente"


# ── Revelation transitions ───────────────────────────────────────────

_VALID_TRANSITIONS: dict[RevelationState, set[RevelationState]] = {
    RevelationState.oculto: {
        RevelationState.rumoreado,
        RevelationState.parcialmente_revelado,
        RevelationState.malinterpretado,
        RevelationState.revelado,
    },
    RevelationState.rumoreado: {
        RevelationState.parcialmente_revelado,
        RevelationState.revelado,
    },
    RevelationState.malinterpretado: {
        RevelationState.parcialmente_revelado,
    },
    RevelationState.parcialmente_revelado: {
        RevelationState.revelado,
    },
    RevelationState.revelado: set(),  # no forward transitions (force only)
}


@dataclass
class SecretsService:
    project_service: Any  # ProjectService
    entity_service: Any = None  # EntityService
    relation_service: Any = None  # RelationService
    issue_service: Any = None  # IssueService

    def _active_project(self) -> Project:
        return self.project_service.active_project

    # ── CRUD: Secrets ──────────────────────────────────────────────

    def create_secret(self, data: dict) -> Result[Secreto, str]:
        proj = self._active_project()
        if not data.get("content", "").strip():
            return Error("Secret content is required")

        importance = data.get("importance", 3)
        if isinstance(importance, (int, float)) and not isinstance(importance, bool):
            if importance < 1 or importance > 5:
                return Error(f"importance must be 1-5, got {importance}")

        secret = Secreto.from_dict(data)
        proj.secrets.append(secret)
        proj.touch()
        return Ok(secret)

    def get_secret(self, secret_id: str) -> Result[Secreto, str]:
        for s in self._active_project().secrets:
            if s.id == secret_id:
                return Ok(s)
        return Error(f"Secreto '{secret_id}' not found")

    def list_secrets(self, state: str | None = None) -> list[Secreto]:
        secrets = self._active_project().secrets
        if state:
            from packages.domain.secrets_models import _parse_enum
            target = _parse_enum(RevelationState, state, None)
            if target is not None:
                return [s for s in secrets if s.revelation_state == target]
        return list(secrets)

    def update_secret(self, secret_id: str, data: dict) -> Result[Secreto, str]:
        result = self.get_secret(secret_id)
        if isinstance(result, Error):
            return result
        secret = result.value

        for field in ("content", "revelation_form", "canon_state", "visibility_state"):
            if field in data:
                setattr(secret, field, data[field])
        for list_field in (
            "affected_entity_ids", "who_knows_entity_ids", "who_suspects_entity_ids",
            "who_ignores_entity_ids", "who_hides_entity_ids", "revelation_consequences",
            "concealment_consequences", "planned_revelation_session_ids",
        ):
            if list_field in data and isinstance(data[list_field], list):
                setattr(secret, list_field, data[list_field])
        if "importance" in data:
            imp = data["importance"]
            if isinstance(imp, (int, float)) and not isinstance(imp, bool):
                if imp < 1 or imp > 5:
                    return Error(f"importance must be 1-5, got {imp}")
                secret.importance = int(imp)

        secret.updated_at = _now()
        self._active_project().touch()
        return Ok(secret)

    def reveal_secret(
        self, secret_id: str, state: str, session_id: str | None = None,
        form: str | None = None, force: bool = False,
    ) -> Result[Secreto, str]:
        from packages.domain.secrets_models import _parse_enum
        result = self.get_secret(secret_id)
        if isinstance(result, Error):
            return result
        secret = result.value

        target = _parse_enum(RevelationState, state, None)
        if target is None:
            return Error(f"Invalid revelation state: '{state}'")

        current = secret.revelation_state
        if not force and target not in _VALID_TRANSITIONS.get(current, set()):
            return Error(
                f"Cannot transition from '{current.value}' to '{target.value}'. "
                f"Valid transitions: {[t.value for t in _VALID_TRANSITIONS.get(current, set())]}"
            )

        secret.revelation_state = target
        if session_id:
            secret.actual_revelation_session_id = session_id
        if form:
            secret.revelation_form = form
        secret.updated_at = _now()
        self._active_project().touch()
        return Ok(secret)

    def get_hidden_secrets(self) -> list[Secreto]:
        return [s for s in self._active_project().secrets
                if s.revelation_state != RevelationState.revelado]

    # ── CRUD: Clues ────────────────────────────────────────────────

    def create_clue(self, data: dict) -> Result[Pista, str]:
        proj = self._active_project()
        if not data.get("content", "").strip():
            return Error("Clue content is required")

        for field in ("clarity", "redundancy", "loss_risk"):
            val = data.get(field)
            if val is not None and isinstance(val, (int, float)) and not isinstance(val, bool):
                if val < 1 or val > 5:
                    return Error(f"{field} must be 1-5, got {val}")

        # Validate associated_secret_id if provided
        secret_id = data.get("associated_secret_id")
        if secret_id and isinstance(secret_id, str) and secret_id.strip():
            found = any(s.id == secret_id for s in proj.secrets)
            if not found:
                return Error(f"Secret '{secret_id}' not found")

        clue = Pista.from_dict(data)
        proj.clues.append(clue)
        proj.touch()
        return Ok(clue)

    def get_clue(self, clue_id: str) -> Result[Pista, str]:
        for c in self._active_project().clues:
            if c.id == clue_id:
                return Ok(c)
        return Error(f"Pista '{clue_id}' not found")

    def list_clues(self, state: str | None = None) -> list[Pista]:
        clues = self._active_project().clues
        if state:
            from packages.domain.secrets_models import _parse_enum
            target = _parse_enum(DeliveryState, state, None)
            if target is not None:
                return [c for c in clues if c.delivery_state == target]
        return list(clues)

    def update_clue(self, clue_id: str, data: dict) -> Result[Pista, str]:
        result = self.get_clue(clue_id)
        if isinstance(result, Error):
            return result
        clue = result.value

        for field in ("content", "probable_interpretation"):
            if field in data:
                setattr(clue, field, data[field])
        for list_field in ("planned_session_ids", "possible_misinterpretations", "character_ids_who_know"):
            if list_field in data and isinstance(data[list_field], list):
                setattr(clue, list_field, data[list_field])
        for field in ("clarity", "redundancy", "loss_risk"):
            val = data.get(field)
            if val is not None and isinstance(val, (int, float)) and not isinstance(val, bool):
                if val < 1 or val > 5:
                    return Error(f"{field} must be 1-5, got {val}")
                setattr(clue, field, int(val))

        clue.updated_at = _now()
        self._active_project().touch()
        return Ok(clue)

    def deliver_clue(
        self, clue_id: str, state: str = "entregada",
        session_id: str | None = None, character_ids: list[str] | None = None,
    ) -> Result[Pista, str]:
        from packages.domain.secrets_models import _parse_enum
        result = self.get_clue(clue_id)
        if isinstance(result, Error):
            return result
        clue = result.value

        target = _parse_enum(DeliveryState, state, None)
        if target is None:
            return Error(f"Invalid delivery state: '{state}'")

        clue.delivery_state = target
        if session_id:
            clue.delivered_session_id = session_id
        if character_ids:
            for cid in character_ids:
                if cid not in clue.character_ids_who_know:
                    clue.character_ids_who_know.append(cid)
        clue.updated_at = _now()
        self._active_project().touch()
        return Ok(clue)

    def link_clue_to_secret(self, clue_id: str, secret_id: str) -> Result[Pista, str]:
        result = self.get_clue(clue_id)
        if isinstance(result, Error):
            return result
        sec_result = self.get_secret(secret_id)
        if isinstance(sec_result, Error):
            return Error(f"Secret '{secret_id}' not found")

        clue = result.value
        clue.associated_secret_id = secret_id
        secret = sec_result.value
        if clue_id not in secret.associated_clue_ids:
            secret.associated_clue_ids.append(clue_id)
        clue.updated_at = _now()
        self._active_project().touch()
        return Ok(clue)

    def unlink_clue_from_secret(self, clue_id: str) -> Result[Pista, str]:
        result = self.get_clue(clue_id)
        if isinstance(result, Error):
            return result
        clue = result.value
        if clue.associated_secret_id:
            sec_result = self.get_secret(clue.associated_secret_id)
            if isinstance(sec_result, Ok):
                secret = sec_result.value
                if clue_id in secret.associated_clue_ids:
                    secret.associated_clue_ids.remove(clue_id)
        clue.associated_secret_id = None
        clue.updated_at = _now()
        self._active_project().touch()
        return Ok(clue)

    def get_pending_clues(self) -> list[Pista]:
        return [c for c in self._active_project().clues
                if c.delivery_state == DeliveryState.pendiente]

    # ── Knowledge queries ──────────────────────────────────────────

    def get_knowledge_for_character(self, entity_id: str) -> dict:
        """What secrets and clues an entity knows, based on RelationService."""
        proj = self._active_project()
        secrets_known = []
        clues_received = []

        if self.relation_service is not None:
            rs = self.relation_service
            # Find relations where entity is source and target is a secret/clue
            for rel in proj.relations:
                if rel.source_id != entity_id:
                    continue
                # Check if target is a secret
                for s in proj.secrets:
                    if rel.target_id == s.id and rel.relation_type in (
                        KnowledgeRelationType.SABE.value,
                        KnowledgeRelationType.CONOCE_PARCIALMENTE.value,
                        KnowledgeRelationType.CREE.value,
                        KnowledgeRelationType.SOSPECHA.value,
                        KnowledgeRelationType.HA_OIDO.value,
                        KnowledgeRelationType.HA_VISTO.value,
                    ):
                        secrets_known.append({"secret_id": s.id, "content": s.content, "type": rel.relation_type})
                # Check if target is a clue
                for c in proj.clues:
                    if rel.target_id == c.id and rel.relation_type == KnowledgeRelationType.HA_RECIBIDO_PISTA.value:
                        clues_received.append({"clue_id": c.id, "content": c.content})

        # Also check manual lists
        for s in proj.secrets:
            if entity_id in s.who_knows_entity_ids:
                if not any(sk["secret_id"] == s.id for sk in secrets_known):
                    secrets_known.append({"secret_id": s.id, "content": s.content, "type": "manual"})
            if entity_id in s.who_suspects_entity_ids:
                if not any(sk["secret_id"] == s.id for sk in secrets_known):
                    secrets_known.append({"secret_id": s.id, "content": s.content, "type": "suspects"})

        return {"entity_id": entity_id, "secrets_known": secrets_known, "clues_received": clues_received}

    def get_knowledge_for_player(self, player_id: str, campaign_id: str) -> dict:
        """Aggregate knowledge from all PCs of a player."""
        # Requires CampaignService to resolve PCs
        try:
            from packages.application.campaign_service import CampaignService
            if isinstance(self.project_service, object):
                ps = self.project_service
                # Try to get campaign service
                cs = CampaignService(project_service=ps, entity_service=self.entity_service)
                campaign = cs.get_campaign(campaign_id)
                if isinstance(campaign, Error):
                    return {"player_id": player_id, "error": str(campaign.error)}
                camp = campaign.value

                all_secrets = []
                all_clues = []
                for pc_eid in camp.player_character_entity_ids:
                    k = self.get_knowledge_for_character(pc_eid)
                    all_secrets.extend(k.get("secrets_known", []))
                    all_clues.extend(k.get("clues_received", []))

                # Deduplicate
                seen_sec = set()
                unique_secrets = []
                for s in all_secrets:
                    if s["secret_id"] not in seen_sec:
                        seen_sec.add(s["secret_id"])
                        unique_secrets.append(s)

                seen_clu = set()
                unique_clues = []
                for c in all_clues:
                    if c["clue_id"] not in seen_clu:
                        seen_clu.add(c["clue_id"])
                        unique_clues.append(c)

                return {"player_id": player_id, "campaign_id": campaign_id,
                        "secrets_known": unique_secrets, "clues_received": unique_clues}
        except Exception:
            pass
        return {"player_id": player_id, "campaign_id": campaign_id, "error": "CampaignService unavailable"}

    def get_knowledge_for_faction(self, faction_entity_id: str) -> dict:
        """What a faction knows."""
        return self.get_knowledge_for_character(faction_entity_id)

    # ── Preview (no side effects) ──────────────────────────────────

    def find_secrets_without_clues(self) -> list[Secreto]:
        proj = self._active_project()
        return [s for s in proj.secrets if not s.associated_clue_ids]

    def find_clues_without_secret(self) -> list[Pista]:
        proj = self._active_project()
        return [c for c in proj.clues if not c.associated_secret_id]

    def find_revealed_without_consequences(self) -> list[Secreto]:
        proj = self._active_project()
        return [
            s for s in proj.secrets
            if s.revelation_state == RevelationState.revelado and not s.revelation_consequences
        ]

    # ── Issue creation (idempotent) ────────────────────────────────

    def run_secret_validation(self) -> list[StructuredIssue]:
        """Create StructuredIssues for detected problems. Idempotent."""
        from packages.domain.candidate_issue import (
            StructuredIssue, StructuredIssueType, StructuredIssueSeverity,
        )
        issues: list[StructuredIssue] = []

        secrets_without_clues = self.find_secrets_without_clues()
        for s in secrets_without_clues:
            if not self._has_open_issue("secret_without_clues", [s.id]):
                issue = StructuredIssue(
                    type=StructuredIssueType.BROKEN_RELATION,
                    severity=StructuredIssueSeverity.MEDIA,
                    description=f"Secret '{s.content[:60]}' ({s.id}) has no associated clues",
                    affected_entity_ids=[s.id],
                    metadata={"subtype": "secret_without_clues"},
                )
                issues.append(issue)

        clues_without_secret = self.find_clues_without_secret()
        for c in clues_without_secret:
            if not self._has_open_issue("clue_without_secret", [c.id]):
                issue = StructuredIssue(
                    type=StructuredIssueType.BROKEN_RELATION,
                    severity=StructuredIssueSeverity.MEDIA,
                    description=f"Clue '{c.content[:60]}' ({c.id}) has no associated secret",
                    affected_entity_ids=[c.id],
                    metadata={"subtype": "clue_without_secret"},
                )
                issues.append(issue)

        revealed_no_consequences = self.find_revealed_without_consequences()
        for s in revealed_no_consequences:
            if not self._has_open_issue("revealed_without_consequences", [s.id]):
                issue = StructuredIssue(
                    type=StructuredIssueType.NO_DESCRIPTION,
                    severity=StructuredIssueSeverity.BAJA,
                    description=f"Secret '{s.content[:60]}' ({s.id}) is revealed but has no consequences",
                    affected_entity_ids=[s.id],
                    metadata={"subtype": "revealed_without_consequences"},
                )
                issues.append(issue)

        # Save issues to project
        if issues:
            proj = self._active_project()
            for issue in issues:
                proj.issues.append(issue)

        return issues

    def _has_open_issue(self, subtype: str, entity_ids: list[str]) -> bool:
        """Check if an open issue of the same subtype and entities already exists."""
        proj = self._active_project()
        entity_set = set(entity_ids)
        for issue in proj.issues:
            if issue.state.value == "abierta":
                if set(issue.affected_entity_ids) == entity_set:
                    if issue.metadata.get("subtype") == subtype:
                        return True
        return False
