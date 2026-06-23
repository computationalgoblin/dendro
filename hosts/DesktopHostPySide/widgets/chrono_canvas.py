"""BETA1-G04 — Vista cronológica: el árbol mirado desde el lado.

Complementaria a la vista concéntrica (mismo proyecto, otro eje). La capa de
CÁLCULO es pura y razona en coordenadas lógicas (cross = eje-anillo,
time = eje-tiempo): eras como estratos a lo largo del tiempo, entidades como
líneas de vida a lo largo del tiempo, hitos como franjas que cruzan el eje
anillo. La capa de VISTA (BETA1-UX7) dibuja la timeline HORIZONTAL —el tiempo
avanza de izquierda a derecha (eje X)— transponiendo cross↔time al colocar los
items y al leer el ratón, de modo que el texto permanece en pie (NO es una
rotación de la escena). Con el flag interno ``_HORIZONTAL=False`` se recupera la
disposición vertical original (Y descendente = tiempo).

- Eje del tiempo = años del calendario del proyecto (horizontal por defecto).
- Eras = estratos a lo largo del tiempo (misma estética de sombras que anillos).
- Entidades = líneas de vida (nacen, mueren o continúan).
- Hitos = franjas que cruzan el eje anillo, con un punto por entidad afectada.
- Eje cruzado = columnas/carriles por anillo efectivo (orden causal de la
  concéntrica).

SIN física (contrato G01 §7): el layout es determinista — el tiempo no se
negocia con muelles. La parte de cálculo es pura (testeable sin Qt).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from packages.ui.graph_physics.rings import (
    UNCLASSIFIED_RING_ID,
    resolve_effective_ring_id,
)

# ── Constantes de layout ──────────────────────────────────────────────────

TOP_MARGIN = 70.0
LEFT_MARGIN = 150.0       # carril de etiquetas de era
COLUMN_GAP = 56.0         # separación entre columnas de anillo
LANE_WIDTH = 92.0         # separación entre líneas de vida del mismo anillo
# BETA1-UX9: cajas de rama. El marco se dibuja ALREDEDOR de los centros de carril
# (no ensancha los carriles): BOX_CROSS_PAD = cuánto se mete el marco hacia dentro
# desde el borde del carril; BOX_NEST_INSET = px que cada nivel de anidamiento
# encoge el marco por ambos lados (para que el borde de la subcaja quede dentro).
BOX_CROSS_PAD = 10.0
BOX_NEST_INSET = 7.0
# BETA1-UX feedback: la cronología es PROPORCIONAL a los años (una era de 200
# años se ve ~10× más alta que una de 20), CON TOPE para que eras enormes no
# rompan la navegación. El tope se alcanza ~300 años; por debajo, proporción
# estricta. MIN garantiza separación legible entre eventos casi coetáneos.
MIN_GAP_PX = 22.0         # alto mínimo entre dos años-ancla consecutivos
MAX_GAP_PX = 1500.0       # tope (≈300 años) — más allá deja de crecer
PX_PER_YEAR = 5.0
BOTTOM_PAD_YEARS = 2
# BETA1-HITO-MULTI: desplazamiento vertical entre franjas de hitos que comparten
# el mismo año (misma "caja"), suficiente para que sus títulos no se solapen.
MILESTONE_BOX_GAP_PX = 22.0
# BETA1-HITO-MULTI: el nombre de la entidad va CENTRADO sobre su línea; el ancho
# del carril se amplía al nombre más ancho (con tope) para que no se solapen.
NAME_MAX_PX = 360.0       # tope del nombre más ancho que dilata el carril
NAME_LANE_PAD = 28.0      # margen a cada lado del nombre dentro del carril
# BETA1-HITO-MULTI: roles de QGraphicsItem.setData para marcar items con la
# entidad (nombre/línea → abrir entidad) o el hito (título → abrir hito).
_ENTITY_ID_ROLE = 0
_MILESTONE_ID_ROLE = 1
# BETA1-UX7: el nombre/rango de una era lleva su id para que clicar la ETIQUETA
# abra la era (antes solo respondía el fondo de la banda). En calendario completo
# el id es "" → el workspace lo enruta a la configuración del calendario.
_ERA_ID_ROLE = 2
# BETA1-HITO-MULTI: holgura (px) para atribuir un clic sobre la franja al carril
# de entidad más cercano. < media de LANE_WIDTH (92) → zonas de carril sin solape.
BAND_LANE_TOL = 40.0
# BETA1-UX2D: px (viewport) que el cursor debe recorrer desde la pulsación para
# que un gesto sobre un mango cuente como ARRASTRE y no como clic. Es CRÍTICO que
# sea generoso: en la cronología, con la vista alejada, unos pocos píxeles = muchos
# años, así que un umbral pequeño (4px) convertía el TEMBLOR normal de un clic en
# un arrastre → el nodo saltaba lejos al clicar ("desaparece") y se editaba el
# lapso sin querer. Usamos el límite canónico clic/arrastre de Qt
# (startDragDistance, ~10px) con un suelo holgado para que clicar NUNCA edite.
_HANDLE_DRAG_THRESHOLD = 12.0

# BETA1-UX2D: banner único en consola para confirmar QUÉ build se está ejecutando
# (el usuario reportaba el mismo fallo tras varios fixes; esto descarta código viejo).
_BANNER_SHOWN = False


def _handle_drag_threshold() -> float:
    """Umbral efectivo clic→arrastre (máx. entre el suelo y el de Qt)."""
    try:
        from PySide6.QtWidgets import QApplication

        return float(max(_HANDLE_DRAG_THRESHOLD, QApplication.startDragDistance()))
    except Exception:  # noqa: BLE001
        return _HANDLE_DRAG_THRESHOLD


def _enum_value(value: Any, default: str = "") -> str:
    return str(getattr(value, "value", value) or default)


# BETA1-UX2D: paso de zoom de la rueda (puro, testeable sin Qt).
ZOOM_MIN_SCALE = 0.02
ZOOM_MAX_SCALE = 8.0
ZOOM_FACTOR = 1.15


def zoom_step(
    current: float,
    zoom_in: bool,
    *,
    min_scale: float = ZOOM_MIN_SCALE,
    max_scale: float = ZOOM_MAX_SCALE,
) -> float | None:
    """Factor de escala a aplicar, o ``None`` si el zoom está en su tope.

    Gate ASIMÉTRICO: acercar solo comprueba el tope superior; alejar solo el
    inferior. El gate combinado anterior (``min < current*factor < max``)
    bloqueaba cualquier acercamiento cuando la escena —muy alta— dejaba
    ``current`` por debajo del mínimo tras ``fit_all`` (no se podía acercar)."""
    if zoom_in:
        return ZOOM_FACTOR if current < max_scale else None
    return 1.0 / ZOOM_FACTOR if current > min_scale else None


# ── Eras efectivas (dominio o derivadas del calendario completo) ──────────
#
# Las eras del DOMINIO (``chronology.eras``) son la fuente canónica, pero hay
# proyectos cuyo tiempo se define con el "calendario completo": las eras viven
# en ``chronology.metadata`` (``era_lengths`` = "Nombre:Largo" por línea) y el
# dominio solo tiene la era trivial "Presente". Para DIBUJAR (estratos + slider)
# derivamos las eras de ese calendario cuando el dominio no las tiene. Es solo
# presentación: no muta canon.


@dataclass
class _EraSpan:
    name: str
    start_year: int
    end_year: int | None
    id: str = ""
    order: int = 0


def _parse_era_lengths(meta: dict) -> list[tuple[str, int]]:
    raw = meta.get("era_lengths")
    out: list[tuple[str, int]] = []
    if isinstance(raw, str):
        for line in raw.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            name, _, length = line.rpartition(":")
            try:
                out.append((name.strip(), int(float(length.strip()))))
            except ValueError:
                continue
    elif isinstance(raw, dict):
        for name, length in raw.items():
            try:
                out.append((str(name), int(float(length))))
            except (TypeError, ValueError):
                continue
    return out


def _has_real_domain_eras(domain_eras: list) -> bool:
    """¿Las eras de dominio describen un calendario real, o es solo la 'Presente'
    abierta autogenerada?"""
    if len(domain_eras) > 1:
        return True
    if len(domain_eras) == 1:
        return getattr(domain_eras[0], "end_year", None) is not None
    return False


def effective_eras(project: Any) -> list[Any]:
    """Eras para DIBUJAR. Prefiere las de dominio; si solo está la 'Presente'
    trivial, las deriva del calendario completo (``metadata.era_lengths``),
    acumulando longitudes en años. No muta nada."""
    chronology = getattr(project, "project_chronology", None)
    domain_eras = list(getattr(chronology, "eras", []) or [])
    if _has_real_domain_eras(domain_eras):
        return domain_eras
    meta = getattr(chronology, "metadata", {}) or {}
    lengths = _parse_era_lengths(meta)
    if not lengths:
        return domain_eras
    spans: list[_EraSpan] = []
    cursor = 0
    for index, (name, length) in enumerate(lengths):
        end = cursor + max(int(length), 0)
        spans.append(_EraSpan(name=name, start_year=cursor, end_year=end, order=index))
        cursor = end
    if spans:  # la última era queda abierta hacia el presente
        last = spans[-1]
        spans[-1] = _EraSpan(name=last.name, start_year=last.start_year, end_year=None, order=last.order)
    return spans


def effective_present_year(project: Any) -> int:
    """Año presente. Prefiere el dominio; si es 0/ausente usa
    ``metadata.current_year`` del calendario, y como respaldo la suma de
    longitudes de era."""
    chronology = getattr(project, "project_chronology", None)
    present = int(getattr(chronology, "present_year", 0) or 0)
    if present:
        return present
    meta = getattr(chronology, "metadata", {}) or {}
    for key in ("current_year", "present_year"):
        try:
            value = int(meta.get(key))
        except (TypeError, ValueError):
            continue
        if value:
            return value
    total = sum(length for _name, length in _parse_era_lengths(meta))
    return total or present


# ── Escala temporal (pura) ────────────────────────────────────────────────


class YearScale:
    """Mapa año → y, monótono creciente, comprimido por tramos.

    Los años-ancla (nacimientos, muertes, hitos, límites de era, presente)
    definen tramos; cada tramo mide ``clamp(años * PX_PER_YEAR, MIN, MAX)``.
    Años intermedios se interpolan linealmente dentro de su tramo.
    """

    def __init__(self, anchor_years: list[int], *, min_gaps: dict[int, float] | None = None):
        anchors = sorted(set(int(y) for y in anchor_years)) or [0]
        self._years: list[int] = anchors
        self._ys: list[float] = [TOP_MARGIN]
        gaps = min_gaps or {}
        for previous, current in zip(anchors, anchors[1:]):
            gap_years = current - previous
            gap_px = min(max(gap_years * PX_PER_YEAR, MIN_GAP_PX), MAX_GAP_PX)
            # BETA1-UX10: un hito reserva hueco para su NOMBRE → el tramo que
            # ARRANCA en su año se ensancha hasta caber el título (puede superar
            # MAX_GAP_PX a propósito), para que dos hitos cercanos no se solapen.
            gap_px = max(gap_px, float(gaps.get(previous, 0.0)))
            self._ys.append(self._ys[-1] + gap_px)

    @property
    def min_year(self) -> int:
        return self._years[0]

    @property
    def max_year(self) -> int:
        return self._years[-1]

    @property
    def bottom(self) -> float:
        return self._ys[-1]

    def y(self, year: int) -> float:
        year = int(year)
        years, ys = self._years, self._ys
        if year <= years[0]:
            return ys[0] - min((years[0] - year) * PX_PER_YEAR, MAX_GAP_PX)
        if year >= years[-1]:
            return ys[-1] + min((year - years[-1]) * PX_PER_YEAR, MAX_GAP_PX)
        # Interpolación dentro del tramo
        for index in range(len(years) - 1):
            if years[index] <= year <= years[index + 1]:
                y0, y1 = ys[index], ys[index + 1]
                a, b = years[index], years[index + 1]
                if b == a:
                    return y0
                t = (year - a) / (b - a)
                return y0 + t * (y1 - y0)
        return ys[-1]

    def year_at(self, y: float) -> int:
        """Inverso de ``y(year)``: dado un Y de escena, el año (entero) más
        cercano. Sirve para arrastrar los mangos de vida en la cronología."""
        years, ys = self._years, self._ys
        y = float(y)
        if y <= ys[0]:
            return int(round(years[0] - (ys[0] - y) / PX_PER_YEAR))
        if y >= ys[-1]:
            return int(round(years[-1] + (y - ys[-1]) / PX_PER_YEAR))
        for index in range(len(ys) - 1):
            y0, y1 = ys[index], ys[index + 1]
            if y0 <= y <= y1:
                a, b = years[index], years[index + 1]
                if y1 == y0:
                    return int(a)
                t = (y - y0) / (y1 - y0)
                return int(round(a + t * (b - a)))
        return int(years[-1])


# ── Modelo de layout (puro) ───────────────────────────────────────────────


@dataclass
class EraBand:
    era_id: str
    name: str
    start_year: int
    end_year: int | None
    y0: float
    y1: float
    index: int  # para alternar sombras


@dataclass
class RingColumn:
    ring_id: str
    name: str
    x_center: float
    x_left: float
    x_right: float


@dataclass
class BranchBox:
    """BETA1-UX9: recuadro de una rama (contenedor) en la cronología. Encierra a
    sus miembros y subramas del mismo anillo. Coordenadas LÓGICAS (cross=anillo,
    time=tiempo); la vista las transpone. La extensión en tiempo es el LAPSO de la
    rama (no el de sus miembros); la extensión en cross abarca el carril cabecera
    de la rama más todos sus carriles descendientes."""
    branch_id: str
    name: str
    color: str
    depth: int          # 0 = rama de primer nivel; +1 por nivel de anidamiento
    ring_id: str
    x_left: float       # cross (anillo)
    x_right: float
    y0: float           # time = y_birth de la rama
    y1: float           # time = y_end de la rama
    member_count: int   # descendientes (directos + anidados) para la píldora


@dataclass
class Lifeline:
    entity_id: str
    name: str
    ring_id: str
    is_tree: bool
    x: float
    birth_year: int
    death_year: int | None
    y_birth: float
    y_end: float
    alive: bool
    color: str = ""


@dataclass
class MilestoneMark:
    milestone_id: str
    title: str
    year: int
    y: float
    # BETA1-HITO-MULTI: el hito es una FRANJA horizontal a la altura de su año que
    # cruza todo el grafo, con un punto en el carril de cada entidad participante.
    # entity_ids va EN PARALELO a entity_xs (mismo orden) para poder vincular.
    entity_xs: list[float] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    # Desplazamiento vertical dentro de la "caja" del año cuando varios hitos lo
    # comparten, para que ambas franjas se lean.
    y_offset: float = 0.0
    # Desambiguación dentro de la caja (mes/día u "Orden N").
    sub_label: str = ""

    @property
    def y_band(self) -> float:
        return self.y + self.y_offset


@dataclass
class ChronoLayout:
    eras: list[EraBand]
    columns: list[RingColumn]
    lifelines: list[Lifeline]
    milestones: list[MilestoneMark]
    width: float
    height: float
    present_year: int
    y_present: float
    # BETA1-UX2C: la escala año↔y se conserva para mapear el arrastre de los
    # mangos de vida (year_at) sin recomputar el layout. Es pura (sin Qt).
    scale: Any = None
    # BETA1-UX9: recuadros de rama (contenedores) que encierran a sus miembros.
    boxes: list[BranchBox] = field(default_factory=list)


# ── Construcción (pura, sin Qt) ───────────────────────────────────────────


def _milestone_sub_label(hito: Any) -> str:
    """Desambiguador dentro de la "caja" de un año: mes/día si el calendario es
    completo (metadata.exact_date), o el orden relativo en su defecto."""
    meta = getattr(hito, "metadata", {}) or {}
    exact = meta.get("exact_date") if isinstance(meta, dict) else None
    if isinstance(exact, dict):
        month = str(exact.get("month", "") or "").strip()
        day = str(exact.get("day", "") or "").strip()
        parts = [p for p in (month, day) if p]
        if parts:
            return " ".join(parts)
    sort_index = meta.get("sort_index") if isinstance(meta, dict) else None
    if sort_index not in (None, ""):
        return f"Orden {sort_index}"
    return ""


def _effective_rings(project: Any) -> tuple[dict[str, str], set[str], dict[str, str]]:
    """entity_id → ring efectivo (C01 §4.2), conjunto de ramas, y membership
    (target→source de las relaciones 'contiene'). BETA1-UX9 necesita membership
    para construir el bosque de contención."""
    entities = list(getattr(project, "entities", []) or [])
    relations = list(getattr(project, "relations", []) or [])
    explicit: dict[str, str] = {}
    trees: set[str] = set()
    for entity in entities:
        eid = str(getattr(entity, "id", ""))
        kind = _enum_value(getattr(entity, "entity_type", None)).lower()
        if kind == "contenedor":
            trees.add(eid)
        layer_ids = list(getattr(entity, "layer_ids", []) or [])
        if layer_ids and str(layer_ids[0]):
            explicit[eid] = str(layer_ids[0])
    membership: dict[str, str] = {}
    for relation in relations:
        if _enum_value(getattr(relation, "relation_type", None)).lower() != "contiene":
            continue
        source = str(getattr(relation, "source_id", ""))
        target = str(getattr(relation, "target_id", ""))
        if source in trees and target:
            membership[target] = source
    resolved = {
        str(getattr(entity, "id", "")): resolve_effective_ring_id(
            str(getattr(entity, "id", "")),
            explicit_ring_ids=explicit,
            membership=membership,
            is_tree=frozenset(trees),
        )
        for entity in entities
    }
    return resolved, trees, membership


def _ring_order(project: Any) -> list[tuple[str, str]]:
    """[(ring_id, nombre)] por rango causal; '__unclassified__' al final."""
    layers = list(getattr(project, "world_layers", []) or [])
    def rank(layer: Any) -> float:
        meta = getattr(layer, "metadata", {}) or {}
        try:
            return float(meta.get("causal_rank"))
        except (TypeError, ValueError):
            try:
                return float(getattr(layer, "order", 0) or 0)
            except (TypeError, ValueError):
                return 0.0
    ordered = sorted(
        (layer for layer in layers if getattr(layer, "is_visible", True)),
        key=rank,
    )
    result = [(str(getattr(layer, "id", "")), str(getattr(layer, "name", "Anillo"))) for layer in ordered]
    result.append((UNCLASSIFIED_RING_ID, "Sin anillo"))
    return result


def _chrono_birth_key(entity: Any, present_year: int) -> tuple[int, str]:
    """Clave de orden de carriles: año de nacimiento, luego nombre."""
    b = getattr(entity, "birth_year", None)
    return (int(b) if b is not None else present_year, str(getattr(entity, "name", "")))


def _assign_branch_lanes(
    roots: list[str],
    children: dict[str, list[str]],
    trees: set[str],
) -> tuple[list[str], list[tuple[str, int, int, int]]]:
    """BETA1-UX9: asigna carriles por CONTENCIÓN dentro de un anillo. ``roots`` y
    cada lista de ``children`` vienen ya ordenadas. Devuelve:
    - el orden de carriles (lista de entity_id; el carril i es la posición i),
      con la cabecera de cada rama PRIMERO y sus descendientes en profundidad;
    - los spans de caja ``(branch_id, depth, first_lane, last_lane)`` por rama.
    Puro y determinista (sin Qt)."""
    ordered: list[str] = []
    boxes: list[tuple[str, int, int, int]] = []

    def walk(node_id: str, depth: int) -> int:
        my_lane = len(ordered)
        ordered.append(node_id)
        last = my_lane
        for kid in children.get(node_id, []):
            last = walk(kid, depth + 1)
        if node_id in trees:
            boxes.append((node_id, depth, my_lane, last))
        return last

    for root in roots:
        walk(root, 0)
    return ordered, boxes


def build_chrono_layout(
    project: Any,
    *,
    lane_width: float = LANE_WIDTH,
    milestone_min_gaps: dict[int, float] | None = None,
) -> ChronoLayout:
    """Layout determinista de la vista cronológica (contrato G01 §7).

    ``lane_width`` (px entre líneas de vida del mismo anillo) se puede ampliar
    para que los nombres centrados sobre cada línea quepan sin solaparse; la
    capa Qt lo calcula desde el nombre más ancho (BETA1-HITO-MULTI).
    ``milestone_min_gaps`` (BETA1-UX10) = por año de hito, el px mínimo a
    reservar DESPUÉS de ese año para que el NOMBRE del hito quepa antes del
    siguiente (la capa Qt lo mide desde el ancho del título; en vertical pasa
    alturas, mucho menores). Pura: solo recibe números, sin depender de Qt."""
    lane_width = max(float(lane_width), LANE_WIDTH)
    # BETA1-UX feedback: eras y presente EFECTIVOS — si el proyecto define el
    # tiempo con calendario completo, las eras viven en metadata y aquí se
    # derivan; si no, se usan las de dominio. Así los estratos se ven siempre.
    present_year = effective_present_year(project)
    eras_domain = effective_eras(project)
    entities = list(getattr(project, "entities", []) or [])
    milestones = list(getattr(project, "causal_milestones", []) or [])

    # 1. Años-ancla
    anchor_years: list[int] = [present_year]
    for era in eras_domain:
        anchor_years.append(int(getattr(era, "start_year", 0) or 0))
        if getattr(era, "end_year", None) is not None:
            anchor_years.append(int(era.end_year))
    for entity in entities:
        birth = getattr(entity, "birth_year", None)
        anchor_years.append(int(birth) if birth is not None else present_year)
        death = getattr(entity, "death_year", None)
        if death is not None:
            anchor_years.append(int(death))
    milestone_years: dict[str, int] = {}
    for hito in milestones:
        year = getattr(hito, "year", None)
        year = int(year) if isinstance(year, int) and not isinstance(year, bool) else present_year
        milestone_years[str(getattr(hito, "id", ""))] = year
        anchor_years.append(year)
    anchor_years.append(max(anchor_years) + BOTTOM_PAD_YEARS)
    scale = YearScale(anchor_years, min_gaps=milestone_min_gaps)

    # 2. Columnas por anillo efectivo. BETA1-UX9: dentro de cada anillo, una rama
    #    agrupa a sus miembros/subramas del MISMO anillo en carriles CONTIGUOS
    #    (cabecera de la rama primero, descendientes en profundidad) para poder
    #    enmarcarlos; las entidades sin rama del anillo quedan como carriles sueltos.
    effective, trees, membership = _effective_rings(project)
    ring_ids_used = {effective.get(str(getattr(e, "id", "")), UNCLASSIFIED_RING_ID) for e in entities}
    columns: list[RingColumn] = []
    lanes_by_ring: dict[str, list[Any]] = {}
    # (ring_id, branch_id, depth, first_lane, last_lane)
    pending_boxes: list[tuple[str, str, int, int, int]] = []
    x_cursor = LEFT_MARGIN + COLUMN_GAP
    for ring_id, ring_name in _ring_order(project):
        members = [
            entity for entity in entities
            if effective.get(str(getattr(entity, "id", "")), UNCLASSIFIED_RING_ID) == ring_id
        ]
        if not members:
            continue
        if ring_id == UNCLASSIFIED_RING_ID and ring_id not in ring_ids_used:
            continue

        member_ids = {str(getattr(e, "id", "")) for e in members}
        ent_by_id = {str(getattr(e, "id", "")): e for e in members}
        sort_key = {mid: _chrono_birth_key(ent_by_id[mid], present_year) for mid in member_ids}
        # Bosque de contención restringido al MISMO anillo: un hijo cuelga de su
        # rama madre solo si AMBOS están en este anillo (un miembro con anillo
        # explícito distinto queda suelto en SU anillo — decisión #1).
        children: dict[str, list[str]] = {mid: [] for mid in member_ids}
        has_parent: set[str] = set()
        for child_id in member_ids:
            parent = membership.get(child_id, "")
            if parent in trees and parent in member_ids:
                children[parent].append(child_id)
                has_parent.add(child_id)
        for kids in children.values():
            kids.sort(key=sort_key.__getitem__)
        roots = sorted((mid for mid in member_ids if mid not in has_parent), key=sort_key.__getitem__)

        ordered_ids, box_spans = _assign_branch_lanes(roots, children, trees)
        ordered = [ent_by_id[mid] for mid in ordered_ids]
        lanes_by_ring[ring_id] = ordered
        for branch_id, depth, first_lane, last_lane in box_spans:
            pending_boxes.append((ring_id, branch_id, depth, first_lane, last_lane))

        lane_count = len(ordered)
        width = max(lane_count - 1, 0) * lane_width
        columns.append(RingColumn(
            ring_id=ring_id,
            name=ring_name,
            x_center=x_cursor + width / 2.0,
            x_left=x_cursor - lane_width / 2.0,
            x_right=x_cursor + width + lane_width / 2.0,
        ))
        x_cursor += width + lane_width / 2.0 + COLUMN_GAP

    total_width = max(x_cursor + COLUMN_GAP, LEFT_MARGIN + 400.0)

    # 3. Eras como estratos
    era_bands: list[EraBand] = []
    bottom_year = scale.max_year
    sorted_eras = sorted(eras_domain, key=lambda era: (int(getattr(era, "start_year", 0) or 0), int(getattr(era, "order", 0) or 0)))
    for index, era in enumerate(sorted_eras):
        start = int(getattr(era, "start_year", 0) or 0)
        end = getattr(era, "end_year", None)
        era_bands.append(EraBand(
            era_id=str(getattr(era, "id", "")),
            name=str(getattr(era, "name", "Era")),
            start_year=start,
            end_year=int(end) if end is not None else None,
            y0=scale.y(start),
            y1=scale.y(int(end)) if end is not None else scale.y(bottom_year) + MIN_GAP_PX,
            index=index,
        ))

    # 4. Líneas de vida
    x_by_entity: dict[str, float] = {}
    lifelines: list[Lifeline] = []
    column_by_ring = {column.ring_id: column for column in columns}
    for ring_id, members in lanes_by_ring.items():
        column = column_by_ring[ring_id]
        start_x = column.x_center - (max(len(members) - 1, 0) * lane_width) / 2.0
        for lane_index, entity in enumerate(members):
            eid = str(getattr(entity, "id", ""))
            birth = getattr(entity, "birth_year", None)
            birth = int(birth) if birth is not None else present_year
            death = getattr(entity, "death_year", None)
            alive = death is None
            end_year = present_year if alive else int(death)
            x = start_x + lane_index * lane_width
            x_by_entity[eid] = x
            meta = getattr(entity, "custom_metadata", {}) or {}
            color = str(meta.get("_node_color", "") or meta.get("tree_color", "") or "")
            lifelines.append(Lifeline(
                entity_id=eid,
                name=str(getattr(entity, "name", "") or "Sin nombre"),
                ring_id=ring_id,
                is_tree=eid in trees,
                x=x,
                birth_year=birth,
                death_year=None if alive else int(death),
                y_birth=scale.y(birth),
                y_end=max(scale.y(end_year), scale.y(birth) + 10.0),
                alive=alive,
                color=color,
            ))

    # 5. Hitos: FRANJA horizontal a la altura del año, con un punto en el carril
    #    de cada entidad participante (BETA1-HITO-MULTI). Ya no hay "entidad
    #    principal": todas las afectadas participan en pie de igualdad.
    marks: list[MilestoneMark] = []
    for hito in milestones:
        hid = str(getattr(hito, "id", ""))
        year = milestone_years.get(hid, present_year)
        affected = [str(v) for v in (getattr(hito, "affected_entity_ids", []) or []) if str(v) in x_by_entity]
        pairs = sorted((x_by_entity[eid], eid) for eid in affected)
        marks.append(MilestoneMark(
            milestone_id=hid,
            title=str(getattr(hito, "title", "") or "Hito"),
            year=year,
            y=scale.y(year),
            entity_xs=[x for x, _ in pairs],
            entity_ids=[eid for _, eid in pairs],
            sub_label=_milestone_sub_label(hito),
        ))

    # Misma "caja" (mismo año) → escalonar en Y para que las franjas se lean.
    by_year: dict[int, list[MilestoneMark]] = {}
    for mark in marks:
        by_year.setdefault(mark.year, []).append(mark)
    for group in by_year.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda m: (m.sub_label, m.title, m.milestone_id))
        span = (len(group) - 1) * MILESTONE_BOX_GAP_PX
        for index, mark in enumerate(group):
            mark.y_offset = index * MILESTONE_BOX_GAP_PX - span / 2.0

    # 6. Cajas de rama (BETA1-UX9): un rect por contenedor. El marco rodea los
    #    CENTROS de carril existentes (no los desplaza); time = LAPSO de la rama
    #    (decisión #5); cada nivel de anidamiento mete el borde hacia dentro.
    ent_by_id_all = {str(getattr(e, "id", "")): e for e in entities}
    boxes: list[BranchBox] = []
    for ring_id, branch_id, depth, first_lane, last_lane in pending_boxes:
        branch_x = x_by_entity.get(branch_id)
        if branch_x is None:
            continue
        span = last_lane - first_lane
        last_x = branch_x + span * lane_width
        half = lane_width / 2.0 - BOX_CROSS_PAD
        inset = depth * BOX_NEST_INSET
        x_left = branch_x - half + inset
        x_right = last_x + half - inset
        be = ent_by_id_all.get(branch_id)
        bbirth = getattr(be, "birth_year", None)
        bbirth = int(bbirth) if bbirth is not None else present_year
        bdeath = getattr(be, "death_year", None)
        bend = present_year if bdeath is None else int(bdeath)
        y0 = scale.y(bbirth)
        y1 = max(scale.y(bend), y0 + 10.0)
        bmeta = getattr(be, "custom_metadata", {}) or {}
        bcolor = str(bmeta.get("_node_color", "") or bmeta.get("tree_color", "") or "")
        boxes.append(BranchBox(
            branch_id=branch_id,
            name=str(getattr(be, "name", "") or "Rama"),
            color=bcolor,
            depth=depth,
            ring_id=ring_id,
            x_left=min(x_left, x_right),
            x_right=max(x_left, x_right),
            y0=y0,
            y1=y1,
            member_count=span,
        ))

    height = scale.bottom + 80.0
    return ChronoLayout(
        eras=era_bands,
        columns=columns,
        lifelines=lifelines,
        milestones=marks,
        width=total_width,
        height=height,
        present_year=present_year,
        y_present=scale.y(present_year),
        boxes=boxes,
        scale=scale,
    )


# ── Vista Qt ──────────────────────────────────────────────────────────────

try:  # la parte pura debe poder importarse sin PySide6
    from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QFontMetrics,
        QLinearGradient,
        QPainter,
        QPainterPath,
        QPen,
        QRadialGradient,
    )
    from PySide6.QtWidgets import (
        QComboBox,
        QFormLayout,
        QGraphicsEllipseItem,
        QGraphicsItem,
        QGraphicsLineItem,
        QGraphicsPathItem,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsSimpleTextItem,
        QGraphicsView,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMenu,
        QPushButton,
        QSpinBox,
        QStyle,
        QVBoxLayout,
        QWidget,
    )
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False


if HAS_QT:

    _BG = QColor("#E6DFCD")  # BETA1-G07: alineado con la viñeta de la concéntrica
    _SHADOW = QColor(92, 90, 62)
    _INK = QColor("#504B2E")
    _MUTED = QColor("#7C806E")
    _LINE = QColor("#8A8563")
    _WHITE = QColor(255, 255, 253, 250)
    _PILL_FILL = QColor("#FBF8EF")
    _PILL_FILL.setAlpha(232)
    _PILL_LINE = QColor("#D2CAB1")
    # BETA1-UX feedback: tintes BOTÁNICOS cálidos para los estratos de era
    # (oro · salvia · terracota · ciruela · musgo). Mismos que el slider de la
    # concéntrica, para que las dos vistas hablen el mismo idioma de color.
    _ERA_TINTS = ("#C8A24C", "#7E9568", "#A87C53", "#937083", "#B28A3C")
    # BETA1-UX9: estilo de las cajas de rama (contenedores).
    _BOX_FILL_ALPHA = 42       # relleno cálido translúcido (deja ver la era debajo)
    _BOX_HEADER_ALPHA = 92     # franja de cabecera, algo más opaca
    BOX_HEADER_PX = 22.0       # grosor (en tiempo) de la franja de cabecera
    BOX_CORNER_RADIUS = 10.0
    BOX_LABEL_PAD = 10.0
    # BETA1-UX feedback: viñeta cálida IDÉNTICA a la concéntrica (corazón con luz
    # → bordes que se hunden). Aquí se pinta centrada en el viewport.
    _VIGNETTE = (
        (0.0, "#F3EDDD"),
        (0.50, "#E6DFCD"),
        (0.82, "#DBD1B9"),
        (1.0, "#CFC4A8"),
    )

    def _add_pill_label(
        scene, text, x, y, *, font, fg, z=31.0, max_w=None, align_right=False,
        center=False, tag=None,
    ):
        """BETA1-UX feedback: etiqueta sobre una píldora de pergamino para que
        sea legible y NO se solape de forma ilegible (elide si excede max_w).
        ``tag`` = (rol, valor) marca píldora y texto con setData para que el clic
        sobre la etiqueta abra el panel correspondiente (BETA1-HITO-MULTI)."""
        shown = text
        if max_w is not None:
            shown = QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, int(max_w))
        item = QGraphicsSimpleTextItem(shown)
        item.setFont(font)
        item.setBrush(QBrush(fg))
        r = item.boundingRect()
        pad_x, pad_y = 7.0, 3.0
        if align_right:
            px = x - r.width() - pad_x
        elif center:
            px = x - r.width() / 2.0
        else:
            px = x
        pill_rect = QRectF(px - pad_x, y - pad_y, r.width() + 2 * pad_x, r.height() + 2 * pad_y)
        path = QPainterPath()
        radius = pill_rect.height() / 2.0
        path.addRoundedRect(pill_rect, radius, radius)
        pill = QGraphicsPathItem(path)
        pill.setBrush(QBrush(_PILL_FILL))
        pill.setPen(QPen(_PILL_LINE, 1.0))
        pill.setZValue(z - 0.1)
        item.setPos(px, y)
        item.setZValue(z)
        if tag is not None:
            pill.setData(tag[0], tag[1])
            item.setData(tag[0], tag[1])
        scene.addItem(pill)
        scene.addItem(item)
        return item

    class _LifelineHead(QGraphicsEllipseItem):
        """Nodo-cabeza de la línea de vida (hoja blanca con halo). Marca el AÑO
        DE ORIGEN y es el mango clicable/arrastrable de la entidad."""

        def __init__(self, lifeline: Lifeline, radius: float):
            super().__init__(-radius, -radius, radius * 2, radius * 2)
            self.entity_id = lifeline.entity_id
            halo = QColor(lifeline.color) if lifeline.color else QColor("#AFA77A")
            halo.setAlpha(70)
            self.setPen(QPen(halo, 5))
            self.setBrush(QBrush(_WHITE))
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.setZValue(30)
            # BETA1-UX2C: arrastrable en vertical para fijar el año de ORIGEN.
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            self.setToolTip("Arrastra ↑/↓ para cambiar el año de origen · doble clic: abrir")

        def paint(self, painter, option, widget=None):  # noqa: N802
            option.state = QStyle.State(option.state & ~QStyle.StateFlag.State_Selected)
            super().paint(painter, option, widget)
            if self.isSelected():
                painter.setPen(QPen(QColor(_SHADOW.red(), _SHADOW.green(), _SHADOW.blue(), 66), 3))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))

    class _LifelineEndHandle(QGraphicsEllipseItem):
        """BETA1-UX2C: mango inferior de la línea de vida. Arrastrarlo fija el año
        de FIN; arrastrarlo hasta/por debajo del presente marca la entidad como
        viva (sin muerte)."""

        def __init__(self, lifeline: Lifeline, radius: float = 5.0):
            super().__init__(-radius, -radius, radius * 2, radius * 2)
            self.entity_id = lifeline.entity_id
            self.setPen(QPen(QColor(_LINE.red(), _LINE.green(), _LINE.blue(), 180), 1.4))
            fill = QColor("#F4EFE0"); fill.setAlpha(235)
            self.setBrush(QBrush(fill))
            self.setZValue(29)
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            self.setToolTip(
                "Arrastra ↑/↓ para cambiar el año de fin · bájalo al presente para "
                "marcar que sigue viva"
            )

    class _LifelineLine(QGraphicsLineItem):
        """Línea de vida con DIANA DE CLIC ANCHA. La línea visible es fina, pero
        su área clicable se ensancha (±HIT px) para que clicar 'sobre la entidad'
        abra su panel en vez de caer en la banda de era de debajo. En calendario
        completo las eras cubren TODO el lienzo, así que sin esto un clic unos
        píxeles fuera de la línea no hacía nada (BETA1-UX7)."""

        HIT = 9.0

        def __init__(self, x1, y1, x2, y2, entity_id: str):
            super().__init__(x1, y1, x2, y2)
            self.setData(_ENTITY_ID_ROLE, str(entity_id))

        def boundingRect(self):  # noqa: N802
            return super().boundingRect().adjusted(-self.HIT, -self.HIT, self.HIT, self.HIT)

        def shape(self):  # noqa: N802 — diana ancha alrededor del segmento
            line = self.line()
            path = QPainterPath()
            if abs(line.x2() - line.x1()) >= abs(line.y2() - line.y1()):
                path.addRect(QRectF(
                    min(line.x1(), line.x2()), line.y1() - self.HIT,
                    abs(line.x2() - line.x1()), 2 * self.HIT,
                ))
            else:
                path.addRect(QRectF(
                    line.x1() - self.HIT, min(line.y1(), line.y2()),
                    2 * self.HIT, abs(line.y2() - line.y1()),
                ))
            return path

    class _MilestoneBand(QGraphicsLineItem):
        """BETA1-HITO-MULTI: franja horizontal del hito a la altura de su año.
        Cruza todo el grafo, es seleccionable y abre el detalle al doble-clic."""

        def __init__(self, mark: MilestoneMark, c0: float, c1: float, horizontal: bool = False):
            # BETA1-UX7: la franja cruza todo el grafo a lo largo del eje ANILLO,
            # a la posición de TIEMPO del hito. En horizontal es una línea vertical
            # (x = tiempo) que recorre el eje Y; en vertical, horizontal como antes.
            self._horizontal = bool(horizontal)
            if self._horizontal:
                super().__init__(mark.y_band, c0, mark.y_band, c1)
            else:
                super().__init__(c0, mark.y_band, c1, mark.y_band)
            self.milestone_id = mark.milestone_id
            self._bloom_phase = 0.0
            self._base_pen = QPen(QColor(_LINE.red(), _LINE.green(), _LINE.blue(), 120), 1.2)
            self.setPen(self._base_pen)
            self.setToolTip(f"{mark.title} — año {mark.year}")
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.setZValue(18)

        def set_bloom_phase(self, phase: float):
            self._bloom_phase = float(phase)
            self.update()

        def boundingRect(self):  # noqa: N802
            if self._horizontal:
                return super().boundingRect().adjusted(-6.0, 0, 6.0, 0)
            return super().boundingRect().adjusted(0, -6.0, 0, 6.0)

        def shape(self):  # noqa: N802 — banda fina pero clicable (±5px)
            line = self.line()
            path = QPainterPath()
            if self._horizontal:
                path.addRect(QRectF(
                    line.x1() - 5.0, min(line.y1(), line.y2()),
                    10.0, abs(line.y2() - line.y1()),
                ))
            else:
                path.addRect(QRectF(
                    min(line.x1(), line.x2()), line.y1() - 5.0,
                    abs(line.x2() - line.x1()), 10.0,
                ))
            return path

        def paint(self, painter, option, widget=None):  # noqa: N802
            option.state = QStyle.State(option.state & ~QStyle.StateFlag.State_Selected)
            if 0.0 < self._bloom_phase < 1.0:
                glow = QColor("#E2B23C")
                glow.setAlpha(int(150 * (1.0 - self._bloom_phase)))
                painter.setPen(QPen(glow, 4.0))
                painter.drawLine(self.line())
            if self.isSelected():
                painter.setPen(QPen(QColor(_SHADOW.red(), _SHADOW.green(), _SHADOW.blue(), 200), 2.0))
            else:
                painter.setPen(self._base_pen)
            painter.drawLine(self.line())

    class _EraBandItem(QGraphicsRectItem):
        """BETA1-HITO-MULTI: estrato de una era. Lleva su era_id para abrir su
        panel de edición al clicarlo (clic simple, como en el resto de la app)."""

        def __init__(self, era_id: str, *args):
            super().__init__(*args)
            self.era_id = str(era_id)

    class _BranchBoxItem(QGraphicsRectItem):
        """BETA1-UX9: recuadro de una rama (contenedor) que encierra a sus
        miembros y subramas. Relleno cálido translúcido + borde suave + franja de
        cabecera (en el inicio del eje TIEMPO). Lleva ``_ENTITY_ID_ROLE`` para que
        clicar el marco/cabecera/interior vacío abra la rama (las vidas/nombres de
        los miembros, en z superior, ganan sobre su propio carril)."""

        def __init__(self, branch_id, color, depth, header_px, horizontal, *args):
            super().__init__(*args)
            self.branch_id = str(branch_id)
            self._color = QColor(color) if color else QColor("#A89878")
            self._depth = int(depth)
            self._header_px = float(header_px)
            self._horizontal = bool(horizontal)
            self.setData(_ENTITY_ID_ROLE, self.branch_id)
            # z entre la banda de era (-30) y las vidas (10); subcajas más arriba.
            self.setZValue(-28 + self._depth)
            self.setPen(QPen(Qt.PenStyle.NoPen))  # el borde lo pinta paint()

        def boundingRect(self):  # noqa: N802
            return self.rect().adjusted(-2.0, -2.0, 2.0, 2.0)

        def paint(self, painter, option, widget=None):  # noqa: N802
            r = self.rect()
            radius = BOX_CORNER_RADIUS
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            path = QPainterPath()
            path.addRoundedRect(r, radius, radius)
            fill = QColor(self._color); fill.setAlpha(_BOX_FILL_ALPHA)
            painter.fillPath(path, QBrush(fill))
            # Franja de cabecera (tinte más opaco) en el INICIO del tiempo: en
            # horizontal el borde izquierdo, en vertical el borde superior.
            header = QColor(self._color); header.setAlpha(_BOX_HEADER_ALPHA)
            if self._horizontal:
                hr = QRectF(r.left(), r.top(), min(self._header_px, r.width()), r.height())
            else:
                hr = QRectF(r.left(), r.top(), r.width(), min(self._header_px, r.height()))
            hpath = QPainterPath()
            hpath.addRoundedRect(hr, radius, radius)
            painter.fillPath(hpath.intersected(path), QBrush(header))
            border = QColor(self._color); border.setAlpha(175)
            painter.setPen(QPen(border, 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    class _GhostNode(QGraphicsEllipseItem):
        """BETA1-HITO-MULTI: marcador TENUE en el cruce franja↔carril de una
        entidad NO vinculada al hito. Clicarlo vincula esa entidad (pasa a punto
        sólido). No germina ni se selecciona; solo invita a vincular."""

        def __init__(self, milestone_id: str, entity_id: str, radius: float = 5.0):
            super().__init__(-radius, -radius, radius * 2, radius * 2)
            self.milestone_id = str(milestone_id)
            self.entity_id = str(entity_id)
            pen = QColor(_LINE); pen.setAlpha(85)
            self.setPen(QPen(pen, 1.0, Qt.PenStyle.DotLine))
            self.setBrush(QBrush(QColor(0, 0, 0, 0)))  # invisible pero clicable
            self.setZValue(36)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Clic para vincular esta entidad al hito")

        def boundingRect(self):  # noqa: N802 — debe CONTENER al shape() ampliado
            return QRectF(-11.0, -11.0, 22.0, 22.0)

        def shape(self):  # noqa: N802 — diana ampliada para clicar con holgura
            path = QPainterPath()
            path.addEllipse(-11.0, -11.0, 22.0, 22.0)
            return path

    class _MilestoneNode(QGraphicsEllipseItem):
        _BLOOM_MARGIN = 30.0

        def __init__(self, mark: MilestoneMark, radius: float = 6.0, entity_id: str = ""):
            super().__init__(-radius, -radius, radius * 2, radius * 2)
            self.milestone_id = mark.milestone_id
            self.entity_id = str(entity_id)
            self.radius = radius
            self._bloom_phase = 0.0  # SEM03: germinación del hito (glow dorado)
            self.setPen(QPen(_LINE, 1.4))
            self.setBrush(QBrush(QColor("#F8F5EA")))
            self.setToolTip(f"{mark.title} — año {mark.year}")
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.setZValue(40)

        def shape(self):  # noqa: N802 — diana ampliada para clicar con holgura
            path = QPainterPath()
            r = max(self.radius + 5.0, 11.0)
            path.addEllipse(-r, -r, 2 * r, 2 * r)
            return path

        def set_bloom_phase(self, phase: float):
            phase = float(phase)
            if (0.0 < phase < 1.0) != (0.0 < self._bloom_phase < 1.0):
                self.prepareGeometryChange()
            self._bloom_phase = phase
            self.update()

        def boundingRect(self):  # noqa: N802
            # Debe CONTENER al shape() ampliado (diana de clic) y al glow de bloom.
            base = super().boundingRect().united(QRectF(-11.0, -11.0, 22.0, 22.0))
            if 0.0 < self._bloom_phase < 1.0:
                m = self._BLOOM_MARGIN
                return base.adjusted(-m, -m, m, m)
            return base

        def paint(self, painter, option, widget=None):  # noqa: N802
            option.state = QStyle.State(option.state & ~QStyle.StateFlag.State_Selected)
            super().paint(painter, option, widget)
            if self.isSelected():
                painter.setPen(QPen(QColor(_SHADOW.red(), _SHADOW.green(), _SHADOW.blue(), 80), 2.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(self.rect().adjusted(1.5, 1.5, -1.5, -1.5))
            if 0.0 < self._bloom_phase < 1.0:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for i in range(3):
                    t = self._bloom_phase - i * 0.16
                    if t <= 0.0 or t >= 1.0:
                        continue
                    rr = self.radius + 3.0 + 24.0 * t
                    glow = QColor("#E2B23C")
                    glow.setAlpha(int(200 * (1.0 - t)))
                    painter.setPen(QPen(glow, 3.0 * (1.0 - t) + 1.0))
                    painter.drawEllipse(QPointF(0.0, 0.0), rr, rr)

    class MilestoneQuickCreatePanel(QWidget):
        """BETA1-HITO-MULTI: panel mínimo para crear un hito desde la cronología
        (clic derecho sobre una era). Es un QWidget (no un QDialog) para mostrarse
        como overlay DENTRO de la app (ModalOverlay), no como ventana del SO. El
        AÑO es obligatorio; mes y día son OPCIONALES y solo se ofrecen si el
        proyecto usa calendario completo. Emite ``submitted(payload)`` /
        ``cancelled`` para que el host cree el hito por el controller."""

        submitted = Signal(dict)
        cancelled = Signal()

        def __init__(self, *, default_year, calendar_meta, era_name="", parent=None):
            super().__init__(parent)
            self.setObjectName("milestoneQuickCreate")
            # WA_StyledBackground: sin esto un QWidget plano NO pinta el fondo del
            # stylesheet y los campos quedan "flotando" sin la tarjeta detrás.
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.setStyleSheet(
                "QWidget#milestoneQuickCreate { background: #FFFDF7; "
                "border: 1px solid #D8D6C8; border-radius: 12px; }"
            )
            self.setMinimumWidth(380)
            self._era_name = str(era_name or "")
            meta = dict(calendar_meta or {})
            full = str(meta.get("mode") or "") == "full_calendar"
            outer = QVBoxLayout(self)
            outer.setContentsMargins(18, 16, 18, 16)
            outer.setSpacing(12)
            header = QLabel(f"Crear hito en «{era_name}»" if era_name else "Crear hito")
            header.setStyleSheet("font-size: 15px; font-weight: 600;")
            outer.addWidget(header)
            form = QFormLayout()
            self.title_edit = QLineEdit("Nuevo hito")
            form.addRow("Título", self.title_edit)
            self.year_spin = QSpinBox()
            self.year_spin.setRange(-999999, 999999)
            self.year_spin.setValue(int(default_year))
            form.addRow("Año", self.year_spin)
            self.month_combo = None
            self.day_spin = None
            if full:
                from hosts.DesktopHostPySide.widgets.calendar_date_picker import DEFAULT_MONTHS
                months = [str(m).strip() for m in (meta.get("months") or DEFAULT_MONTHS) if str(m).strip()]
                self.month_combo = QComboBox()
                self.month_combo.addItem("(ninguno)", "")
                for month in months:
                    self.month_combo.addItem(month, month)
                form.addRow("Mes (opcional)", self.month_combo)
                self.day_spin = QSpinBox()
                self.day_spin.setRange(0, 99)  # 0 → sin día
                self.day_spin.setSpecialValueText("(ninguno)")
                form.addRow("Día (opcional)", self.day_spin)
            outer.addLayout(form)
            row = QHBoxLayout()
            row.addStretch(1)
            cancel_btn = QPushButton("Cancelar")
            cancel_btn.clicked.connect(self.cancelled.emit)
            row.addWidget(cancel_btn)
            create_btn = QPushButton("Crear")
            create_btn.setObjectName("primaryButton")
            create_btn.setDefault(True)
            create_btn.clicked.connect(lambda: self.submitted.emit(self.payload()))
            row.addWidget(create_btn)
            outer.addLayout(row)

        def payload(self) -> dict:
            title = self.title_edit.text().strip() or "Nuevo hito"
            year = int(self.year_spin.value())
            data: dict = {"title": title, "year": year}
            month = str(self.month_combo.currentData() or "") if self.month_combo is not None else ""
            day = int(self.day_spin.value()) if self.day_spin is not None else 0
            if month:
                exact: dict = {"year": year, "month": month}
                if day > 0:
                    exact["day"] = str(day)
                if self._era_name:
                    exact["era"] = self._era_name
                data["metadata"] = {"exact_date": exact}
            return data

    class ChronoCanvasView(QGraphicsView):
        """Vista cronológica del proyecto. Determinista, SIN física."""

        entityActivated = Signal(str)
        milestoneActivated = Signal(str)
        # CRON: clic derecho sobre un hito → iniciar/continuar recorrido cronológico.
        walkRequested = Signal(str)
        escapePressed = Signal()
        # BETA1-UX2C: el usuario editó el lapso de una entidad arrastrando su
        # nodo. death = None → sigue viva. Lo persiste el workspace por controller.
        lifespanEdited = Signal(str, int, object)
        # BETA1-HITO-MULTI: clic derecho sobre una era → solicitar crear hito.
        # Lleva el año sugerido y el nombre de la era; el workspace muestra el
        # panel (overlay interno) y crea el hito por el controller.
        milestoneCreateRequested = Signal(int, str)
        # BETA1-HITO-MULTI: clic simple sobre una era → abrir su panel de edición.
        eraActivated = Signal(str)
        # BETA1-HITO-MULTI: clic en un cruce "fantasma" → vincular la entidad al
        # hito. (milestone_id, entity_id). Lo persiste el workspace por controller.
        milestoneEntityLinkRequested = Signal(str, str)

        # BETA1-UX7: la cronología se dibuja HORIZONTAL (el tiempo avanza de
        # izquierda a derecha). El layout puro sigue siendo vertical (x=anillo,
        # y=tiempo); aquí se transpone x↔y al colocar items y al leer el ratón,
        # de modo que el texto permanece en pie (NO es una rotación de la escena).
        _HORIZONTAL = True

        def __init__(self, parent=None):
            super().__init__(parent)
            self._horizontal = self._HORIZONTAL
            scene = QGraphicsScene(self)
            # BETA1-UX2D (items que "desaparecen" al clicar y NO vuelven hasta
            # reconstruir la escena): es la firma clásica de un índice espacial
            # (árbol BSP) que queda OBSOLETO — un item acaba con bounds caducados en
            # el índice y el render lo SALTA en cada repintado (por eso un repintado
            # completo no lo arregla, pero recrear los items —rebuild— sí). NoIndex
            # recorre todos los items (esta escena es pequeña y estática, coste
            # imperceptible) y elimina el problema de raíz.
            scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
            self.setScene(scene)
            global _BANNER_SHOWN
            if not _BANNER_SHOWN:
                _BANNER_SHOWN = True
                print(
                    "[Dendro] ChronoCanvas UX2D-r7: rebuild-on-click "
                    "(NoIndex + FullViewport)",
                    flush=True,
                )
            # BETA1-UX2C: estado de arrastre de mangos de vida.
            self._lifeline_views: dict[str, dict] = {}
            self._press_handle: tuple[str, str] | None = None
            self._press_pos = QPointF()  # BETA1-UX2D: ancla para el umbral clic/arrastre
            self._handle_drag: dict | None = None
            self._handle_moved = False
            self._project = None  # BETA1-UX2D: último proyecto (para reconstruir bajo demanda)
            self._rebuild_pending = False  # evita reconstrucciones diferidas duplicadas
            # BETA1-UX2D: la cronología corre en RASTER (no GPU). Es una vista
            # ESTÁTICA (sin física) y, al ser un QGraphicsView GL hermano del grafo
            # alternado por setVisible y que reconstruye su escena (scene.clear) en
            # cada show, el viewport OpenGL provocaba artefactos (eras que
            # "desaparecían" al pulsar) y un crash al volver del grafo. El raster es
            # estable y fluido de sobra para una escena que no anima. El grafo sí
            # mantiene GPU (allí la física a 60 fps lo aprovecha).
            self.setRenderHints(
                QPainter.RenderHint.Antialiasing
                | QPainter.RenderHint.TextAntialiasing
                | QPainter.RenderHint.SmoothPixmapTransform
            )
            # BETA1-UX2D (items que "desaparecen" al clicar): en raster el modo por
            # defecto (Minimal) solo repinta las regiones sucias y, con las bandas
            # de era enormes + la viñeta radial + la atmósfera de fondo, al
            # interactuar quedaban zonas SIN repintar (los items seguían en la
            # escena —el conteo no cambia— pero no se pintaban). Repintar todo el
            # viewport en cada cambio elimina el artefacto y es barato para una
            # escena estática como esta.
            self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
            self._apply_vignette()  # viñeta radial inicial (igual que la concéntrica)
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self._space_panning = False
            self._layout: ChronoLayout | None = None
            # SEM03: germinación de hitos (mismo patrón que la concéntrica).
            self._milestone_items: dict[str, list] = {}
            self._bloom_items: dict[str, float] = {}
            # CRON: hito actualmente enfocado por el recorrido cronológico.
            self._walk_highlight_id: str | None = None
            # CRON: pulso sostenido del hito mientras la IA analiza el paso.
            self._walk_pulse_id: str | None = None
            self._walk_pulse_phase = 0.0
            self._walk_pulse_timer = QTimer(self)
            self._walk_pulse_timer.setInterval(40)
            self._walk_pulse_timer.timeout.connect(self._walk_pulse_tick)
            self._bloom_timer = QTimer(self)
            self._bloom_timer.setInterval(40)
            self._bloom_timer.timeout.connect(self._bloom_tick)
            # BETA1-G08: misma atmósfera sutil de hojas que la concéntrica.
            from hosts.DesktopHostPySide.widgets.canvas_atmosphere import CanvasAtmosphere
            self._atmosphere = CanvasAtmosphere(self, ctx=None, count=11)

        def set_atmosphere_context(self, ctx) -> None:
            self._atmosphere.set_context(ctx)

        # ── BETA1-UX7: transposición logical(cross, time) ↔ escena ────────────
        # El layout puro razona en (cross = eje-anillo, time = eje-tiempo). En
        # horizontal el tiempo va al eje X y el anillo al Y; en vertical se queda
        # como estaba. Centralizar el mapeo aquí evita repartir la orientación
        # por todo el render y la interacción.

        def _pt(self, cross: float, time: float) -> "QPointF":
            """Coordenada lógica (cross, time) → punto de escena."""
            return QPointF(time, cross) if self._horizontal else QPointF(cross, time)

        def _time_axis(self, scene_point: "QPointF") -> float:
            """Componente de TIEMPO de un punto de escena."""
            return scene_point.x() if self._horizontal else scene_point.y()

        def _cross_axis(self, scene_point: "QPointF") -> float:
            """Componente de ANILLO (cross) de un punto de escena."""
            return scene_point.y() if self._horizontal else scene_point.x()

        def _add_line(self, scene, cross0, time0, cross1, time1, pen):
            """Añade a la escena una línea definida en coords lógicas."""
            p0 = self._pt(cross0, time0)
            p1 = self._pt(cross1, time1)
            return scene.addLine(p0.x(), p0.y(), p1.x(), p1.y(), pen)

        def _logical_rect(self, cross0, time0, cross1, time1) -> "QRectF":
            """QRectF (normalizado) de dos esquinas lógicas."""
            return QRectF(self._pt(cross0, time0), self._pt(cross1, time1)).normalized()

        def _drag_cursor(self):
            """Cursor de arrastre de mangos: a lo largo del eje del tiempo."""
            return (
                Qt.CursorShape.SizeHorCursor
                if self._horizontal
                else Qt.CursorShape.SizeVerCursor
            )

        def _apply_vignette(self, layout=None):
            """BETA1-UX feedback: MISMO mecanismo de fondo que la concéntrica —
            una viñeta radial cálida como ``backgroundBrush`` (no un fillRect
            opaco en drawBackground). Así ambas vistas COMPONEN igual (incluida
            cualquier transparencia de ventana del sistema) y comparten halo. El
            centro se sitúa en el corazón del contenido cronológico."""
            if layout is not None:
                # BETA1-UX7: centro en el corazón del contenido, transpuesto si
                # la cronología es horizontal.
                center = self._pt(layout.width / 2.0, (TOP_MARGIN + layout.height) / 2.0)
                cx = center.x()
                cy = center.y()
                radius = max(layout.width, layout.height, 600.0) * 0.62
            else:
                cx, cy, radius = 0.0, 0.0, 1500.0
            grad = QRadialGradient(QPointF(cx, cy), radius)
            for stop, hexc in _VIGNETTE:
                grad.setColorAt(stop, QColor(hexc))
            self.setBackgroundBrush(QBrush(grad))

        def drawBackground(self, painter, rect):  # noqa: N802 (Qt API)
            super().drawBackground(painter, rect)  # viñeta radial (backgroundBrush)
            self._atmosphere.paint(painter)

        def showEvent(self, event):  # noqa: N802 (Qt API)
            super().showEvent(event)
            self._atmosphere.start()

        def hideEvent(self, event):  # noqa: N802 (Qt API)
            self._atmosphere.stop()
            # BETA1-UX2D: para el glow al ocultar la vista; un timer vivo sobre una
            # escena que se reconstruirá al volver es un riesgo innecesario.
            self._bloom_timer.stop()
            super().hideEvent(event)

        # — construcción de escena —

        def set_project(self, project: Any) -> None:
            # BETA1-UX2D: guardamos el proyecto para poder RECONSTRUIR la escena bajo
            # demanda (única cura observada del artefacto "items que no se pintan").
            self._project = project
            # BETA1-UX2D (crash): reconstruir la escena NUNCA debe tumbar la app.
            # Si los datos del proyecto provocan una excepción al construir el
            # layout (años/eras/hitos inesperados), la registramos y dejamos una
            # escena vacía pero válida en lugar de propagar (un fallo en un slot
            # de Qt aborta el proceso). El traceback queda para diagnosticar.
            try:
                self._rebuild_scene(project)
            except Exception:  # noqa: BLE001 — robustez de UI por encima de todo
                import traceback
                traceback.print_exc()
                try:
                    self.scene().clear()
                except Exception:  # noqa: BLE001
                    pass
                self._layout = None
                self._lifeline_views = {}
                self._milestone_items = {}
                self._bloom_items = {}
                self._handle_drag = None
                self._press_handle = None

        def _rebuild_scene(self, project: Any) -> None:
            scene = self.scene()
            scene.clear()
            # SEM03: la escena se reconstruye; reinicia el lookup y el glow.
            self._milestone_items = {}
            self._bloom_items = {}
            self._lifeline_views = {}  # BETA1-UX2C: mangos de vida por entidad
            self._handle_drag = None
            self._press_handle = None
            self._bloom_timer.stop()
            if project is None:
                self._layout = None
                return
            # BETA1-HITO-MULTI: ensancha los carriles para que los nombres,
            # ahora CENTRADOS sobre cada línea, quepan sin solaparse. Mide el
            # nombre más ancho (en negrita para contenedores) con tope.
            name_metric = QFont("Georgia"); name_metric.setPointSize(9)
            fm_plain = QFontMetrics(name_metric)
            name_bold = QFont(name_metric); name_bold.setBold(True)
            fm_bold = QFontMetrics(name_bold)
            widest = 0.0
            for entity in list(getattr(project, "entities", []) or []):
                ename = str(getattr(entity, "name", "") or "Sin nombre")
                is_tree = _enum_value(getattr(entity, "entity_type", None)).lower() == "contenedor"
                adv = (fm_bold if is_tree else fm_plain).horizontalAdvance(ename)
                widest = max(widest, min(float(adv), NAME_MAX_PX))
            lane_width = max(LANE_WIDTH, widest + NAME_LANE_PAD)
            layout = build_chrono_layout(project, lane_width=lane_width)
            # BETA1-UX10: reservar hueco en el TIEMPO para el NOMBRE de cada hito
            # → dos hitos de años cercanos no solapan sus títulos. Se mide el ancho
            # real del título (en horizontal el footprint es el ancho; en vertical
            # la altura, mucho menor) y se reconstruye pasando el mínimo por año.
            if layout.milestones:
                title_fm = QFont("Georgia"); title_fm.setPointSize(9); title_fm.setItalic(True)
                fm_title = QFontMetrics(title_fm)
                min_gaps: dict[int, float] = {}
                for m in layout.milestones:
                    text = m.title + (f" · {m.sub_label}" if m.sub_label else "")
                    if self._horizontal:
                        foot = fm_title.horizontalAdvance(text) + 26.0
                    else:
                        foot = fm_title.height() + 12.0
                    min_gaps[m.year] = max(min_gaps.get(m.year, 0.0), foot)
                layout = build_chrono_layout(
                    project, lane_width=lane_width, milestone_min_gaps=min_gaps
                )
            self._layout = layout
            self._apply_vignette(layout)  # halo centrado en el contenido temporal

            # BETA1-UX: estratos de era con BISEL cálido (borde superior
            # iluminado → fondo en sombra), como las coronas de la concéntrica.
            # Profundidad sin contorno ni efectos gráficos.
            for band in layout.eras:
                h = max(band.y1 - band.y0, MIN_GAP_PX)
                # BETA1-UX7: el estrato cubre todo el eje ANILLO (0..width) y el
                # tramo de TIEMPO de la era (y0..y0+h). En horizontal es una
                # COLUMNA vertical; en vertical, una banda horizontal como antes.
                band_rect = self._logical_rect(0, band.y0, layout.width, band.y0 + h)
                rect = _EraBandItem(
                    band.era_id, band_rect.x(), band_rect.y(),
                    band_rect.width(), band_rect.height(),
                )
                # BETA1-UX feedback: cada era es un ESTRATO de color claramente
                # visible (antes casi transparente → "no aparecen las eras"). Su
                # tamaño en el eje del tiempo es proporcional a los años (YearScale):
                # una era de 200 años se ve ~10× más larga que una de 20.
                tint = QColor(_ERA_TINTS[band.index % len(_ERA_TINTS)])
                g0 = self._pt(0.0, band.y0)
                g1 = self._pt(0.0, band.y0 + h)
                grad = QLinearGradient(g0, g1)
                top = QColor(tint); top.setAlpha(82)
                mid = QColor(tint); mid.setAlpha(42)
                bot = QColor(tint); bot.setAlpha(60)
                grad.setColorAt(0.0, top)
                grad.setColorAt(min(0.18, 46.0 / h), mid)
                grad.setColorAt(1.0, bot)
                rect.setBrush(QBrush(grad))
                rect.setPen(QPen(Qt.PenStyle.NoPen))
                rect.setZValue(-30)
                scene.addItem(rect)
                # Filo iluminado + sombra fina que separa los estratos (la misma
                # sensación de relieve que las coronas) en el borde de inicio de era.
                hi_line = QColor("#FCF8EE"); hi_line.setAlpha(165)
                top_edge = self._add_line(scene, 0, band.y0, layout.width, band.y0, QPen(hi_line, 1.6))
                top_edge.setZValue(-29)
                sh_line = QColor(52, 47, 28); sh_line.setAlpha(46)
                shadow_edge = self._add_line(
                    scene, 0, band.y0 + 1.6, layout.width, band.y0 + 1.6, QPen(sh_line, 1.0)
                )
                shadow_edge.setZValue(-29)
                era_font = QFont("Georgia"); era_font.setPointSize(11); era_font.setItalic(True)
                years_text = f"{band.start_year} → {band.end_year if band.end_year is not None else '…'}"
                yr_font = QFont("Georgia"); yr_font.setPointSize(8)
                # BETA1-UX7: la etiqueta (nombre y rango) lleva el id de la era
                # para que clicar el NOMBRE abra la era (no solo el fondo).
                era_tag = (_ERA_ID_ROLE, band.era_id)
                if self._horizontal:
                    # BETA1-UX7: nombre y rango de años APILADOS (dos líneas) en la
                    # esquina superior-izquierda de la columna. Si fueran a la misma
                    # altura (mismo cross) con distinto tiempo se solaparían —el bug
                    # de la captura—; aquí el tiempo (X) los ancla al inicio de la
                    # era y el cross (Y) los separa en dos renglones.
                    label_x = self._pt(0, band.y0).x() + 10
                    name_max = max(80.0, min(band.y1 - band.y0 - 16.0, 360.0))
                    _add_pill_label(
                        scene, band.name, label_x, 10,
                        font=era_font, fg=_INK, z=8, max_w=name_max, tag=era_tag,
                    )
                    _add_pill_label(
                        scene, years_text, label_x, 32,
                        font=yr_font, fg=_MUTED, z=8, max_w=name_max, tag=era_tag,
                    )
                else:
                    name_at = self._pt(14, band.y0 + 8)
                    _add_pill_label(
                        scene, band.name, name_at.x(), name_at.y(),
                        font=era_font, fg=_INK, z=8, max_w=LEFT_MARGIN - 10, tag=era_tag,
                    )
                    years_at = self._pt(14, band.y0 + 32)
                    _add_pill_label(
                        scene, years_text, years_at.x(), years_at.y(),
                        font=yr_font, fg=_MUTED, z=8, max_w=LEFT_MARGIN - 10, tag=era_tag,
                    )

            # BETA1-UX9: cajas de rama (contenedores) que encierran a sus miembros.
            # Tras las eras y antes de las vidas; z entre ambas para que vidas,
            # cabezas y nombres queden por encima (interior "click-through": clic en
            # marco/cabecera/vacío abre la rama; clic en una vida/nombre va a esa
            # entidad). Exteriores primero (depth asc) para que las subcajas pinten
            # su borde sobre el interior de la madre.
            for box in sorted(layout.boxes, key=lambda b: b.depth):
                box_rect = self._logical_rect(box.x_left, box.y0, box.x_right, box.y1)
                box_item = _BranchBoxItem(
                    box.branch_id, box.color, box.depth, BOX_HEADER_PX, self._horizontal,
                    box_rect.x(), box_rect.y(), box_rect.width(), box_rect.height(),
                )
                scene.addItem(box_item)
                # Etiqueta nombre (+ recuento) en la cabecera; clic → abrir la rama.
                box_label = box.name if box.member_count <= 0 else f"{box.name}  ·  {box.member_count}"
                box_font = QFont("Georgia"); box_font.setPointSize(9); box_font.setBold(True)
                box_anchor = self._pt(box.x_left + BOX_LABEL_PAD, box.y0 + 6.0)
                _add_pill_label(
                    scene, box_label, box_anchor.x(), box_anchor.y(),
                    font=box_font, fg=_INK, z=9, max_w=240,
                    tag=(_ENTITY_ID_ROLE, box.branch_id),
                )

            # Cabeceras de columna (anillos — el lector conserva el mapa mental).
            # BETA1-UX7: en horizontal pasan al margen izquierdo, centradas en su
            # carril; en vertical quedan arriba, centradas en su columna.
            for column in layout.columns:
                header = QGraphicsSimpleTextItem(column.name)
                header.setBrush(QBrush(_MUTED))
                font = QFont("Georgia")
                font.setPointSize(9)
                header.setFont(font)
                r = header.boundingRect()
                base = self._pt(column.x_center, TOP_MARGIN - 46)
                if self._horizontal:
                    header.setPos(base.x() - r.width(), base.y() - r.height() / 2.0)
                else:
                    header.setPos(base.x() - r.width() / 2.0, base.y())
                scene.addItem(header)

            # Línea del presente (cruza todo el eje anillo a la posición de tiempo
            # del presente: horizontal → línea vertical; vertical → horizontal).
            present_pen = QPen(QColor(_LINE.red(), _LINE.green(), _LINE.blue(), 90), 1, Qt.PenStyle.DashLine)
            self._add_line(scene, 0, layout.y_present, layout.width, layout.y_present, present_pen)
            present_label = QGraphicsSimpleTextItem(f"presente · {layout.present_year}")
            present_label.setBrush(QBrush(QColor(_MUTED.red(), _MUTED.green(), _MUTED.blue(), 190)))
            tiny = QFont("Georgia")
            tiny.setPointSize(8)
            tiny.setItalic(True)
            present_label.setFont(tiny)
            pr = present_label.boundingRect()
            pbase = self._pt(layout.width, layout.y_present)
            if self._horizontal:
                present_label.setPos(pbase.x() - pr.width() - 4, pbase.y() - pr.height() - 16)
            else:
                present_label.setPos(pbase.x() - pr.width() - 16, pbase.y() - 16)
            scene.addItem(present_label)

            # Líneas de vida. BETA1-UX7: cada vida es una línea a lo largo del eje
            # del TIEMPO a su posición de ANILLO; en horizontal queda horizontal.
            for lifeline in layout.lifelines:
                width = 3.4 if lifeline.is_tree else 2.2
                pen = QPen(QColor(_LINE.red(), _LINE.green(), _LINE.blue(), 200), width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p0 = self._pt(lifeline.x, lifeline.y_birth)
                p1 = self._pt(lifeline.x, lifeline.y_end)
                line = _LifelineLine(p0.x(), p0.y(), p1.x(), p1.y(), lifeline.entity_id)
                line.setPen(pen)
                line.setZValue(10)
                scene.addItem(line)  # diana ancha: clic en/junto a la línea → abrir entidad
                if lifeline.alive:
                    # Continúa: trazo que se desvanece más allá del presente
                    fade = QPen(QColor(_LINE.red(), _LINE.green(), _LINE.blue(), 60), width, Qt.PenStyle.DotLine)
                    self._add_line(
                        scene, lifeline.x, lifeline.y_end, lifeline.x, lifeline.y_end + 26, fade
                    ).setZValue(10)
                else:
                    # Remate sutil de muerte: tick perpendicular a la vida.
                    cap = QPen(QColor(_LINE.red(), _LINE.green(), _LINE.blue(), 150), 2)
                    self._add_line(
                        scene, lifeline.x - 6, lifeline.y_end, lifeline.x + 6, lifeline.y_end, cap
                    ).setZValue(10)
                arrows = "←/→" if self._horizontal else "↑/↓"
                head = _LifelineHead(lifeline, 8.0 if lifeline.is_tree else 6.5)
                head.setPos(self._pt(lifeline.x, lifeline.y_birth))
                head.setCursor(self._drag_cursor())
                head.setToolTip(f"Arrastra {arrows} para cambiar el año de origen · doble clic: abrir")
                scene.addItem(head)
                # BETA1-UX2C: mango de fin arrastrable + registro para editar el
                # lapso estirando el nodo.
                end_handle = _LifelineEndHandle(lifeline)
                end_handle.setPos(self._pt(lifeline.x, lifeline.y_end))
                end_handle.setCursor(self._drag_cursor())
                end_handle.setToolTip(
                    f"Arrastra {arrows} para cambiar el año de fin · llévalo al presente "
                    "para marcar que sigue viva"
                )
                scene.addItem(end_handle)
                self._lifeline_views[lifeline.entity_id] = {
                    "line": line,
                    "head": head,
                    "end": end_handle,
                    "x": lifeline.x,
                    "birth": lifeline.birth_year,
                    "death": lifeline.death_year,
                }
                # BETA1-HITO-MULTI: nombre CENTRADO sobre su línea, SIN recuadro
                # (texto suelto), y POR ENCIMA del nodo para no taparlo (el nodo
                # marca el origen y debe quedar libre para arrastrar el lapso).
                # Los carriles ya son lo bastante anchos (lane_width dilatado al
                # nombre más ancho), así que las etiquetas no se solapan.
                name_font = QFont("Georgia")
                name_font.setPointSize(9)
                if lifeline.is_tree:
                    name_font.setBold(True)
                shown = QFontMetrics(name_font).elidedText(
                    lifeline.name, Qt.TextElideMode.ElideRight, int(lane_width - 12.0)
                )
                name_item = QGraphicsSimpleTextItem(shown)
                name_item.setFont(name_font)
                name_item.setBrush(QBrush(_INK))
                r = name_item.boundingRect()
                head_r = 8.0 if lifeline.is_tree else 6.5
                # BETA1-UX7: el nombre va junto al origen sin tapar el nodo.
                # Horizontal: ENCIMA de la línea (desplazado en el eje anillo) y
                # anclado al origen leyendo hacia la derecha → SIEMPRE visible (a
                # la izquierda del origen se salía por el borde izquierdo para las
                # entidades más antiguas, que es justo donde el clic fallaba).
                # Vertical: encima, centrado en el carril.
                nbase = self._pt(lifeline.x, lifeline.y_birth)
                if self._horizontal:
                    name_item.setPos(
                        nbase.x() - head_r,
                        nbase.y() - head_r - 6.0 - r.height(),
                    )
                else:
                    name_item.setPos(
                        nbase.x() - r.width() / 2.0,
                        nbase.y() - head_r - 8.0 - r.height(),
                    )
                name_item.setZValue(31)
                name_item.setData(_ENTITY_ID_ROLE, lifeline.entity_id)  # clic en el nombre → abrir entidad
                scene.addItem(name_item)

            # Hitos: cada hito es una FRANJA horizontal a la altura de su año que
            # cruza todo el grafo, con un punto por entidad participante
            # (BETA1-HITO-MULTI). Los hitos del MISMO año comparten "caja": el año
            # se rotula UNA sola vez a la izquierda (centrado en la caja) y cada
            # franja lleva su título a la derecha del año; mes/día (sub_label)
            # desambiguan dentro de la caja. Los rótulos viven dentro del área del
            # grafo (a la derecha del margen de eras) para no chocar con ellas.
            self._milestone_items = {}
            year_font = QFont("Georgia"); year_font.setPointSize(8)
            title_font = QFont("Georgia"); title_font.setPointSize(9); title_font.setItalic(True)
            band_x1 = max(layout.width, LEFT_MARGIN + COLUMN_GAP)
            label_x = LEFT_MARGIN + 12.0
            year_tag_w = 56.0
            boxes: dict[int, list] = {}
            for mark in layout.milestones:
                boxes.setdefault(mark.year, []).append(mark)
            for year, box in boxes.items():
                cy = sum(m.y_band for m in box) / len(box)
                # Año una sola vez por caja, junto al inicio del eje anillo,
                # centrado en la posición de tiempo de la caja.
                year_at = self._pt(label_x, cy - 7.0)
                _add_pill_label(
                    scene, f"Año {year}", year_at.x(), year_at.y(),
                    font=year_font, fg=_MUTED, z=34, max_w=year_tag_w + 28.0,
                )
                # BETA1-UX10b: los hitos del MISMO año comparten posición de
                # tiempo (ensanchar el eje no puede separarlos), así que sus
                # TÍTULOS se apilan en el eje PERPENDICULAR (cross) — en
                # horizontal hacia abajo, en vertical hacia un lado — para que no
                # se solapen. Un solo hito por año conserva su sitio exacto.
                title_step = QFontMetrics(title_font).height() + 8.0
                title_base_cross = label_x + year_tag_w + 10.0
                for stack_i, mark in enumerate(box):
                    y = mark.y_band
                    items: list = []
                    band = _MilestoneBand(mark, LEFT_MARGIN, band_x1, self._horizontal)
                    scene.addItem(band)
                    items.append(band)
                    # Título junto al año, pegado a su franja; mes/día desambiguan
                    # los hitos de la misma caja.
                    title_text = mark.title
                    if mark.sub_label:
                        title_text += f" · {mark.sub_label}"
                    title_at = self._pt(
                        title_base_cross + stack_i * title_step, y - 9.0
                    )
                    _add_pill_label(
                        scene, title_text, title_at.x(), title_at.y(),
                        font=title_font, fg=_INK, z=34, max_w=300,
                        tag=(_MILESTONE_ID_ROLE, mark.milestone_id),
                    )
                    # Un punto SÓLIDO por entidad ya vinculada (intersección
                    # franja↔carril); clicarlo abre el hito.
                    for ex, eid in zip(mark.entity_xs, mark.entity_ids):
                        node = _MilestoneNode(mark, entity_id=eid)
                        node.setPos(self._pt(ex, y))
                        scene.addItem(node)
                        items.append(node)
                    # Fantasmas TENUES en los cruces de entidades NO vinculadas
                    # (dentro de su lapso de vida): clicarlos vincula la entidad.
                    linked = set(mark.entity_ids)
                    for lifeline in layout.lifelines:
                        if lifeline.entity_id in linked:
                            continue
                        if not (lifeline.birth_year <= mark.year and (
                            lifeline.death_year is None or mark.year <= lifeline.death_year
                        )):
                            continue
                        ghost = _GhostNode(mark.milestone_id, lifeline.entity_id)
                        ghost.setPos(self._pt(lifeline.x, y))
                        scene.addItem(ghost)  # fuera de la lista de bloom (no germina)
                    self._milestone_items[mark.milestone_id] = items

            rect = self._logical_rect(0, 0, layout.width, layout.height)
            scene.setSceneRect(rect.adjusted(-60, -60, 60, 60))

        def bloom_milestone(self, milestone_id: str) -> bool:
            # SEM03: germina la marca del hito recién creado. No-op si la vista
            # cronológica no está construida o no contiene ese hito.
            if milestone_id not in self._milestone_items:
                return False
            self._bloom_items[milestone_id] = 0.0
            if not self._bloom_timer.isActive():
                self._bloom_timer.start()
            return True

        def center_on_milestone(self, milestone_id: str, *, highlight: bool = True) -> bool:
            """CRON: centra la cámara en el hito actual del recorrido y lo resalta.

            Sin animación suave (eso queda para la épica de UX visual): usa el
            ``centerOn`` nativo de QGraphicsView. Devuelve False si la vista no
            está construida o no contiene ese hito.
            """
            key = str(milestone_id)
            items = self._milestone_items.get(key) or []
            if not items:
                return False
            self.centerOn(items[0])
            if highlight:
                self._walk_highlight_id = key
                # Reusa la germinación como pulso de foco (no muta canon).
                self.bloom_milestone(key)
            return True

        def clear_walk_highlight(self) -> None:
            """CRON: quita el resaltado del hito del recorrido."""
            self.stop_walk_pulse()
            key = self._walk_highlight_id
            self._walk_highlight_id = None
            if key is None:
                return
            self._bloom_items.pop(key, None)
            for item in self._milestone_items.get(key) or []:
                setter = getattr(item, "set_bloom_phase", None)
                if callable(setter):
                    setter(0.0)

        def start_walk_pulse(self, milestone_id: str) -> bool:
            """CRON: enfoca la cámara en el hito y emite un PULSO SOSTENIDO desde su
            posición mientras la IA analiza. Devuelve False si no está en la vista."""
            key = str(milestone_id)
            items = self._milestone_items.get(key) or []
            if not items:
                return False
            self.centerOn(items[0])
            self._walk_highlight_id = key
            self._walk_pulse_id = key
            self._walk_pulse_phase = 0.0
            if not self._walk_pulse_timer.isActive():
                self._walk_pulse_timer.start()
            return True

        def stop_walk_pulse(self) -> None:
            """CRON: detiene el pulso sostenido (al llegar el resultado del paso)."""
            if self._walk_pulse_timer.isActive():
                self._walk_pulse_timer.stop()
            key = self._walk_pulse_id
            self._walk_pulse_id = None
            for item in self._milestone_items.get(key) or []:
                setter = getattr(item, "set_bloom_phase", None)
                if callable(setter):
                    setter(0.0)

        def _walk_pulse_tick(self) -> None:
            key = self._walk_pulse_id
            items = self._milestone_items.get(key) or []
            if not items:
                self.stop_walk_pulse()
                return
            # Oscilación 0→1→0 (triángulo) para un latido continuo de "analizando".
            self._walk_pulse_phase = (self._walk_pulse_phase + 0.06) % 1.0
            tri = self._walk_pulse_phase * 2.0
            phase = tri if tri <= 1.0 else 2.0 - tri
            for item in items:
                setter = getattr(item, "set_bloom_phase", None)
                if callable(setter):
                    setter(phase)

        def _bloom_tick(self) -> None:
            for key in list(self._bloom_items):
                phase = self._bloom_items[key] + 0.05
                items = self._milestone_items.get(key) or []
                if not items or phase >= 1.0:
                    self._bloom_items.pop(key, None)
                    for item in items:
                        item.set_bloom_phase(0.0)
                    continue
                self._bloom_items[key] = phase
                for item in items:
                    item.set_bloom_phase(phase)
            if not self._bloom_items:
                self._bloom_timer.stop()

        # — interacción (coherente con la concéntrica: zoom/pan/Space) —

        def wheelEvent(self, event):  # noqa: N802
            # BETA1-UX2D: gate asimétrico (ver zoom_step). La cronología es muy
            # alta; fit_all deja m11≈0.10 y el gate combinado anterior bloqueaba
            # todo acercamiento.
            factor = zoom_step(self.transform().m11(), event.angleDelta().y() > 0)
            if factor is not None:
                self.scale(factor, factor)
            event.accept()

        def keyPressEvent(self, event):  # noqa: N802
            if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
                self._space_panning = True
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                event.accept()
                return
            if event.key() == Qt.Key.Key_Escape:
                self.scene().clearSelection()
                self.escapePressed.emit()
                event.accept()
                return
            super().keyPressEvent(event)

        def keyReleaseEvent(self, event):  # noqa: N802
            if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
                self._space_panning = False
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                event.accept()
                return
            super().keyReleaseEvent(event)

        # — BETA1-UX2C: editar el lapso de vida estirando el nodo —

        def _handle_at(self, pos):
            """(entity_id, role) del mango bajo *pos* (coords de viewport), o None."""
            item = self.itemAt(pos)
            while item is not None:
                if isinstance(item, _LifelineEndHandle):
                    return item.entity_id, "death"
                if isinstance(item, _LifelineHead):
                    return item.entity_id, "birth"
                item = item.parentItem()
            return None

        def _begin_handle_drag(self, entity_id: str, role: str) -> None:
            self._handle_drag = {"entity_id": entity_id, "role": role}

        def _set_lifeline_line(self, line, cross: float, t0: float, t1: float) -> None:
            """Reposiciona una línea de vida (constante en el anillo, t0→t1 en el
            eje del tiempo), respetando la orientación."""
            p0 = self._pt(cross, t0)
            p1 = self._pt(cross, t1)
            line.setLine(p0.x(), p0.y(), p1.x(), p1.y())

        def _update_handle_drag(self, time_value: float) -> None:
            """Mueve en vivo el mango/línea al año bajo el cursor (snap a entero).

            ``time_value`` es la coordenada de ESCENA en el eje del TIEMPO (X en
            horizontal, Y en vertical). Recalcula ambos extremos desde los años
            pendientes, así no depende de leer la geometría de la línea."""
            drag = self._handle_drag
            if not drag or self._layout is None or self._layout.scale is None:
                return
            info = self._lifeline_views.get(drag["entity_id"])
            if info is None:
                return
            scale = self._layout.scale
            present = int(self._layout.present_year)
            cross = info["x"]
            line = info["line"]
            year = scale.year_at(time_value)
            if drag["role"] == "birth":
                death = info.get("death_pending", info["death"])
                upper = death if death is not None else present
                year = min(year, upper)  # origen ≤ fin/presente
                info["birth_pending"] = year
                birth_t = scale.y(year)
                end_year = info.get("death_pending", info["death"])
                end_t = scale.y(end_year if end_year is not None else present)
                self._set_lifeline_line(line, cross, birth_t, end_t)
                info["head"].setPos(self._pt(cross, birth_t))
            else:  # fin / muerte
                birth = info.get("birth_pending", info["birth"])
                if year >= present:  # al/ más allá del presente ⇒ sigue viva
                    info["death_pending"] = None
                    end_t = scale.y(present)
                else:
                    year = max(year, birth)  # fin ≥ origen
                    info["death_pending"] = year
                    end_t = scale.y(year)
                birth_t = scale.y(info.get("birth_pending", info["birth"]))
                self._set_lifeline_line(line, cross, birth_t, end_t)
                info["end"].setPos(self._pt(cross, end_t))

        def _finish_handle_drag(self):
            drag = self._handle_drag
            self._handle_drag = None
            if not drag:
                return None
            info = self._lifeline_views.get(drag["entity_id"])
            if info is None:
                return None
            birth = int(info.get("birth_pending", info["birth"]) or 0)
            death = info["death_pending"] if "death_pending" in info else info["death"]
            if death is not None:
                death = int(death)
                if death < birth:
                    death = birth
            info["birth"], info["death"] = birth, death
            info.pop("birth_pending", None)
            info.pop("death_pending", None)
            self.lifespanEdited.emit(drag["entity_id"], birth, death)
            return drag["entity_id"], birth, death

        def mousePressEvent(self, event):  # noqa: N802
            if event.button() == Qt.MouseButton.LeftButton and not self._space_panning:
                self._press_pos = event.position()  # ancla clic/arrastre (mangos)
                hit = self._handle_at(event.position().toPoint())
                if hit is not None:
                    self._press_handle = hit
                    self._handle_moved = False
                    event.accept()
                    return
                # NoDrag: el clic izquierdo NUNCA arrastra el lienzo (el paneo es con
                # barra espaciadora), así que un clic sobre un item se resuelve YA, en
                # el PRESS. Hacerlo aquí —y no en el release— lo hace inmune al umbral
                # de movimiento y al orden de super(), que con el ratón real impedían
                # que el clic llegara a vincular/abrir (BETA1-HITO-MULTI).
                if self._dispatch_click(event.position().toPoint()):
                    event.accept()
                    return
            super().mousePressEvent(event)

        def _dispatch_click(self, view_pos) -> bool:
            # BETA1-HITO-MULTI: clic simple → abrir panel (entidad/hito/era) o
            # vincular (fantasma), como en el resto de la app. Devuelve True si
            # algo respondió al clic.
            # BETA1-UX7: el carril (anillo) vive en el eje cruzado al tiempo.
            scene_cross = (
                self._cross_axis(self.mapToScene(view_pos)) if view_pos is not None else None
            )
            item = self.itemAt(view_pos)
            while item is not None:
                if isinstance(item, _GhostNode):
                    # Cruce no vinculado → vincular la entidad al hito.
                    self.milestoneEntityLinkRequested.emit(item.milestone_id, item.entity_id)
                    return True
                if isinstance(item, _MilestoneNode):
                    # Intersección ya vinculada → abrir el HITO (la entidad sigue
                    # accesible por su línea de vida / nombre). El punto sólido
                    # representa la participación en el hito, así que abrirlo lleva
                    # al hito, no al personaje.
                    self.milestoneActivated.emit(item.milestone_id)
                    return True
                if isinstance(item, _MilestoneBand):
                    # Clic SOBRE la franja: resolver por el carril más cercano
                    # (la diana real es ancha, no el puntito), así un clic en la
                    # intersección vincula/abre la entidad aunque no acierte el
                    # marcador. Entre carriles → abre el hito.
                    return self._resolve_band_click(item.milestone_id, scene_cross)
                if isinstance(item, _LifelineHead):
                    self.entityActivated.emit(item.entity_id)
                    return True
                if isinstance(item, _EraBandItem):
                    self.eraActivated.emit(item.era_id)
                    return True
                mid = item.data(_MILESTONE_ID_ROLE)  # título del hito → abrir hito
                if mid:
                    self.milestoneActivated.emit(str(mid))
                    return True
                eid = item.data(_ENTITY_ID_ROLE)  # nombre/línea → abrir entidad
                if eid:
                    self.entityActivated.emit(str(eid))
                    return True
                era = item.data(_ERA_ID_ROLE)  # etiqueta de era → abrir/editar era
                if era is not None:
                    self.eraActivated.emit(str(era))
                    return True
                item = item.parentItem()
            return False

        def _resolve_band_click(self, milestone_id, scene_cross) -> bool:
            # BETA1-HITO-MULTI: un clic sobre la franja se atribuye al carril de
            # entidad MÁS CERCANO (±BAND_LANE_TOL px): si ya está vinculada → abre
            # su panel; si no y está viva ese año → la vincula; entre carriles
            # (lejos de todo carril) → abre el hito. ``scene_cross`` es la posición
            # en el eje del anillo (BETA1-UX7).
            layout = self._layout
            if layout is None or scene_cross is None or not layout.lifelines:
                self.milestoneActivated.emit(str(milestone_id))
                return True
            nearest = min(layout.lifelines, key=lambda lf: abs(lf.x - scene_cross))
            if abs(nearest.x - scene_cross) > BAND_LANE_TOL:
                self.milestoneActivated.emit(str(milestone_id))
                return True
            mark = next(
                (m for m in layout.milestones if m.milestone_id == str(milestone_id)), None
            )
            linked = set(mark.entity_ids) if mark is not None else set()
            if nearest.entity_id in linked:
                # Intersección ya vinculada → abrir el HITO (coherente con el clic
                # sobre el punto sólido).
                self.milestoneActivated.emit(str(milestone_id))
            elif mark is not None and nearest.birth_year <= mark.year and (
                nearest.death_year is None or mark.year <= nearest.death_year
            ):
                self.milestoneEntityLinkRequested.emit(str(milestone_id), nearest.entity_id)
            else:
                self.milestoneActivated.emit(str(milestone_id))
            return True

        def mouseMoveEvent(self, event):  # noqa: N802
            if self._press_handle is not None:
                # BETA1-UX2D: hasta superar el umbral, es un CLIC (no relocaliza
                # el mango). Solo a partir de ahí empieza el arrastre real.
                if not self._handle_moved and (
                    (event.position() - self._press_pos).manhattanLength()
                    <= _handle_drag_threshold()
                ):
                    event.accept()
                    return
                if self._handle_drag is None:
                    self._begin_handle_drag(*self._press_handle)
                time_value = self._time_axis(self.mapToScene(event.position().toPoint()))
                self._update_handle_drag(time_value)
                self._handle_moved = True
                event.accept()
                return
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event):  # noqa: N802
            rebuilt_elsewhere = False
            click_entity = None
            if self._press_handle is not None:
                handle = self._press_handle
                self._press_handle = None
                if self._handle_drag is not None and self._handle_moved:
                    # Editar el lapso ya dispara un refresh (rebuild) en el workspace.
                    self._finish_handle_drag()
                    rebuilt_elsewhere = True
                else:
                    # Clic (sin arrastre) sobre el nodo de una entidad → abrir su panel.
                    self._handle_drag = None
                    click_entity = handle[0]
                event.accept()
            else:
                # El abrir/vincular ya se resolvió en el press (NoDrag); aquí solo
                # se cierra el gesto y se cura el artefacto de render.
                super().mouseReleaseEvent(event)
            if click_entity:
                self.entityActivated.emit(click_entity)
            # BETA1-UX2D (items que "desaparecen" al clicar): el diagnóstico
            # (DENDRO_CHRONO_DEBUG) PROBÓ que tras el clic los items siguen en la
            # escena, visibles, opacos y en vista — pero la PANTALLA no los refleja,
            # y NI un repintado síncrono NI redimensionar/minimizar lo curan. La
            # ÚNICA cura observada es RECONSTRUIR la escena (recrear los QGraphicsItem
            # — lo que ya ocurre al editar un lapso o al salir/entrar). Así que tras
            # un clic que no haya reconstruido ya, forzamos esa reconstrucción de
            # forma DIFERIDA (se ejecuta tras desenrollar el evento; preserva
            # zoom/scroll porque set_project no toca la transformación de la vista).
            if not rebuilt_elsewhere:
                self._schedule_scene_rebuild()
            self._debug_dump_items("release")

        def _schedule_scene_rebuild(self) -> None:
            """Reconstruye la escena en el próximo ciclo del event loop (cura el
            artefacto de render). No-op si aún no hay proyecto cargado."""
            project = getattr(self, "_project", None)
            if project is not None and not self._rebuild_pending:
                self._rebuild_pending = True
                QTimer.singleShot(0, self._do_scheduled_rebuild)

        def _do_scheduled_rebuild(self) -> None:
            self._rebuild_pending = False
            project = getattr(self, "_project", None)
            if project is not None:
                self.set_project(project)

        def _debug_dump_items(self, tag: str) -> None:
            """Diagnóstico opt-in: con DENDRO_CHRONO_DEBUG vuelca el estado de cada
            etiqueta tras una interacción, para cazar items que el render salta."""
            import os
            if not os.environ.get("DENDRO_CHRONO_DEBUG"):
                return
            view_rect = self.mapToScene(self.viewport().rect()).boundingRect()
            for item in self.scene().items():
                if isinstance(item, (QGraphicsSimpleTextItem, QGraphicsPathItem)):
                    br = item.sceneBoundingRect()
                    label = item.text()[:28] if isinstance(item, QGraphicsSimpleTextItem) else "<pill>"
                    print(
                        f"[chrono-dbg {tag}] '{label}' vis={item.isVisible()} "
                        f"op={item.opacity():.2f} z={item.zValue():.1f} "
                        f"br=({br.x():.0f},{br.y():.0f} {br.width():.0f}x{br.height():.0f}) "
                        f"inView={view_rect.intersects(br)}",
                        flush=True,
                    )

        def mouseDoubleClickEvent(self, event):  # noqa: N802
            # Misma semántica que el clic simple (única fuente de verdad).
            if self._dispatch_click(event.position().toPoint()):
                event.accept()
                return
            super().mouseDoubleClickEvent(event)

        def _milestone_id_at(self, view_pos) -> str:
            """CRON: id del hito bajo el cursor (marca, franja o título), o ''."""
            item = self.itemAt(view_pos)
            while item is not None:
                if isinstance(item, (_MilestoneNode, _MilestoneBand)):
                    return str(item.milestone_id)
                mid = item.data(_MILESTONE_ID_ROLE)
                if mid:
                    return str(mid)
                item = item.parentItem()
            return ""

        def contextMenuEvent(self, event):  # noqa: N802
            # BETA1-HITO-MULTI: clic derecho sobre una era → solicitar crear un
            # hito ahí. El año se sugiere desde la posición (acotado a la era).
            # El panel lo muestra el workspace como overlay interno (no ventana).
            layout = getattr(self, "_layout", None)
            if layout is None:
                return super().contextMenuEvent(event)
            # CRON: clic derecho SOBRE un hito → iniciar/continuar el recorrido aquí.
            milestone_id = self._milestone_id_at(event.pos())
            if milestone_id:
                menu = QMenu(self)
                walk_action = menu.addAction("Iniciar/continuar creación cronológica desde aquí")
                if menu.exec(event.globalPos()) is walk_action:
                    self.walkRequested.emit(milestone_id)
                event.accept()
                return
            # BETA1-UX7: el año bajo el cursor está en el eje del tiempo.
            t = self._time_axis(self.mapToScene(event.pos()))
            era = next((b for b in layout.eras if b.y0 <= t <= b.y1), None)
            menu = QMenu(self)
            label = f"Crear hito en «{era.name}»…" if era is not None else "Crear hito aquí…"
            action = menu.addAction(label)
            if menu.exec(event.globalPos()) is not action:
                event.accept()
                return
            year = int(layout.scale.year_at(t)) if layout.scale is not None else 0
            if era is not None:
                hi = era.end_year if era.end_year is not None else year
                year = max(era.start_year, min(year, max(hi, era.start_year)))
            self.milestoneCreateRequested.emit(year, era.name if era is not None else "")
            event.accept()

        def fit_all(self) -> None:
            if self.scene().items():
                self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
                if self.transform().m11() > 1.0:
                    self.resetTransform()


__all__ = [
    "ChronoLayout",
    "EraBand",
    "Lifeline",
    "MilestoneMark",
    "RingColumn",
    "YearScale",
    "build_chrono_layout",
    "zoom_step",
]
if HAS_QT:
    __all__.append("ChronoCanvasView")
