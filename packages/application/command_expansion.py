"""Resolución pura de @menciones contra entidades/hitos conocidos.

Único superviviente de los helpers de la command bar (retirada en BETA2-WIKI-10;
el resto — fan-out de relaciones, lotes, planificación Acción×Ámbito — se borró
en la limpieza post-épica). ``parse_mentions`` sigue vivo como primitiva de las
referencias estructuradas (``structured_reference_service``): sin IA ni Qt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

# ---------------------------------------------------------------------------
# @-menciones
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

