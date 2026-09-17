"""BETA2-STRUCT: análisis estructural determinista del proyecto.

Emite hallazgos ``ring_move`` cuando el **potencial de propagación causal ATRIBUIDO** a una
entidad no cuadra con su anillo actual, ``ascending_exception`` (Fase 2, STRUCT-05) cuando
una relación no-causal bajo→alto con extremo inferior de potencia alta debería poder escalar
(§16), y ``branch_move`` (Fase 3, STRUCT-06) cuando la potencia AGREGADA de una rama con
contenido no cuadra con su anillo (aceptar arrastra el subárbol). Determinista, coste IA
cero, ``Result``-based. La mitad
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
from packages.application.foco_rings import (
    contained_descendant_ids,
    effective_rank_map,
    ring_display_info,
    ring_id_for,
)
from packages.application.narrative_impact_service import CAUSAL_RELATION_TYPES
from packages.application.world_layer_causal import get_causal_rank
from packages.domain.candidate_issue import Candidate, CandidateType
from packages.domain.entity_taxonomy import is_branch
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

    kind: str  # ring_move (F1) | ascending_exception (F2, STRUCT-05) | branch_move (F3, STRUCT-06)
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
    # BETA-FIX-05 (G-05): fingerprints YA APLICADOS en esta sesión.
    # Sin esto una tarjeta aceptada seguía re-aceptable (candidato duplicado) si
    # la caché/las propuestas de sesión la re-emitían antes de refrescarse.
    _applied_fingerprints: set = field(default_factory=set, init=False, repr=False)

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
            return Ok(self._without_applied(self._cache))
        findings = self._compute(proj)
        self._cache_key = key
        self._cache = findings
        return Ok(self._without_applied(findings))

    def _without_applied(self, findings: list[StructuralFinding]) -> list[StructuralFinding]:
        """FIX-05: un hallazgo aplicado no vuelve a listarse aunque la caché lo tenga."""
        return [f for f in findings if f.fingerprint not in self._applied_fingerprints]

    def mark_applied(self, fingerprint: str) -> None:
        """FIX-05: sella un hallazgo como aplicado (idempotencia de la aceptación)."""
        normalized = str(fingerprint or "").strip()
        if normalized:
            self._applied_fingerprints.add(normalized)

    def is_applied(self, fingerprint: str) -> bool:
        return str(fingerprint or "").strip() in self._applied_fingerprints

    def count(self) -> int:
        """Contador ambiental '(N) ajustes estructurales' (coste IA cero).

        FIX-05: cuenta lo MISMO que lista el panel — hallazgos deterministas +
        propuestas de estructura IA vigentes (antes excluía las propuestas y la
        píldora «⚙ N» no cuadraba con las tarjetas).
        """
        res = self.analyze()
        deterministas = len(res.value) if isinstance(res, Ok) else 0
        return deterministas + len(self.structure_proposals())

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
        return self._without_applied(self._structure_proposals)

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
        # FIX-05: dedup por fingerprint (la IA puede repetir un nombre en la misma
        # respuesta → dos tarjetas con el mismo fingerprint) y sin re-proponer
        # anillos que YA existen en el proyecto (reintento tras aceptar).
        seen: set[str] = set()
        existing_ring_names = {
            str(getattr(layer, "name", "") or "").strip().lower()
            for layer in getattr(proj, "world_layers", []) or []
        }
        for c in data.get("crear") or []:
            if not isinstance(c, dict):
                continue
            nombre = str(c.get("nombre") or "").strip()
            if not nombre:
                continue
            fingerprint = f"ring_create:{nombre}"
            if (
                fingerprint in seen
                or fingerprint in self._applied_fingerprints
                or nombre.lower() in existing_ring_names
            ):
                continue
            seen.add(fingerprint)
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
            merge_fingerprint = f"ring_merge:{src}->{dst}"
            if merge_fingerprint in seen or merge_fingerprint in self._applied_fingerprints:
                continue
            seen.add(merge_fingerprint)
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
            if self._is_branch_with_content(proj, entity):
                # STRUCT-06: una rama CON contenido se juzga como branch_move (mover
                # arrastrando el subárbol), nunca como ring_move suelto — moverla sola
                # rompería la contención visual.
                finding = self._build_branch_finding(proj, entity, n)
                if finding is not None and not self._is_suppressed(
                    entity, finding.fingerprint, current_rev
                ):
                    findings.append(finding)
                continue
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

        BETA2-FIX-05 (G2-07) — CALIBRACIÓN. En la campaña larga del beta
        (800 fichas, 1.760 relaciones, 9 anillos) esta vía sola emitía **105 de los 203
        avisos** (51,7 %), sin tope ni agrupación: hasta 13 tarjetas para la MISMA
        entidad. Dos acotaciones, las dos semánticas (no umbrales al tuntún):

        1. **La potencia del extremo inferior debe alcanzar a la del superior.** Antes
           bastaba con ≥70 aunque el extremo de arriba tuviera 95: proponer que un 72
           "apalanque" a un 95 no es una excepción ascendente, es ruido. Sin potencia
           atribuida arriba no se juzga a la baja (silencio honesto: se propone).
        2. **Una tarjeta por ENTIDAD inferior**, no una por relación — la decisión que
           el usuario toma es sobre la entidad ("esta cosa de abajo empuja hacia
           arriba"); se conserva la relación de mayor confianza y se desempata por id
           para que el panel no baile entre refrescos.

        Medido sobre ese mismo mundo: 105 → 28 (total 203 → 126), sin perder ninguno
        de los 57 hallazgos de movimiento con `gap == 3` (los 55 desajustes plantados).
        """
        if not hasattr(proj, "entity_by_id"):
            return []
        pos_cache: dict[str, int] = {}

        def _pos(entity_id: str) -> int:
            if entity_id not in pos_cache:
                _, pos, _ = ring_display_info(proj, entity_id)
                pos_cache[entity_id] = pos
            return pos_cache[entity_id]

        # entidad inferior → mejor hallazgo (agrupación, punto 2 del docstring).
        best: dict[str, StructuralFinding] = {}
        for rel in getattr(proj, "relations", []) or []:
            if rel.relation_type in CAUSAL_RELATION_TYPES or is_ascending_exception(rel):
                continue  # ya escala (causal) o ya está marcada
            source = proj.entity_by_id(rel.source_id)
            target = proj.entity_by_id(rel.target_id)
            if source is None or target is None:
                continue
            if not self._eligible(source) or not self._eligible(target):
                continue
            # WS-N: SIMÉTRICO respecto a la orientación source/target (como el motor de
            # impacto que consume la marca). Se juzga por el extremo de MENOR anillo
            # (mayor _pos) con potencia atribuida alta, no solo cuando ese extremo es el
            # source (antes se subdetectaba ~la mitad de las relaciones elegibles).
            pos_source, pos_target = _pos(source.id), _pos(target.id)
            if pos_source == pos_target:
                continue  # mismo anillo → no hay ascenso
            low, high = (source, target) if pos_source > pos_target else (target, source)
            potency = get_annotated_potency(low)
            if potency is None or potency < _ASC_MIN_POTENCY:
                continue  # silencio honesto: sin potencia alta atribuida en el extremo inferior
            high_potency = get_annotated_potency(high)
            if high_potency is not None and potency < high_potency:
                continue  # FIX-05 punto 1: no apalanca a quien ya es más potente
            finding = self._build_ascending_finding(rel, low, high, potency)
            if self._is_suppressed(low, finding.fingerprint, current_rev):
                continue
            current = best.get(low.id)
            if current is None or (finding.confidence, finding.fingerprint) > (
                current.confidence,
                current.fingerprint,
            ):
                best[low.id] = finding
        return [best[key] for key in sorted(best)]

    def _build_ascending_finding(self, rel, source, target, potency: int) -> StructuralFinding:
        source_name = getattr(source, "name", "") or source.id
        target_name = getattr(target, "name", "") or target.id
        rel_type = getattr(rel.relation_type, "value", rel.relation_type)
        # BETA2-FIX-13 (G2-20). Esto decía, literalmente, «(contrato
        # §16)»: la aplicación citaba su propia especificación interna, por número
        # de sección, a una novelista que no tiene ningún §16 que abrir. Y usaba
        # «apalancamiento» a pelo, que no significa nada fuera del repo.
        # El DATO no cambia (`exception_kind` sigue valiendo "apalancamiento",
        # fijado por tests y consumido por candidate_service): cambia el texto.
        reasons = [
            f"«{source_name}» (potencial atribuido {potency}/100) está en un anillo inferior "
            f"al de «{target_name}», unidos por la relación no-causal «{rel_type}».",
            f"Hoy, si cambias «{source_name}», el aviso no sube hasta «{target_name}»: "
            "los avisos viajan del centro hacia fuera. Por su potencial, este caso "
            "debería ser una excepción y avisar también hacia dentro (en Dendro eso se "
            f"llama «{_DEFAULT_ASC_KIND}»: algo pequeño que mueve algo grande).",
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

    # ── branch_move (STRUCT-06) ─────────────────────────────────────────

    @staticmethod
    def _is_branch_with_content(proj, entity) -> bool:
        # WS-N: la ramitud se DERIVA del tipo (FACCION/CULTURA/RELIGION/INSTITUCION/
        # SISTEMA_MAGICO/LOCALIZACION + legacy CONTENEDOR), no del literal "contenedor".
        # Antes, una rama real con miembros (p.ej. una facción) no se reconocía y se le
        # proponía un ring_move SUELTO que, al aceptar, movía el contenedor solo y
        # huérfanaba a sus miembros en el anillo viejo — rompiendo la contención (el
        # invariante que STRUCT-06 existía para garantizar).
        return is_branch(entity) and bool(contained_descendant_ids(proj, entity.id))

    def _build_branch_finding(self, proj, container, n: int) -> StructuralFinding | None:
        """Hallazgo ``branch_move``: la potencia AGREGADA de la rama no cuadra con su anillo.

        Agregado = media de las potencias ATRIBUIDAS de la rama y su contenido transitivo
        (silencio honesto: sin ninguna potencia atribuida en el subárbol, no se juzga).
        Aceptar mueve el contenedor Y su contenido (cierre en application, no en la UI).
        """
        member_ids = contained_descendant_ids(proj, container.id)
        values: list[int] = []
        own = get_annotated_potency(container)
        if own is not None:
            values.append(own)
        for member_id in member_ids:
            member = proj.entity_by_id(member_id)
            if member is None:
                continue
            pot = get_annotated_potency(member)
            if pot is not None:
                values.append(pot)
        if not values:
            return None  # silencio honesto para toda la rama
        aggregate = round(sum(values) / len(values))
        target_pos = self._expected_position(aggregate, n)
        _, current_pos, _ = ring_display_info(proj, container.id)
        current_ring_id = ring_id_for(proj, container.id) or ""
        rank_map = effective_rank_map(list(getattr(proj, "world_layers", []) or []))
        target_ring_id = next(
            (lid for lid, pos in rank_map.items() if pos == target_pos), None
        )
        if not target_ring_id or str(target_ring_id) == str(current_ring_id):
            return None
        gap = abs(target_pos - current_pos)
        if gap < _MIN_GAP:
            return None
        confidence = self._confidence(gap)
        if confidence < _MIN_CONFIDENCE:
            return None
        name = getattr(container, "name", "") or container.id
        current_name = self._ring_name(proj, current_ring_id) if current_ring_id else "Sin anillo"
        target_name = self._ring_name(proj, target_ring_id)
        reasons = [
            f"La rama «{name}» y su contenido ({len(member_ids)} elemento(s)) tienen una "
            f"potencialidad causal agregada de {aggregate}/100 "
            f"(sobre {len(values)} valor(es) atribuido(s)).",
            f"Ese potencial corresponde al anillo «{target_name}» (banda {target_pos}/{n}), "
            f"pero la rama está en «{current_name}» (posición {current_pos}).",
        ]
        expected = self._expected_consequences(proj, container.id, target_ring_id)
        expected.append(
            f"Se moverán también los {len(member_ids)} elemento(s) contenidos (transitivo)."
        )
        proposed = {
            "kind": "branch_move",
            "entity_id": container.id,
            "current_ring_id": current_ring_id,
            "target_ring_id": target_ring_id,
            "member_ids": member_ids,
            "reasons": reasons,
            "expected_consequences": expected,
        }
        return StructuralFinding(
            kind="branch_move",
            target_id=container.id,
            proposed_data=proposed,
            confidence=confidence,
            fingerprint=f"branch_move:{container.id}:{current_ring_id}->{target_ring_id}",
            title=(
                f"Reubicar rama «{name}» (+{len(member_ids)}): {current_name} → {target_name}"
            ),
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
