"""I27 — Fase REDUCE: reconciliación global de menciones → ``ImportGraph``.

Segunda pasada del rediseño map→reduce. Toma las MENCIONES crudas del MAP (I26),
fragmentadas entre ventanas, y produce un grafo de candidatos COHERENTE con
identidad estable:

- **Blocking determinista**: agrupa menciones de la misma entidad/rama
  reutilizando ``_norm``/``_similarity`` del servicio de deduplicación (sin
  duplicar lógica). Es el camino base y funciona SIN IA.
- **Árbitro IA (opcional, intent ``import_reconcile``)**: para los clústeres en
  la zona gris de similitud, una única llamada decide qué nombres son la misma
  entidad. Degrada con elegancia: sin proveedor o ante fallo, se queda en
  blocking determinista (nunca falla en silencio).

Asigna IDs provisionales estables (``imp_e_*`` hojas, ``imp_b_*`` ramas,
``imp_r_*`` relaciones) y **reescribe las relaciones a esos IDs** — adiós a la
resolución frágil por nombre. Las incidencias (menciones ``issue`` y relaciones
sin extremo resoluble) se conservan en ``graph.metadata['issues']``.
"""

from __future__ import annotations

import json
from typing import Any

from packages.application.ai_request_gateway import AIRequestGateway, GatewayRequest
from packages.application.import_dating import apply_dating
from packages.application.import_deduplication_service import _norm, _similarity
from packages.application.prompt_registry import get_prompt
from packages.domain.import_models import (
    ConsolidatedEntity,
    ConsolidatedRelation,
    ImportGraph,
    RelevanceTier,
)
from packages.domain.result import Ok, Result
from packages.infrastructure.ai_provider import AIProvider

RECONCILE_INTENT = "import_reconcile"
GROUPING_INTENT = "import_grouping"

# Umbrales de clustering determinista.
MERGE_THRESHOLD = 0.86      # >= : misma entidad, se fusiona sin preguntar.
AMBIGUOUS_LOW = 0.62        # [low, merge): zona gris → la decide el árbitro IA.

# I30 — Relevancia en dos niveles. Único umbral (configurable por parámetro): un
# candidato con relevance >= este valor es FUERTE (primer plano); por debajo es
# MARGINAL (sección plegable). Nada se descarta — ambos niveles viven en el grafo.
RELEVANCE_STRONG_THRESHOLD = 0.6


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _names_of(mention: dict[str, Any]) -> set[str]:
    """Nombres normalizados de una mención node (name + aliases)."""
    names = {_norm(mention.get("name"))}
    for alias in mention.get("aliases", []) or []:
        n = _norm(alias)
        if n:
            names.add(n)
    return {n for n in names if n}


def _best_cluster_score(mention: dict[str, Any], cluster: dict[str, Any]) -> float:
    """Similitud máxima entre los nombres de una mención y los de un clúster."""
    best = 0.0
    for mname in _names_of(mention) or {_norm(mention.get("name"))}:
        for cname in cluster["names"]:
            best = max(best, _similarity(mname, cname))
    return best


def _cluster_nodes(
    nodes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[tuple[int, int]]]:
    """Agrupa menciones entity/branch en clústeres (greedy por similitud de nombre).

    Devuelve (clusters, ambiguous_pairs). Cada clúster es
    ``{"mentions": [...], "names": set[str]}``. ``ambiguous_pairs`` son pares de
    índices de clúster cuya similitud cae en la zona gris [AMBIGUOUS_LOW,
    MERGE_THRESHOLD) — candidatos a que el árbitro IA decida fusionar.
    """
    clusters: list[dict[str, Any]] = []
    for node in nodes:
        best_i, best_score = None, 0.0
        for i, cluster in enumerate(clusters):
            score = _best_cluster_score(node, cluster)
            if score > best_score:
                best_score, best_i = score, i
        if best_i is not None and best_score >= MERGE_THRESHOLD:
            clusters[best_i]["mentions"].append(node)
            clusters[best_i]["names"] |= _names_of(node)
        else:
            clusters.append({"mentions": [node], "names": _names_of(node)})

    ambiguous: list[tuple[int, int]] = []
    for i in range(len(clusters)):
        for j in range(i + 1, len(clusters)):
            score = max(
                (_similarity(a, b) for a in clusters[i]["names"] for b in clusters[j]["names"]),
                default=0.0,
            )
            if AMBIGUOUS_LOW <= score < MERGE_THRESHOLD:
                ambiguous.append((i, j))
    return clusters, ambiguous


