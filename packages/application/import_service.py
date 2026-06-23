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
    ImportMode,
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

    @staticmethod
    def _taxonomy_dict(proj: Any) -> dict[str, Any]:
        taxonomy = getattr(proj, "import_taxonomy", None)
        if taxonomy is not None and hasattr(taxonomy, "to_dict"):
            return taxonomy.to_dict()
        return {}

    @staticmethod
    def _canon_digest(proj: Any, *, limit: int = 40) -> dict[str, Any]:
        """Resumen compacto del canon (nombres) para desambiguar la extracción."""
        entities: list[str] = []
        branches: list[str] = []
        for ent in getattr(proj, "entities", []) or []:
            name = getattr(ent, "name", "")
            if not name:
                continue
            etype = getattr(getattr(ent, "entity_type", None), "value", "")
            if etype == "contenedor":
                branches.append(name)
            else:
                entities.append(name)
        rings = [
            f"{getattr(wl, 'id', '')}|{getattr(wl, 'name', '')}"
            for wl in getattr(proj, "world_layers", []) or []
            if getattr(wl, "name", "")
        ]
        return {
            "entities": entities[:limit],
            "branches": branches[:limit],
            "rings": rings[:limit],
        }

    # ── Pipeline ────────────────────────────────────────────────────────

    def import_document(
        self,
        file_path: str | Path,
        format: ImportFormat,
        *,
        mode: ImportMode = ImportMode.CANON,
    ) -> Result[ImportBasket, str]:
        """Full import pipeline: source → extract → basket (bifurcado por modo).

        Args:
            file_path: Path to the document file.
            format: ImportFormat (TEXT_PLAIN, MARKDOWN or PDF).
            mode: ImportMode. CANON extrae candidatos para revisión→canon;
                CONTEXTO indexa el documento como material de referencia (sin
                candidatos de canon).

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

        # ── Step 3: Build basket por modo ──
        if mode == ImportMode.CONTEXTO:
            basket = self._build_contexto_basket(source_id, segments, path, format)
        else:
            basket = self._build_canon_basket(source_id, segments, path, format)

        # ── COMMIT: only now add to project (no save — CLI handles that) ──
        proj.sources.append(source)
        proj.import_baskets.append(basket)

        return Ok(basket)

    def _build_canon_basket(
        self,
        source_id: str,
        segments: list[DocumentSegment],
        path: Path,
        format: ImportFormat,
    ) -> ImportBasket:
        """Modo Canon: el basket nace SIN candidatos.

        La extracción es un paso explícito posterior por IA (``extract_ai_candidates``,
        lanzado en un worker de fondo). La heurística de palabras queda retirada del
        flujo canon (los métodos ``generate_import_candidates`` / ``detect_*`` se
        conservan para uso programático y tests, pero ya no se invocan aquí)."""
        return self.create_review_basket(
            source_id, segments, [],
            path=str(path), format=format.value, import_mode=ImportMode.CANON.value,
        )

    def _build_contexto_basket(
        self,
        source_id: str,
        segments: list[DocumentSegment],
        path: Path,
        format: ImportFormat,
    ) -> ImportBasket:
        """Modo Contexto: sin candidatos de canon; los segmentos quedan como
        material de referencia indexable en el RAG. El resumen IA se genera
        bajo demanda (paso separado, como la extracción IA)."""
        return self.create_review_basket(
            source_id, segments, [],
            path=str(path), format=format.value, import_mode=ImportMode.CONTEXTO.value,
        )

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
        import_mode: str = "canon",
    ) -> ImportBasket:
        """Create an ImportBasket for review.

        Args:
            source_id: Source UUID.
            segments: Extracted document segments.
            candidates: Generated import candidates.
            path: Original file path (for metadata).
            format: Import format string (for metadata).
            import_mode: ImportMode.value ("canon"/"contexto"). Se espeja en
                metadata para que corpus_indexer lo lea sin depender del modelo.
        """
        now = _now_iso()
        return ImportBasket(
            id=_new_id(),
            source_id=source_id,
            segments=segments,
            import_candidates=candidates,
            review_state="pendiente",
            import_mode=import_mode,
            created_at=now,
            updated_at=now,
            metadata={
                "source_id": source_id,
                "document_id": source_id,
                "file_name": Path(path).name if path else "",
                "file_path": path,
                "format": format,
                "import_format": format,
                "import_mode": import_mode,
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
        progress_callback: Any = None,
        should_cancel: Any = None,
        max_workers: int | None = None,
        generate_config: bool = False,
    ) -> Result[list[ImportCandidate], str]:
        """Analyze imported chunks with AI and append reviewable candidates.

        This method mutates only the import review basket. It never creates
        entities, relations, milestones or other canon objects.

        ``progress_callback(done, total, label)`` y ``should_cancel()`` permiten
        feedback por segmento y cancelación (los usa el worker de la UI).
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

        from packages.application.import_ai_extraction_service import (
            ImportAIExtractionService,
            resolve_import_concurrency,
        )

        workers = max_workers if max_workers is not None else resolve_import_concurrency()
        context = dict(project_context or {})
        context.setdefault("project_name", getattr(proj, "name", ""))
        # Modo Canon dirigido: la IA recibe la taxonomía del proyecto y un
        # resumen del canon existente para extraer coherente y sin duplicar.
        context.setdefault("import_taxonomy", self._taxonomy_dict(proj))
        context.setdefault("canon_digest", self._canon_digest(proj))
        extractor = ImportAIExtractionService(
            provider=provider,
            allow_simulated=allow_simulated,
            max_workers=workers,
        )
        result = extractor.extract_for_basket(
            basket,
            project_context=context,
            replace_existing=replace_existing,
            progress_callback=progress_callback,
            should_cancel=should_cancel,
        )
        if isinstance(result, Error):
            return result

        # I15: consolidar duplicados internos del documento ANTES de presentar
        # (la IA no debe ofrecer el mismo candidato N veces).
        from packages.application.import_deduplication_service import ImportDeduplicationService
        dedupe = ImportDeduplicationService(project=proj)
        dedupe.consolidate_basket(basket)
        # I16: marcar coincidencias con el canon existente (enrich_existing).
        self._mark_enrich_targets(basket, dedupe)

        # I13: propuesta de configuración de proyecto (calendario/temporal/config),
        # automática al importar desde el host. Best-effort: no rompe la extracción.
        if generate_config:
            self._maybe_generate_project_config(
                basket, context, provider=provider, allow_simulated=allow_simulated
            )

        presentable = [
            c for c in basket.import_candidates
            if c.review_state != ImportReviewState.FUSIONADO
        ]
        return Ok(presentable)

    def _maybe_generate_project_config(
        self, basket: ImportBasket, context: dict[str, Any], *, provider, allow_simulated: bool
    ) -> None:
        """Genera la propuesta de config (I13) sin romper la extracción si falla."""
        try:
            entity_names = [
                str((c.proposed_data or {}).get("name") or "").strip()
                for c in basket.import_candidates
                if (c.proposed_data or {}).get("kind") == "entity"
            ]
            from packages.application.import_project_config_service import (
                ImportProjectConfigService,
            )

            result = ImportProjectConfigService(
                provider=provider, allow_simulated=allow_simulated
            ).generate_for_basket(
                basket, project_context=context, entity_names=[n for n in entity_names if n]
            )
            if isinstance(result, Error):
                basket.metadata.setdefault("project_config_suggestion_error", result.error)
        except Exception as exc:  # noqa: BLE001 — best-effort, no rompe la extracción
            basket.metadata.setdefault("project_config_suggestion_error", str(exc))

    def apply_project_config_suggestion(self, basket_id: str) -> Result[dict[str, Any], str]:
        """Aplica la propuesta de config de proyecto (I13) tras aceptación explícita.

        Acción explícita del usuario: aplica el calendario (vía
        ``ProjectChronologyService.apply_candidate``), ubica las entidades en el
        tiempo (mergea birth/death/nature en sus ImportCandidate, que siguen
        revisables por entidad) y aplica la taxonomía. Devuelve un resumen de lo
        aplicado. Tono/género quedan capturados en la propuesta (aplicación
        profunda diferida).
        """
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        proj = proj_r.value
        basket = next((b for b in proj.import_baskets if b.id == basket_id), None)
        if basket is None:
            return Error(f"Import basket '{basket_id[:8]}' not found")
        proposal = (getattr(basket, "metadata", {}) or {}).get("project_config_suggestion")
        if not isinstance(proposal, dict):
            return Error("No hay propuesta de configuración para esta cesta")

        applied: dict[str, Any] = {"chronology": False, "entities_placed": 0, "taxonomy": False}

        chron = proposal.get("chronology") or {}
        if chron.get("eras") or chron.get("mode") not in (None, "", "none"):
            from packages.application.project_chronology_service import ProjectChronologyService

            # El servicio almacena las eras como NOMBRES (+ era_lengths aparte); las
            # eras ricas {name,start_year,end_year} se traducen aquí.
            rich_eras = [e for e in (chron.get("eras") or []) if isinstance(e, dict)]
            era_names = [str(e.get("name") or "").strip() for e in rich_eras if str(e.get("name") or "").strip()]
            era_lengths: dict[str, int] = {}
            for era in rich_eras:
                name = str(era.get("name") or "").strip()
                start, end = era.get("start_year"), era.get("end_year")
                if name and isinstance(start, int) and isinstance(end, int) and end >= start:
                    era_lengths[name] = end - start
            chrono_proposal = {
                "kind": "project_chronology_suggestion",
                "mode": chron.get("mode") or "vague_periods",
                "calendar_name": chron.get("calendar_name") or "",
                "eras": era_names,
                "era_lengths": era_lengths,
                "supports_exact_dates": bool(chron.get("supports_exact_dates", False)),
            }
            if chron.get("present_year") is not None:
                chrono_proposal["current_date"] = {"year": chron.get("present_year")}
            res = ProjectChronologyService(project_service=self.project_service).apply_candidate(
                chrono_proposal
            )
            if isinstance(res, Error):
                return res
            applied["chronology"] = True

        applied["entities_placed"] = self._place_entities_in_time(
            basket, proposal.get("entity_temporal") or []
        )

        taxonomy = (proposal.get("config") or {}).get("taxonomy") or {}
        if any(taxonomy.get(k) for k in ("allowed_entity_types", "allowed_branch_types", "extraction_guidance")):
            self._apply_taxonomy(proj, taxonomy)
            applied["taxonomy"] = True

        proposal["applied"] = True
        basket.metadata["project_config_suggestion"] = proposal
        return Ok(applied)

    def _basket_with_proposal(self, basket_id: str) -> Result[tuple[Any, dict[str, Any]], str]:
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return proj_r
        basket = next((b for b in proj_r.value.import_baskets if b.id == basket_id), None)
        if basket is None:
            return Error(f"Import basket '{basket_id[:8]}' not found")
        proposal = (getattr(basket, "metadata", {}) or {}).get("project_config_suggestion")
        if not isinstance(proposal, dict):
            return Error("No hay propuesta de configuración para esta cesta")
        return Ok((basket, proposal))

    def update_project_config_suggestion(
        self, basket_id: str, edits: dict[str, Any]
    ) -> Result[dict[str, Any], str]:
        """Edita los campos núcleo del calendario en la propuesta (I13).

        Solo muta la propuesta en ``basket.metadata`` (no canon, no config). Las
        ediciones admitidas son ``mode``, ``calendar_name`` y ``present_year``.
        """
        found = self._basket_with_proposal(basket_id)
        if isinstance(found, Error):
            return found
        basket, proposal = found.value
        chron = dict(proposal.get("chronology") or {})
        if "mode" in edits:
            mode = str(edits.get("mode") or "").strip()
            if mode in {"none", "vague_periods", "full_calendar"}:
                chron["mode"] = mode
        if "calendar_name" in edits:
            chron["calendar_name"] = str(edits.get("calendar_name") or "").strip()
        if "present_year" in edits:
            value = edits.get("present_year")
            try:
                chron["present_year"] = int(value) if value not in (None, "") else None
            except (TypeError, ValueError):
                pass
        proposal["chronology"] = chron
        basket.metadata["project_config_suggestion"] = proposal
        return Ok(proposal)

    def discard_project_config_suggestion(self, basket_id: str) -> Result[bool, str]:
        """Descarta la propuesta de config sin aplicarla (acción del usuario)."""
        found = self._basket_with_proposal(basket_id)
        if isinstance(found, Error):
            return found
        basket, _proposal = found.value
        basket.metadata.pop("project_config_suggestion", None)
        return Ok(True)

    @staticmethod
    def _place_entities_in_time(basket: ImportBasket, placements: list) -> int:
        """Mergea birth/death/nature en los candidatos de entidad que casan por nombre."""
        by_name: dict[str, Any] = {}
        for cand in getattr(basket, "import_candidates", []) or []:
            payload = cand.proposed_data or {}
            if str(payload.get("kind") or "").lower() != "entity":
                continue
            name = str(payload.get("name") or "").strip().lower()
            if name:
                by_name.setdefault(name, cand)
        placed = 0
        for place in placements:
            if not isinstance(place, dict):
                continue
            cand = by_name.get(str(place.get("name") or "").strip().lower())
            if cand is None:
                continue
            payload = cand.proposed_data
            if place.get("birth_year") is not None:
                payload.setdefault("birth_year", place["birth_year"])
            if place.get("death_year") is not None:
                payload.setdefault("death_year", place["death_year"])
            if place.get("nature"):
                payload.setdefault("temporal_nature", place["nature"])
            placed += 1
        return placed

    @staticmethod
    def _apply_taxonomy(proj: Any, taxonomy: dict[str, Any]) -> None:
        """Une los tipos propuestos a la taxonomía del proyecto (sin pisar lo existente)."""
        tax_obj = getattr(proj, "import_taxonomy", None)
        if tax_obj is None:
            return
        for attr, key in (
            ("allowed_entity_types", "allowed_entity_types"),
            ("allowed_branch_types", "allowed_branch_types"),
        ):
            if not hasattr(tax_obj, attr):
                continue
            existing = list(getattr(tax_obj, attr) or [])
            merged = list(dict.fromkeys(existing + list(taxonomy.get(key) or [])))
            setattr(tax_obj, attr, merged)
        guidance = str(taxonomy.get("extraction_guidance") or "").strip()
        if guidance and hasattr(tax_obj, "extraction_guidance") and not getattr(tax_obj, "extraction_guidance", ""):
            tax_obj.extraction_guidance = guidance

    @staticmethod
    def _mark_enrich_targets(basket: ImportBasket, dedupe: Any) -> None:
        """I16: marca candidatos que coinciden con el canon existente.

        Detecta duplicados frente a ``project.entities`` (reusa la detección del
        servicio de dedup) y, para los que coinciden, escribe en ``proposed_data``
        ``enrich_target_id`` + ``presentation_kind="enrich_existing"`` para que al
        aceptar se enriquezca la entidad existente en vez de crear un duplicado.
        """
        dedupe._mark_canon_duplicates(basket)
        for cand in basket.import_candidates:
            if cand.review_state == ImportReviewState.FUSIONADO:
                continue
            if not getattr(cand, "possible_duplicates", None):
                continue
            payload = cand.proposed_data if isinstance(cand.proposed_data, dict) else {}
            target_id = cand.possible_duplicates[0]
            if target_id:
                payload["enrich_target_id"] = target_id
                payload["presentation_kind"] = "enrich_existing"
                cand.proposed_data = payload

    # ── Context summary (I12, Modo Contexto) ─────────────────────────────

    def summarize_context_basket(
        self,
        basket_id: str,
        *,
        provider=None,
        allow_simulated: bool = False,
        project_context: dict[str, Any] | None = None,
    ) -> Result[dict[str, Any], str]:
        """Genera un resumen IA no-canon para una cesta en modo contexto.

        Solo muta ``basket.metadata['context_summary']``; nunca crea canon ni
        candidatos. Restringido a cestas en modo contexto.
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
        if getattr(basket, "import_mode", "canon") != ImportMode.CONTEXTO.value:
            return Error("El resumen de contexto solo aplica a cestas en modo contexto")

        from packages.application.import_context_summary_service import (
            ImportContextSummaryService,
        )

        context = dict(project_context or {})
        context.setdefault("project_name", getattr(proj, "name", ""))
        service = ImportContextSummaryService(
            provider=provider,
            allow_simulated=allow_simulated,
        )
        return service.summarize_basket(basket, project_context=context)

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
        if import_cand.candidate_type == CandidateType.ANILLO.value or kind == "ring_suggestion":
            result = self._apply_ring_candidate(basket, import_cand, payload)
            if isinstance(result, Error):
                return result
            import_cand.review_state = ImportReviewState.ACEPTADO
            basket.updated_at = _now_iso()
            return result
        if payload.get("enrich_target_id"):
            # I16: el candidato coincide con una entidad existente → enriquecerla.
            result = self._enrich_entity_candidate(proj, basket, import_cand, payload)
        elif import_cand.candidate_type == CandidateType.RELACION.value or kind == "relation":
            result = self._apply_relation_candidate(proj, basket, import_cand, payload)
        else:
            result = self._apply_entity_candidate(basket, import_cand, payload)
        if isinstance(result, Error):
            return result
        import_cand.review_state = ImportReviewState.ACEPTADO
        basket.updated_at = _now_iso()
        return result

    def _enrich_entity_candidate(
        self,
        proj,
        basket: ImportBasket,
        import_cand: ImportCandidate,
        payload: dict[str, Any],
    ) -> Result[Any, str]:
        """I16: enriquece una entidad de canon existente con la info del candidato.

        Une aliases (sin duplicar ni añadir el propio nombre) y completa
        descripción breve/cuerpo solo si están vacías. Si el objetivo ya no
        existe, cae a crear la entidad nueva.
        """
        target_id = str(payload.get("enrich_target_id") or "").strip()
        target = next(
            (e for e in getattr(proj, "entities", []) or [] if getattr(e, "id", "") == target_id),
            None,
        )
        if target is None:
            return self._apply_entity_candidate(basket, import_cand, payload)

        target_name_norm = str(getattr(target, "name", "")).strip().lower()
        merged_aliases = list(getattr(target, "aliases", []) or [])
        seen = {a.strip().lower() for a in merged_aliases}
        incoming = [str(payload.get("name") or payload.get("title") or "")]
        incoming.extend(str(a) for a in (payload.get("aliases") or []))
        for alias in incoming:
            al = alias.strip()
            if al and al.lower() != target_name_norm and al.lower() not in seen:
                merged_aliases.append(al)
                seen.add(al.lower())

        data: dict[str, Any] = {"aliases": merged_aliases}
        new_brief = payload.get("brief_description") or payload.get("summary") or ""
        new_body = payload.get("description") or payload.get("body") or ""
        if new_brief and not str(getattr(target, "brief_description", "") or "").strip():
            data["brief_description"] = new_brief
        if new_body and not str(getattr(target, "extended_description", "") or "").strip():
            data["extended_description"] = new_body

        from packages.application.entity_service import EntityService
        entity_service = self.entity_service or EntityService(self.project_service)
        return entity_service.update_entity(target_id, data)

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

    def _apply_ring_candidate(
        self,
        basket: ImportBasket,
        import_cand: ImportCandidate,
        payload: dict[str, Any],
    ) -> Result[Any, str]:
        """Materializa un candidato de anillo como WorldLayer vía servicio."""
        name = str(
            payload.get("ring_name") or payload.get("name") or payload.get("title") or ""
        ).strip()
        if not name:
            return Error("Ring import candidate needs a name")
        description = str(
            payload.get("description") or payload.get("summary") or payload.get("body") or ""
        )
        from packages.application.world_layer_service import WorldLayerService
        layer_service = WorldLayerService(project_service=self.project_service)
        return layer_service.create_layer(name=name, description=description)

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
