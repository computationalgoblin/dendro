"""BETA2-STRUCT: análisis estructural determinista del proyecto.

Emite hallazgos ``ring_move`` cuando el **potencial de propagación causal ATRIBUIDO** a una
entidad no cuadra con su anillo actual, y ``ascending_exception`` (Fase 2, STRUCT-05) cuando
una relación no-causal bajo→alto con extremo inferior de potencia alta debería poder escalar
(§16). Determinista, coste IA cero, ``Result``-based. La mitad
de ACEPTACIÓN ya existe (``CandidateService`` + ``build_ring_move_proposal``, BETA2-MEM-08); la
de GENERACIÓN es este detector. La IA solo enriquece la justificación al abrir (STRUCT-04).

**Qué es el "potencial de propagación causal" (modelo de producto, STRUCT-09).** El anillo ES
una clasificación de potencialidad causal (cuánto puede una entidad propagar consecuencias por
el mundo), pero esa potencialidad **la atribuye la IA de forma SEMÁNTICA leyendo qué ES la
entidad** — una *guerra* propaga mucho (potencia alta → anillo aguas-arriba); un *campesino* no
(baja → exterior). NO se infiere de la topología (eso confundía "muy conectado" con "causa
fundamental" y proponía mover un rey a Metafísica). La IA fija la métrica **al Regar** (semántico)
en ``custom_metadata["_causal_potency_basal"]`` (§14 potencia basal; sin modelo paralelo). El
detector solo LEE esa métrica atribuida y compara — determinista. **Silencio honesto:** una
entidad SIN potencia atribuida no se juzga (no hay ruido hasta que la IA la ha valorado).

Modelo de detección (sin persistir nada pendiente → derive-on-read):
- **Potencia atribuida P(e)** = ``get_annotated_potency`` (0..100), o ``None`` (se ignora).
- **Banda esperada** = mapeo ABSOLUTO de P a una posición de anillo (P alto → posición 1,
  aguas-arriba; P bajo → posición N, exterior). No percentil → no fuerza llenar el anillo
  superior.
- **Dispara** si ``|banda_esperada − posición_actual| ≥ _MIN_GAP`` con ``confianza ≥ 0.6``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from packages.application.causal_potency import (
    build_ring_move_proposal,
    get_annotated_potency,
    is_ascending_exception,
)
from packages.application.foco_rings import effective_rank_map, ring_display_info, ring_id_for
from packages.application.narrative_impact_service import CAUSAL_RELATION_TYPES
from packages.application.world_layer_causal import get_causal_rank
from packages.domain.candidate_issue import Candidate, CandidateType
from packages.domain.result import Error, Ok, Result

_MIN_GAP = 1  # bandas de anillo de diferencia para proponer un movimiento (potencia semántica:
# un desajuste de 1 banda ya es señal; incluye colocar una entidad sin anillo). La confianza
# crece con el gap.
_MIN_CONFIDENCE = 0.6

# BETA2-STRUCT-05: umbral de potencia atribuida del extremo INFERIOR para proponer una
# excepción ascendente sobre una relación no-causal bajo→alto. Solo se juzgan relaciones
# cuyo extremo bajo tiene potencia atribuida (silencio honesto, como en ring_move).
_ASC_MIN_POTENCY = 70
# Tipo de excepción por defecto de la PROPUESTA determinista (el más genérico del §16:
# algo inferior que apalanca influencia hacia arriba). La elección semántica fina entre
# los 5 tipos es tarea del usuario/IA al revisar, no del detector.
_DEFAULT_ASC_KIND = "apalancamiento"

# Claves de supresión de decisiones (custom_metadata, schema-safe, sin bump de esquema).
DISMISS_KEY = "_struct_dismissed"  # list[fingerprint] — hasta que el fingerprint cambie
SNOOZE_KEY = "_struct_snoozed"  # {fingerprint: index_revision} — hasta el próximo cambio

_EXCLUDED_CANON = frozenset({"rechazado", "archivado"})

_ENRICH_SYSTEM = (
    "Eres un editor narrativo. Redacta en 2-3 frases, en español, una justificación en prosa "
    "de por qué la reubicación de anillo propuesta es coherente. Usa SOLO la información dada "
    "(razones y consecuencias); no inventes hechos ni fechas. No decides ni cambias nada: solo "
    'redactas. Devuelve JSON: {"justificacion": "..."}.'
)

_STRUCTURE_SYSTEM = (
    "Eres un arquitecto de mundos que ORGANIZA la estructura causal de un proyecto narrativo "
    "CONCRETO. Te doy la identidad del proyecto (título, premisa, género, tono), sus ANILLOS "
    "causales actuales (cada uno con su 'posicion': 1 = causa más fundamental / aguas-arriba / "
    "centro; mayor = consecuencia / aguas-abajo / exterior) y una muestra de entidades con su "
    "potencialidad causal (0-100) y su anillo. Propón MEJORAS a la ESTRUCTURA de anillos (NO "
    "muevas entidades sueltas: eso es otra vía):\n"
    "- CREAR un anillo causal que falte: una banda de potencialidad sin representar o un dominio "
    "necesario. IMPORTANTE — el nombre debe ser DIEGÉTICO y propio de ESTE mundo: apóyate en su "
    "premisa, género, tono y en el vocabulario de sus entidades, de modo que suene a que "
    "pertenece a la ficción. NADA de etiquetas genéricas o abstractas tipo «Estratos de Alto "
    "Impacto», «Capa 1» o «Nivel Causal». Da nombre, descripción breve que ANCLE el anillo en la "
    "narrativa del proyecto, y 'rank' (1..15): recuerda que MÁS potencial causal ⇒ rank MÁS BAJO "
    "(aguas-arriba, centro); MENOS potencial ⇒ rank MÁS ALTO (exterior). Sé coherente con las "
    "posiciones de los anillos existentes.\n"
    "- FUSIONAR dos anillos redundantes o casi vacíos (indica origen y destino por su 'id').\n"
    "Inferir qué anillos hacen falta es tu tarea (al usuario le resulta abstracto). No inventes "
    "entidades ni toques canon. Si la estructura ya es buena, devuelve listas vacías. "
    'Devuelve SOLO JSON: {"crear": [{"nombre": "...", "descripcion": "...", "rank": <1-15>}], '
    '"fusionar": [{"origen_id": "...", "destino_id": "...", "motivo": "..."}]}'
)


@dataclass(frozen=True)
class StructuralFinding:
    """Hallazgo estructural revisable (efímero; se deriva en lectura, no se persiste)."""

    kind: str  # "ring_move" (Fase 1) | "ascending_exception" (Fase 2, STRUCT-05)
    target_id: str  # entidad afectada (en ascending_exception: el extremo INFERIOR)
    proposed_data: dict[str, Any]  # §17, con la forma de build_ring_move_proposal
    confidence: float
    fingerprint: str
    title: str = ""

    def reasons(self) -> list[str]:
        return list(self.proposed_data.get("reasons") or [])


@dataclass
class StructuralAnalysisService:
    """Detector determinista de reubicaciones de anillo (BETA2-STRUCT-01)."""

    project_service: Any
    impact_service: Any = None
    ai_job_service: Any = None
    _cache_key: tuple[Any, Any] | None = field(default=None, init=False, repr=False)
    _cache: list[StructuralFinding] = field(default_factory=list, init=False, repr=False)
    # STRUCT-07: propuestas de ESTRUCTURA de anillos (crear/fusionar) generadas por la IA bajo
    # demanda. Son de sesión (no derive-on-read): se guardan aquí hasta aceptar/descartar.
    _structure_proposals: list[StructuralFinding] = field(
        default_factory=list, init=False, repr=False
    )

    def _proj(self):
        return getattr(self.project_service, "active_project", None)

    # ── API pública ─────────────────────────────────────────────────────

    def analyze(self) -> Result[list[StructuralFinding], str]:
        """Todos los hallazgos estructurales vigentes (cacheado por index_revision)."""
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        key = (getattr(proj, "id", ""), getattr(proj, "_index_revision", 0))
        if self._cache_key == key:
            return Ok(list(self._cache))
        findings = self._compute(proj)
        self._cache_key = key
        self._cache = findings
        return Ok(list(findings))

    def count(self) -> int:
        """Contador ambiental '(N) ajustes estructurales' (coste IA cero)."""
        res = self.analyze()
        return len(res.value) if isinstance(res, Ok) else 0

    def as_candidate(self, finding: StructuralFinding) -> Candidate:
        """Materializa un Candidato transitorio para enrutar por el pipeline de aceptación."""
        pd = dict(finding.proposed_data)
        if finding.kind == "ascending_exception":
            ctype = CandidateType.RELACION
            affected = [
                str(pd.get("source_entity_id") or ""),
                str(pd.get("target_entity_id") or ""),
            ]
            affected = [a for a in affected if a]
        else:
            ctype = CandidateType.ANILLO
            affected = [finding.target_id]
        return Candidate(
            candidate_type=ctype,
            title=finding.title or "Ajuste estructural",
            proposed_data=pd,
            affected_entity_ids=affected,
            confidence=finding.confidence,
            source="structural_analysis",
            justification="; ".join(pd.get("reasons") or []),
            expected_impact="; ".join(pd.get("expected_consequences") or []),
        )

    def dismiss(self, fingerprint: str) -> Result[bool, str]:
        """Rechaza un hallazgo: se suprime hasta que su fingerprint cambie (topología)."""
        return self._suppress(fingerprint, DISMISS_KEY)

    def postpone(self, fingerprint: str) -> Result[bool, str]:
        """Aplaza un hallazgo: se suprime hasta el próximo cambio de canon."""
        return self._suppress(fingerprint, SNOOZE_KEY)

    def enrich_justification(self, finding: StructuralFinding) -> Result[str, str]:
        """Redacción narrativa OPCIONAL de la justificación (provider-optional, STRUCT-04).

        La base son SIEMPRE las razones/consecuencias deterministas §17. Si hay proveedor,
        la IA las reescribe en prosa; ante cualquier fallo vuelve a la base. Nunca escribe
        canon ni muta ``proposed_data``.
        """
        baseline = self._deterministic_justification(finding)
        svc = self.ai_job_service
        if svc is None or svc.provider_unconfigured():
            return Ok(baseline)
        try:
            text, err = svc.raw_json_completion(_ENRICH_SYSTEM, self._enrich_user(finding))
        except Exception:  # noqa: BLE001 — nunca rompe: cae a la base determinista
            return Ok(baseline)
        if err or not text:
            return Ok(baseline)
        try:
            narrative = str(json.loads(text).get("justificacion") or "").strip()
        except (ValueError, TypeError, AttributeError):
            return Ok(baseline)
        return Ok(narrative or baseline)

    def baseline_justification(self, finding: StructuralFinding) -> str:
        """Justificación determinista (razones + consecuencias §17), sin IA."""
        return self._deterministic_justification(finding)

    # ── STRUCT-07: propuesta de ESTRUCTURA de anillos (crear/fusionar, IA bajo demanda) ──

    def propose_ring_structure(self) -> Result[list[StructuralFinding], str]:
        """La IA propone CREAR/FUSIONAR anillos leyendo todo el proyecto (holístico, semántico).

        Provider-optional: sin proveedor devuelve Error (es una tarea IA, no determinista). Las
        propuestas se guardan en sesión (`structure_proposals`) hasta aceptar/descartar. Nunca
        escribe canon: son Candidatos revisables (aceptar reutiliza `ring_template`/`ring_merge`).
        """
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        svc = self.ai_job_service
        if svc is None or svc.provider_unconfigured():
            return Error("No hay proveedor de IA configurado para proponer estructura de anillos.")
        context = self._ring_structure_context(proj)
        try:
            text, err = svc.raw_json_completion(_STRUCTURE_SYSTEM, context)
        except Exception:  # noqa: BLE001 — nunca rompe la UI
            return Error("El proveedor de IA falló al proponer estructura.")
        if err or not text:
            return Error(str(err) or "Sin respuesta del proveedor.")
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            return Error("El proveedor devolvió una respuesta no-JSON.")
        parsed = self._parse_structure(proj, data if isinstance(data, dict) else {})
        self._structure_proposals = parsed
        return Ok(list(parsed))

    def structure_proposals(self) -> list[StructuralFinding]:
        """Propuestas de estructura vigentes en la sesión (crear/fusionar)."""
        return list(self._structure_proposals)

    def discard_structure_proposal(self, fingerprint: str) -> None:
        """Quita una propuesta de estructura de la sesión (tras aceptar o descartar)."""
        self._structure_proposals = [
            f for f in self._structure_proposals if f.fingerprint != fingerprint
        ]

    def _ring_structure_context(self, proj) -> str:
        layers = list(getattr(proj, "world_layers", []) or [])
        rank_map = effective_rank_map(layers)
        counts: dict[str, int] = {}
        for e in getattr(proj, "entities", []) or []:
            for lid in getattr(e, "layer_ids", []) or []:
                counts[lid] = counts.get(lid, 0) + 1
        rings = [
            {
                "id": str(wl.id),
                "nombre": str(getattr(wl, "name", "")),
                # posición EFECTIVA 1..N (ancla real para la IA); el causal_rank crudo
                # suele ser None en proyectos sin ranking manual y no orientaba.
                "posicion": rank_map.get(str(wl.id)),
                "miembros": counts.get(str(wl.id), 0),
            }
            for wl in sorted(layers, key=lambda layer: rank_map.get(str(layer.id), 999))
        ]
        ents: list[dict[str, Any]] = []
        for e in getattr(proj, "entities", []) or []:
            pot = get_annotated_potency(e)
            if pot is None:
                continue
            ents.append(
                {
                    "nombre": str(getattr(e, "name", "")),
                    "potencial": pot,
                    "anillo": ring_id_for(proj, e.id) or "",
                }
            )
            if len(ents) >= 40:
                break
        return json.dumps(
            {
                "proyecto": self._narrative_identity(proj),
                "anillos": rings,
                "entidades_con_potencial": ents,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _narrative_identity(proj) -> dict[str, Any]:
        """Identidad narrativa compacta del proyecto para que los nombres de anillo
        propuestos sean DIEGÉTICOS (propios de este mundo), no etiquetas genéricas."""
        cfg = getattr(proj, "creative_config", None)
        ident = getattr(cfg, "identidad", None)
        estilo = getattr(cfg, "estilo", None)
        return {
            "titulo": str(getattr(proj, "name", "") or ""),
            "premisa": str(getattr(ident, "premisa", "") or ""),
            "resumen": str(getattr(ident, "resumen_corto", "") or ""),
            "genero": str(getattr(ident, "genero_principal", "") or ""),
            "subgeneros": list(getattr(ident, "subgeneros", []) or []),
            "tono": str(getattr(estilo, "tono", "") or ""),
        }

    def _parse_structure(self, proj, data: dict) -> list[StructuralFinding]:
        out: list[StructuralFinding] = []
        for c in data.get("crear") or []:
            if not isinstance(c, dict):
                continue
            nombre = str(c.get("nombre") or "").strip()
            if not nombre:
                continue
            rank = c.get("rank")
            has_rank = isinstance(rank, (int, float))
            desc = str(c.get("descripcion") or "").strip()
            pd = {
                "kind": "ring_template",
                "ring_name": nombre,
                "description": desc,
                "order": int(rank) if has_rank else 0,
                # causal_rank fija el orden VISUAL del anillo nuevo (effective_rank_map);
                # sin él, el anillo caía al final (rank None → desempate por order).
                "causal_rank": int(rank) if has_rank else None,
                "reasons": [desc] if desc else [f"Anillo causal propuesto: «{nombre}»."],
            }
            out.append(
                StructuralFinding(
                    kind="ring_create", target_id="", proposed_data=pd, confidence=0.7,
                    fingerprint=f"ring_create:{nombre}", title=f"Crear anillo «{nombre}»",
                )
            )
        for m in data.get("fusionar") or []:
            if not isinstance(m, dict):
                continue
            src = str(m.get("origen_id") or "").strip()
            dst = str(m.get("destino_id") or "").strip()
            if not src or not dst or src == dst:
                continue
            motivo = str(m.get("motivo") or "").strip()
            pd = {
                "kind": "ring_merge",
                "source_ring_id": src,
                "target_ring_id": dst,
                "reasons": [motivo] if motivo else ["Anillos redundantes o casi vacíos."],
            }
            out.append(
                StructuralFinding(
                    kind="ring_merge", target_id="", proposed_data=pd, confidence=0.7,
                    fingerprint=f"ring_merge:{src}->{dst}",
                    title=(
                        f"Fusionar «{self._ring_name(proj, src)}» → «{self._ring_name(proj, dst)}»"
                    ),
                )
            )
        return out

    @staticmethod
    def _deterministic_justification(finding: StructuralFinding) -> str:
        pd = finding.proposed_data
        parts = list(pd.get("reasons") or []) + list(pd.get("expected_consequences") or [])
        return " ".join(parts).strip() or (finding.title or "Reubicación de anillo propuesta.")

    @staticmethod
    def _enrich_user(finding: StructuralFinding) -> str:
        pd = finding.proposed_data
        return json.dumps(
            {
                "elemento": pd.get("entity_id", ""),
                "anillo_actual": pd.get("current_ring_id", ""),
                "anillo_sugerido": pd.get("target_ring_id", ""),
                "razones": list(pd.get("reasons") or []),
                "consecuencias": list(pd.get("expected_consequences") or []),
                "formato_salida": {"justificacion": "string"},
            },
            ensure_ascii=False,
        )

    # ── cómputo determinista ────────────────────────────────────────────

    def _compute(self, proj) -> list[StructuralFinding]:
        layers = list(getattr(proj, "world_layers", []) or [])
        rank_map = effective_rank_map(layers)  # {layer_id: posición 1..N}
        if not rank_map:
            return []
        pos_to_layer = {pos: lid for lid, pos in rank_map.items()}
        n = len(rank_map)
        entities = [e for e in getattr(proj, "entities", []) or [] if self._eligible(e)]
        current_rev = getattr(proj, "_index_revision", 0)
        findings: list[StructuralFinding] = []
        for entity in entities:
            potency = get_annotated_potency(entity)
            if potency is None:
                continue  # silencio honesto: sin métrica atribuida por la IA, no se juzga
            target_pos = self._expected_position(potency, n)
            target_ring_id = pos_to_layer.get(target_pos)
            if not target_ring_id:
                continue
            current_ring_id = ring_id_for(proj, entity.id) or ""
            _, current_pos, _ = ring_display_info(proj, entity.id)
            if str(target_ring_id) == str(current_ring_id):
                continue
            gap = abs(target_pos - current_pos)
            if gap < _MIN_GAP:
                continue
            confidence = self._confidence(gap)
            if confidence < _MIN_CONFIDENCE:
                continue
            finding = self._build_finding(
                proj, entity, potency, current_ring_id, target_ring_id,
                current_pos, target_pos, n, confidence,
            )
            holder = proj.entity_by_id(entity.id) if hasattr(proj, "entity_by_id") else None
            if holder is not None and self._is_suppressed(holder, finding.fingerprint, current_rev):
                continue
            findings.append(finding)
        findings.extend(self._compute_ascending(proj, current_rev))
        findings.sort(key=lambda f: f.confidence, reverse=True)
        return findings

    def _compute_ascending(self, proj, current_rev) -> list[StructuralFinding]:
        """BETA2-STRUCT-05: excepciones ascendentes como propuesta.

        Patrón: relación NO causal cuyo extremo inferior (posición de anillo mayor)
        tiene potencia atribuida alta — su influencia real escala hacia el extremo
        superior, pero el motor de impacto no la propagará mientras la relación no
        esté marcada como excepción (§16). El detector la propone; el usuario acepta.
        """
        if not hasattr(proj, "entity_by_id"):
            return []
        pos_cache: dict[str, int] = {}

        def _pos(entity_id: str) -> int:
            if entity_id not in pos_cache:
                _, pos, _ = ring_display_info(proj, entity_id)
                pos_cache[entity_id] = pos
            return pos_cache[entity_id]

        findings: list[StructuralFinding] = []
        for rel in getattr(proj, "relations", []) or []:
            if rel.relation_type in CAUSAL_RELATION_TYPES or is_ascending_exception(rel):
                continue  # ya escala (causal) o ya está marcada
            source = proj.entity_by_id(rel.source_id)
            target = proj.entity_by_id(rel.target_id)
            if source is None or target is None:
                continue
            if not self._eligible(source) or not self._eligible(target):
                continue
            potency = get_annotated_potency(source)
            if potency is None or potency < _ASC_MIN_POTENCY:
                continue  # silencio honesto: sin potencia alta atribuida, no se juzga
            if _pos(source.id) <= _pos(target.id):
                continue  # solo bajo→alto (source más abajo que target)
            finding = self._build_ascending_finding(rel, source, target, potency)
            if self._is_suppressed(source, finding.fingerprint, current_rev):
                continue
            findings.append(finding)
        return findings

    def _build_ascending_finding(self, rel, source, target, potency: int) -> StructuralFinding:
        source_name = getattr(source, "name", "") or source.id
        target_name = getattr(target, "name", "") or target.id
        rel_type = getattr(rel.relation_type, "value", rel.relation_type)
        reasons = [
            f"«{source_name}» (potencial atribuido {potency}/100) está en un anillo inferior "
            f"al de «{target_name}», unidos por la relación no-causal «{rel_type}».",
            "Sin marca de excepción, un cambio en el extremo inferior no escala hacia arriba "
            f"(contrato §16); su potencial sugiere que sí debería ({_DEFAULT_ASC_KIND}).",
        ]
        expected = [
            f"Los cambios en «{source_name}» podrán marcar «Falta regar» ascendentemente "
            f"la Memoria de «{target_name}» (y de su cadena causal)."
        ]
        proposed = {
            "kind": "ascending_exception",
            "relation_id": rel.id,
            "source_entity_id": source.id,
            "target_entity_id": target.id,
            "exception_kind": _DEFAULT_ASC_KIND,
            "reasons": reasons,
            "expected_consequences": expected,
        }
        confidence = round(min(1.0, _MIN_CONFIDENCE + (potency - _ASC_MIN_POTENCY) * 0.01), 3)
        return StructuralFinding(
            kind="ascending_exception",
            target_id=source.id,
            proposed_data=proposed,
            confidence=confidence,
            fingerprint=f"ascending_exception:{source.id}:{rel.id}",
            title=f"Excepción ascendente: «{source_name}» ⇗ «{target_name}»",
        )

    @staticmethod
    def _expected_position(potency: int, n: int) -> int:
        """Mapeo ABSOLUTO de la potencia (0..100) a una posición de anillo.

        Potencia alta -> posición 1 (aguas-arriba); baja -> posición N (exterior). Absoluto (no
        percentil) para no forzar que la entidad más potente ocupe siempre el anillo superior.
        """
        pos = round(1 + (100 - potency) / 100 * (n - 1))
        return max(1, min(n, pos))

    @staticmethod
    def _confidence(gap: int) -> float:
        conf = _MIN_CONFIDENCE + 0.05 * min(gap - _MIN_GAP, 8)
        return round(min(1.0, conf), 3)

    def _build_finding(
        self, proj, entity, potency, current_ring_id, target_ring_id,
        current_pos, target_pos, n, confidence,
    ) -> StructuralFinding:
        name = getattr(entity, "name", "") or entity.id
        current_name = self._ring_name(proj, current_ring_id) if current_ring_id else "Sin anillo"
        target_name = self._ring_name(proj, target_ring_id)
        reasons = [
            f"La IA atribuyó a «{name}» una potencialidad de propagación causal de "
            f"{potency}/100.",
            f"Ese potencial corresponde al anillo «{target_name}» (banda {target_pos}/{n}), "
            f"pero está en «{current_name}» (posición {current_pos}).",
        ]
        expected = self._expected_consequences(proj, entity.id, target_ring_id)
        proposed = build_ring_move_proposal(
            entity.id,
            current_ring_id=current_ring_id,
            target_ring_id=target_ring_id,
            context="",
            reasons=reasons,
            supporting_relation_ids=[],
            expected_consequences=expected,
        )
        fingerprint = f"ring_move:{entity.id}:{current_ring_id}->{target_ring_id}"
        title = f"Reubicar «{name}»: {current_name} → {target_name}"
        return StructuralFinding(
            kind="ring_move",
            target_id=entity.id,
            proposed_data=proposed,
            confidence=confidence,
            fingerprint=fingerprint,
            title=title,
        )

    def _expected_consequences(self, proj, entity_id: str, target_ring_id: str) -> list[str]:
        if self.impact_service is None:
            return []
        target_layer = next(
            (
                layer
                for layer in getattr(proj, "world_layers", []) or []
                if str(layer.id) == str(target_ring_id)
            ),
            None,
        )
        at_rank = get_causal_rank(target_layer) if target_layer is not None else None
        try:
            deps = self.impact_service.preview_entity_dependents(entity_id, at_rank=at_rank)
        except Exception:  # noqa: BLE001 — efecto derivado, nunca rompe el análisis
            return []
        return [
            f"Al mover, hasta {len(deps)} dependiente(s) podrían quedar «Falta regar» "
            "(solo los que tengan Memoria)."
        ]

    @staticmethod
    def _ring_name(proj, ring_id: str) -> str:
        for layer in getattr(proj, "world_layers", []) or []:
            if str(layer.id) == str(ring_id):
                return str(getattr(layer, "name", "") or ring_id)
        return str(ring_id)

    @staticmethod
    def _eligible(entity) -> bool:
        canon = getattr(entity, "canon_state", None)
        value = getattr(canon, "value", canon)
        return str(value).lower() not in _EXCLUDED_CANON

    # ── supresión de decisiones ─────────────────────────────────────────

    def _suppress(self, fingerprint: str, key: str) -> Result[bool, str]:
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        holder = self._holder_for_fingerprint(proj, fingerprint)
        if holder is None:
            return Error("Elemento del hallazgo no encontrado")
        meta = getattr(holder, "custom_metadata", None)
        if not isinstance(meta, dict):
            meta = {}
            holder.custom_metadata = meta
        if key == DISMISS_KEY:
            current = list(meta.get(key) or [])
            if fingerprint not in current:
                current.append(fingerprint)
            meta[key] = current
        if hasattr(holder, "touch"):
            holder.touch()
        if hasattr(proj, "touch"):
            proj.touch()
        if key == SNOOZE_KEY:
            snoozed = dict(meta.get(key) or {})
            snoozed[fingerprint] = getattr(proj, "_index_revision", 0)  # rev POST-touch
            meta[key] = snoozed
        self._cache_key = None  # invalida la caché derive-on-read
        return Ok(True)

    @staticmethod
    def _is_suppressed(holder, fingerprint: str, current_rev: Any) -> bool:
        meta = getattr(holder, "custom_metadata", None)
        if not isinstance(meta, dict):
            return False
        if fingerprint in (meta.get(DISMISS_KEY) or []):
            return True
        snoozed = meta.get(SNOOZE_KEY)
        if isinstance(snoozed, dict) and snoozed.get(fingerprint) == current_rev:
            return True
        return False

    @staticmethod
    def _holder_for_fingerprint(proj, fingerprint: str):
        parts = str(fingerprint).split(":")
        if len(parts) < 2 or not hasattr(proj, "entity_by_id"):
            return None
        return proj.entity_by_id(parts[1])


__all__ = ["StructuralAnalysisService", "StructuralFinding"]