def _most_common_nonempty(values: list[str]) -> str:
    counts: dict[str, int] = {}
    for v in values:
        v = _text(v)
        if v:
            counts[v] = counts.get(v, 0) + 1
    if not counts:
        return ""
    # Más frecuente; empate → el más largo (más específico).
    return sorted(counts, key=lambda k: (counts[k], len(k)), reverse=True)[0]


def _first_nonnull(values: list[Any]) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


def _build_consolidated_entity(
    cluster: dict[str, Any], provisional_id: str
) -> ConsolidatedEntity:
    """Funde las menciones de un clúster en una ``ConsolidatedEntity`` única."""
    mentions = cluster["mentions"]
    kind = "branch" if any(m.get("kind") == "branch" for m in mentions) else "entity"
    names = [_text(m.get("name")) for m in mentions if _text(m.get("name"))]
    canonical = _most_common_nonempty(names) or (names[0] if names else "")

    aliases: list[str] = []
    seen = {_norm(canonical)}
    for m in mentions:
        for cand in [_text(m.get("name"))] + [_text(a) for a in m.get("aliases", []) or []]:
            if cand and _norm(cand) not in seen:
                aliases.append(cand)
                seen.add(_norm(cand))

    bodies = [_text(m.get("body")) for m in mentions if _text(m.get("body"))]
    body = max(bodies, key=len) if bodies else ""
    summaries = [_text(m.get("summary")) for m in mentions if _text(m.get("summary"))]

    layer_ids: list[str] = []
    for m in mentions:
        for lid in m.get("layer_ids", []) or []:
            if _text(lid) and lid not in layer_ids:
                layer_ids.append(lid)

    source_refs: list[dict] = []
    mention_ids: list[str] = []
    for m in mentions:
        mention_ids.append(_text(m.get("local_id")))
        for ref in m.get("source_references", []) or []:
            if isinstance(ref, dict):
                source_refs.append(ref)

    return ConsolidatedEntity(
        provisional_id=provisional_id,
        kind=kind,
        name=canonical,
        aliases=aliases,
        entity_type=_most_common_nonempty([_text(m.get("entity_type")) for m in mentions]),
        branch_type=_most_common_nonempty([_text(m.get("branch_type")) for m in mentions]),
        summary=summaries[0] if summaries else "",
        body=body,
        evidence=_most_common_nonempty([_text(m.get("evidence")) for m in mentions]),
        source_references=source_refs,
        birth_year=_first_nonnull([m.get("birth_year") for m in mentions]),
        death_year=_first_nonnull([m.get("death_year") for m in mentions]),
        temporal_nature=_most_common_nonempty([_text(m.get("temporal_nature")) for m in mentions]),
        layer_ids=layer_ids,
        mention_ids=[mid for mid in mention_ids if mid],
        relevance=max((float(m.get("relevance", 0.0) or 0.0) for m in mentions), default=0.0),
        confidence=max((float(m.get("confidence", 0.0) or 0.0) for m in mentions), default=0.0),
    )


# ---------------------------------------------------------------------------
# Árbitro IA (opcional)
# ---------------------------------------------------------------------------


