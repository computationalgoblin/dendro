"""Pure command-bar expansion helpers for the deterministic AI pipeline.

These functions turn one user submission (prompt + selection + the chosen
Acción×Ámbito) into the concrete unit(s) of work, without any IA or Qt:

* parse_mentions  — resolve ``@Nombre`` references against known entities/hitos.
* relation_fanout_pairs — one relation job per pair when >2 entities are picked.
* consecutive_batches — split an oversized selection into sequential job batches.

Keeping this layer pure makes the matrix behaviours fully unit-testable with no
provider configured.
"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from typing import Iterable

from packages.application.ai_jobs import (
    BRANCH_TYPES,
    AIJobType,
    CommandAction,
    CommandScope,
    job_type_for_command,
)

# ---------------------------------------------------------------------------
# @-mentions (used by Editar and Explicar)
# ---------------------------------------------------------------------------

# Max @references honoured per prompt (product spec: "max 2 @").
DEFAULT_MAX_MENTIONS = 2

_MENTION_AT_RE = re.compile(r"@")
# A bare unresolved token runs until a delimiter that cannot be part of a name.
_UNRESOLVED_TOKEN_RE = re.compile(r"[^,@\n;]+")


@dataclass(frozen=True)
class MentionRef:
    """A resolved ``@`` reference to an existing entity or milestone."""

    raw: str          # the literal text matched after '@'
    name: str         # canonical name of the resolved target
    ref_id: str       # entity/milestone id
    ref_type: str     # "entity" | "milestone"


@dataclass
class ParsedMentions:
    refs: list[MentionRef] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    overflow: bool = False  # True when more than max_refs were matched

    @property
    def ref_ids(self) -> list[str]:
        return [r.ref_id for r in self.refs]

    def to_dict(self) -> dict:
        return {
            "refs": [
                {"raw": r.raw, "name": r.name, "ref_id": r.ref_id, "ref_type": r.ref_type}
                for r in self.refs
            ],
            "unresolved": list(self.unresolved),
            "overflow": self.overflow,
        }


def parse_mentions(
    prompt: str,
    known: Iterable[tuple[str, str, str]],
    *,
    max_refs: int = DEFAULT_MAX_MENTIONS,
) -> ParsedMentions:
    """Resolve ``@Nombre`` mentions in *prompt* against *known* targets.

    *known* is an iterable of ``(id, name, type)`` where type is ``"entity"`` or
    ``"milestone"``. Names may contain spaces, so each ``@`` greedily matches the
    LONGEST known name that follows it (case-insensitive). Tokens that match no
    known name are returned in ``unresolved``. At most *max_refs* references are
    kept; extra matches set ``overflow`` so the UI can warn.
    """
    text = prompt or ""
    # Longest names first so "Tierras del Norte" wins over a hypothetical "Tierras".
    candidates = sorted(
        ((str(i), str(n), str(t)) for i, n, t in known if str(n).strip()),
        key=lambda item: len(item[1]),
        reverse=True,
    )
    lowered = text.lower()

    result = ParsedMentions()

    for m in _MENTION_AT_RE.finditer(text):
        at = m.start()
        after = at + 1
        ref = None
        for ref_id, name, ref_type in candidates:
            if lowered.startswith(name.lower(), after):
                ref = MentionRef(
                    raw=text[after:after + len(name)],
                    name=name,
                    ref_id=ref_id,
                    ref_type=ref_type,
                )
                break
        if ref is not None:
            if len(result.refs) < max_refs:
                # de-dupe repeated mentions of the same target
                if all(existing.ref_id != ref.ref_id for existing in result.refs):
                    result.refs.append(ref)
                else:
                    continue
            else:
                result.overflow = True
        else:
            token_match = _UNRESOLVED_TOKEN_RE.match(text, after)
            token = (token_match.group(0).strip() if token_match else "")
            if token:
                result.unresolved.append(token)

    return result


# ---------------------------------------------------------------------------
# Relation fan-out (Crear + Relación)
# ---------------------------------------------------------------------------

# Product spec: "Max 6" relation jobs (C(4,2) = 6 → effectively up to 4 entities).
MAX_RELATION_JOBS = 6


def relation_fanout_pairs(
    entity_ids: Iterable[str],
    *,
    max_jobs: int = MAX_RELATION_JOBS,
) -> tuple[list[tuple[str, str]], bool]:
    """Pairs for a Crear+Relación fan-out: one job per unordered entity pair.

    With 2 entities → 1 pair; 3 → 3; 4 → 6. Returns ``(pairs, overflow)`` capped
    at *max_jobs*; ``overflow`` is True when the selection produces more pairs
    than allowed (so the UI can ask the user to narrow the selection).
    """
    ids = [e for e in dict.fromkeys(str(x) for x in entity_ids) if e]
    pairs = list(itertools.combinations(ids, 2))
    overflow = len(pairs) > max_jobs
    return pairs[:max_jobs], overflow


# ---------------------------------------------------------------------------
# Consecutive batching (Analizar over large selections)
# ---------------------------------------------------------------------------

# Product spec: build consecutive jobs when a selection exceeds 6 entities.
MAX_ENTITIES_PER_JOB = 6


def consecutive_batches(
    entity_ids: Iterable[str],
    *,
    batch_size: int = MAX_ENTITIES_PER_JOB,
) -> list[list[str]]:
    """Split a selection into consecutive batches of at most *batch_size*.

    A selection of <= batch_size yields a single batch (the common case); larger
    selections are chunked so each becomes its own sequential job.
    """
    ids = [e for e in (str(x) for x in entity_ids) if e]
    if not ids:
        return []
    size = max(1, int(batch_size))
    return [ids[i:i + size] for i in range(0, len(ids), size)]


# ---------------------------------------------------------------------------
# Submission planner — one user submission → the concrete job(s) to create
# ---------------------------------------------------------------------------

MAX_SUGGESTIONS = 3          # Crear Hoja/Rama
MAX_EDIT_SELECTION = 6       # Editar: max 6 elements
MAX_EXPLAIN_CREATIONS = 3    # Explicar: max 3 created entities/hitos


@dataclass
class PlannedJob:
    """One job to create: a job type, the prompt, and context to merge in."""

    job_type: AIJobType
    prompt: str
    context_overrides: dict = field(default_factory=dict)


@dataclass
class CommandPlan:
    jobs: list[PlannedJob] = field(default_factory=list)
    error: str | None = None          # blocking: nothing is created
    warnings: list[str] = field(default_factory=list)


def _clamp(value: int, low: int, high: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = low
    return max(low, min(high, v))


def plan_command_jobs(
    action: "CommandAction | str",
    scope: "CommandScope | str",
    prompt: str,
    *,
    selected_entity_ids: Iterable[str] | None = None,
    selected_relation_ids: Iterable[str] | None = None,
    known_mentions: Iterable[tuple[str, str, str]] | None = None,
    suggestion_count: int = 1,
    active_ring_id: str = "",
) -> CommandPlan:
    """Expand one deterministic submission into the job(s) to create.

    Pure: no IA, no Qt, no project access — the host passes the selection and the
    known mention targets. Encodes the per-cell behaviours: relation fan-out,
    Crear-Anillo's no-selection rule, suggestion count, Editar's selection/@ caps,
    Explicar's branching hint, and consecutive batching for large Analizar runs.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return CommandPlan(error="Escribe una orden para Dendro")
    try:
        act = action if isinstance(action, CommandAction) else CommandAction(str(action))
        scp = scope if isinstance(scope, CommandScope) else CommandScope(str(scope))
        base_type = job_type_for_command(act, scp)
    except ValueError as exc:
        return CommandPlan(error=str(exc))

    entities = [e for e in (str(x) for x in (selected_entity_ids or [])) if e]
    relations = [r for r in (str(x) for x in (selected_relation_ids or [])) if r]

    warnings: list[str] = []
    mentions = parse_mentions(prompt, known_mentions or [])
    if mentions.overflow:
        warnings.append("Solo se usan las 2 primeras @menciones.")
    if mentions.unresolved:
        warnings.append("Referencias @ no encontradas: " + ", ".join(mentions.unresolved))

    common: dict = {
        "command_action": act.value,
        "command_scope": scp.value,
        "mentions": mentions.to_dict(),
    }

    # --- Crear + Relación: one job per pair (fan-out) ----------------------
    if act is CommandAction.CREAR and scp is CommandScope.RELACION:
        if len(entities) < 2:
            return CommandPlan(error="Selecciona al menos dos entidades para crear relaciones.")
        pairs, overflow = relation_fanout_pairs(entities)
        if overflow:
            warnings.append(
                f"Se crean {len(pairs)} relaciones (máx {MAX_RELATION_JOBS}); reduce la selección."
            )
        jobs = [
            PlannedJob(base_type, prompt, {
                **common,
                "selected_entity_ids": list(pair),
                "fanout_pair": list(pair),
                "fanout_index": i,
                "fanout_total": len(pairs),
            })
            for i, pair in enumerate(pairs)
        ]
        return CommandPlan(jobs=jobs, warnings=warnings)

    # --- Crear + Anillo: no selection; uses creative config + previous ring -
    if act is CommandAction.CREAR and scp is CommandScope.ANILLO:
        if entities or relations:
            return CommandPlan(
                error=(
                    "Crear Anillo no admite selección: se basa en la configuración "
                    "creativa y el anillo anterior."
                ),
            )
        return CommandPlan(jobs=[PlannedJob(base_type, prompt, {
            **common,
            "ring_template": True,
            "previous_ring_id": active_ring_id,
        })], warnings=warnings)

    # --- Crear + Hoja/Rama: configurable suggestion count ---------
    if act is CommandAction.CREAR and scp in (
        CommandScope.HOJA, CommandScope.RAMA
    ):
        count = _clamp(suggestion_count, 1, MAX_SUGGESTIONS)
        return CommandPlan(jobs=[PlannedJob(base_type, prompt, {
            **common,
            "selected_entity_ids": entities,
            "suggestion_count": count,
        })], warnings=warnings)

    # --- Analizar: consecutive batches when selection > 6 ------------------
    if act is CommandAction.ANALIZAR:
        if len(entities) <= MAX_ENTITIES_PER_JOB:
            return CommandPlan(jobs=[PlannedJob(base_type, prompt, {
                **common, "selected_entity_ids": entities, "selected_relation_ids": relations,
            })], warnings=warnings)
        batches = consecutive_batches(entities)
        warnings.append(
            f"Selección > {MAX_ENTITIES_PER_JOB}: {len(batches)} análisis consecutivos."
        )
        jobs = [
            PlannedJob(base_type, prompt, {
                **common, "selected_entity_ids": batch,
                "batch_index": i, "batch_total": len(batches),
            })
            for i, batch in enumerate(batches)
        ]
        return CommandPlan(jobs=jobs, warnings=warnings)

    # --- Editar: cap selection at 6, mentions already parsed (max 2) -------
    if act is CommandAction.EDITAR:
        used = entities
        if len(entities) > MAX_EDIT_SELECTION:
            used = entities[:MAX_EDIT_SELECTION]
            warnings.append(
                f"Editar admite máx {MAX_EDIT_SELECTION} elementos; se usan los primeros."
            )
        return CommandPlan(jobs=[PlannedJob(base_type, prompt, {
            **common, "selected_entity_ids": used, "selected_relation_ids": relations,
        })], warnings=warnings)

    # --- Explicar / Expandir: branching hint + active ring -----------------
    if act in (CommandAction.EXPLICAR, CommandAction.EXPANDIR):
        explain_target = "modify_refs" if mentions.refs else "create_in_active_ring"
        return CommandPlan(jobs=[PlannedJob(base_type, prompt, {
            **common,
            "selected_entity_ids": entities,
            "selected_relation_ids": relations,
            "active_ring_id": active_ring_id,
            "explain_target": explain_target,
            "max_creations": MAX_EXPLAIN_CREATIONS,
        })], warnings=warnings)

    # --- Fallback: single job ---------------------------------------------
    return CommandPlan(jobs=[PlannedJob(base_type, prompt, {
        **common, "selected_entity_ids": entities, "selected_relation_ids": relations,
    })], warnings=warnings)


