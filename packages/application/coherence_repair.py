"""UX8 — reparación de coherencia: convierte el informe de incoherencias en
CAMBIOS CONCRETOS sobre el canon (no sugerencias literales).

Flujo (host-agnóstico):
1. Un job IA ``REPAIR_COHERENCE`` devuelve ``repair_changes`` (valores finales ya
   redactados). ``normalize_repair_changes`` los limpia/valida.
2. ``resolve_repair_changes(changes, project)`` calcula, contra el canon actual, el
   ANTES y el DESPUÉS de cada cambio + una etiqueta legible, para que el host los
   muestre como una lista revisable (diff) con casilla por cambio.
3. ``apply_resolved_change`` aplica un cambio (posiblemente editado por el usuario)
   al canon vía los servicios de aplicación — nunca toca persistencia directa, y
   solo se invoca por acción humana explícita (botón «Aplicar»).

No crea semillas/candidatos: la revisión vive en un panel dedicado del host.
"""
from __future__ import annotations

from typing import Any

from packages.domain.causal_milestone import CausalMilestone
from packages.domain.relation import RelationType
from packages.domain.result import Error, Ok, Result

_CHANGE_TYPES = frozenset(
    {"edit_entity", "edit_relation", "create_relation", "create_entity", "create_milestone"}
)
_NO_EXISTE = "(no existe)"


def _s(value: Any) -> str:
    return str(value or "").strip()


def normalize_repair_changes(raw: Any) -> list[dict[str, Any]]:
    """Valida y normaliza la salida del modelo. Descarta cambios mal formados.

    Cada cambio conserva solo los campos relevantes a su tipo. Un cambio vago que
    el modelo no convirtió en valores concretos (sin objetivo o sin texto) se omite.
    """
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ct = _s(item.get("change_type")).lower()
        if ct not in _CHANGE_TYPES:
            continue
        rationale = _s(item.get("rationale"))
        if ct == "edit_entity":
            name = _s(item.get("entity_name") or item.get("name"))
            value = _s(item.get("proposed_value"))
            field = _s(item.get("field")).lower() or "body"
            if field not in ("brief_description", "body"):
                field = "body"
            if not (name and value):
                continue
            out.append({"change_type": ct, "entity_name": name, "field": field,
                        "proposed_value": value, "rationale": rationale})
        elif ct in ("edit_relation", "create_relation"):
            src = _s(item.get("source_name"))
            tgt = _s(item.get("target_name"))
            rtype = _s(item.get("relation_type"))
            desc = _s(item.get("description"))
            body = _s(item.get("body"))
            if not (src and tgt) or not (rtype or desc or body):
                continue
            out.append({"change_type": ct, "source_name": src, "target_name": tgt,
                        "relation_type": rtype, "description": desc, "body": body,
                        "rationale": rationale})
        elif ct == "create_entity":
            name = _s(item.get("name") or item.get("entity_name"))
            if not name:
                continue
            out.append({"change_type": ct, "name": name,
                        "entity_type": _s(item.get("entity_type")) or "personaje",
                        "brief_description": _s(item.get("brief_description")
                                                or item.get("description")),
                        "body": _s(item.get("body") or item.get("extended_description")),
                        "rationale": rationale})
        elif ct == "create_milestone":
            title = _s(item.get("title") or item.get("name"))
            if not title:
                continue
            out.append({"change_type": ct, "title": title,
                        "summary": _s(item.get("summary") or item.get("description")),
                        "body": _s(item.get("body")), "rationale": rationale})
    return out


# ── resolución (antes/después) ──────────────────────────────────────────────


def _find_entity(project, name: str):
    target = name.lower()
    return next((e for e in getattr(project, "entities", [])
                 if _s(getattr(e, "name", "")).lower() == target), None)


def _find_relation(project, source_id: str, target_id: str):
    rels = getattr(project, "relations", [])
    direct = next((r for r in rels
                   if r.source_id == source_id and r.target_id == target_id), None)
    if direct is not None:
        return direct
    return next((r for r in rels
                 if {r.source_id, r.target_id} == {source_id, target_id}), None)


_FIELD_ES = {"brief_description": "descripción breve", "body": "cuerpo"}