def _arbiter_merge_groups(
    provider: AIProvider,
    clusters: list[dict[str, Any]],
    ambiguous: list[tuple[int, int]],
    project_context: dict[str, Any],
) -> list[set[int]]:
    """Pregunta al árbitro qué clústeres ambiguos son la misma entidad.

    Devuelve grupos de índices de clúster a fusionar. Degradación segura: ante
    cualquier fallo (sin proveedor real, JSON inválido) devuelve [] (blocking).
    """
    involved = sorted({i for pair in ambiguous for i in pair})
    if not involved:
        return []
    catalog = []
    for i in involved:
        cluster = clusters[i]
        name = _most_common_nonempty([_text(m.get("name")) for m in cluster["mentions"]])
        summary = next((_text(m.get("summary")) for m in cluster["mentions"]
                        if _text(m.get("summary"))), "")
        catalog.append({"id": i, "name": name, "summary": summary})

    system = (
        "Eres el árbitro de reconciliación de importación de Dendro (fase REDUCE).\n"
        "Recibes candidatos que PODRÍAN ser la misma entidad (nombres parecidos).\n"
        "Decide qué 'id' se refieren a la MISMA entidad del mundo. Devuelve SOLO JSON:\n"
        '{"merges": [[id, id, ...], ...]}\n'
        "Cada grupo lista los id que son el mismo. No agrupes lo que claramente difiere. "
        "Si ninguno coincide, devuelve merges vacío."
    )
    request = GatewayRequest(
        intent=RECONCILE_INTENT,
        user_prompt=json.dumps({"candidates": catalog}, ensure_ascii=False, default=str),
        context={"project_name": project_context.get("project_name", "")},
        system_prompt_override=system,
        json_mode=True,
        validate=True,
    )
    response = AIRequestGateway(provider=provider).execute(request)
    if response.error:
        return []
    parsed = response.parsed_json
    raw_groups = parsed.get("merges") if isinstance(parsed, dict) else None
    if not isinstance(raw_groups, list):
        return []
    valid = set(involved)
    groups: list[set[int]] = []
    for group in raw_groups:
        if not isinstance(group, list):
            continue
        ids = {int(x) for x in group if isinstance(x, (int, float)) and int(x) in valid}
        if len(ids) >= 2:
            groups.append(ids)
    return groups