# ---------------------------------------------------------------------------
# Ejemplos por celda Acción×Ámbito (descubribilidad / onboarding del flujo IA)
# ---------------------------------------------------------------------------

# Ejemplo de orden por par para CREAR/EDITAR (el ámbito cambia el ejemplo).
_EXAMPLES_BY_PAIR: dict[tuple["CommandAction", "CommandScope"], str] = {
    (CommandAction.CREAR, CommandScope.HOJA):
        "un herrero exiliado que oculta su pasado noble",
    (CommandAction.CREAR, CommandScope.RAMA):
        "una orden de monjes guerreros y su jerarquía interna",
    (CommandAction.CREAR, CommandScope.RELACION):
        "por qué estas dos facciones se traicionaron",
    (CommandAction.CREAR, CommandScope.ANILLO):
        "un nuevo estrato: la era de los primeros reinos",
    (CommandAction.CREAR, CommandScope.HITO):
        "la batalla que dividió el continente en dos",
    (CommandAction.EDITAR, CommandScope.HOJA):
        "hazlo más sombrío: dale una cicatriz y una deuda de sangre",
    (CommandAction.EDITAR, CommandScope.RAMA):
        "unifica el tono de esta cultura hacia lo melancólico",
    (CommandAction.EDITAR, CommandScope.RELACION):
        "convierte esta alianza en una rivalidad latente",
    (CommandAction.EDITAR, CommandScope.ANILLO):
        "reescribe este estrato con un clima más árido",
    (CommandAction.EDITAR, CommandScope.HITO):
        "adelanta este suceso un siglo y suaviza sus consecuencias",
}