def resolve_repair_changes(changes: list[dict[str, Any]], project) -> list[dict[str, Any]]:
    """Añade `label`, `before`, `after`, `applicable` y `note` a cada cambio.

    `after` es el texto editable que verá el usuario; `_change` conserva el cambio
    normalizado para aplicarlo. `applicable=False` marca cambios cuyo objetivo no se
    resuelve (p. ej. editar una entidad inexistente): el host los muestra deshabilitados.
    """
    resolved: list[dict[str, Any]] = []
    for ch in changes:
        ct = ch["change_type"]
        label, before, after, applicable, note = "", _NO_EXISTE, "", True, ch.get("rationale", "")
        text_field = ""
        if ct == "edit_entity":
            ent = _find_entity(project, ch["entity_name"])
            field = ch["field"]
            label = f"{ch['entity_name']} · {_FIELD_ES.get(field, field)}"
            after = ch["proposed_value"]
            if ent is None:
                applicable, before = False, _NO_EXISTE
                note = f"No se encontró la entidad «{ch['entity_name']}»."
            else:
                dom = "extended_description" if field == "body" else "brief_description"
                before = _s(getattr(ent, dom, ""))
        elif ct in ("edit_relation", "create_relation"):
            src = _find_entity(project, ch["source_name"])
            tgt = _find_entity(project, ch["target_name"])
            label = f"Relación  {ch['source_name']} → {ch['target_name']}"
            text_field = "body" if ch["body"] else "description"
            after = ch["body"] or ch["description"]
            rel = None
            if src is not None and tgt is not None:
                rel = _find_relation(project, src.id, tgt.id)
            if src is None or tgt is None:
                applicable = False
                note = "Falta alguna de las dos entidades de la relación."
            elif rel is not None:
                meta = dict(getattr(rel, "custom_metadata", {}) or {})
                before = _s(meta.get("_body")) if text_field == "body" else _s(
                    getattr(rel, "description", ""))
            else:
                before = _NO_EXISTE
        elif ct == "create_entity":
            label = f"Nueva entidad: {ch['name']}"
            text_field = "body" if ch["body"] else "brief_description"
            after = ch["body"] or ch["brief_description"]
        elif ct == "create_milestone":
            label = f"Nuevo hito: {ch['title']}"
            after = ch["body"] or ch["summary"]
        resolved.append({
            "change_type": ct, "label": label, "before": before, "after": after,
            "applicable": applicable, "note": note, "text_field": text_field,
            "_change": ch,
        })
    return resolved


# ── aplicación a canon ──────────────────────────────────────────────────────


def _coerce_relation_type(value: str) -> RelationType:
    try:
        return RelationType(value)
    except ValueError:
        return RelationType.ESTA_RELACIONADO_CON


def apply_resolved_change(
    resolved: dict[str, Any], *, project, entity_service, relation_service,
) -> Result[str, str]:
    """Aplica un cambio resuelto (con `after` posiblemente editado) al canon.

    Devuelve Ok(descripción_breve) o Error. Solo debe llamarse por acción humana
    explícita (botón «Aplicar seleccionados»). Usa los servicios de aplicación,
    nunca persistencia directa.
    """
    ch = dict(resolved.get("_change") or {})
    ct = ch.get("change_type")
    after = _s(resolved.get("after"))
    text_field = resolved.get("text_field") or ""

    if ct == "edit_entity":
        if entity_service is None:
            return Error("EntityService no disponible")
        ent = _find_entity(project, ch["entity_name"])
        if ent is None:
            return Error(f"No se encontró la entidad «{ch['entity_name']}».")
        dom = "extended_description" if ch["field"] == "body" else "brief_description"
        res = entity_service.update_entity(ent.id, {dom: after})
        return Ok(f"Editada «{ent.name}»") if not isinstance(res, Error) else res

    if ct in ("edit_relation", "create_relation"):
        if relation_service is None:
            return Error("RelationService no disponible")
        src = _find_entity(project, ch["source_name"])
        tgt = _find_entity(project, ch["target_name"])
        if src is None or tgt is None:
            return Error("Faltan entidades para la relación.")
        rel = _find_relation(project, src.id, tgt.id)
        # El texto editado (`after`) reemplaza el campo narrativo principal.
        desc = after if text_field == "description" else ch["description"]
        body = after if text_field == "body" else ch["body"]
        if rel is not None:  # edit
            updates: dict[str, Any] = {}
            if ch["relation_type"]:
                updates["relation_type"] = _coerce_relation_type(ch["relation_type"])
            if desc:
                updates["description"] = desc
            if body:
                meta = dict(getattr(rel, "custom_metadata", {}) or {})
                meta["_body"] = body
                updates["custom_metadata"] = meta
            if not updates:
                return Error("La reparación de relación no propone cambios.")
            res = relation_service.update_relation(rel.id, updates)
            return Ok(f"Relación {src.name} → {tgt.name}") if not isinstance(res, Error) else res
        data: dict[str, Any] = {"description": desc}
        if body:
            data["custom_metadata"] = {"_body": body}
        res = relation_service.create_relation(
            source_id=src.id, target_id=tgt.id,
            relation_type=_coerce_relation_type(ch["relation_type"] or "esta_relacionado_con"),
            data=data,
        )
        return Ok(f"Relación {src.name} → {tgt.name}") if not isinstance(res, Error) else res

    if ct == "create_entity":
        if entity_service is None:
            return Error("EntityService no disponible")
        brief = after if text_field == "brief_description" else ch["brief_description"]
        body = after if text_field == "body" else ch["body"]
        res = entity_service.create_entity({
            "name": ch["name"], "entity_type": ch["entity_type"],
            "brief_description": brief, "extended_description": body,
        })
        return Ok(f"Creada «{ch['name']}»") if not isinstance(res, Error) else res

    if ct == "create_milestone":
        hito = CausalMilestone.from_dict({
            "title": ch["title"], "description": ch["summary"] or after,
        })
        if hasattr(project, "causal_milestones"):
            project.causal_milestones.append(hito)
            if hasattr(project, "touch"):
                project.touch()
            return Ok(f"Hito «{ch['title']}»")
        return Error("El proyecto no admite hitos.")

    return Error(f"Tipo de cambio no soportado: {ct}")