def _apply_merges(
    clusters: list[dict[str, Any]], groups: list[set[int]]
) -> list[dict[str, Any]]:
    """Fusiona clústeres según los grupos de índices del árbitro (union-find simple)."""
    if not groups:
        return clusters
    parent = list(range(len(clusters)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for group in groups:
        members = sorted(group)
        for other in members[1:]:
            parent[find(other)] = find(members[0])

    merged: dict[int, dict[str, Any]] = {}
    for i, cluster in enumerate(clusters):
        root = find(i)
        if root not in merged:
            merged[root] = {"mentions": [], "names": set()}
        merged[root]["mentions"].extend(cluster["mentions"])
        merged[root]["names"] |= cluster["names"]
    return list(merged.values())


# ---------------------------------------------------------------------------
# Relevancia en dos niveles (I30)
# ---------------------------------------------------------------------------


def apply_relevance_tiers(
    graph: ImportGraph, *, threshold: float = RELEVANCE_STRONG_THRESHOLD
) -> ImportGraph:
    """Asigna ``RelevanceTier`` (fuerte/marginal) por umbral, in place.

    No descarta nada: solo etiqueta para que el asistente (I31) presente los
    candidatos fuertes en primer plano y los marginales en sección plegable.
    """
    strong = RelevanceTier.FUERTE
    weak = RelevanceTier.MARGINAL
    for entity in graph.entities:
        entity.relevance_tier = strong if entity.relevance >= threshold else weak
    for relation in graph.relations:
        relation.relevance_tier = strong if relation.relevance >= threshold else weak
    return graph


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def _resolve_endpoint(name: str, name_to_pid: dict[str, str]) -> str | None:
    """Resuelve un nombre de extremo de relación a un id provisional.

    Exacto por nombre normalizado; si no, mejor coincidencia por similitud >=
    ``MERGE_THRESHOLD`` (tolera variantes menores). None si nada resuelve.
    """
    norm = _norm(name)
    if not norm:
        return None
    if norm in name_to_pid:
        return name_to_pid[norm]
    best_pid, best_score = None, 0.0
    for cand_norm, pid in name_to_pid.items():
        score = _similarity(norm, cand_norm)
        if score > best_score:
            best_score, best_pid = score, pid
    return best_pid if best_score >= MERGE_THRESHOLD else None


def reconcile_mentions(
    mentions: list[dict[str, Any]],
    *,
    provider: AIProvider | None = None,
    project_context: dict[str, Any] | None = None,
) -> Result[ImportGraph, str]:
    """Consolida las menciones del MAP en un ``ImportGraph`` coherente (fase REDUCE).

    Determinista por defecto; usa el árbitro IA solo si se pasa ``provider`` y hay
    clústeres ambiguos. Nunca lanza: siempre devuelve ``Ok(ImportGraph)``.
    """
    mentions = list(mentions or [])
    nodes = [m for m in mentions if m.get("kind") in ("entity", "branch")]
    relations = [m for m in mentions if m.get("kind") == "relation"]
    issues = [dict(m) for m in mentions if m.get("kind") == "issue"]

    clusters, ambiguous = _cluster_nodes(nodes)
    if provider is not None and ambiguous:
        groups = _arbiter_merge_groups(provider, clusters, ambiguous, project_context or {})
        clusters = _apply_merges(clusters, groups)

    entities: list[ConsolidatedEntity] = []
    name_to_pid: dict[str, str] = {}
    e_counter = b_counter = 0
    for cluster in clusters:
        is_branch = any(m.get("kind") == "branch" for m in cluster["mentions"])
        if is_branch:
            b_counter += 1
            pid = f"imp_b_{b_counter:04d}"
        else:
            e_counter += 1
            pid = f"imp_e_{e_counter:04d}"
        entity = _build_consolidated_entity(cluster, pid)
        entities.append(entity)
        for norm_name in cluster["names"]:
            name_to_pid.setdefault(norm_name, pid)

    cons_relations: list[ConsolidatedRelation] = []
    r_counter = 0
    for rel in relations:
        source_pid = _resolve_endpoint(_text(rel.get("source_name")), name_to_pid)
        target_pid = _resolve_endpoint(_text(rel.get("target_name")), name_to_pid)
        if not source_pid or not target_pid:
            issues.append({
                "local_id": _text(rel.get("local_id")),
                "kind": "issue",
                "message": (
                    "Relación sin extremo resoluble en el grafo: "
                    f"{_text(rel.get('source_name'))} → {_text(rel.get('target_name'))}."
                ),
                "source_references": rel.get("source_references", []),
            })
            continue
        r_counter += 1
        cons_relations.append(ConsolidatedRelation(
            provisional_id=f"imp_r_{r_counter:04d}",
            source_provisional_id=source_pid,
            target_provisional_id=target_pid,
            relation_type=_text(rel.get("relation_type")) or "otro",
            summary=_text(rel.get("summary")),
            evidence=_text(rel.get("evidence")),
            mention_ids=[_text(rel.get("local_id"))] if rel.get("local_id") else [],
            relevance=float(rel.get("relevance", 0.0) or 0.0),
            confidence=float(rel.get("confidence", 0.0) or 0.0),
        ))

    graph = ImportGraph(
        entities=entities,
        relations=cons_relations,
        raw_mentions=mentions,
        metadata={
            "reconciled": True,
            "node_mentions": len(nodes),
            "entity_count": len(entities),
            "relation_count": len(cons_relations),
            "issues": issues,
            "arbiter_used": bool(provider is not None and ambiguous),
            "relevance_threshold": RELEVANCE_STRONG_THRESHOLD,
        },
    )
    apply_relevance_tiers(graph)  # I30: etiqueta fuerte/marginal sin descartar nada
    # I29: data y valida contra las eras del proyecto (no bloquea; solo etiqueta).
    apply_dating(graph, chronology=(project_context or {}).get("chronology_applied"))
    return Ok(graph)


# ---------------------------------------------------------------------------
# Fase STRUCTURE (I28) — agrupación en ramas sobre el grafo consolidado
# ---------------------------------------------------------------------------


def _next_branch_index(graph: ImportGraph) -> int:
    """Siguiente índice libre para un id provisional ``imp_b_NNNN``."""
    max_n = 0
    for entity in graph.entities:
        pid = entity.provisional_id
        if pid.startswith("imp_b_"):
            try:
                max_n = max(max_n, int(pid[len("imp_b_"):]))
            except ValueError:
                pass
    return max_n + 1


def propose_structure(
    graph: ImportGraph,
    *,
    provider: AIProvider | None = None,
    project_context: dict[str, Any] | None = None,
) -> ImportGraph:
    """Propone ramas (contenedores) sobre el grafo YA consolidado (fase STRUCTURE).

    Opera sobre los IDs provisionales del grafo, no sobre nombres crudos. Reusa el
    intent ``import_grouping`` (la IA referencia nombres; se resuelven a IDs).

    **Garantías duras** (en código, no confiadas a la IA):
    - *Sin huérfanas*: nunca se elimina una entidad; las hojas no agrupadas siguen
      a nivel raíz del grafo.
    - *Sin ramas vacías*: una rama propuesta que no resuelve ningún miembro se
      descarta; nunca entra al grafo sin ``member_ids``.

    Degrada con elegancia: sin proveedor o ante fallo, devuelve el grafo intacto.
    """
    if provider is None or not graph.entities:
        return graph

    catalog = [
        {"name": e.name, "kind": e.kind,
         "summary": e.summary or (e.body[:120] if e.body else "")}
        for e in graph.entities if e.name
    ]
    world_layers = (project_context or {}).get("world_layers") or []
    lang = (project_context or {}).get("language") or "es"
    system = get_prompt(GROUPING_INTENT, lang) or ""

    request = GatewayRequest(
        intent=GROUPING_INTENT,
        user_prompt=json.dumps(
            {"task": "group_entities_into_branches", "entities": catalog,
             "world_layers": world_layers},
            ensure_ascii=False, default=str,
        ),
        context={"project_name": (project_context or {}).get("project_name", "")},
        system_prompt_override=system,
        json_mode=True,
        validate=True,
    )
    response = AIRequestGateway(provider=provider).execute(request)
    if response.error:
        return graph
    parsed = response.parsed_json
    branches = parsed.get("branches") if isinstance(parsed, dict) else None
    if not isinstance(branches, list):
        return graph

    # name → pid de las entidades actuales (nombre canónico + alias).
    name_to_pid: dict[str, str] = {}
    for e in graph.entities:
        for nm in [e.name, *e.aliases]:
            if _norm(nm):
                name_to_pid.setdefault(_norm(nm), e.provisional_id)
    pid_to_entity = {e.provisional_id: e for e in graph.entities}

    next_idx = _next_branch_index(graph)
    proposed_parent: list[tuple[str, str]] = []  # (child_branch_pid, parent_name)
    created = 0

    for raw in branches:
        if not isinstance(raw, dict):
            continue
        bname = _text(raw.get("name"))
        if not bname:
            continue
        member_names = raw.get("members") if isinstance(raw.get("members"), list) else []
        member_pids: list[str] = []
        for mname in member_names:
            pid = _resolve_endpoint(_text(mname), name_to_pid)
            if pid and pid not in member_pids:
                member_pids.append(pid)

        # ¿La rama propuesta ya existe como entidad/rama del grafo?
        existing_pid = _resolve_endpoint(bname, name_to_pid)
        branch_entity = pid_to_entity.get(existing_pid) if existing_pid else None
        if branch_entity is not None and branch_entity.is_branch:
            # Reusar rama existente: añade miembros (excluyéndose a sí misma).
            for pid in member_pids:
                if pid != branch_entity.provisional_id and pid not in branch_entity.member_ids:
                    branch_entity.member_ids.append(pid)
        else:
            # Sin miembros resolubles → NO crear rama vacía.
            if not member_pids:
                continue
            pid = f"imp_b_{next_idx:04d}"
            next_idx += 1
            branch_entity = ConsolidatedEntity(
                provisional_id=pid,
                kind="branch",
                name=bname,
                branch_type=_text(raw.get("branch_type")) or "contenedor",
                body=_text(raw.get("body")),
                layer_ids=[_text(x) for x in (raw.get("layer_ids") or []) if _text(x)],
                member_ids=[p for p in member_pids if p != pid],
                relevance=0.7,
                relevance_tier=RelevanceTier.FUERTE,
                confidence=0.6,
            )
            graph.entities.append(branch_entity)
            pid_to_entity[pid] = branch_entity
            name_to_pid.setdefault(_norm(bname), pid)
            created += 1

        parent_name = _text(raw.get("parent"))
        if parent_name and parent_name.lower() not in ("null", "none"):
            proposed_parent.append((branch_entity.provisional_id, parent_name))

    # Anidamiento de ramas: añade cada rama-hija como miembro de su rama-padre.
    for child_pid, parent_name in proposed_parent:
        parent_pid = _resolve_endpoint(parent_name, name_to_pid)
        parent = pid_to_entity.get(parent_pid) if parent_pid else None
        if parent is not None and parent.is_branch and parent.provisional_id != child_pid:
            if child_pid not in parent.member_ids:
                parent.member_ids.append(child_pid)

    graph.metadata["structure_applied"] = True
    graph.metadata["branches_created"] = created
    return graph