# La trío analítica (ANALIZAR/EXPLICAR/EXPANDIR) oculta el ámbito en la UI, así que
# su ejemplo depende solo de la acción.
_EXAMPLES_BY_ACTION: dict["CommandAction", str] = {
    CommandAction.ANALIZAR: "¿hay contradicciones entre @Facción y @Reino?",
    CommandAction.EXPLICAR: "explica el origen de esta guerra a partir de sus causas",
    CommandAction.EXPANDIR: "amplía la cultura y costumbres de este anillo",
}

_EXAMPLE_FALLBACK = "describe a Dendro qué quieres crear o cambiar"


def example_for_command(
    action: "CommandAction | str",
    scope: "CommandScope | str",
) -> str:
    """Ejemplo de orden, en español, para una celda Acción×Ámbito.

    Sirve como placeholder dinámico del input y de muestra en la ayuda; mantiene
    los textos en una única fuente (pura, sin Qt). Para la trío analítica el ámbito
    no influye (la UI lo oculta), así que se usa el ejemplo por acción. Tolera
    valores str o enum y nunca lanza: devuelve un texto genérico si el par es raro.
    """
    try:
        act = action if isinstance(action, CommandAction) else CommandAction(str(action))
    except ValueError:
        return _EXAMPLE_FALLBACK
    if act in _EXAMPLES_BY_ACTION:
        return _EXAMPLES_BY_ACTION[act]
    try:
        scp = scope if isinstance(scope, CommandScope) else CommandScope(str(scope))
    except ValueError:
        return _EXAMPLE_FALLBACK
    return _EXAMPLES_BY_PAIR.get((act, scp), _EXAMPLE_FALLBACK)


