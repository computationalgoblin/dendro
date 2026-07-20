"""Navegación por anillos del Modo Foco (BETA2-FOCO-25, ronda 3).

Reorienta el vecindario del centro alrededor de la POSICIÓN DE ANILLO (rango
causal de capa) en vez de la semántica causal de tipo de relación:

- relacionadas en anillos SUPERIORES (menor rango) ⇒ Raíces (arriba);
- relacionadas en anillos INFERIORES (mayor rango) ⇒ Brotes (abajo);
- relacionadas del MISMO anillo ⇒ Entorno (a la derecha);
- compañeras de la rama directa del centro ⇒ extensión de la rama a la derecha.

El tipo de relación deja de decidir la zona (lo sigue haciendo
``foco_zones.classify_neighbors`` para el contexto de riego), pero se conserva
como rótulo del conector en la UI.

Módulo PURO (stdlib + dominio + ``world_layer_causal``): no importa Qt ni la
capa ``ui`` (``packages/ui/graph_physics`` queda vetado por límites de módulos),
así que el anillo efectivo se calcula aquí desde el dominio.

El RANGO efectivo de un anillo es su POSICIÓN en el orden de anillos del Mapa:
``causal_rank`` propio, o el de la capa por defecto homónima cuando el proyecto
no lo persistió (mismo criterio que ``_effective_world_layers`` del Mapa), y
las capas sin rango van después ordenadas por ``order``. Así TODA capa es
comparable y la navegación coincide con lo que el usuario ve en el Mapa.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.application.foco_zones import is_ghost_entity
from packages.application.world_layer_causal import get_causal_rank
from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.entity_taxonomy import is_branch
from packages.domain.project import Project
from packages.domain.relation import RelationType
from packages.domain.world_layer import WorldLayer, default_world_layers

# Estados de canon que no participan del jardín activo (mismo criterio que foco_zones).
_EXCLUDED_CANON = frozenset({CanonState.ARCHIVADO, CanonState.DESCARTADO})

# Anillo de las entidades sin capa clasificable.
UNCLASSIFIED_RING_ID = "__unclassified__"


@dataclass(frozen=True)
class RingNeighbor:
    """Vecina clasificada por su anillo relativo al centro.

    ``relation_id`` vacío = no llega por relación directa (p. ej. compañera de
    rama). ``rank`` None = anillo sin rango causal comparable.
    """

    entity_id: str
    relation_id: str
    ring_id: str
    rank: int | None
    is_ghost: bool


@dataclass(frozen=True)
class RingNavigation:
    """Destinos de navegación precomputados para el centro (ids, o "" si no hay)."""

    prev: str = ""  # ← anterior en el anillo actual (cíclico)
    next: str = ""  # → siguiente en el anillo actual (cíclico)
    up: str = ""  # Shift+↑ relacionada del anillo más cercano superior / adyacente
    down: str = ""  # Shift+↓ simétrico hacia abajo
    container: str = ""  # ↑ la rama contenedora directa del centro
    member: str = ""  # ↓ primera entidad contenida (cuando el centro es rama)


def effective_rank_map(layers: list[WorldLayer]) -> dict[str, int]:
    """Posición 1-based de cada capa en el orden de anillos del Mapa.

    ``causal_rank`` propio, o el de la capa por defecto homónima si el proyecto
    no lo persistió (mismo merge que ``_effective_world_layers`` del Mapa);
    las capas sin rango van después, ordenadas por ``order`` y nombre. El
    resultado hace TODA capa comparable (anillo superior = posición menor).
    """
    defaults_by_id = {layer.id: layer for layer in default_world_layers()}

    def _merged_rank(layer: WorldLayer) -> int | None:
        rank = get_causal_rank(layer)
        if rank is None:
            default = defaults_by_id.get(str(getattr(layer, "id", "")))
            if default is not None:
                rank = get_causal_rank(default)
        return rank

    def _key(layer: WorldLayer) -> tuple[int, int, str]:
        rank = _merged_rank(layer)
        if rank is None:
            return (1, int(getattr(layer, "order", 0) or 0), str(layer.name).casefold())
        return (0, rank, str(layer.name).casefold())

    ordered = sorted(layers, key=_key)
    return {str(layer.id): index + 1 for index, layer in enumerate(ordered)}


@dataclass
class _RingResolver:
    """Resuelve el anillo efectivo de una entidad con caché e herencia de rama."""

    project: Project
    rank_by_layer: dict[str, int]
    _cache: dict[str, tuple[str, int | None]] = field(default_factory=dict)

    def ring(self, entity_id: str, _guard: frozenset[str] = frozenset()) -> tuple[str, int | None]:
        cached = self._cache.get(entity_id)
        if cached is not None:
            return cached
        entity = self.project.entity_by_id(entity_id)
        result = self._resolve(entity, _guard | {entity_id})
        self._cache[entity_id] = result
        return result

    def _resolve(
        self, entity: NarrativeEntity | None, guard: frozenset[str]
    ) -> tuple[str, int | None]:
        if entity is None:
            return (UNCLASSIFIED_RING_ID, None)
        # 1) Primera capa propia conocida: su posición en el orden de anillos.
        for layer_id in entity.layer_ids or []:
            rank = self.rank_by_layer.get(layer_id)
            if rank is not None:
                return (layer_id, rank)
        # 2) Sin capa propia ⇒ hereda el anillo de la rama contenedora directa.
        container_id = _immediate_container(self.project, entity.id)
        if container_id and container_id not in guard:
            return self.ring(container_id, guard)
        # 3) Sin clasificar ⇒ anillo EXTERIOR comparable (como en el Mapa, donde
        #    "__unclassified__" es el anillo más externo). Así las entidades sin
        #    capa participan de Raíces/Brotes y del salto Shift+↑/↓.
        return (UNCLASSIFIED_RING_ID, len(self.rank_by_layer) + 1)


def _resolver(project: Project) -> _RingResolver:
    return _RingResolver(project, effective_rank_map(list(project.world_layers or [])))


def ring_display_info(project: Project, entity_id: str) -> tuple[str, int, int]:
    """(nombre del anillo, posición 1-based, total de anillos) del centro.

    Para la píldora del Foco (FOCO-26). El anillo no clasificado se presenta
    como «Sin anillo» en la posición exterior (total + 1 no se suma: se informa
    la posición dentro del total de capas + 1 exterior).
    """
    resolver = _resolver(project)
    ring_id, rank = resolver.ring(entity_id)
    total = len(resolver.rank_by_layer)
    if ring_id == UNCLASSIFIED_RING_ID or rank is None:
        return ("Sin anillo", total + 1, total + 1)
    for layer in project.world_layers or []:
        if str(layer.id) == ring_id:
            return (str(layer.name or ring_id), rank, total + 1)
    return (ring_id, rank, total + 1)


def ring_id_for(project: Project, entity_id: str) -> str | None:
    """BETA2-CLEANUP-PANELES: id del anillo (world layer) efectivo del centro, o
    ``None`` si la entidad no pertenece a ningún anillo real («Sin anillo»).

    Se usa para abrir el panel de anillo desde el banner del Foco (edición). No
    devuelve el sentinel ``UNCLASSIFIED_RING_ID`` (no es un anillo editable)."""
    if not entity_id:
        return None
    ring_id, _rank = _resolver(project).ring(entity_id)
    if not ring_id or ring_id == UNCLASSIFIED_RING_ID:
        return None
    return str(ring_id)


def direct_containments(project: Project, entity_id: str) -> list[tuple[str, str]]:
    """[(container_id, relation_id)] de las contenciones DIRECTAS, orden por nombre.

    Contención = ``CONTIENE`` con la rama como origen, o ``PERTENECE_A`` con la
    entidad como origen. Lo usa el asistente de contención (FOCO-26) para
    detectar que la entidad ya vive en otra rama.
    """
    found: dict[str, str] = {}
    for relation in project.relations_for(entity_id):
        container_id = ""
        if relation.relation_type == RelationType.CONTIENE and relation.target_id == entity_id:
            container_id = relation.source_id
        elif relation.relation_type == RelationType.PERTENECE_A and relation.source_id == entity_id:
            container_id = relation.target_id
        if not container_id or container_id == entity_id:
            continue
        container = project.entity_by_id(container_id)
        if container is None or container.canon_state in _EXCLUDED_CANON:
            continue
        found.setdefault(container_id, relation.id)

    def _name_key(item: tuple[str, str]) -> tuple[str, str]:
        entity = project.entity_by_id(item[0])
        return ((entity.name if entity else "").casefold(), item[0])

    return sorted(found.items(), key=_name_key)


def _immediate_container(project: Project, entity_id: str) -> str:
    """Id de la rama que contiene directamente a ``entity_id`` (o "")."""
    containments = direct_containments(project, entity_id)
    return containments[0][0] if containments else ""


def _branch_member_ids(project: Project, container_id: str) -> list[str]:
    """Ids de los miembros directos de la rama ``container_id`` (target de CONTIENE)."""
    members: list[str] = []
    for relation in project.relations_for(container_id):
        member_id = ""
        if relation.relation_type == RelationType.CONTIENE and relation.source_id == container_id:
            member_id = relation.target_id
        elif (
            relation.relation_type == RelationType.PERTENECE_A
            and relation.target_id == container_id
        ):
            member_id = relation.source_id
        if member_id and member_id != container_id:
            members.append(member_id)
    return members


def branch_members(project: Project, container_id: str) -> list[str]:
    """FOCO-30: ids de los contenidos directos vivos de una rama, orden por nombre.

    Para la estantería de miniaturas de la tarjeta central: filtra canon excluido y
    ordena por nombre (desempate por id) para una lectura estable.
    """
    ids: list[str] = []
    for member_id in _branch_member_ids(project, container_id):
        member = project.entity_by_id(member_id)
        if member is None or member.canon_state in _EXCLUDED_CANON:
            continue
        ids.append(member_id)

    def _name_key(eid: str) -> tuple[str, str]:
        entity = project.entity_by_id(eid)
        return ((entity.name if entity else "").casefold(), eid)

    return sorted(dict.fromkeys(ids), key=_name_key)


def contained_descendant_ids(project: Project, container_id: str) -> list[str]:
    """BETA2-STRUCT-06: cierre transitivo DESCENDENTE de la contención de una rama.

    Ids de TODO el contenido de ``container_id`` (miembros y sub-miembros, todos
    los niveles), en orden DFS estable, sin el propio contenedor y con guard de
    ciclos. Es la primitiva de application que usa la aceptación ``branch_move``
    para mover una rama CON su contenido (este cierre vivía solo en la UI:
    ``workspaces._contained_descendant_ids``).
    """
    ordered: list[str] = []
    seen: set[str] = {container_id}

    def _visit(current: str) -> None:
        for member_id in _branch_member_ids(project, current):
            if not member_id or member_id in seen:
                continue
            seen.add(member_id)
            ordered.append(member_id)
            _visit(member_id)

    _visit(container_id)
    return ordered


def _containment_related(project: Project, entity_id: str) -> set[str]:
    """Cierre transitivo de la contención alrededor de ``entity_id``.

    Reúne TODAS las ramas que la contienen (subiendo por co-padres y niveles) y
    TODOS sus contenidos (bajando por miembros y sub-miembros). No incluye
    ``entity_id``. Con guard de ciclos (una contención mal formada no cuelga).

    Sirve para EXCLUIR de la rotación del anillo (FOCO-31) tanto los ancestros
    (se alcanzan con ↑) como los descendientes de la entidad enfocada (se alcanzan
    con ↓/estantería): la rotación son iguales del anillo, sin jerarquía.
    """
    related: set[str] = set()

    # Ancestros: todos los contenedores, en todos los niveles y co-padres.
    stack = [cid for cid, _ in direct_containments(project, entity_id)]
    while stack:
        current = stack.pop()
        if current == entity_id or current in related:
            continue
        related.add(current)
        stack.extend(cid for cid, _ in direct_containments(project, current))

    # Descendientes: todos los miembros, en todos los niveles.
    stack = list(_branch_member_ids(project, entity_id))
    while stack:
        current = stack.pop()
        if current == entity_id or current in related:
            continue
        related.add(current)
        stack.extend(_branch_member_ids(project, current))

    return related


def _empty_zones() -> dict[str, list[RingNeighbor]]:
    return {"raices": [], "entorno": [], "brotes": [], "branch_mates": []}


def classify_ring_neighbors(project: Project, entity_id: str) -> dict[str, list[RingNeighbor]]:
    """Clasifica a las vecinas directas del centro por su anillo relativo.

    Devuelve siempre las claves ``raices``/``entorno``/``brotes``/``branch_mates``.
    ``raices`` va ordenada del anillo MÁS superior al más cercano (rango asc);
    ``brotes`` del más cercano al más inferior (rango asc); dentro de cada anillo,
    por nombre (y a igualdad, id). Las compañeras de rama se excluyen de las
    otras zonas para no duplicarse.
    """
    zones = _empty_zones()
    center = project.entity_by_id(entity_id)
    if center is None:
        return zones

    resolver = _resolver(project)
    center_ring_id, center_rank = resolver.ring(entity_id)

    # Compañeras de rama (extensión derecha): miembros de la rama directa del centro.
    container_id = _immediate_container(project, entity_id)
    branch_ids: set[str] = set()
    if container_id:
        for member_id in _branch_member_ids(project, container_id):
            if member_id == entity_id:
                continue
            member = project.entity_by_id(member_id)
            if member is None or member.canon_state in _EXCLUDED_CANON:
                continue
            branch_ids.add(member_id)

    # Vecinas por relación directa, con su primera relación (para el rótulo).
    neighbor_relation: dict[str, str] = {}
    for relation in project.relations_for(entity_id):
        # FOCO-30: la contención NO se dibuja en las bandas — la rama enfocada
        # muestra sus contenidos como estantería en la tarjeta, y la contenedora
        # como marco envolvente. Así "Contiene/Pertenece a" deja el banner derecho.
        if relation.relation_type in (RelationType.CONTIENE, RelationType.PERTENECE_A):
            continue
        other_id = relation.target_id if relation.source_id == entity_id else relation.source_id
        if other_id == entity_id:
            continue
        other = project.entity_by_id(other_id)
        if other is None or other.canon_state in _EXCLUDED_CANON:
            continue
        neighbor_relation.setdefault(other_id, relation.id)

    def _make(other_id: str, relation_id: str) -> RingNeighbor:
        ring_id, rank = resolver.ring(other_id)
        return RingNeighbor(
            other_id, relation_id, ring_id, rank, is_ghost_entity(project.entity_by_id(other_id))
        )

    for other_id, relation_id in neighbor_relation.items():
        if other_id in branch_ids or other_id == container_id:
            continue  # la rama y sus miembros se dibujan aparte (marco + extensión).
        neighbor = _make(other_id, relation_id)
        if center_rank is not None and neighbor.rank is not None:
            if neighbor.rank < center_rank:
                zones["raices"].append(neighbor)
                continue
            if neighbor.rank > center_rank:
                zones["brotes"].append(neighbor)
                continue
        # Mismo anillo, o rango no comparable ⇒ Entorno (derecha).
        zones["entorno"].append(neighbor)

    for member_id in sorted(branch_ids):
        zones["branch_mates"].append(_make(member_id, ""))

    def _name_key(neighbor: RingNeighbor) -> tuple[str, str]:
        entity = project.entity_by_id(neighbor.entity_id)
        return ((entity.name if entity else "").casefold(), neighbor.entity_id)

    # Raíces: más superior (menor rango) arriba. Brotes: más cercano (menor rango) primero.
    zones["raices"].sort(key=lambda n: (n.rank if n.rank is not None else 0, *_name_key(n)))
    zones["brotes"].sort(key=lambda n: (n.rank if n.rank is not None else 0, *_name_key(n)))
    zones["entorno"].sort(key=_name_key)
    zones["branch_mates"].sort(key=_name_key)
    return zones


def _ring_members(
    project: Project, resolver: _RingResolver, ring_id: str, center_id: str
) -> list[str]:
    """Ids de las entidades del anillo ``ring_id``, orden POR CONEXIÓN con el centro.

    FOCO-31: la rotación MEZCLA ramas y hojas del mismo anillo. Se excluye el
    conjunto de contención del centro (``_containment_related``): las ramas que lo
    contienen (se alcanzan con ↑) y —si el centro es rama— sus propios contenidos
    (se alcanzan con ↓/estantería). La rotación son iguales del anillo, sin jerarquía.

    Orden (FOCO-28): primero las directamente relacionadas con el centro, por
    grado de relación descendente; luego el resto; desempate alfabético. El propio
    centro (sin auto-relaciones) queda entre las no relacionadas, ordenado por
    nombre, para que el índice de rotación ←/→ sea estable.
    """
    excluded = _containment_related(project, center_id)
    members: list[str] = []
    for entity in project.entities:
        if entity.canon_state in _EXCLUDED_CANON:
            continue
        if entity.id in excluded:
            continue
        if resolver.ring(entity.id)[0] == ring_id:
            members.append(entity.id)

    # Grado de relación de cada vecino con el centro (nº de relaciones directas).
    neighbors: dict[str, int] = {}
    for relation in project.relations_for(center_id):
        other = relation.target_id if relation.source_id == center_id else relation.source_id
        if other != center_id:
            neighbors[other] = neighbors.get(other, 0) + 1

    def _connection_key(eid: str) -> tuple[int, int, str, str]:
        entity = project.entity_by_id(eid)
        name = (entity.name if entity else "").casefold()
        # bucket 0 = directamente relacionada; -grado ⇒ más conectadas primero.
        return (0 if eid in neighbors else 1, -neighbors.get(eid, 0), name, eid)

    return sorted(members, key=_connection_key)


def ring_navigation(project: Project, entity_id: str) -> RingNavigation:
    """Destinos de teclado para el centro: rotación (←/→) y salto de anillo (Shift+↑/↓)."""
    center = project.entity_by_id(entity_id)
    if center is None:
        return RingNavigation()

    resolver = _resolver(project)
    center_ring_id, center_rank = resolver.ring(entity_id)
    center_is_container = is_branch(center)

    # Rotación cíclica por el anillo actual, MEZCLANDO ramas y hojas (FOCO-31);
    # se excluyen los ancestros de contención (↑) y —si el centro es rama— sus
    # contenidos (↓/estantería). Ver ``_ring_members``.
    members = _ring_members(project, resolver, center_ring_id, entity_id)
    prev = next_ = ""
    if entity_id in members and len(members) > 1:
        idx = members.index(entity_id)
        prev = members[(idx - 1) % len(members)]
        next_ = members[(idx + 1) % len(members)]

    # Salto de anillo: relacionada del anillo más cercano; si no, entidad del adyacente.
    related_ids: set[str] = set()
    for relation in project.relations_for(entity_id):
        other_id = relation.target_id if relation.source_id == entity_id else relation.source_id
        if other_id != entity_id:
            related_ids.add(other_id)

    up = _adjacent_target(project, resolver, entity_id, center_rank, related_ids, superior=True)
    down = _adjacent_target(project, resolver, entity_id, center_rank, related_ids, superior=False)

    # ↑ sube a la rama contenedora; ↓ baja a la primera contenida (si es rama).
    container = _immediate_container(project, entity_id)
    member = ""
    if center_is_container:
        member_ids = []
        for member_id in _branch_member_ids(project, entity_id):
            other = project.entity_by_id(member_id)
            if other is None or other.canon_state in _EXCLUDED_CANON:
                continue
            member_ids.append(member_id)

        def _name_key(eid: str) -> tuple[str, str]:
            entity = project.entity_by_id(eid)
            return ((entity.name if entity else "").casefold(), eid)

        member = sorted(member_ids, key=_name_key)[0] if member_ids else ""

    return RingNavigation(
        prev=prev, next=next_, up=up, down=down, container=container, member=member
    )


def _adjacent_target(
    project: Project,
    resolver: _RingResolver,
    entity_id: str,
    center_rank: int | None,
    related_ids: set[str],
    *,
    superior: bool,
) -> str:
    """Destino del salto Shift+↑ (superior) o Shift+↓ (inferior).

    Prioriza una entidad RELACIONADA en el anillo más cercano en esa dirección;
    si no hay ninguna relacionada, cualquier entidad (determinista) del anillo
    adyacente que exista en el proyecto. "" si no hay anillo en esa dirección.
    """
    if center_rank is None:
        return ""

    # Rango de cada entidad candidata (con rango comparable) en la dirección pedida.
    def _in_direction(rank: int | None) -> bool:
        if rank is None:
            return False
        return rank < center_rank if superior else rank > center_rank

    # 1) Relacionadas en la dirección: elegir la del anillo más cercano al centro.
    best_related: tuple[int, str, str] | None = None  # (distancia, name, id)
    for other_id in related_ids:
        if other_id == entity_id:
            continue
        other = project.entity_by_id(other_id)
        if other is None or other.canon_state in _EXCLUDED_CANON:
            continue
        rank = resolver.ring(other_id)[1]
        if not _in_direction(rank):
            continue
        distance = abs(rank - center_rank)  # type: ignore[operator]
        key = (distance, other.name.casefold(), other_id)
        if best_related is None or key < best_related:
            best_related = key
    if best_related is not None:
        return best_related[2]

    # 2) Sin relacionada: anillo adyacente con entidades. Rango más cercano al centro.
    ranks_present: set[int] = set()
    for entity in project.entities:
        if entity.canon_state in _EXCLUDED_CANON:
            continue
        rank = resolver.ring(entity.id)[1]
        if _in_direction(rank):
            ranks_present.add(rank)  # type: ignore[arg-type]
    if not ranks_present:
        return ""
    adjacent_rank = max(ranks_present) if superior else min(ranks_present)
    candidates: list[str] = []
    for entity in project.entities:
        if entity.canon_state in _EXCLUDED_CANON or entity.id == entity_id:
            continue
        if resolver.ring(entity.id)[1] == adjacent_rank:
            candidates.append(entity.id)

    def _name_key(eid: str) -> tuple[str, str]:
        entity = project.entity_by_id(eid)
        return ((entity.name if entity else "").casefold(), eid)

    return sorted(candidates, key=_name_key)[0] if candidates else ""
