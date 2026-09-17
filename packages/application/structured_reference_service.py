"""StructuredReferenceService — @menciones estructuradas (BETA2-MEM-03).

Convierte las @menciones que el usuario escribe en campos de prosa en
``StructuredReference`` persistidas (modelo sidecar: el texto se guarda tal cual;
la referencia resuelta vive en ``project.structured_references``). Reutiliza el
parser probado ``command_expansion.parse_mentions`` como ÚNICA regla de
resolución (contrato §10, criterio 6: no dos reglas incompatibles); encima añade
detección de ambigüedad por nombres duplicados y estado reparable.

Sin IA: todo es determinista y funciona sin proveedor configurado. La UI nunca
escribe persistencia directa; llama a este servicio de aplicación al guardar.
Backlinks on-demand sobre las refs persistidas (O(refs), no O(texto)).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

from packages.application.command_expansion import parse_mentions
from packages.domain.entity_taxonomy import is_branch
from packages.domain.narrative_memory import MemoryCitation, MemoryTargetKind
from packages.domain.result import Error, Ok, Result
from packages.domain.structured_reference import ReferenceStatus, StructuredReference

# Sin tope de menciones en prosa (el tope 2 de la command bar es una regla de UI).
_PROSE_MAX_MENTIONS = 10_000


def _as_kind(value: MemoryTargetKind | str) -> MemoryTargetKind:
    if isinstance(value, MemoryTargetKind):
        return value
    return MemoryTargetKind(str(value))


def _first_word(token: str) -> str:
    """Alias limpio para una mención no resuelta en prosa.

    El parser de la command bar captura hasta un delimitador (`,`/`;`/salto);
    en prosa eso engulliría la frase, así que nos quedamos con la primera
    palabra y recortamos puntuación de borde.
    """
    parts = (token or "").split()
    if not parts:
        return ""
    return parts[0].strip(".,;:!?()[]\"'").strip()


def build_known_targets(project: Any) -> list[tuple[str, str, str]]:
    """Lista ``(id, name, kind)`` de elementos mencionables por @nombre.

    Cobertura "Moderado" (BETA2-MEM-03): entidades (rama/hoja), hitos y anillos.
    Las relaciones no se teclean como @mención (sin nombre corto natural) pero sí
    reciben backlinks vía source/target de la relación.
    """
    known: list[tuple[str, str, str]] = []
    for e in getattr(project, "entities", []) or []:
        name = getattr(e, "name", "") or ""
        if not name.strip():
            continue
        kind = MemoryTargetKind.BRANCH.value if is_branch(e) else MemoryTargetKind.ENTITY.value
        known.append((getattr(e, "id", ""), name, kind))
    for h in getattr(project, "causal_milestones", []) or []:
        title = getattr(h, "title", "") or ""
        if title.strip():
            known.append((getattr(h, "id", ""), title, MemoryTargetKind.MILESTONE.value))
    for wl in getattr(project, "world_layers", []) or []:
        name = getattr(wl, "name", "") or ""
        if name.strip():
            known.append((getattr(wl, "id", ""), name, MemoryTargetKind.RING.value))
    return known


def _name_index(known: Iterable[tuple[str, str, str]]) -> dict[str, list[tuple[str, str]]]:
    """name.lower() -> lista de (id, kind), para detectar nombres duplicados."""
    index: dict[str, list[tuple[str, str]]] = {}
    for ref_id, name, kind in known:
        index.setdefault(name.lower(), []).append((ref_id, kind))
    return index


# ═══════════════════════════════════════════════════════════════════════
# Resolución de los ENLACES DE UNA PÁGINA de wiki (BETA2-FIX-07)
# ═══════════════════════════════════════════════════════════════════════
#
# La IA que escribe una página (`update_memory`) rellena `wikilinks`/`citations`/
# `issues[].anclado_a` con `MemoryCitation`. En el beta escribía el NOMBRE dentro
# de `ref_id` y nadie lo resolvía: 27 de 27 enlaces rotos persistidos. Aquí vive
# la resolución, hermana de `resolve_references` y con su MISMA regla (contrato
# §10, criterio 6: no dos reglas incompatibles) — reutiliza `build_known_targets`
# y añade plegado de mayúsculas/acentos, que la wiki necesita porque el modelo no
# copia los nombres carácter a carácter.


def fold_name(text: Any) -> str:
    """Pliega un nombre para compararlo: sin acentos, en minúsculas, sin dobles espacios."""
    descompuesto = unicodedata.normalize("NFD", str(text or ""))
    sin_tildes = "".join(ch for ch in descompuesto if unicodedata.category(ch) != "Mn")
    return " ".join(sin_tildes.casefold().split())


def canon_kind_by_id(project: Any) -> dict[str, str]:
    """``id -> kind real`` de TODO el canon referenciable desde una página.

    Más amplio que ``build_known_targets`` a propósito: cubre también las
    relaciones (no tienen nombre corto, pero sí id enlazable) y los elementos sin
    nombre, que existen aunque no sean mencionables por @nombre.
    """
    index: dict[str, str] = {}
    for e in getattr(project, "entities", []) or []:
        eid = str(getattr(e, "id", "") or "")
        if eid:
            index.setdefault(
                eid,
                MemoryTargetKind.BRANCH.value if is_branch(e) else MemoryTargetKind.ENTITY.value,
            )
    for r in getattr(project, "relations", []) or []:
        rid = str(getattr(r, "id", "") or "")
        if rid:
            index.setdefault(rid, MemoryTargetKind.RELATION.value)
    for h in getattr(project, "causal_milestones", []) or []:
        hid = str(getattr(h, "id", "") or "")
        if hid:
            index.setdefault(hid, MemoryTargetKind.MILESTONE.value)
    for layer in getattr(project, "world_layers", []) or []:
        lid = str(getattr(layer, "id", "") or "")
        if lid:
            index.setdefault(lid, MemoryTargetKind.RING.value)
    return index


@dataclass(frozen=True)
class PageRefResolution:
    """Reparto de los enlaces de una página tras resolverlos contra el canon.

    ``ambiguas`` y ``descartadas`` NO se persisten (``MemoryCitation`` no tiene
    estado y dárselo sería cambio de esquema): se devuelven para que quien llama
    los cuente y los DIGA. Descartar en silencio es el pecado que este ticket
    corrige, no uno nuevo que introduce.
    """

    resueltas: list[MemoryCitation] = field(default_factory=list)
    ambiguas: list[MemoryCitation] = field(default_factory=list)
    descartadas: list[MemoryCitation] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "resueltos": len(self.resueltas),
            "ambiguos": len(self.ambiguas),
            "descartados": len(self.descartadas),
        }


def resolve_page_refs(
    project: Any,
    refs: Iterable[MemoryCitation] | None,
    *,
    known: list[tuple[str, str, str]] | None = None,
    kinds_by_id: dict[str, str] | None = None,
) -> PageRefResolution:
    """Resuelve enlaces de página contra el canon (función pura, sin IA).

    Regla, en este orden:

    1. ``ref_kind=project`` → se conserva tal cual (no apunta a un elemento; el
       lint tampoco lo evalúa).
    2. ``ref_id`` que YA es un id del canon → se conserva y se le **corrige el
       kind** al real (la IA escribe ``entity`` de una rama o de un hito).
    3. ``ref_id`` que es el NOMBRE exacto de un elemento (plegando mayúsculas y
       acentos) → se reescribe con su id y su kind reales.
    4. Nombre que corresponde a VARIOS elementos → **ambigua**: no se inventa un
       ganador y no se persiste.
    5. Todo lo demás → **descartada**.

    Las relaciones solo resuelven por id: no tienen nombre corto y
    ``build_known_targets`` no las indexa (a conciencia).
    """
    known = known if known is not None else build_known_targets(project)
    kinds = kinds_by_id if kinds_by_id is not None else canon_kind_by_id(project)
    por_nombre: dict[str, list[str]] = {}
    for ref_id, name, _kind in known:
        if ref_id:
            por_nombre.setdefault(fold_name(name), []).append(ref_id)

    resueltas: list[MemoryCitation] = []
    ambiguas: list[MemoryCitation] = []
    descartadas: list[MemoryCitation] = []
    for ref in refs or []:
        raw_kind = str(getattr(ref.ref_kind, "value", ref.ref_kind) or "")
        ref_id = str(ref.ref_id or "").strip()
        nota = ref.nota
        if raw_kind == MemoryTargetKind.PROJECT.value:
            resueltas.append(MemoryCitation(MemoryTargetKind.PROJECT, ref_id, nota))
            continue
        if ref_id and ref_id in kinds:
            resueltas.append(MemoryCitation(MemoryTargetKind(kinds[ref_id]), ref_id, nota))
            continue
        candidatos = list(dict.fromkeys(por_nombre.get(fold_name(ref_id), [])))
        if len(candidatos) == 1:
            elegido = candidatos[0]
            kind = kinds.get(elegido, MemoryTargetKind.ENTITY.value)
            resueltas.append(MemoryCitation(MemoryTargetKind(kind), elegido, nota))
        elif len(candidatos) > 1:
            ambiguas.append(MemoryCitation(MemoryTargetKind(raw_kind or "entity"), ref_id, nota))
        else:
            descartadas.append(MemoryCitation(MemoryTargetKind(raw_kind or "entity"), ref_id, nota))
    return PageRefResolution(resueltas, ambiguas, descartadas)


def resolve_references(
    project: Any,
    source_kind: MemoryTargetKind | str,
    source_id: str,
    field_texts: dict[str, str],
    *,
    hints: dict[str, tuple[str, str]] | None = None,
    known: list[tuple[str, str, str]] | None = None,
) -> list[StructuredReference]:
    """Resuelve las @menciones de los campos de un elemento (función pura).

    ``hints`` mapea ``alias.lower() -> (kind, target_id)`` con los picks exactos
    del autocompletar (fijan el id sin ambigüedad). ``field_texts`` debe traer
    TODOS los campos con menciones del elemento (se recomputan enteros).
    """
    src_kind = _as_kind(source_kind)
    known = known if known is not None else build_known_targets(project)
    index = _name_index(known)
    hints = {k.lower(): v for k, v in (hints or {}).items()}

    out: list[StructuredReference] = []
    for source_field, text in field_texts.items():
        parsed = parse_mentions(text or "", known, max_refs=_PROSE_MAX_MENTIONS)
        for mref in parsed.refs:
            alias = mref.raw
            hint = hints.get(alias.lower())
            if hint:
                out.append(
                    StructuredReference(
                        source_kind=src_kind,
                        source_id=source_id,
                        source_field=source_field,
                        target_kind=_as_kind(hint[0]),
                        target_id=hint[1],
                        alias=alias,
                        status=ReferenceStatus.RESUELTA,
                    )
                )
                continue
            candidates = index.get(mref.name.lower(), [])
            distinct_ids = list({cid for cid, _ in candidates})
            if len(distinct_ids) > 1:
                out.append(
                    StructuredReference(
                        source_kind=src_kind,
                        source_id=source_id,
                        source_field=source_field,
                        target_kind=_as_kind(mref.ref_type),
                        target_id="",
                        alias=alias,
                        status=ReferenceStatus.AMBIGUA,
                        candidate_target_ids=distinct_ids,
                    )
                )
            else:
                out.append(
                    StructuredReference(
                        source_kind=src_kind,
                        source_id=source_id,
                        source_field=source_field,
                        target_kind=_as_kind(mref.ref_type),
                        target_id=mref.ref_id,
                        alias=alias,
                        status=ReferenceStatus.RESUELTA,
                    )
                )
        for token in parsed.unresolved:
            alias = _first_word(token)
            if not alias:
                continue
            hint = hints.get(alias.lower())
            if hint:
                out.append(
                    StructuredReference(
                        source_kind=src_kind,
                        source_id=source_id,
                        source_field=source_field,
                        target_kind=_as_kind(hint[0]),
                        target_id=hint[1],
                        alias=alias,
                        status=ReferenceStatus.RESUELTA,
                    )
                )
            else:
                out.append(
                    StructuredReference(
                        source_kind=src_kind,
                        source_id=source_id,
                        source_field=source_field,
                        target_kind=src_kind,
                        target_id="",
                        alias=alias,
                        status=ReferenceStatus.NO_RESUELTA,
                    )
                )
    return out


def backlinks_for(
    project: Any, target_kind: MemoryTargetKind | str, target_id: str
) -> list[StructuredReference]:
    """Quién menciona a este elemento (on-demand sobre refs persistidas)."""
    kind = _as_kind(target_kind)
    return [
        r
        for r in (getattr(project, "structured_references", []) or [])
        if r.target_kind == kind and r.target_id == target_id and r.is_resolved()
    ]


@dataclass
class StructuredReferenceService:
    """CRUD/consulta de referencias estructuradas del proyecto activo (Result)."""

    project_service: Any

    def _proj(self):
        return getattr(self.project_service, "active_project", None)

    def _ensure_refs(self) -> list[StructuredReference] | None:
        proj = self._proj()
        if proj is None:
            return None
        if not isinstance(getattr(proj, "structured_references", None), list):
            proj.structured_references = []
        return proj.structured_references

    def sync_element_references(
        self,
        source_kind: MemoryTargetKind | str,
        source_id: str,
        field_texts: dict[str, str],
        *,
        hints: dict[str, tuple[str, str]] | None = None,
    ) -> Result[list[StructuredReference], str]:
        """Recomputa las refs de un elemento al guardar y reemplaza en la colección.

        Solo toca los campos presentes en ``field_texts`` (soporta guardados
        parciales). Idempotente: mismo texto → mismas refs.
        """
        refs = self._ensure_refs()
        if refs is None:
            return Error("No hay proyecto activo")
        proj = self._proj()
        src_kind = _as_kind(source_kind)
        provided = set(field_texts.keys())
        new_refs = resolve_references(proj, src_kind, source_id, field_texts, hints=hints)
        proj.structured_references = [
            r
            for r in refs
            if not (
                r.source_kind == src_kind
                and r.source_id == source_id
                and r.source_field in provided
            )
        ] + new_refs
        if hasattr(proj, "touch"):
            proj.touch()
        return Ok(new_refs)

    def references_of(
        self, source_kind: MemoryTargetKind | str, source_id: str
    ) -> Result[list[StructuredReference], str]:
        refs = self._ensure_refs()
        if refs is None:
            return Error("No hay proyecto activo")
        kind = _as_kind(source_kind)
        return Ok([r for r in refs if r.source_kind == kind and r.source_id == source_id])

    def backlinks(
        self, target_kind: MemoryTargetKind | str, target_id: str
    ) -> Result[list[StructuredReference], str]:
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        return Ok(backlinks_for(proj, target_kind, target_id))

    def unresolved(self) -> Result[list[StructuredReference], str]:
        """Menciones reparables (ambiguas o no resueltas) para la UI de reparación."""
        refs = self._ensure_refs()
        if refs is None:
            return Error("No hay proyecto activo")
        return Ok([r for r in refs if r.status != ReferenceStatus.RESUELTA])

    def resolve_reference(
        self, reference_id: str, target_kind: MemoryTargetKind | str, target_id: str
    ) -> Result[StructuredReference, str]:
        """Repara una mención ambigua/no resuelta fijando su target elegido."""
        refs = self._ensure_refs()
        if refs is None:
            return Error("No hay proyecto activo")
        for r in refs:
            if r.id == reference_id:
                r.target_kind = _as_kind(target_kind)
                r.target_id = target_id
                r.status = ReferenceStatus.RESUELTA
                r.candidate_target_ids = []
                proj = self._proj()
                if hasattr(proj, "touch"):
                    proj.touch()
                return Ok(r)
        return Error("No existe la referencia indicada")


__all__ = [
    "PageRefResolution",
    "StructuredReferenceService",
    "backlinks_for",
    "build_known_targets",
    "canon_kind_by_id",
    "fold_name",
    "resolve_page_refs",
    "resolve_references",
]