# ---------------------------------------------------------------------------
# Causal-deductive context ordering (Anillos → Ramas → Hojas)
# ---------------------------------------------------------------------------

CAUSAL_ORDER_INSTRUCTION = (
    "Prioriza el contexto por causalidad de forma deductiva: primero los anillos "
    "y sus hitos (estratos causales superiores), luego las ramas y las relaciones/"
    "hitos entre ellas, y por último las hojas y las relaciones entre hojas."
)


def _is_branch(entity: dict) -> bool:
    if str(entity.get("display_type") or "").lower() == "rama":
        return True
    return str(entity.get("entity_type") or "").lower() in BRANCH_TYPES


def order_context_by_causality(
    *,
    entities: Iterable[dict] | None = None,
    relations: Iterable[dict] | None = None,
    rings: Iterable[dict] | None = None,
    milestones: Iterable[dict] | None = None,
) -> dict:
    """Group/sort the authorized context by causal hierarchy.

    The model should read the result top-down (most causally-upstream first):
    anillos (sorted by ``order``, each with its hitos) → ramas + relations/hitos
    between branches → hojas + relations between leaves. Pure and defensive: each
    input is a list of plain dicts and any may be missing.
    """
    ents = [e for e in (entities or []) if isinstance(e, dict)]
    rels = [r for r in (relations or []) if isinstance(r, dict)]
    ring_list = [r for r in (rings or []) if isinstance(r, dict)]
    miles = [m for m in (milestones or []) if isinstance(m, dict)]

    branches = [e for e in ents if _is_branch(e)]
    leaves = [e for e in ents if not _is_branch(e)]
    branch_ids = {str(e.get("id")) for e in branches}
    leaf_ids = {str(e.get("id")) for e in leaves}

    def _endpoints(rel: dict) -> tuple[str, str]:
        return str(rel.get("source_id") or ""), str(rel.get("target_id") or "")

    rel_between_branches = [r for r in rels if all(x in branch_ids for x in _endpoints(r))]
    rel_between_leaves = [r for r in rels if all(x in leaf_ids for x in _endpoints(r))]
    handled = {id(r) for r in rel_between_branches} | {id(r) for r in rel_between_leaves}
    rel_mixed = [r for r in rels if id(r) not in handled]

    def _ring_order(ring: dict) -> int:
        try:
            return int(ring.get("order", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _milestones_for_ring(ring_id: str) -> list[dict]:
        if not ring_id:
            return []
        return [m for m in miles if ring_id in {str(x) for x in (m.get("layer_ids") or [])}]

    anillos = []
    for ring in sorted(ring_list, key=_ring_order):
        ring_id = str(ring.get("id") or "")
        anillos.append({**ring, "hitos": _milestones_for_ring(ring_id)})

    ring_ids = {str(r.get("id") or "") for r in ring_list}
    unbound_milestones = [
        m for m in miles
        if not ({str(x) for x in (m.get("layer_ids") or [])} & ring_ids)
    ]

    return {
        "orden": ["anillos", "ramas", "hojas"],
        "instruccion": CAUSAL_ORDER_INSTRUCTION,
        "anillos": anillos,
        "ramas": branches,
        "relaciones_entre_ramas": rel_between_branches,
        "hojas": leaves,
        "relaciones_entre_hojas": rel_between_leaves,
        "relaciones_mixtas": rel_mixed,
        "hitos_sin_anillo": unbound_milestones,
    }
