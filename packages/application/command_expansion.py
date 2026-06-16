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
