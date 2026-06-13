"""ImportService — document import pipeline (B17-T03).

Provides the complete import pipeline: register Source, extract text,
generate import candidates, detect duplicates/contradictions,
create review basket, accept/reject candidates, and partial filtering.

Commit-at-end: no mutation of the project until all steps succeed.
Accept creates a Candidate B14 in PENDIENTE state — never canon directly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.domain.candidate_issue import Candidate, CandidateState, CandidateType
from packages.domain.import_models import (
    DocumentSegment,
    ImportBasket,
    ImportCandidate,
    ImportFormat,
    ImportReviewState,
)
from packages.domain.result import Error, Ok, Result
from packages.domain.source_history import Source, SourceType
from packages.infrastructure.text_extractor import create_extractor


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _milestone_year(payload: dict[str, Any]) -> int | None:
    values = [payload.get("year")]
    structured = payload.get("structured_date")
    if isinstance(structured, dict):
        values.extend([structured.get("year"), structured.get("current_year")])
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


# ── Candidate type mapping ─────────────────────────────────────────────


def _map_to_candidate_type(import_candidate_type: str) -> CandidateType:
    """Map ImportCandidate.candidate_type to CandidateType."""
    try:
        return CandidateType(import_candidate_type)
    except ValueError:
        # Best-effort fallback mapping
        mapping = {
            "entidad": CandidateType.ENTIDAD,
            "relacion": CandidateType.RELACION,
            "evento": CandidateType.ENTIDAD,
            "fuente": CandidateType.FUENTE,
            "cambio": CandidateType.CAMBIO,
            "correccion": CandidateType.CORRECCION,
            "fusion": CandidateType.FUSION,
            "incidencia": CandidateType.INCIDENCIA,
        }
        return mapping.get(import_candidate_type, CandidateType.ENTIDAD)


# ── Heuristic entity/realtion detection ─────────────────────────────────


def _detect_entities_from_text(text: str) -> list[dict]:
    """Detect named entity candidates via simple heuristics (no IA).

    Looks for:
      - Capitalized words/phrases (potential proper names)
      - Patterns like "X es un/una" (definitional)
    """
    candidates: list[dict] = []
    seen: set[str] = set()

    import re

    # Capitalized phrases (2+ words starting with uppercase)
    capitalized = re.findall(r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)\b', text)
    for phrase in capitalized:
        phrase = phrase.strip()
        if phrase not in seen and len(phrase) > 2:
            seen.add(phrase)
            candidates.append({"name": phrase, "type": "entidad"})

    # Single capitalized words (not at start of sentence — simple heuristic)
    words = re.findall(r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\b', text)
    for word in words:
        if word not in seen and word.lower() not in {"Que", "Los", "Las", "Del", "Por", "Con", "Una", "Para", "Como", "Pero", "Este", "Esta", "Entre"}:
            seen.add(word)
            candidates.append({"name": word, "type": "entidad"})

    return candidates


def _detect_relations_from_text(text: str) -> list[dict]:
    """Detect potential relations via simple verb patterns (no IA)."""
    import re
    relations: list[dict] = []

    patterns = [
        (r'(\w+)\s+(protege|protegió)\s+a?\s*(\w+)', "protege"),
        (r'(\w+)\s+(vive\s+en|habita\s+en|reside\s+en)\s+(.+)', "vive_en"),
        (r'(\w+)\s+(es\s+aliado\s+de|es\s+amigo\s+de)\s+(\w+)', "es_aliado_de"),
        (r'(\w+)\s+(es\s+enemigo\s+de|odia\s+a)\s+(\w+)', "es_enemigo_de"),
        (r'(\w+)\s+(gobierna|lidera|dirige)\s+(.+)', "gobierna"),
    ]

    for pattern, rel_type in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            source = match.group(1).capitalize()
            target = match.group(3).capitalize() if len(match.groups()) >= 3 else match.group(2)
            relations.append({
                "type": rel_type,
                "source_name": source,
                "target_name": target,
            })

    return relations


# ═══════════════════════════════════════════════════════════════════════════
# ImportService
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ImportService:
    """Pipeline for importing documents into the narrative knowledge base.

    Uses commit-at-end pattern: builds Source, segments, candidates
    and basket in memory, only appending to the project when all steps
    complete successfully.
    """

    project_service: Any  # ProjectService
    candidate_service: Any = None  # CandidateService
    source_service: Any = None  # SourceService
    entity_service: Any = None  # EntityService
    relation_service: Any = None  # RelationService

    def _proj(self) -> Result[Any, str]:
        p = self.project_service.active_project
        if p is None:
            return Error("No active project")
        return Ok(p)

    def _save(self, proj, project_path: Path | None = None) -> Result[None, str]:
        from packages.persistence.store import ProjectStore
        store = ProjectStore()
        if project_path:
            return store.save(proj, project_path)
        ps = self.project_service
        if hasattr(ps, "_current_path") and ps._current_path:
            return store.save(proj, ps._current_path)
        return Error("No project path to save to")

    # ── Pipeline ────────────────────────────────────────────────────────

    def import_document(
        self, file_path: str | Path, format: ImportFormat
    ) -> Result[ImportBasket, str]:
        """Full import pipeline: source → extract → candidates → basket.

        Args:
            file_path: Path to the document file.
            format: ImportFormat (TEXT_PLAIN or PDF).

        Returns:
            Ok(ImportBasket) with the review basket, or Err on failure.

        Commit-at-end: the project is not mutated until all steps succeed.
        """
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        proj = proj_r.value
        path = Path(file_path)

        # ── Step 1: Create Source (local, not yet in project) ──
        source_id = _new_id()
        source = Source(
            id=source_id,
            source_type=SourceType.DOCUMENTO_IMPORTADO,
            name=path.name,
            description=f"Imported from {path}",
        )

        # ── Step 2: Extract text ──
        extractor = create_extractor(format)
        extract_result = extractor.extract(path, source_id)
        if isinstance(extract_result, Error):
            return Error(extract_result.error)

        segments = extract_result.value
        if not segments:
            # Empty document — still create basket for review
            pass

        # ── Step 3: Generate import candidates ──
        import_candidates = self.generate_import_candidates(segments)

        # ── Step 4: Detect duplicates ──
        import_candidates = self.detect_duplicates(import_candidates, proj)

        # ── Step 5: Detect contradictions ──
        import_candidates = self.detect_contradictions(import_candidates, proj)

        # ── Step 6: Create basket ──
        basket = self.create_review_basket(source_id, segments, import_candidates, path=str(path), format=format.value)

        # ── COMMIT: only now add to project (no save — CLI handles that) ──
        proj.sources.append(source)
        proj.import_baskets.append(basket)

        return Ok(basket)

    def extract_segments(
        self, file_path: str | Path, format: ImportFormat, source_id: str
    ) -> Result[list[DocumentSegment], str]:
        """Extract text segments from a file.

        Args:
            file_path: Path to the document file.
            format: ImportFormat to use.
            source_id: Source UUID to assign to all segments.

        Returns:
            Ok(list[DocumentSegment]) or Err.
        """
        extractor = create_extractor(format)
        return extractor.extract(Path(file_path), source_id)

    def generate_import_candidates(
        self, segments: list[DocumentSegment]
    ) -> list[ImportCandidate]:
        """Generate ImportCandidates from document segments via heuristics.

        Detects entities (proper names) and relations (verb patterns).
        No IA in this block (§17.7).
        """
        candidates: list[ImportCandidate] = []
        for seg in segments:
            text = seg.raw_text

            # Entity candidates
            entities = _detect_entities_from_text(text)
            for ent in entities:
                cand = ImportCandidate(
                    id=_new_id(),
                    segment_id=seg.id,
                    candidate_type=CandidateType.ENTIDAD.value,
                    proposed_data={"name": ent.get("name", ""), "type": ent.get("type", "")},
                    confidence=0.5,
                    review_state=ImportReviewState.PENDIENTE,
                )
                candidates.append(cand)

            # Relation candidates
            relations = _detect_relations_from_text(text)
            for rel in relations:
                cand = ImportCandidate(
                    id=_new_id(),
                    segment_id=seg.id,
                    candidate_type=CandidateType.RELACION.value,
                    proposed_data={
                        "source_name": rel.get("source_name", ""),
                        "target_name": rel.get("target_name", ""),
                        "relation_type": rel.get("type", ""),
                    },
                    confidence=0.5,
                    review_state=ImportReviewState.PENDIENTE,
                )
                candidates.append(cand)

        return candidates

    def detect_duplicates(
        self, candidates: list[ImportCandidate], proj=None
    ) -> list[ImportCandidate]:
        """Mark possible_duplicates by comparing names against existing entities.

        Uses simple name matching (case-insensitive).
        """
        if proj is None:
            proj_r = self._proj()
            if isinstance(proj_r, Error):
                return candidates
            proj = proj_r.value

        existing_names: dict[str, str] = {}
        for entity in proj.entities:
            name = getattr(entity, "name", "")
            if name:
                existing_names[name.lower()] = entity.id

        for cand in candidates:
            name = cand.proposed_data.get("name", "")
            if name and name.lower() in existing_names:
                cand.possible_duplicates.append(existing_names[name.lower()])

        return candidates

    def detect_contradictions(
        self, candidates: list[ImportCandidate], proj=None
    ) -> list[ImportCandidate]:
        """Mark possible_contradictions via basic heuristics.

        For now, marks entities with the same name but different proposed types
        as potential contradictions. More sophisticated analysis deferred.
        """
        # Basic pass-through for now — marks possible_contradictions from
        # candidates with the same proposed name but different type
        name_to_cands: dict[str, list[ImportCandidate]] = {}
        for cand in candidates:
            name = cand.proposed_data.get("name", "")
            if name:
                name_to_cands.setdefault(name.lower(), []).append(cand)

        for name, group in name_to_cands.items():
            if len(group) > 1:
                for cand in group:
                    for other in group:
                        if other.id != cand.id:
                            cand.possible_contradictions.append(other.id)

        return candidates

    def create_review_basket(
        self,
        source_id: str,
        segments: list[DocumentSegment],
        candidates: list[ImportCandidate],
        path: str = "",
        format: str = "",
    ) -> ImportBasket:
        """Create an ImportBasket for review.

        Args:
            source_id: Source UUID.
            segments: Extracted document segments.
            candidates: Generated import candidates.
            path: Original file path (for metadata).
            format: Import format string (for metadata).
        """
        now = _now_iso()
        return ImportBasket(
            id=_new_id(),
            source_id=source_id,
            segments=segments,
            import_candidates=candidates,
            review_state="pendiente",
            created_at=now,
            updated_at=now,
            metadata={
                "source_id": source_id,
                "document_id": source_id,
                "file_name": Path(path).name if path else "",
                "file_path": path,
                "format": format,
                "import_format": format,
                "created_at": now,
                "imported_at": now,
                "extraction_warnings": [],
            },
        )

    # ── Accept / Reject ──────────────────────────────────────────────────

    def accept_import_candidate(
        self, basket_id: str, cand_id: str
    ) -> Result[Candidate, str]:
        """Accept an ImportCandidate → creates Candidate B14 PENDIENTE.

        NEVER creates an entity/relation directly. The user must run
        ``candidate accept <id>`` to promote to canon.

        Idempotent: double accept returns an error.
        """
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        proj = proj_r.value

        # Find basket and candidate
        basket = None
        for b in proj.import_baskets:
            if b.id == basket_id:
                basket = b
                break
        if basket is None:
            return Error(f"Import basket '{basket_id[:8]}' not found")

        import_cand = None
        for ic in basket.import_candidates:
            if ic.id == cand_id:
                import_cand = ic
                break
        if import_cand is None:
            return Error(f"Import candidate '{cand_id[:8]}' not found")

        # Idempotent guard
        allowed = {ImportReviewState.PENDIENTE, ImportReviewState.EDITADO, ImportReviewState.PARCIAL}
        if import_cand.review_state not in allowed:
            state_map = {
                ImportReviewState.ACEPTADO: f"Candidate ya fue aceptado: {cand_id[:8]}",
                ImportReviewState.RECHAZADO: "Candidate ya fue rechazado. Use import review un-reject para revertir.",
                ImportReviewState.FUSIONADO: "Candidate ya fue fusionado.",
            }
            msg = state_map.get(import_cand.review_state, f"Candidate ya fue procesado: {import_cand.review_state.value}")
            return Error(msg)

        # Map candidate_type to CandidateType
        ct = _map_to_candidate_type(import_cand.candidate_type)

        # Create Candidate B14 PENDIENTE
        proposed = dict(import_cand.proposed_data)
        if import_cand.proposed_relations:
            proposed["proposed_relations"] = list(import_cand.proposed_relations)
        cand_data = {
            "candidate_type": ct.value,
            "state": CandidateState.PENDIENTE.value,
            "proposed_data": proposed,
            "confidence": import_cand.confidence,
            "source_id": basket.source_id,
            "metadata": {
                "import_basket_id": basket_id,
                "segment_id": import_cand.segment_id,
                "import_candidate_id": cand_id,
            },
        }

        candidate = Candidate.from_dict(cand_data)
        proj.candidates.append(candidate)

        # Update import candidate state
        import_cand.review_state = ImportReviewState.ACEPTADO
        basket.updated_at = _now_iso()

        return Ok(candidate)

    def reject_import_candidate(
        self, basket_id: str, cand_id: str
    ) -> Result[None, str]:
        """Reject an ImportCandidate — changes review_state, no Candidate created."""
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        proj = proj_r.value

        basket = None
        for b in proj.import_baskets:
            if b.id == basket_id:
                basket = b
                break
        if basket is None:
            return Error(f"Import basket '{basket_id[:8]}' not found")

        import_cand = None
        for ic in basket.import_candidates:
            if ic.id == cand_id:
                import_cand = ic
                break
        if import_cand is None:
            return Error(f"Import candidate '{cand_id[:8]}' not found")

        if import_cand.review_state not in (
            ImportReviewState.PENDIENTE, ImportReviewState.EDITADO, ImportReviewState.PARCIAL,
        ):
            return Error(
                f"Cannot reject candidate in state '{import_cand.review_state.value}'. "
                f"Only PENDIENTE, EDITADO, or PARCIAL can be rejected."
            )

        import_cand.review_state = ImportReviewState.RECHAZADO
        basket.updated_at = _now_iso()

        return Ok(None)

    # ── Edit / Merge (B26-T00, DC-026, DC-027) ─────────────────────────

    def edit_import_candidate(self, basket_id, cand_id, data) -> Result[None, str]:
        proj_r = self._proj()
        if isinstance(proj_r, Error): return proj_r
        proj = proj_r.value
        basket, import_cand = self._find_basket_cand(proj, basket_id, cand_id)
        if basket is None: return Error(f"Import basket '{basket_id[:8]}' not found")
        if import_cand is None: return Error(f"Import candidate '{cand_id[:8]}' not found")
        if import_cand.review_state not in (ImportReviewState.PENDIENTE, ImportReviewState.EDITADO):
            return Error(f"Cannot edit candidate in state '{import_cand.review_state.value}'")
        if import_cand.proposed_data is None or not isinstance(import_cand.proposed_data, dict):
            import_cand.proposed_data = {}
        for key, value in dict(data or {}).items():
            if key in {"candidate_type", "type"}:
                import_cand.candidate_type = str(value)
            elif key == "desc":
                import_cand.proposed_data["description"] = value
            else:
                import_cand.proposed_data[str(key)] = value
        if import_cand.review_state == ImportReviewState.PENDIENTE:
            import_cand.review_state = ImportReviewState.EDITADO
        basket.updated_at = _now_iso()
        return Ok(None)

    def merge_import_candidates(self, basket_id, cand_ids) -> Result[ImportBasket, str]:
        proj_r = self._proj()
        if isinstance(proj_r, Error): return proj_r
        proj = proj_r.value
        basket = None
        for b in proj.import_baskets:
            if b.id == basket_id: basket = b; break
        if basket is None: return Error(f"Import basket '{basket_id[:8]}' not found")
        from packages.application.import_deduplication_service import ImportDeduplicationService
        dedupe = ImportDeduplicationService(project=proj)
        suggestion = dedupe.create_merge_suggestion(basket, list(cand_ids), reason="manual_merge")
        if isinstance(suggestion, Error):
            return suggestion
        accepted = dedupe.accept_merge_suggestion(basket, suggestion.value.id)
        if isinstance(accepted, Error):
            return accepted
        basket.updated_at = _now_iso()
        return Ok(basket)

    def _find_basket_cand(self, proj, basket_id, cand_id):
        basket = None; import_cand = None
        for b in proj.import_baskets:
            if b.id == basket_id: basket = b; break
        if basket:
            for ic in basket.import_candidates:
                if ic.id == cand_id: import_cand = ic; break
        return basket, import_cand

    # ── AI extraction (I03) ──────────────────────────────────────────────

    def extract_ai_candidates(
        self,
        basket_id: str,
        *,
        provider=None,
        allow_simulated: bool = False,
        replace_existing: bool = False,
        project_context: dict[str, Any] | None = None,
    ) -> Result[list[ImportCandidate], str]:
        """Analyze imported chunks with AI and append reviewable candidates.

        This method mutates only the import review basket. It never creates
        entities, relations, milestones or other canon objects.
        """
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        proj = proj_r.value
        basket = None
        for b in proj.import_baskets:
            if b.id == basket_id:
                basket = b
                break
        if basket is None:
            return Error(f"Import basket '{basket_id[:8]}' not found")

        from packages.application.import_ai_extraction_service import ImportAIExtractionService

        context = dict(project_context or {})
        context.setdefault("project_name", getattr(proj, "name", ""))
        extractor = ImportAIExtractionService(
            provider=provider,
            allow_simulated=allow_simulated,
        )
        return extractor.extract_for_basket(
            basket,
            project_context=context,
            replace_existing=replace_existing,
        )

    # ── Deduplication / aliases (I04) ────────────────────────────────────

    def analyze_import_duplicates(self, basket_id: str) -> Result[list[ImportCandidate], str]:
        """Create merge suggestions for duplicate/alias import candidates."""
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        proj = proj_r.value
        basket = None
        for b in proj.import_baskets:
            if b.id == basket_id:
                basket = b
                break
        if basket is None:
            return Error(f"Import basket '{basket_id[:8]}' not found")
        from packages.application.import_deduplication_service import ImportDeduplicationService
        return ImportDeduplicationService(project=proj).analyze_basket(basket, append=True)

    def accept_import_merge_suggestion(
        self, basket_id: str, suggestion_id: str
    ) -> Result[ImportCandidate, str]:
        """Accept a merge suggestion and create a merged review candidate."""
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        proj = proj_r.value
        basket = None
        for b in proj.import_baskets:
            if b.id == basket_id:
                basket = b
                break
        if basket is None:
            return Error(f"Import basket '{basket_id[:8]}' not found")
        from packages.application.import_deduplication_service import ImportDeduplicationService
        return ImportDeduplicationService(project=proj).accept_merge_suggestion(basket, suggestion_id)

    def reject_import_merge_suggestion(self, basket_id: str, suggestion_id: str) -> Result[None, str]:
        """Reject a merge suggestion without changing source candidates."""
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        proj = proj_r.value
        basket = None
        for b in proj.import_baskets:
            if b.id == basket_id:
                basket = b
                break
        if basket is None:
            return Error(f"Import basket '{basket_id[:8]}' not found")
        from packages.application.import_deduplication_service import ImportDeduplicationService
        return ImportDeduplicationService(project=proj).reject_merge_suggestion(basket, suggestion_id)

    # ── Review application (I05) ─────────────────────────────────────────

    def apply_import_candidate_to_canon(
        self,
        basket_id: str,
        cand_id: str,
    ) -> Result[Any, str]:
        """Apply a reviewed import candidate through normal app services.

        This is the explicit Review Workspace accept action. It never lets the
        UI write directly to project collections.
        """
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        proj = proj_r.value
        basket, import_cand = self._find_basket_cand(proj, basket_id, cand_id)
        if basket is None:
            return Error(f"Import basket '{basket_id[:8]}' not found")
        if import_cand is None:
            return Error(f"Import candidate '{cand_id[:8]}' not found")
        if import_cand.review_state not in (
            ImportReviewState.PENDIENTE, ImportReviewState.EDITADO, ImportReviewState.PARCIAL,
        ):
            return Error(f"Cannot apply candidate in state '{import_cand.review_state.value}'")

        payload = dict(import_cand.proposed_data or {})
        kind = str(payload.get("kind") or "").lower()
        if kind == "merge_suggestion":
            return self.accept_import_merge_suggestion(basket_id, cand_id)
        if kind == "import_issue":
            return Error("Import issues cannot be applied to canon")
        if kind in {"milestone", "causal_milestone"}:
            result = self._apply_milestone_candidate(proj, basket, import_cand, payload)
            if isinstance(result, Error):
                return result
            import_cand.review_state = ImportReviewState.ACEPTADO
            basket.updated_at = _now_iso()
            return result
        if import_cand.candidate_type == CandidateType.RELACION.value or kind == "relation":
            result = self._apply_relation_candidate(proj, basket, import_cand, payload)
        else:
            result = self._apply_entity_candidate(basket, import_cand, payload)
        if isinstance(result, Error):
            return result
        import_cand.review_state = ImportReviewState.ACEPTADO
        basket.updated_at = _now_iso()
        return result

    def _apply_entity_candidate(
        self,
        basket: ImportBasket,
        import_cand: ImportCandidate,
        payload: dict[str, Any],
    ) -> Result[Any, str]:
        name = str(payload.get("name") or payload.get("title") or payload.get("entity_name") or "").strip()
        if not name:
            return Error("Entity import candidate needs a name")
        kind = str(payload.get("kind") or "entity").lower()
        entity_type = (
            payload.get("entity_type")
            or payload.get("branch_type")
            or ("contenedor" if kind == "branch" else "nota")
        )
        custom_metadata = dict(payload.get("custom_metadata") or {})
        custom_metadata.update({
            "import_basket_id": basket.id,
            "import_candidate_id": import_cand.id,
            "source_references": list(payload.get("source_references") or []),
        })
        if kind == "branch":
            custom_metadata.setdefault("display_type", "rama")
            custom_metadata.setdefault("candidate_tree", True)
        data = {
            "name": name,
            "aliases": list(payload.get("aliases") or []),
            "entity_type": entity_type,
            "brief_description": payload.get("brief_description") or payload.get("summary") or "",
            "extended_description": payload.get("description") or payload.get("body") or "",
            "canon_state": "borrador",
            "visibility_state": payload.get("visibility") or "visible_usuario",
            "origin": "import_review",
            "custom_metadata": custom_metadata,
        }
        from packages.application.entity_service import EntityService
        entity_service = self.entity_service or EntityService(self.project_service)
        return entity_service.create_entity(data)

    def _apply_relation_candidate(
        self,
        proj,
        basket: ImportBasket,
        import_cand: ImportCandidate,
        payload: dict[str, Any],
    ) -> Result[Any, str]:
        source_id = str(payload.get("source_id") or "").strip()
        target_id = str(payload.get("target_id") or "").strip()
        if not source_id or not target_id:
            source_id, target_id = self._resolve_relation_endpoints_by_name(proj, payload)
        if not source_id or not target_id:
            return Error("No se pudieron encontrar las entidades para esta relacion importada")
        data = dict(payload)
        data["source_id"] = source_id
        data["target_id"] = target_id
        data.setdefault("description", payload.get("summary") or payload.get("body") or payload.get("evidence") or "")
        data.setdefault("source", "import_review")
        data["custom_metadata"] = dict(payload.get("custom_metadata") or {})
        data["custom_metadata"].update({
            "import_basket_id": basket.id,
            "import_candidate_id": import_cand.id,
            "source_references": list(payload.get("source_references") or []),
        })
        from packages.application.relation_service import RelationService
        relation_service = self.relation_service or RelationService(self.project_service)
        return relation_service.create_relation(
            source_id=source_id,
            target_id=target_id,
            relation_type=payload.get("relation_type") or "esta_relacionado_con",
            data=data,
        )

    def _apply_milestone_candidate(
        self,
        proj,
        basket: ImportBasket,
        import_cand: ImportCandidate,
        payload: dict[str, Any],
    ) -> Result[Any, str]:
        title = str(payload.get("title") or payload.get("name") or "").strip()
        if not title:
            return Error("Milestone import candidate needs a title")
        milestone_payload = {
            "id": payload.get("id") or "",
            "title": title,
            "description": payload.get("description") or payload.get("summary") or payload.get("body") or "",
            "milestone_type": payload.get("milestone_type") or "otro",
            "layer_ids": list(payload.get("layer_ids") or payload.get("linked_ring_ids") or []),
            "affected_entity_ids": list(payload.get("affected_entity_ids") or payload.get("linked_entity_ids") or []),
            "affected_branch_ids": list(payload.get("affected_branch_ids") or payload.get("linked_branch_ids") or []),
            "affected_layer_ids": list(payload.get("affected_layer_ids") or []),
            "caused_relation_ids": list(payload.get("caused_relation_ids") or payload.get("linked_relation_ids") or []),
            "causal_parent_hito_ids": list(payload.get("causal_parent_hito_ids") or []),
            "causal_child_hito_ids": list(payload.get("causal_child_hito_ids") or []),
            "source_ids": [basket.source_id] if basket.source_id else [],
            "confidence": import_cand.confidence,
            "rationale": payload.get("confidence_reason") or payload.get("evidence") or "",
            "tags": list(payload.get("tags") or []),
            "visibility_state": payload.get("visibility") or "visible_usuario",
            "metadata": {
                "import_basket_id": basket.id,
                "import_candidate_id": import_cand.id,
                "source_references": list(payload.get("source_references") or []),
                "date_label": payload.get("date_label", ""),
                "structured_date": payload.get("structured_date") or {},
            },
            "year": _milestone_year(payload),
        }
        from packages.application.causal_milestone_service import CausalMilestoneService
        milestone_service = CausalMilestoneService(project_service=self.project_service)
        result = milestone_service.create_hito_manual(milestone_payload)
        if isinstance(result, Error):
            return result
        chronology = getattr(proj, "project_chronology", None)
        if chronology is not None and hasattr(chronology, "link_milestone"):
            chronology.link_milestone(result.value.id)
        return result

    @staticmethod
    def _resolve_relation_endpoints_by_name(project: Any, proposed_data: dict) -> tuple[str, str]:
        source_name = str(proposed_data.get("source_name") or "").strip().lower()
        target_name = str(proposed_data.get("target_name") or "").strip().lower()
        sid = ""
        tid = ""
        for entity in list(getattr(project, "entities", []) or []):
            name = str(getattr(entity, "name", "") or "").strip().lower()
            aliases = [str(alias).strip().lower() for alias in getattr(entity, "aliases", []) or []]
            names = [name, *aliases]
            if not sid and source_name and any(source_name == n or source_name in n for n in names):
                sid = str(getattr(entity, "id", ""))
            if not tid and target_name and any(target_name == n or target_name in n for n in names):
                tid = str(getattr(entity, "id", ""))
        return sid, tid

    # ── Partial / Filtered view ──────────────────────────────────────────

    def partial_import(
        self, basket_id: str, filters: dict[str, Any] | None = None
    ) -> Result[ImportBasket, str]:
        """Return a filtered view of the basket — does NOT mutate canon.

        Filters can include: characters_only, locations_only, factions_only, etc.
        """
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        proj = proj_r.value

        basket = None
        for b in proj.import_baskets:
            if b.id == basket_id:
                basket = b
                break
        if basket is None:
            return Error(f"Import basket '{basket_id[:8]}' not found")

        if not filters:
            return Ok(basket)

        # Apply filters
        filtered_candidates = []
        for cand in basket.import_candidates:
            include = True
            if filters.get("characters_only") and cand.candidate_type != CandidateType.ENTIDAD.value:
                include = False
            if filters.get("locations_only") and cand.candidate_type != CandidateType.ENTIDAD.value:
                include = False
            if filters.get("factions_only") and cand.candidate_type != CandidateType.ENTIDAD.value:
                include = False
            if filters.get("relations_only") and cand.candidate_type != CandidateType.RELACION.value:
                include = False
            if filters.get("events_only") and cand.candidate_type != CandidateType.ENTIDAD.value:
                include = False
            if include:
                filtered_candidates.append(cand)

        # Return a shallow copy of the basket with filtered candidates
        filtered_basket = ImportBasket(
            id=basket.id,
            source_id=basket.source_id,
            segments=basket.segments,
            import_candidates=filtered_candidates,
            review_state=basket.review_state,
            created_at=basket.created_at,
            updated_at=basket.updated_at,
            metadata=dict(basket.metadata),
        )
        return Ok(filtered_basket)

    # ── Basket queries ───────────────────────────────────────────────────

    def list_baskets(self) -> Result[list[ImportBasket], str]:
        """List all import baskets in the active project."""
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        return Ok(list(proj_r.value.import_baskets))

    def get_basket(self, basket_id: str) -> Result[ImportBasket, str]:
        """Get a specific import basket by ID."""
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        for b in proj_r.value.import_baskets:
            if b.id == basket_id:
                return Ok(b)
        return Error(f"Import basket '{basket_id[:8]}' not found")
