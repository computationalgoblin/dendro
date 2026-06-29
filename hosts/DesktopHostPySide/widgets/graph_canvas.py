"""Graph canvas for B31-T03/B31-T06.

Visual graph derived from the active project. The graph is a view over existing
entities and relations; relation creation is emitted as an intent and executed
outside the canvas through application services.
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, replace
from typing import Any

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QLineF,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QStyle,
    QStyleOptionGraphicsItem,
    QStyleOptionSlider,
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
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.canvas_atmosphere import CanvasAtmosphere
from hosts.DesktopHostPySide.widgets.chrono_canvas import effective_eras, effective_present_year
from hosts.DesktopHostPySide.widgets.gpu_viewport import install_gpu_viewport
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_alive
from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    ENTITY_KIND_PALETTE,
    RELATION_KIND_PALETTE,
    TICK_INTERVAL,
    EmptyState,
    enum_human,
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE,
    RADIUS_LG,
    SPACE_2XL,
    SURFACE,
    SURFACE_HI,
)
from packages.application.world_layer_causal import get_causal_rank, sort_layers_by_causal_rank
from packages.domain.world_layer import default_world_layers
from packages.ui.graph_physics import (
    UNCLASSIFIED_RING_ID,
    Body,
    PhysicsEngine,
    Spring,
    resolve_effective_ring_id,
)


def _env_positive_int(name: str, default: int) -> int:
    """Entero positivo desde entorno con fallback (override de tuners L01)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


# BETA1-L01: umbral de "modo rendimiento". Por encima de este nº de cuerpos
# top-level en el motor global, el grafo deja de recalcular los anillos por
# frame (O(n)) y la física hace ráfagas de asentamiento ACOTADAS (autofreeze) en
# vez de correr en vivo indefinidamente tras cada cambio. Conserva la sensación
# "viva" en proyectos pequeños/medianos; en enormes prioriza la usabilidad.
PHYSICS_LIVE_MAX_BODIES = _env_positive_int("NARRATIVE_PHYSICS_LIVE_MAX_BODIES", 300)
# Frames máximos por ráfaga de asentamiento en modo rendimiento (16 ms/frame →
# 75 ≈ 1.2 s). Para antes lo que ocurra: convergencia por energía o fin del presupuesto.
PHYSICS_SETTLE_FRAME_BUDGET = _env_positive_int("NARRATIVE_PHYSICS_SETTLE_FRAMES", 75)
# BETA1-L01: por encima de este nº de items visibles se PAUSA la brisa de fondo
# (atmósfera). Es decorativa, pero su timer hace `viewport.update()` ~18 veces/seg
# y, con viewport GL (repintado total), eso REPINTA todo el grafo de forma continua
# aunque nada se mueva ni la física esté activa. Con cientos de nodos el coste del
# repintado permanente supera con creces el valor del adorno. Override por entorno.
ATMOSPHERE_MAX_ITEMS = _env_positive_int("NARRATIVE_ATMOSPHERE_MAX_ITEMS", 250)
# BETA1-L01: instrumentación de pintado. NARRATIVE_PERF_LOG=1 imprime cada ~1s:
# pintados/seg (si es >0 en reposo → repintado continuo), ms medio/máx por frame
# y si el viewport es GL. Cero coste cuando está apagado.
_PERF_LOG = os.environ.get("NARRATIVE_PERF_LOG", "").strip() in {"1", "true", "True"}
# BETA1-L01: nivel de detalle (LOD) del lienzo. Visto de lejos (zoom out) se
# pintan TODOS los nodos visibles a la vez; el texto es ilegible y el halo de 3
# pasadas con antialiasing por nodo cuesta cientos de ms con ~779 nodos. Por
# debajo de estos LOD se pinta barato o se omite. De cerca (pocos nodos) detalle
# completo. lod = 1.0 ≈ 1:1; <1 = alejado.
# Detalle COMPLETO (halo de 3 pasadas + texto + hover/selección) solo de cerca.
_NODE_FULL_LOD = float(os.environ.get("NARRATIVE_NODE_FULL_LOD", "") or 0.55)
# Por debajo de esto: nodo MÍNIMO (punto liso con antialiasing). Entre _NODE_MIN_LOD
# y _NODE_FULL_LOD: tier MEDIO — antialiasing + UNA pasada de halo cálido + relleno
# (se ve bien de lejos a una fracción del coste). El texto aparece con el detalle
# completo. Todos los valores son ajustables por entorno.
_NODE_MIN_LOD = float(os.environ.get("NARRATIVE_NODE_MIN_LOD", "") or 0.12)
_LABEL_MIN_LOD = _NODE_FULL_LOD

# BETA1-L02: navegación / zoom. Paso por gesto de rueda y techo de acercamiento.
# El SUELO de alejamiento es dinámico (ver _min_zoom): para grafos pequeños es
# _ZOOM_OUT_FLOOR, pero para grafos enormes baja hasta la escala que enmarca todo
# el contenido — antes estaba fijo en 0.22 y no dejaba ver el grafo completo.
_ZOOM_STEP = 1.08
_ZOOM_MAX = 3.0
_ZOOM_OUT_FLOOR = 0.22


class _LodTextItem(QGraphicsSimpleTextItem):
    """BETA1-L01: etiqueta que NO se pinta con zoom bajo. Rasterizar cientos de
    etiquetas ilegibles domina el coste al ver el grafo entero; de cerca (pocos
    nodos visibles) se pinta con normalidad."""

    def paint(self, painter, option, widget=None):  # noqa: N802 (Qt signature)
        if option.levelOfDetailFromTransform(painter.worldTransform()) < _LABEL_MIN_LOD:
            return
        super().paint(painter, option, widget)


def _paint_inner_halo(painter: QPainter, path: QPainterPath):
    """BETA1-F05: feedback de selección — halo oscuro INTERNO en el contorno
    de la forma, como si el elemento se hundiera en el lienzo. Sustituye al
    marco azul. Tres pasadas concéntricas con alpha decreciente, recortadas
    al interior de la forma."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setClipPath(path)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for width, alpha in ((16.0, 22), (9.0, 40), (4.0, 66)):
        pen = QPen(QColor(58, 54, 36, alpha), width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)
    painter.restore()


def _b44trace(message: str):
    """Temporary B44 diagnostic trace; remove after Windows repro is diagnosed."""
    print(f"B44TRACE {message}", flush=True)


# BETA1-UX04: paleta de tipos BOTÁNICA y CÁLIDA — vive como halo sutil de la
# hoja (no como relleno). Antes eran azules/lavandas/mentas frías (#7C9BFF…)
# que rompían el pergamino+oro; ahora son tonos de tierra, savia y arcilla que
# armonizan con la identidad. Distintos entre sí, todos cálidos.
# BETA1-UX06: movimiento de cámara "expresivo pero elegante". Las transiciones
# explícitas (encajar, centrar, enfocar) se deslizan en vez de saltar. El gate
# permite desactivarlo (tests/capturas) para llegar al encuadre final al
# instante (las animaciones no terminan con processEvents sin tiempo real).
MOTION_ENABLED = True
_CAM_MS = 360  # ~MOTION_SLOW
# BETA1-L02c: foco de anillo "inmersivo" (como introducirse en él). La cámara del
# foco usa una transición más larga y de desaceleración profunda; los vecinos
# (anillo de dentro y de fuera) quedan tenues pero visibles, y el encuadre es algo
# más amplio para que asomen. Afinables por si el feel necesita retoque.
_RING_FOCUS_CAM_MS = 600  # transición del foco de anillo (resto de cámaras = _CAM_MS)
_RING_NEIGHBOR_OPACITY = 0.18  # opacidad de nodos/anillos NO enfocados (contexto tenue)
_RING_FRAME_PAD_FACTOR = 0.5  # margen extra = banda del anillo × factor (vecinos asoman)

# UX15: paleta cálida por tipo centralizada en el design system (antes duplicada).
_NODE_COLORS = ENTITY_KIND_PALETTE

# UX21: paleta cálida de relaciones (UX05) centralizada en el design system.
_EDGE_COLORS = RELATION_KIND_PALETTE

_STATUS_COLORS = {
    "canonico": "#6CCB8E",
    "canon": "#6CCB8E",
    "borrador": "#E0C46C",
    "propuesto": "#DCA35F",
    "archivado": "#8993A5",
}

_VISIBILITY_COLORS = {
    "oculto": "#D46A6A",
    "secreto": "#D46A6A",
    "privado": "#D46A6A",
    "publico": "#6CCB8E",
    "publico_mundo": "#6CCB8E",
}


_CONTAINER_COLOR = "#E8E2D2"
_CONTAINER_HEADER_COLOR = "#BDB6A2"
_CONTAINER_PADDING = 44.0
_CONTAINER_HEADER_HEIGHT = 48.0
_CONTAINER_MIN_WIDTH = 280.0
_CONTAINER_MIN_HEIGHT = 200.0
_CONTAINER_CHILD_SPACING = 52.0


@dataclass(frozen=True)
class _NodeView:
    entity: Any
    entity_id: str
    name: str
    kind: str
    subtitle: str
    canon: str
    visibility: str
    layer_id: str = ""
    proposed: bool = False
    # BETA1-G06: vida temporal de la entidad (None = sin dato / pre-migración,
    # death None = sigue viva). Permite la "fotografía" del grafo en un año.
    birth_year: int | None = None
    death_year: int | None = None


@dataclass(frozen=True)
class _EdgeView:
    relation: Any
    relation_id: str
    source_id: str
    target_id: str
    kind: str
    label: str
    direction: str = "unidireccional"
    color: str = ""
    proposed: bool = False
    inter_ring: bool = False
    causal: bool = False
    # BETA1-G06: intervalo temporal EXPLÍCITO de la relación (opcional). Por
    # defecto None → la existencia se deriva de la de sus extremos. Si se
    # define (custom_metadata.birth_year/death_year), acota la relación a un
    # tramo propio (p. ej. dos personajes longevos que se enemistan en el año 50).
    birth_year: int | None = None
    death_year: int | None = None


@dataclass(frozen=True)
class _RingVisual:
    """Calculated B44 concentric ring state. Ephemeral UI data, never canon."""

    ring_id: str
    display_name: str
    causal_rank: int | None
    color: str
    inner_radius: float
    outer_radius: float
    item_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    count_label: str = ""
    state: str = "normal"  # normal | focused | hidden


@dataclass(frozen=True)
class VisualFilterState:
    """Ephemeral B37 visual filters. Never persisted and never mutates canon."""

    entity_types: tuple[str, ...] = ()
    relation_types: tuple[str, ...] = ()
    relation_families: tuple[str, ...] = ()
    tree_id: str = ""
    layer_ids: tuple[str, ...] = ()
    focus_entity_ids: tuple[str, ...] = ()
    canon_states: tuple[str, ...] = ()
    visibility_states: tuple[str, ...] = ()
    show_relations: bool = True

    def is_active(self) -> bool:
        return bool(
            self.entity_types
            or self.relation_types
            or self.relation_families
            or self.tree_id
            or self.layer_ids
            or self.focus_entity_ids
            or self.canon_states
            or self.visibility_states
            or not self.show_relations
        )


@dataclass(frozen=True)
class GraphSearchResult:
    """Clean search result for Creación. IDs stay internal and are not display text."""

    item_id: str
    item_kind: str  # entity | tree | relation
    title: str
    type_label: str
    category: str
    summary: str = ""
    parent_tree_name: str = ""
    parent_tree_id: str = ""
    is_inside_collapsed_tree: bool = False

    def display_lines(self) -> tuple[str, str, str]:
        where = f"Dentro de {self.parent_tree_name}" if self.parent_tree_name else self.category
        details = " · ".join(part for part in [self.type_label, where] if part)
        return (self.title, details, self.summary)


def _enum_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


def _parse_optional_year(value: Any) -> int | None:
    """BETA1-G06: lee un año entero o None (acepta strings, ignora basura)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def interval_contains_year(birth: int | None, death: int | None, year: int) -> bool:
    """BETA1-G06: ¿el intervalo [birth, death] contiene ``year``? (puro, testeable).

    - ``birth is None`` → sin fecha de nacimiento conocida: no se oculta nunca
      (entidad pre-migración o relación derivada de extremos).
    - ``death is None`` → sigue existiendo (intervalo abierto).
    """
    if birth is None:
        return True
    if year < int(birth):
        return False
    return death is None or year <= int(death)


def _entity_view(entity: Any) -> _NodeView:
    kind = _enum_value(getattr(entity, "entity_type", None), "entidad")
    subtitle = (
        getattr(entity, "brief_description", None)
        or getattr(entity, "brief", None)
        or getattr(entity, "description", None)
        or "Sin descripción breve"
    )
    return _NodeView(
        entity=entity,
        entity_id=str(getattr(entity, "id", "")),
        name=str(getattr(entity, "name", "Sin nombre")),
        kind=kind,
        subtitle=str(subtitle),
        canon=_enum_value(getattr(entity, "canon_state", None), ""),
        visibility=_enum_value(getattr(entity, "visibility_state", None), ""),
        layer_id=str((getattr(entity, "layer_ids", []) or [""])[0] or ""),
        birth_year=_parse_optional_year(getattr(entity, "birth_year", None)),
        death_year=_parse_optional_year(getattr(entity, "death_year", None)),
    )


def _relation_view(relation: Any) -> _EdgeView:
    kind = _enum_value(getattr(relation, "relation_type", None), "relación")
    label = enum_human(kind)
    direction = _enum_value(getattr(relation, "direction", None), "unidireccional")
    meta = dict(getattr(relation, "custom_metadata", {}) or {})
    color = meta.get("_edge_color", "") or _EDGE_COLORS.get(kind.lower(), "")
    return _EdgeView(
        relation=relation,
        relation_id=str(getattr(relation, "id", "")),
        source_id=str(getattr(relation, "source_id", "")),
        target_id=str(getattr(relation, "target_id", "")),
        kind=kind,
        label=label,
        direction=direction,
        color=color,
        causal=relation_family(kind) == "causal",
        # BETA1-G06: leer del campo de dominio (v26+); caer a custom_metadata
        # como respaldo para SimpleNamespace de tests que no tienen el atributo.
        birth_year=_parse_optional_year(getattr(relation, "birth_year", meta.get("birth_year"))),
        death_year=_parse_optional_year(getattr(relation, "death_year", meta.get("death_year"))),
    )


def _candidate_is_pending_ai(candidate: Any) -> bool:
    source = str(getattr(candidate, "source", "")).lower()
    state = _enum_value(getattr(candidate, "state", None), "")
    return source in {"ia", "ai"} and state in {"pendiente", "requiere_revision"}


def _candidate_node_view(candidate: Any) -> _NodeView | None:
    data = dict(getattr(candidate, "proposed_data", {}) or {})
    name = data.get("name") or getattr(candidate, "title", "")
    if not name:
        return None
    kind = str(data.get("entity_type") or data.get("type") or "concepto")
    return _NodeView(
        entity=candidate,
        entity_id=f"cand_node_{getattr(candidate, 'id', '')}",
        name=str(name),
        kind=kind,
        subtitle="Sugerencia IA · no canon",
        canon="propuesto",
        visibility="privado",
        layer_id=str(
            data.get("layer_id")
            or (
                (data.get("layer_ids") or [""])[0]
                if isinstance(data.get("layer_ids"), list)
                else ""
            )
        ),
        proposed=True,
    )


def _candidate_edge_view(candidate: Any, known_entity_ids: set[str]) -> _EdgeView | None:
    data = dict(getattr(candidate, "proposed_data", {}) or {})
    source_id = str(data.get("source_id") or "")
    target_id = str(data.get("target_id") or "")
    if (
        not source_id
        or not target_id
        or source_id not in known_entity_ids
        or target_id not in known_entity_ids
    ):
        return None
    kind = str(data.get("relation_type") or "esta_relacionado_con")
    return _EdgeView(
        relation=candidate,
        relation_id=f"cand_rel_{getattr(candidate, 'id', '')}",
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        label=f"IA · {enum_human(kind)}",
        proposed=True,
    )


def _fit_text(text: str, max_chars: int) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


# Semillas (SEM02): margen extra del boundingRect para que el glow de germinación
# se repinte sin dejar artefactos, y duración de la animación de bloom.
_BLOOM_MARGIN = 30.0


def _paint_bloom_rings(
    painter: QPainter, cx: float, cy: float, base_r: float, phase: float
) -> None:
    """Anillos dorados que se expanden y se desvanecen: una semilla germinando."""
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(3):
        t = phase - i * 0.16
        if t <= 0.0 or t >= 1.0:
            continue
        rr = base_r + 4.0 + 26.0 * t
        glow = QColor(GOLD)
        glow.setAlpha(int(200 * (1.0 - t)))
        painter.setPen(QPen(glow, 3.5 * (1.0 - t) + 1.0))
        painter.drawEllipse(QPointF(cx, cy), rr, rr)


# SEM · Acreción cósmica: la "semilla" germina como una ACRECIÓN — motas de
# polvo orbitando que convergen y condensan en un núcleo luminoso. Ambiental
# (sin etapas legibles tipo barra de progreso): todo se interpola de forma
# continua sobre _phase (0..1) y el latido. No hay metáfora de planta.

# Suavizado de la fase mostrada hacia el objetivo del job (lerp por frame del
# timer de semilla a 40 ms): el avance entra de forma gradual, sin saltos.
_SEED_PHASE_LERP = 0.15

# Curva de easing (EASING_STD = OutCubic) para el crecimiento del núcleo.
_GERM_EASE = QEasingCurve(QEasingCurve.Type.OutCubic)

# Nº de motas de polvo que orbitan y caen hacia el núcleo al condensarse.
_SEED_MOTES = 7

# Velocidad tangencial (px/paso, ~60 Hz) de la semilla viva orbitando su corona.
# ~½ de la inicial: deriva pausada. La irregularidad (deriva del eje) la añade
# el motor vía Body.orbit_drift / orbit_drift_rate.
_SEED_ORBIT_SPEED = 1.5
_SEED_ORBIT_DRIFT = 16.0  # radio (px) de migración del centro de la órbita
_SEED_ORBIT_DRIFT_RATE = 0.011  # rad/paso: el eje migra lento → no se repite


class GraphNodeItem(QGraphicsEllipseItem):
    """Visual node item; stores full entity ID internally, never shows it.

    Compact mode: shows name + type + status dot only.
    Brief description is available in the detail panel, not rendered inside the node.
    """

    def __init__(self, node: _NodeView, *, x: float, y: float, radius: float = 58.0):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.node = node
        self.radius = radius
        self._coherence_selected = False
        self._hovered = False  # BETA1-UX05: feedback de hover
        self._bloom_phase = 0.0  # SEM02: fase de germinación (0..1), 0 = inactiva
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # BETA1-B03: edges must follow items. Scene-position notifications
        # also fire when an ANCESTOR moves, so nested children keep their
        # relations attached while their tree is dragged.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self._connected_edges: list = []
        self.setAcceptHoverEvents(True)
        self.setZValue(2)
        # BETA1-L01: NO usar setCacheMode(DeviceCoordinateCache) aquí. Parecía
        # buena idea (cachear la hoja estática), pero con el viewport GL
        # (QOpenGLWidget) es una patología conocida de Qt: cada item cacheado
        # necesita su propia superficie raster que se sube a textura GL en cada
        # frame → el pintado de 779 nodos pasó de ~30ms a ~750ms en hardware real
        # (medido con NARRATIVE_PERF_LOG). Sin caché, Qt pinta los items
        # directamente por el viewport GL, que es justo lo que conviene.

        color = QColor(_NODE_COLORS.get(node.kind.lower(), "#9A8E72"))
        self._normal_pen = QPen(
            QColor("#DCA35F" if node.proposed else "#F7F1E8"), 2.6 if node.proposed else 2.0
        )
        if node.proposed:
            self._normal_pen.setStyle(Qt.PenStyle.DashLine)
        self._highlight_pen = QPen(QColor("#EBCB8B"), 4.0)
        self._selected_pen = QPen(
            QColor("#8B7A36"), 5.0
        )  # oro (vestigial; selección real = halo interno)
        # BETA1-F05: hojas BLANCAS — el color del tipo vive como halo sutil
        # exterior (ver paint()), no como relleno.
        self._halo_color = QColor(color)
        self.setBrush(QBrush(QColor(255, 255, 253, 250)))
        self.setPen(self._normal_pen)

        # Name — centred, fitted to node width
        title = _LodTextItem(_fit_text(node.name, 20), self)
        title.setBrush(QBrush(QColor("#111827")))
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        title.setFont(font)
        title_rect = title.boundingRect()
        title.setPos(-title_rect.width() / 2, -title_rect.height() / 2 - 6)
        self._title_item = title  # BETA1-L01: ref para update-in-place

        # Type — small label below name
        type_label = _LodTextItem(_fit_text(enum_human(node.kind), 18), self)
        type_label.setBrush(QBrush(QColor("#4B5563")))
        type_label.setFont(QFont("", 7))
        type_rect = type_label.boundingRect()
        type_label.setPos(-type_rect.width() / 2, title_rect.height() / 2 - 4)
        self._type_item = type_label  # BETA1-L01: ref para update-in-place

        # UX28: se retiran las "bolitas" de estado/visibilidad del nodo — el detalle
        # ya muestra canon y visibilidad; en el lienzo ensuciaban la hoja.
        self._status_dot = QGraphicsEllipseItem(-radius + 8, -radius + 8, 10, 10, self)
        self._status_dot.setBrush(QBrush(QColor(_STATUS_COLORS.get(node.canon.lower(), "#A4AEC0"))))
        self._status_dot.setPen(QPen(QColor("#F7F1E8"), 1.0))
        self._status_dot.setVisible(False)

        visibility_key = node.visibility.lower()
        if visibility_key in _VISIBILITY_COLORS and visibility_key not in {
            "publico",
            "publico_mundo",
        }:
            self._visibility_dot = QGraphicsEllipseItem(radius - 18, -radius + 8, 10, 10, self)
            self._visibility_dot.setBrush(QBrush(QColor(_VISIBILITY_COLORS[visibility_key])))
            self._visibility_dot.setPen(QPen(QColor("#F7F1E8"), 1.0))
            self._visibility_dot.setVisible(False)

        self.setToolTip("")

    def set_drag_highlight(self, enabled: bool):
        # BETA1-F05: feedback por repintado (halo/ámbar), no por pen-swap
        self._drag_highlighted = bool(enabled)
        self.update()

    def set_coherence_selected(self, enabled: bool):
        self._coherence_selected = bool(enabled)
        self.update()

    def set_bloom_phase(self, phase: float):
        # SEM02: avance de la animación de germinación; el canvas la pulsa.
        phase = float(phase)
        if (0.0 < phase < 1.0) != (0.0 < self._bloom_phase < 1.0):
            self.prepareGeometryChange()  # el boundingRect cambia al (des)activarse
        self._bloom_phase = phase
        self.update()

    def apply_view_update(self, node: _NodeView) -> None:
        """BETA1-L01: refresca los visuales de una HOJA in situ (sin reconstruir
        el grafo). Solo cambia lo visible de una edición de atributos: nombre,
        tipo (etiqueta + halo) y estado 'propuesto'. NO toca posición ni física.
        El llamante garantiza que sigue siendo una hoja (no contenedor)."""
        self.node = node
        # Nombre (recentrado)
        self._title_item.setText(_fit_text(node.name, 20))
        title_rect = self._title_item.boundingRect()
        self._title_item.setPos(-title_rect.width() / 2, -title_rect.height() / 2 - 6)
        # Tipo (recentrado bajo el nombre)
        self._type_item.setText(_fit_text(enum_human(node.kind), 18))
        type_rect = self._type_item.boundingRect()
        self._type_item.setPos(-type_rect.width() / 2, title_rect.height() / 2 - 4)
        # Halo del tipo
        self._halo_color = QColor(_NODE_COLORS.get(node.kind.lower(), "#9A8E72"))
        # Trazo 'propuesto' (rastro discontinuo ámbar) vs canónico
        self._normal_pen = QPen(
            QColor("#DCA35F" if node.proposed else "#F7F1E8"), 2.6 if node.proposed else 2.0
        )
        if node.proposed:
            self._normal_pen.setStyle(Qt.PenStyle.DashLine)
        self.update()

    def boundingRect(self):  # noqa: N802 (Qt signature)
        # SEM02: ampliar solo durante el glow para cubrirlo sin artefactos.
        base = super().boundingRect()
        if 0.0 < self._bloom_phase < 1.0:
            return base.adjusted(-_BLOOM_MARGIN, -_BLOOM_MARGIN, _BLOOM_MARGIN, _BLOOM_MARGIN)
        return base

    def hoverEnterEvent(self, event):  # noqa: N802 (Qt signature)
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):  # noqa: N802 (Qt signature)
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def paint(self, painter: QPainter, option, widget=None):
        # BETA1-L01: LOD con tier MEDIO de calidad. Visto de lejos (muchos nodos
        # a la vez) se omiten texto y adornos, pero el NODO conserva calidad:
        # antialiasing siempre + un halo cálido (1 pasada en vez de 3). Solo a
        # zoom extremo se cae a punto liso. Pasa de cientos de ms a una fracción
        # sin el escalón feo del recorte total.
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod < _NODE_FULL_LOD:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            halo = getattr(self, "_halo_color", None)
            if halo is not None and lod >= _NODE_MIN_LOD:
                glow = QColor(halo)
                glow.setAlpha(120)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(glow, 6.0))
                painter.drawEllipse(self.rect())
            painter.setBrush(self.brush())
            if halo is not None and lod < _NODE_MIN_LOD:
                painter.setPen(QPen(halo, 1.0))  # borde fino para definir el punto
            else:
                painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawEllipse(self.rect())
            return
        # BETA1-F05: pintura propia — SIN marquee negro de Qt (causa de las
        # "pestañas negras"), SIN contorno marcado, halo interno al
        # seleccionar y aro ámbar solo como destino de drop.
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ellipse = QPainterPath()
        ellipse.addEllipse(self.rect())
        # BETA1-F05: halo EXTERIOR sutil con el color del tipo — se pinta
        # sobre el contorno y el relleno blanco posterior tapa la mitad
        # interna, dejando solo el resplandor hacia fuera.
        halo = getattr(self, "_halo_color", None)
        if halo is not None:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # UX28: contorno de tipo más presente (antes apenas se percibía).
            for width, alpha in ((13.0, 40), (7.0, 80), (3.0, 140)):
                glow = QColor(halo)
                glow.setAlpha(alpha)
                painter.setPen(QPen(glow, width))
                painter.drawPath(ellipse)
        painter.setBrush(self.brush())
        if self.node.proposed:
            painter.setPen(self._normal_pen)  # propuesto: rastro discontinuo
        else:
            painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawPath(ellipse)
        if getattr(self, "_drag_highlighted", False):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#EBCB8B"), 3.0))
            painter.drawPath(ellipse)
        # BETA1-UX05: hover — aro de oro suave que invita a interactuar (no se
        # pinta si ya está seleccionada, donde manda el halo interno).
        if getattr(self, "_hovered", False) and not self._coherence_selected:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            hov = QColor("#BBAA66")
            hov.setAlpha(150)
            painter.setPen(QPen(hov, 2.2))
            painter.drawPath(ellipse)
        if self._coherence_selected:
            _paint_inner_halo(painter, ellipse)
        if 0.0 < self._bloom_phase < 1.0:
            _paint_bloom_rings(painter, 0.0, 0.0, self.radius, self._bloom_phase)

    def itemChange(self, change, value):
        # BETA1-B03: keep relations attached while the node moves (own move
        # or an ancestor tree dragging it along).
        if change in (
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged,
        ):
            for edge in getattr(self, "_connected_edges", ()):  # noqa: B007
                edge.update_path()
        return super().itemChange(change, value)


class GraphTreeItem(QGraphicsRectItem):
    """Visual tree-container item for ``contenedor`` entities.

    Renders as a rounded rectangle with a **fixed header bar** at the top.
    The header always shows: name, type badge, member count, collapse toggle.
    Brief description lives in the detail panel, never in the content area.

    Children (GraphNodeItem / GraphTreeItem) are positioned below the header.
    The container auto-resizes to encompass children with padding.

    Collapse/Expand:
    - Collapsing hides child nodes AND their internal edges.
    - Expanding restores everything and recalculates layout.

    External relations (entity↔tree, tree↔tree narrative) connect to
    the tree's header or border, not the center.
    """

    def __init__(
        self,
        node: _NodeView,
        *,
        x: float,
        y: float,
        width: float = _CONTAINER_MIN_WIDTH,
        height: float = _CONTAINER_MIN_HEIGHT,
    ):
        super().__init__(0, 0, width, height)
        self.node = node
        self._width = width
        self._height = height
        self._coherence_selected = False
        self._bloom_phase = 0.0  # SEM02: fase de germinación (0..1), 0 = inactiva
        self._collapsed = False
        self._expanded_rect: QRectF | None = None
        self.setPos(x - width / 2, y - height / 2)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # BETA1-B03: see GraphNodeItem — edges follow trees too, including
        # nested trees dragged along by an ancestor.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self._connected_edges: list = []
        self.setAcceptHoverEvents(True)
        self.setZValue(0)

        # ── Z-order hierarchy ──
        # Background: z=0 (this item)
        # Header: z=1
        # Children (nodes/subtrees): z=2+
        # Handles/edges on top: z=10
        self._BASE_Z = 0
        self._HEADER_Z = 1
        self._CHILD_Z = 2
        self._DEPTH = 0  # set during set_graph for nested containers

        # Pens
        self._normal_pen = QPen(
            QColor("#DCA35F" if node.proposed else "#A4AEC0"), 2.0 if not node.proposed else 2.6
        )
        if node.proposed:
            self._normal_pen.setStyle(Qt.PenStyle.DashLine)
        self._highlight_pen = QPen(QColor("#EBCB8B"), 3.5)
        self._selected_pen = QPen(
            QColor("#8B7A36"), 4.0
        )  # oro (vestigial; selección real = halo interno)

        # UX28: la rama no se rellena de color (velo blanco translúcido), pero su
        # CONTORNO lleva el color de su TIPO de entidad (paleta de Dendro) — así el
        # color "funciona" sin teñir la caja.
        bg_color = QColor(255, 255, 255, 80)
        self.setBrush(QBrush(bg_color))
        _tcolor = QColor(_NODE_COLORS.get(node.kind.lower(), "#9A8E72"))
        _tcolor.setAlpha(170)
        self._normal_pen = QPen(_tcolor, 1.8)
        if node.proposed:
            self._normal_pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(self._normal_pen)

        # ── Header: sin barra (estética orgánica F05) — solo el título ──
        self._header_item = QGraphicsRectItem(0, 0, width, _CONTAINER_HEADER_HEIGHT, self)
        self._header_item.setZValue(self._HEADER_Z)
        self._header_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self._header_item.setPen(QPen(Qt.PenStyle.NoPen))

        # Title in header
        self._title_item = QGraphicsSimpleTextItem(_fit_text(node.name, 26), self)
        self._title_item.setBrush(QBrush(QColor("#2D2A1E")))
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        self._title_item.setFont(title_font)
        self._reposition_title()

        # Type badge in header (right side)
        type_text = _fit_text(enum_human(node.kind), 14)
        self._type_badge = QGraphicsSimpleTextItem(type_text, self)
        self._type_badge.setBrush(QBrush(QColor("#6F6A42")))
        self._type_badge.setFont(QFont("", 7))
        self._reposition_type_badge()
        # BETA1-F05: sin etiqueta de tipo ("contenedor") en el grafo
        self._type_badge.setVisible(False)

        # Member count (updates dynamically)
        self._count_item = QGraphicsSimpleTextItem("", self)
        self._count_item.setBrush(QBrush(QColor("#5C5A3E")))
        self._count_item.setFont(QFont("", 8))
        # BETA1-F05: el conteo tampoco — solo el nombre, dentro de la rama
        self._count_item.setVisible(False)

        # Collapse indicator
        self._collapse_indicator = QGraphicsSimpleTextItem("", self)
        self._collapse_indicator.setBrush(QBrush(QColor("#6F6A42")))
        self._collapse_indicator.setFont(QFont("", 8))
        self._collapse_indicator.setVisible(False)

        # UX28: se retiran las "bolitas" de estado/visibilidad también en la rama.
        self._status_dot = QGraphicsEllipseItem(width - 20, 8, 10, 10, self)
        self._status_dot.setBrush(QBrush(QColor(_STATUS_COLORS.get(node.canon.lower(), "#A4AEC0"))))
        self._status_dot.setPen(QPen(QColor("#F7F1E8"), 1.0))
        self._status_dot.setVisible(False)

        visibility_key = node.visibility.lower()
        if visibility_key in _VISIBILITY_COLORS and visibility_key not in {
            "publico",
            "publico_mundo",
        }:
            self._visibility_dot = QGraphicsEllipseItem(width - 36, 8, 10, 10, self)
            self._visibility_dot.setBrush(QBrush(QColor(_VISIBILITY_COLORS[visibility_key])))
            self._visibility_dot.setPen(QPen(QColor("#F7F1E8"), 1.0))
            self._visibility_dot.setVisible(False)

        # Track children and internal edges
        self._child_nodes: list[GraphNodeItem | GraphTreeItem] = []
        self._internal_edges: list[GraphEdgeItem] = []

        self.setToolTip("")

    # ── Helper repositioning ──

    def _reposition_title(self):
        # BETA1-F05: el nombre vive DENTRO de la cápsula, centrado en su
        # franja superior (no en una barra de cabecera).
        tr = self._title_item.boundingRect()
        rect = self.rect()
        self._title_item.setPos(
            rect.left() + (rect.width() - tr.width()) / 2,
            rect.top() + max(8.0, (_CONTAINER_HEADER_HEIGHT - tr.height()) / 2),
        )

    def _reposition_type_badge(self):
        br = self._type_badge.boundingRect()
        self._type_badge.setPos(
            self._width - br.width() - 46, (_CONTAINER_HEADER_HEIGHT - br.height()) / 2
        )

    def _reposition_status_dots(self):
        self._status_dot.setRect(self._width - 20, 8, 10, 10)
        if hasattr(self, "_visibility_dot"):
            self._visibility_dot.setRect(self._width - 36, 8, 10, 10)

    def _update_count(self):
        n = len(self._child_nodes)
        label = f"({n})"
        self._count_item.setText(label)
        cr = self._count_item.boundingRect()
        self._count_item.setPos(
            10 + self._title_item.boundingRect().width() + 6,
            (_CONTAINER_HEADER_HEIGHT - cr.height()) / 2,
        )

    # ------------------------------------------------------------------
    # Descendant helpers (transitive)
    # ------------------------------------------------------------------

    def _descendants(self) -> list["GraphNodeItem | GraphTreeItem"]:
        """All descendant nodes transitively (children + grandchildren + ...)."""
        result: list[GraphNodeItem | GraphTreeItem] = []
        stack = list(self._child_nodes)
        while stack:
            item = stack.pop()
            result.append(item)
            if isinstance(item, GraphTreeItem):
                stack.extend(item._child_nodes)
        return result

    def _descendant_tree_ids(self) -> set[str]:
        """Entity IDs of all descendant containers."""
        ids: set[str] = set()
        for d in self._descendants():
            if isinstance(d, GraphTreeItem):
                ids.add(d.node.entity_id)
        return ids

    def _all_descendant_entity_ids(self) -> set[str]:
        """Entity IDs of ALL descendant items (nodes + trees)."""
        return {d.node.entity_id for d in self._descendants()}

    def _descendant_edges(self, all_edges: list) -> list:
        """All edges that involve at least one descendant entity."""
        desc_ids = self._all_descendant_entity_ids()
        result = []
        for edge in all_edges:
            src_id = edge.source.node.entity_id if hasattr(edge.source, "node") else ""
            tgt_id = edge.target.node.entity_id if hasattr(edge.target, "node") else ""
            if src_id in desc_ids or tgt_id in desc_ids:
                result.append(edge)
        return result

    # ------------------------------------------------------------------
    # Collapse / Expand (transitive)
    # ------------------------------------------------------------------

    def toggle_collapse(self):
        if self._collapsed:
            self._expand()
        else:
            self._collapse()
        # BETA1-B03: a nested collapse/expand changes this tree's size, so
        # every ancestor container must refit around it (bottom-up).
        ancestor = self.parentItem()
        while isinstance(ancestor, GraphTreeItem):
            if ancestor._child_nodes:
                ancestor.resize_to_fit_children()
            ancestor = ancestor.parentItem()
        # BETA1-B03: rings react to content size changes. Children keep
        # their own positions (hidden on collapse, restored on expand);
        # only ring radii and top-level slots are recomputed.
        scene = self.scene()
        if scene is not None:
            for view in scene.views():
                if isinstance(view, GraphCanvasView):
                    view._relayout_concentric()
                    break

    def _collapse(self):
        """Hide ALL descendants transitively + all their edges, shrink."""
        self._expanded_rect = QRectF(self.rect())
        # 1. Hide all descendants transitively
        for desc in self._descendants():
            desc.setVisible(False)
            # Also collapse any descendant trees so their state is consistent
            if isinstance(desc, GraphTreeItem) and not desc._collapsed:
                desc._collapse_silent()
        # 2. Hide all edges involving any descendant
        if hasattr(self, "_canvas_edges"):
            for edge in self._descendant_edges(self._canvas_edges):
                edge.setVisible(False)
        # 3. Show collapse indicator with total descendant count
        n = len(self._descendants())
        label = f"{n} miembro{'s' if n != 1 else ''}"
        self._collapse_indicator.setText(label)
        self._collapse_indicator.setVisible(True)
        # 4. Shrink to header + indicator
        collapse_h = _CONTAINER_HEADER_HEIGHT + 20
        title_w = self._title_item.boundingRect().width()
        ind_w = self._collapse_indicator.boundingRect().width()
        collapse_w = max(_CONTAINER_MIN_WIDTH, title_w + ind_w + 60)
        self._width = collapse_w
        self._height = collapse_h
        self.setRect(0, 0, collapse_w, collapse_h)
        self._header_item.setRect(0, 0, collapse_w, _CONTAINER_HEADER_HEIGHT)
        self._reposition_title()
        self._reposition_type_badge()
        self._reposition_status_dots()
        self._collapse_indicator.setPos(10, _CONTAINER_HEADER_HEIGHT + 4)
        # Hide member count badge (collapse indicator shows the count instead)
        self._count_item.setVisible(False)
        self._collapsed = True
        self._update_attached_edges()  # BETA1-B03: no floating edges

    def _collapse_silent(self):
        """Mark as collapsed and shrink, but don't recurse (parent handles that)."""
        self._expanded_rect = QRectF(self.rect())
        self._collapsed = True
        n = len(self._descendants())
        label = f"{n} miembro{'s' if n != 1 else ''}"
        self._collapse_indicator.setText(label)
        self._collapse_indicator.setVisible(True)
        collapse_h = _CONTAINER_HEADER_HEIGHT + 20
        collapse_w = max(_CONTAINER_MIN_WIDTH, self._title_item.boundingRect().width() + 60)
        self._width = collapse_w
        self._height = collapse_h
        self.setRect(0, 0, collapse_w, collapse_h)
        self._header_item.setRect(0, 0, collapse_w, _CONTAINER_HEADER_HEIGHT)
        self._reposition_title()
        self._reposition_type_badge()
        self._reposition_status_dots()
        self._collapse_indicator.setPos(10, _CONTAINER_HEADER_HEIGHT + 4)

    def _expand(self):
        """Restore ALL descendants transitively + recalculate layout bottom-up."""
        self._collapsed = False
        self._collapse_indicator.setVisible(False)
        # Restore member count badge
        self._count_item.setVisible(True)
        # 1. Expand descendant trees first (bottom-up)
        for child in self._child_nodes:
            if isinstance(child, GraphTreeItem) and child._collapsed:
                child._expand()
        # 2. Show direct children
        for child in self._child_nodes:
            child.setVisible(True)
        # 3. Re-show all descendant edges via global edge visibility pass
        if hasattr(self, "_canvas_edges"):
            self._refresh_edge_visibility()
        # 4. Recalculate size
        if self._child_nodes:
            self.resize_to_fit_children()
        elif self._expanded_rect is not None:
            self._width = self._expanded_rect.width()
            self._height = self._expanded_rect.height()
            self.setRect(self._expanded_rect)
            self._header_item.setRect(0, 0, self._width, _CONTAINER_HEADER_HEIGHT)
            self._reposition_title()
            self._reposition_type_badge()
            self._reposition_status_dots()
        self._update_attached_edges()  # BETA1-B03: no floating edges

    def _refresh_edge_visibility(self):
        """Show/hide all canvas edges based on source+target visibility."""
        if not hasattr(self, "_canvas_edges"):
            return
        for edge in self._canvas_edges:
            src_vis = edge.source.isVisible()
            tgt_vis = edge.target.isVisible()
            edge.setVisible(src_vis and tgt_vis)

    def set_canvas_edges(self, edges: list):
        """Store reference to all canvas edges for visibility management."""
        self._canvas_edges = edges

    def refresh_hierarchical_visibility(self):
        """Central visibility refresh: compute hidden IDs and apply to all items.

        Called after collapse, expand, set_graph, or any structural change.
        Rules:
        - A node/tree is hidden if any ancestor tree is collapsed.
        - An edge is visible only if both source and target are visible.
        """
        if not hasattr(self, "_canvas_edges"):
            return
        # Collect all descendant entity IDs of collapsed trees
        hidden_ids: set[str] = set()
        # Walk all trees in the scene to find collapsed ones
        # (this works for any tree, not just self)
        pass  # visibility is managed per-tree in _collapse/_expand/_refresh_edge_visibility

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    # ------------------------------------------------------------------
    # Child / Edge management
    # ------------------------------------------------------------------

    def add_child_node(self, child):
        """Register a child item (GraphNodeItem or GraphTreeItem).

        Makes the child a Qt child (setParentItem) so it paints above
        the container background and participates in scene hit testing
        with correct z-ordering.
        """
        self._child_nodes.append(child)
        # Make child a Qt child of this container for z-ordering
        child.setParentItem(self)
        # Position relative to parent's local coordinates
        child.setZValue(
            self._CHILD_Z + child._DEPTH if isinstance(child, GraphTreeItem) else self._CHILD_Z
        )
        self._update_count()

    def child_node_count(self) -> int:
        return len(self._child_nodes)

    def register_internal_edge(self, edge):
        """Register an edge between two children of this container."""
        self._internal_edges.append(edge)

    def find_internal_edges(self, all_edges: list):
        """Scan all_edges and register those whose source+target are both children."""
        child_ids = set()
        for child in self._child_nodes:
            child_ids.add(child.node.entity_id)
        # Also include this tree's own ID (entity inside tree → tree itself)
        child_ids.add(self.node.entity_id)
        self._internal_edges = []
        for edge in all_edges:
            src_id = edge.source.node.entity_id if hasattr(edge.source, "node") else ""
            tgt_id = edge.target.node.entity_id if hasattr(edge.target, "node") else ""
            if src_id in child_ids and tgt_id in child_ids:
                self._internal_edges.append(edge)

    def resize_to_fit_children(self):
        """Expand the rectangle so all children fit below the header with padding.

        Uses boundingRect() for sub-trees (which accounts for their own children)
        and radius for regular nodes.  Works correctly for nested containers.

        Since children are Qt children (parentItem=self), child.pos() is already
        in local coordinates — no need to subtract self.pos().
        """
        if not self._child_nodes:
            return
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for child in self._child_nodes:
            if not child.isVisible():
                continue
            # child.pos() is already in parent-local coords (Qt child)
            cx = child.pos().x()
            cy = child.pos().y()
            if isinstance(child, GraphTreeItem):
                # Use the tree's actual bounding rect (includes its children)
                br = child.boundingRect()
                min_x = min(min_x, cx + br.left() - 8)
                min_y = min(min_y, cy + br.top() - 8)
                max_x = max(max_x, cx + br.right() + 8)
                max_y = max(max_y, cy + br.bottom() + 8)
            else:
                cr = getattr(child, "radius", 58.0)
                min_x = min(min_x, cx - cr - 8)
                min_y = min(min_y, cy - cr - 8)
                max_x = max(max_x, cx + cr + 8)
                max_y = max(max_y, cy + cr + 8)
        # Ensure header is above all children
        min_y = min(min_y, 0)
        min_x = min(min_x, 0)
        # Add padding
        min_x -= _CONTAINER_PADDING
        min_y -= _CONTAINER_PADDING
        max_x += _CONTAINER_PADDING
        max_y += _CONTAINER_PADDING
        # Ensure header height at top
        min_y = min(min_y, -_CONTAINER_HEADER_HEIGHT - 8)
        w = max(_CONTAINER_MIN_WIDTH, max_x - min_x)
        h = max(_CONTAINER_MIN_HEIGHT, max_y - min_y)
        self._width = w
        self._height = h
        self.setRect(min_x, min_y, w, h)
        self._header_item.setRect(min_x, min_y, w, _CONTAINER_HEADER_HEIGHT)
        self._title_item.setPos(
            min_x + 10,
            min_y + (_CONTAINER_HEADER_HEIGHT - self._title_item.boundingRect().height()) / 2,
        )
        self._type_badge.setPos(
            min_x + w - self._type_badge.boundingRect().width() - 46,
            min_y + (_CONTAINER_HEADER_HEIGHT - self._type_badge.boundingRect().height()) / 2,
        )
        self._status_dot.setRect(min_x + w - 20, min_y + 8, 10, 10)
        if hasattr(self, "_visibility_dot"):
            self._visibility_dot.setRect(min_x + w - 36, min_y + 8, 10, 10)
        self._count_item.setPos(
            min_x + 10 + self._title_item.boundingRect().width() + 6,
            min_y + (_CONTAINER_HEADER_HEIGHT - self._count_item.boundingRect().height()) / 2,
        )
        # BETA1-B03: the rect changed → connection points moved. Recalculate
        # attached relations so none is left floating.
        self._update_attached_edges()

    def _update_attached_edges(self):
        """BETA1-B03: refresh geometry of every relation touching this tree
        or its content (rect/size changes don't fire itemChange)."""
        for edge in getattr(self, "_connected_edges", ()):  # noqa: B007
            edge.update_path()
        for edge in getattr(self, "_internal_edges", ()):  # noqa: B007
            edge.update_path()

    @property
    def radius(self) -> float:
        """Effective 'radius' for edge shortening — distance from center to top of header."""
        return min(self._width, self._height) / 2

    def connection_point(self, from_pos: QPointF) -> QPointF:
        """Return the best point on the header border for an external relation edge.

        This avoids edges going to the center of the container where children are.
        """
        center = self.scenePos() + QPointF(self._width / 2, self._height / 2)
        # Prefer connecting to the header area (top portion)
        header_center = self.scenePos() + QPointF(
            self._width / 2, self.rect().top() + _CONTAINER_HEADER_HEIGHT / 2
        )
        return header_center

    def set_drag_highlight(self, enabled: bool):
        # BETA1-F05: feedback por repintado (halo/ámbar), no por pen-swap
        self._drag_highlighted = bool(enabled)
        self.update()

    def set_coherence_selected(self, enabled: bool):
        self._coherence_selected = bool(enabled)
        self.update()

    def set_bloom_phase(self, phase: float):
        # SEM02: avance de la animación de germinación; el canvas la pulsa.
        phase = float(phase)
        if (0.0 < phase < 1.0) != (0.0 < self._bloom_phase < 1.0):
            self.prepareGeometryChange()  # el boundingRect cambia al (des)activarse
        self._bloom_phase = phase
        self.update()

    def boundingRect(self):  # noqa: N802 (Qt signature)
        # SEM02: ampliar solo durante el glow para cubrirlo sin artefactos.
        base = super().boundingRect()
        if 0.0 < self._bloom_phase < 1.0:
            return base.adjusted(-_BLOOM_MARGIN, -_BLOOM_MARGIN, _BLOOM_MARGIN, _BLOOM_MARGIN)
        return base

    def mouseDoubleClickEvent(self, event):
        local_pos = event.pos()
        header_bottom = self.rect().top() + _CONTAINER_HEADER_HEIGHT
        if local_pos.y() <= header_bottom:
            self.toggle_collapse()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def shape(self) -> QPainterPath:
        """Hit testing: full rect always. Children have higher z-order so they
        get priority in _item_node_at when expanded and a child is under cursor."""
        path = QPainterPath()
        path.addRect(self.rect())
        return path

    def mousePressEvent(self, event):
        """Handle clicks: select the container and propagate to canvas view."""
        # Always propagate to the view so it can handle selection + entitySelected
        # regardless of where in the container the click lands.
        super().mousePressEvent(event)

    def _notify_canvas_selected(self):
        """Propagate selection to the GraphCanvasView so entitySelected fires."""
        views = self.scene().views() if self.scene() else []
        for view in views:
            if isinstance(view, GraphCanvasView):
                view.entitySelected.emit(self.node.entity_id)
                view._set_single_node_selection(self)
                break

    def paint(self, painter: QPainter, option, widget=None):
        # BETA1-F05: forma CIRCULAR/orgánica — cápsula con radio máximo
        # (círculo cuando el contenido es compacto, píldora al crecer).
        # Sin contorno marcado; halo interno al seleccionar; aro ámbar solo
        # como destino de drop.
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        radius = min(rect.width(), rect.height()) / 2.0
        capsule = QPainterPath()
        capsule.addRoundedRect(rect, radius, radius)
        painter.setBrush(self.brush())
        # UX28: el contorno de la rama lleva SIEMPRE el color de su tipo (antes solo
        # se dibujaba si era propuesta → las ramas canónicas salían sin color).
        painter.setPen(self._normal_pen)
        painter.drawPath(capsule)
        if getattr(self, "_drag_highlighted", False):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#EBCB8B"), 3.0))
            painter.drawPath(capsule)
        if self._coherence_selected:
            _paint_inner_halo(painter, capsule)
        if 0.0 < self._bloom_phase < 1.0:
            center = rect.center()
            _paint_bloom_rings(painter, center.x(), center.y(), radius, self._bloom_phase)

    def itemChange(self, change, value):
        # Children are Qt children (parentItem=self) so they move automatically.
        # No manual delta propagation needed.
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            self._previous_pos = self.pos()
        # BETA1-B03: keep this tree's relations attached while it moves
        if change in (
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged,
        ):
            for edge in getattr(self, "_connected_edges", ()):  # noqa: B007
                edge.update_path()
        return super().itemChange(change, value)


class GraphEdgeItem(QGraphicsPathItem):
    """Selectable relation edge derived from a domain relation.

    Draws arrowheads for directed edges and positions the handle
    near the source (directed) or at the center (bidirectional).
    """

    _ARROW_SIZE = 12.0

    def __init__(
        self,
        edge: _EdgeView,
        source: GraphNodeItem | GraphTreeItem,
        target: GraphNodeItem | GraphTreeItem,
    ):
        super().__init__()
        self.edge = edge
        self.source = source
        self.target = target
        # BETA1-B03: register on both endpoints so their itemChange keeps
        # this edge's geometry in sync while they move.
        for endpoint in (source, target):
            registry = getattr(endpoint, "_connected_edges", None)
            if registry is not None and self not in registry:
                registry.append(self)
        self._is_bidirectional = edge.direction == "bidireccional"
        self._coherence_selected = False
        self._bloom_phase = 0.0  # SEM03: germinación de relación (glow en el punto medio)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # BETA1-F05: zona de click generosa — el shape por defecto era el
        # grosor del trazo (~2px), por eso las relaciones "no se podían
        # seleccionar". Ver shape() más abajo.
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)  # BETA1-UX05: invita a clicar
        self.setZValue(100)  # Always above containers and nodes

        # Resolve colour: stored colour > type colour > default
        base_color = edge.color or _EDGE_COLORS.get(edge.kind.lower(), "#9A8E72")
        color = QColor("#DCA35F" if edge.proposed else base_color)

        self._normal_pen = QPen(color, 2.6 if edge.proposed else 2.2)
        if edge.inter_ring:
            self._normal_pen.setStyle(
                Qt.PenStyle.DashDotLine if edge.causal else Qt.PenStyle.DotLine
            )
            self._normal_pen.setWidthF(3.0 if edge.causal else 2.4)
        elif edge.proposed:
            self._normal_pen.setStyle(Qt.PenStyle.DashLine)
        self._normal_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._selected_pen = QPen(color.lighter(135), 4.0)
        self._selected_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(self._normal_pen)
        self._color = color

        # Label
        self.label_item = QGraphicsSimpleTextItem(_fit_text(edge.label, 28), self)
        self.label_item.setBrush(QBrush(QColor("#6B7280")))
        self.label_item.setScale(0.86)

        # Handle (bolita)
        self.handle_item = QGraphicsEllipseItem(-5, -5, 10, 10, self)
        self.handle_item.setBrush(QBrush(QColor("#D08770")))
        self.handle_item.setPen(QPen(QColor("#F7F1E8"), 1.2))
        self.handle_item.setToolTip("")
        self.handle_item.setAcceptHoverEvents(True)
        self.handle_item.setCursor(Qt.CursorShape.PointingHandCursor)

        # Arrowhead polygons (drawn as child items)
        self._arrow_fwd = QGraphicsPathItem(self)
        self._arrow_fwd.setPen(QPen(color, 1.0))
        self._arrow_fwd.setBrush(QBrush(color))
        self._arrow_fwd.setZValue(2)
        if self._is_bidirectional:
            self._arrow_bwd = QGraphicsPathItem(self)
            self._arrow_bwd.setPen(QPen(color, 1.0))
            self._arrow_bwd.setBrush(QBrush(color))
            self._arrow_bwd.setZValue(2)
        else:
            self._arrow_bwd = None

        self.update_path()

    def shape(self) -> QPainterPath:  # noqa: N802 (Qt signature)
        # BETA1-UX05: zona clickable generosa (~16px) alrededor de la línea.
        # ANTES estaba decorada @staticmethod, lo que ROMPÍA el override virtual
        # de Qt: el hit-test caía al shape base (grosor del trazo ~2px) y las
        # relaciones eran casi imposibles de clicar. Como método de instancia,
        # el ensanchado sí se aplica.
        stroker = QPainterPathStroker()
        stroker.setWidth(16.0)
        return stroker.createStroke(self.path())

    @staticmethod
    def _make_arrowhead(tip: QPointF, angle: float, size: float) -> QPainterPath:
        """Create a filled triangular arrowhead pointing at *tip*."""
        p1 = QPointF(
            tip.x() - size * math.cos(angle - math.pi / 6),
            tip.y() - size * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            tip.x() - size * math.cos(angle + math.pi / 6),
            tip.y() - size * math.sin(angle + math.pi / 6),
        )
        path = QPainterPath(tip)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()
        return path

    def update_path(self):
        # For containers, use connection_point (header) instead of center
        if isinstance(self.source, GraphTreeItem) and hasattr(self.source, "connection_point"):
            start = self.source.connection_point(self.target.scenePos())
        else:
            start = self.source.scenePos()
        if isinstance(self.target, GraphTreeItem) and hasattr(self.target, "connection_point"):
            end = self.target.connection_point(start)
        else:
            end = self.target.scenePos()

        # Shorten the line slightly so the arrowhead doesn't overlap the node circle
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        dist = math.hypot(dx, dy) or 1.0
        shorten = min(self.source.radius + 4, dist * 0.15)

        start_adj = QPointF(
            start.x() + (dx / dist) * shorten,
            start.y() + (dy / dist) * shorten,
        )
        end_adj = QPointF(
            end.x() - (dx / dist) * shorten,
            end.y() - (dy / dist) * shorten,
        )

        # Bezier curve
        ctrl_offset = QPointF(-dy * 0.12, dx * 0.12)
        c1 = QPointF(
            start_adj.x() + dx * 0.45 + ctrl_offset.x(),
            start_adj.y() + dy * 0.45 + ctrl_offset.y(),
        )
        c2 = QPointF(
            start_adj.x() + dx * 0.55 + ctrl_offset.x(),
            start_adj.y() + dy * 0.55 + ctrl_offset.y(),
        )
        path = QPainterPath(start_adj)
        path.cubicTo(c1, c2, end_adj)
        self.setPath(path)

        # Arrowhead at target (always for directed; for bidir too)
        angle_at_end = math.atan2(
            end_adj.y() - c2.y(),
            end_adj.x() - c2.x(),
        )
        self._arrow_fwd.setPath(self._make_arrowhead(end_adj, angle_at_end, self._ARROW_SIZE))

        # Arrowhead at source (bidirectional only)
        if self._arrow_bwd is not None:
            angle_at_start = math.atan2(
                start_adj.y() - c1.y(),
                start_adj.x() - c1.x(),
            )
            self._arrow_bwd.setPath(
                self._make_arrowhead(start_adj, angle_at_start, self._ARROW_SIZE)
            )

        # Label at ~45% (so it doesn't overlap arrows)
        label_pt = path.pointAtPercent(0.45)
        rect = self.label_item.boundingRect()
        self.label_item.setPos(label_pt.x() - rect.width() * 0.43, label_pt.y() - 18)

        # Handle: centered for bidirectional, near source (25%) for directed
        if self._is_bidirectional:
            handle_pt = path.pointAtPercent(0.5)
        else:
            handle_pt = path.pointAtPercent(0.25)
        self.handle_item.setPos(handle_pt)

    def set_coherence_selected(self, enabled: bool):
        self._coherence_selected = bool(enabled)
        self.setPen(self._selected_pen if enabled else self._normal_pen)

    def set_bloom_phase(self, phase: float):
        # SEM03: germinación de la arista; el canvas la pulsa.
        phase = float(phase)
        if (0.0 < phase < 1.0) != (0.0 < self._bloom_phase < 1.0):
            self.prepareGeometryChange()
        self._bloom_phase = phase
        self.update()

    def boundingRect(self):  # noqa: N802 (Qt signature)
        base = super().boundingRect()
        if 0.0 < self._bloom_phase < 1.0:
            m = 40.0  # cubre el glow en el punto medio de la arista
            return base.adjusted(-m, -m, m, m)
        return base

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        if 0.0 < self._bloom_phase < 1.0:
            path = self.path()
            if not path.isEmpty():
                mid = path.pointAtPercent(0.5)
                _paint_bloom_rings(painter, mid.x(), mid.y(), 8.0, self._bloom_phase)

    def hoverEnterEvent(self, event):  # noqa: N802 (Qt signature)
        # BETA1-UX05: realce sutil al pasar el ratón (no pisa la selección).
        if not self._coherence_selected:
            hover_pen = QPen(self._color.lighter(122), self._normal_pen.widthF() + 1.2)
            hover_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            if self._normal_pen.style() != Qt.PenStyle.SolidLine:
                hover_pen.setStyle(self._normal_pen.style())
            self.setPen(hover_pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):  # noqa: N802 (Qt signature)
        if not self._coherence_selected:
            self.setPen(self._normal_pen)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self.setPen(self._selected_pen)
        super().mousePressEvent(event)


class GraphRingItem(QGraphicsPathItem):
    """B44 selectable ring background. Empty-area clicks select the ring.

    Nodes, tree containers and relation handles have higher z-order, so this
    item only wins hit testing in empty corona areas.
    """

    def __init__(self, ring: _RingVisual, path: QPainterPath):
        super().__init__(path)
        self.ring = ring
        self._base_pen: QPen | None = None
        self._bloom_phase = 0.0  # SEM03: germinación de anillo (pulso dorado en la banda)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("")
        self.setZValue(-100)

    def paint(self, painter: QPainter, option, widget=None):
        # BETA1-B02: suppress Qt's default selection marquee (a dashed
        # bounding RECTANGLE around the whole ring). Selection feedback is the
        # highlighted ring outline applied in itemChange instead.
        clean = QStyleOptionGraphicsItem(option)
        clean.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, clean, widget)
        if 0.0 < self._bloom_phase < 1.0:
            t = self._bloom_phase
            glow = QColor(GOLD)
            glow.setAlpha(int(170 * (1.0 - abs(2.0 * t - 1.0))))  # entra y sale
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(glow, 2.0 + 7.0 * (1.0 - t)))
            painter.drawPath(self.path())

    def set_bloom_phase(self, phase: float):
        # SEM03: germinación del anillo; el canvas la pulsa.
        phase = float(phase)
        if (0.0 < phase < 1.0) != (0.0 < self._bloom_phase < 1.0):
            self.prepareGeometryChange()
        self._bloom_phase = phase
        self.update()

    def boundingRect(self):  # noqa: N802 (Qt signature)
        base = super().boundingRect()
        if 0.0 < self._bloom_phase < 1.0:
            m = 12.0  # cubre el trazo dorado más ancho durante el glow
            return base.adjusted(-m, -m, m, m)
        return base

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            # BETA1-F05: la selección de anillo profundiza la hendidura
            # (sombra más intensa), sin contornos azules.
            if getattr(self, "_base_brush", None) is None:
                self._base_brush = QBrush(self.brush())
            if value:
                deep = QColor(self._base_brush.color())
                deep.setAlpha(min(255, deep.alpha() + 30))
                self.setBrush(QBrush(deep))
            else:
                self.setBrush(self._base_brush)
        return super().itemChange(change, value)

    def _canvas_view(self):
        scene = self.scene()
        if scene is None:
            return None
        for view in scene.views():
            if isinstance(view, GraphCanvasView):
                return view
        return None

    def mousePressEvent(self, event):
        # BETA1-B02: only the left button selects. Without this filter the
        # right button also triggered select_ring before the context menu
        # opened, causing a view jump on every right click.
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        view = self._canvas_view()
        if view is not None:
            view.select_ring(self.ring.ring_id)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        view = self._canvas_view()
        if view is not None:
            view.select_ring(self.ring.ring_id)
            view.focus_ring_scope(self.ring.ring_id)
        event.accept()


class GraphSeedItem(QGraphicsEllipseItem):
    """SEM04: semilla germinante transitoria dibujada EN el grafo.

    No es canon y no entra en la física (no se registra en ``_nodes``/``_trees``).
    Modos: ``germinating`` (job en curso, crece con el progreso + latido),
    ``candidate`` (en reposo, clickable → abre revisión), ``blooming``/``withering``
    (animación de salida). El gestor del canvas la pulsa cada 40 ms.
    """

    _R = 15.0

    def __init__(self, *, candidate_id: str = "", job_id: str = ""):
        super().__init__(-self._R, -self._R, self._R * 2, self._R * 2)
        self.candidate_id = candidate_id
        self.job_id = job_id
        self.mode = "germinating" if job_id else "candidate"
        self._phase = 0.0  # germinación mostrada 0..1 (suavizada)
        self._target_phase = 0.0  # objetivo según el progreso real del job
        self._pulse = 0.0  # latido continuo
        self._anim = 0.0  # avance de bloom/wither 0..1
        self.setZValue(1500)
        self.setBrush(QBrush(QColor(255, 255, 253, 235)))
        self.setPen(QPen(QColor(GOLD), 2.0))
        if candidate_id:
            self.setAcceptHoverEvents(True)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Semilla pendiente — pulsa para revisar")

    def set_phase(self, phase: float):
        # Fija el objetivo; la fase mostrada lo persigue suavemente en tick().
        self._target_phase = max(0.0, min(1.0, float(phase)))
        self.update()

    def restore_phase(self, phase: float):
        # Tras un rebuild: restaura fase mostrada y objetivo sin re-animar.
        self._phase = self._target_phase = max(0.0, min(1.0, float(phase)))
        self.update()

    def set_mode(self, mode: str):
        self.mode = mode
        self.update()

    def tick(self, *, pulse: float, anim_step: float = 0.0) -> bool:
        """Avanza la animación. True si terminó (procede retirarla)."""
        self._pulse = pulse
        if self.mode in ("blooming", "withering"):
            was = 0.0 < self._anim < 1.0
            self._anim = min(1.0, self._anim + anim_step)
            if not was:
                self.prepareGeometryChange()
            self.update()
            return self._anim >= 1.0
        if self.mode == "germinating":
            # Persigue suavemente el objetivo del job (sin pasarse): germinación
            # paulatina aunque el progreso del job dé saltos.
            diff = self._target_phase - self._phase
            if abs(diff) > 1e-4:
                self._phase += diff * _SEED_PHASE_LERP
                if abs(self._target_phase - self._phase) < 1e-3:
                    self._phase = self._target_phase
        self.update()
        return False

    def boundingRect(self):  # noqa: N802 (Qt signature)
        base = super().boundingRect()
        if self.mode in ("germinating", "blooming"):
            m = _BLOOM_MARGIN
            return base.adjusted(-m, -m, m, m)
        return base

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        latido = 0.5 + 0.5 * math.sin(self._pulse)
        if self.mode == "withering":
            t = self._anim
            r = self._R * (1.0 - 0.6 * t)
            col = QColor("#9A9486")
            col.setAlpha(int(200 * (1.0 - t)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col))
            painter.drawEllipse(QPointF(0.0, 0.0), r, r)
            return
        if self.mode == "germinating":
            # SEM: acreción cósmica ambiental (polvo → núcleo), no una planta.
            self._paint_accretion(painter, latido)
            return
        # candidate / blooming: círculo pleno.
        r = self._R
        painter.setBrush(QBrush(QColor(255, 255, 253, 235)))
        painter.setPen(QPen(QColor(GOLD), 2.0))
        painter.drawEllipse(QPointF(0.0, 0.0), r, r)
        # semilla interior
        seed = QColor(GOLD)
        seed.setAlpha(220)
        painter.setBrush(QBrush(seed))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(0.0, 0.0), r * 0.3, r * 0.3)
        # salida floreciente o latido continuo
        if self.mode == "blooming":
            _paint_bloom_rings(painter, 0.0, 0.0, r, self._anim)
        else:
            halo = QColor(GOLD)
            halo.setAlpha(int(30 + 50 * latido))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(halo, 2.0 + 2.0 * latido))
            rr = r + 5.0 + 4.0 * latido
            painter.drawEllipse(QPointF(0.0, 0.0), rr, rr)

    def _paint_accretion(self, painter: QPainter, latido: float) -> None:
        """SEM: acreción cósmica — motas de polvo que orbitan y caen hacia un
        núcleo que se condensa y enciende. Ambiental y CONTINUO (sin etapas
        legibles): todo se interpola sobre ``_phase`` (0..1) y el latido. A
        pincel (sin QGraphicsEffect [[qt-avoid-graphics-effects-on-dynamic-widgets]])."""
        ease = _GERM_EASE.valueForProgress
        p = ease(self._phase)
        spin = self._pulse * 0.6  # giro lento del disco de polvo

        # Halo difuso que respira y gana cuerpo conforme se condensa.
        halo = QColor(GOLD)
        halo.setAlpha(int(18 + 40 * p + 18 * latido))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(halo, 1.0 + 2.5 * p + 1.0 * latido))
        halo_r = self._R * (0.7 + 0.9 * p) + 3.0 * latido
        painter.drawEllipse(QPointF(0.0, 0.0), halo_r, halo_r)

        # Disco de acreción: motas que orbitan y caen hacia el núcleo (su radio
        # de órbita ↓ con p) y se desvanecen al fundirse. Reparto irregular por
        # ángulo dorado y caída a distinto ritmo → textura orgánica.
        painter.setPen(Qt.PenStyle.NoPen)
        far = self._R * 1.7
        for i in range(_SEED_MOTES):
            ga = i * 2.39996
            ang = spin + ga
            fall = min(1.0, p * (0.7 + 0.5 * ((i % 3) / 2.0)))
            wob = 1.0 + 0.12 * math.sin(self._pulse * 1.7 + ga)
            dist = far * (1.0 - 0.82 * fall) * wob
            mote = QColor(GOLD)
            mote.setAlpha(int(180 * (1.0 - 0.6 * fall)))
            painter.setBrush(QBrush(mote))
            mr = 1.6 + 1.4 * (1.0 - fall)
            painter.drawEllipse(QPointF(math.cos(ang) * dist, math.sin(ang) * dist), mr, mr)

        # Núcleo luminoso que se condensa: crece y brilla con el progreso.
        core_r = self._R * (0.26 + 0.5 * p)
        glow = QColor(255, 252, 240, int(120 + 110 * p))
        gr = core_r + 2.0 + 1.5 * latido
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(0.0, 0.0), gr, gr)
        core = QColor(GOLD)
        core.setAlpha(int(150 + 90 * p))
        painter.setBrush(QBrush(core))
        painter.drawEllipse(QPointF(0.0, 0.0), core_r, core_r)
        # chispa central que palpita más fuerte al acercarse a estar lista.
        spark = QColor(255, 255, 250, int(120 + 120 * latido * p))
        painter.setBrush(QBrush(spark))
        painter.drawEllipse(QPointF(0.0, 0.0), core_r * 0.4, core_r * 0.4)

    def mousePressEvent(self, event):  # noqa: N802 (Qt signature)
        if self.candidate_id and event.button() == Qt.MouseButton.LeftButton:
            for view in self.scene().views() if self.scene() else []:
                if isinstance(view, GraphCanvasView):
                    view._seed_clicked(self.candidate_id)
                    break
            event.accept()
            return
        super().mousePressEvent(event)


_STRUCTURAL_RELATIONS = {"contiene", "pertenece_a"}
_CAUSAL_RELATIONS = {"deriva_de", "condiciona", "explica", "contradice", "produce_consecuencia_en"}
_COHERENCE_RELATIONS = {"incidencia", "contradiccion", "hueco", "reparacion"}


def relation_family(kind: str) -> str:
    value = (kind or "").lower()
    if value in _STRUCTURAL_RELATIONS:
        return "estructural"
    if value in _CAUSAL_RELATIONS:
        return "causal"
    if value in _COHERENCE_RELATIONS or "coher" in value or "incid" in value:
        return "coherencia"
    return "narrativa"


class GraphCanvasView(QGraphicsView):
    """Interactive view: pan/zoom with selectable nodes and edges."""

    entitySelected = Signal(str)
    relationSelected = Signal(str)
    relationCreateRequested = Signal(str, str)
    graphSelectionChanged = Signal(list, list)
    nodeAssignToTreeRequested = Signal(str, str)  # entity_id, tree_entity_id
    relationCreateRejected = Signal(str)
    ringSelected = Signal(str, str)  # ring_id, display_name
    ringFocused = Signal(str, str)  # ring_id, display_name
    ringFocusCleared = Signal()  # BETA1-L02: foco de anillo eliminado (panel resalta)
    searchRequested = Signal()  # BETA1-L02b: tecla 'd' → barra de búsqueda flotante
    seedClicked = Signal(str)  # SEM04: candidate_id de una semilla germinante pulsada
    # BETA1-B01: context-menu intents. The canvas only emits intent; the
    # CreationWorkspace wires them to its existing creation/deletion routes
    # so no persistence logic lives here.
    contextCreateEntityRequested = Signal()
    contextCreateTreeRequested = Signal()
    contextCreateEntityInTreeRequested = Signal(str)  # parent tree entity_id
    contextCreateSubtreeRequested = Signal(str)  # parent tree entity_id
    contextDeleteRequested = Signal()
    contextAIActionRequested = Signal(str)
    # BETA1-B02: emitted after Escape has cancelled modes and cleared the
    # selection, so the workspace can close contextual surfaces (drawer).
    escapePressed = Signal()
    # BETA1-B03: 'Mover a anillo' — entity_id, ring_id (= world layer id).
    # The workspace resolves it through EntityController.update (CRUD-U).
    nodeAssignToRingRequested = Signal(str, str)
    # BETA1-B03: ring CRUD intents (LayerController routes in the workspace)
    ringCreateRequested = Signal()
    ringEditRequested = Signal(str)  # ring_id
    ringDeleteRequested = Signal(str)  # ring_id
    # BETA1-B03: dragging content OUT of its container extracts it (the
    # workspace removes the 'contiene' membership).
    nodeExtractFromTreeRequested = Signal(str)  # entity_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFrameShape(QFrame.Shape.NoFrame)
        # BETA1-UX2A: viewport GPU (OpenGL) para render fluido; no-op/fallback a
        # raster bajo offscreen o sin GL. Antes del setScene para que el viewport
        # ya esté listo cuando se pinte.
        install_gpu_viewport(self)
        # BETA1-G07: lienzo con VIÑETA radial cálida centrada en el origen — el
        # "corazón" del mundo (centro de los anillos) recibe una luz suave que
        # se hunde hacia los bordes. Da profundidad e inmersión sin distraer;
        # las hojas blancas y los velos de rama siguen destacando.
        vignette = QRadialGradient(QPointF(0.0, 0.0), 1500.0)
        vignette.setColorAt(0.0, QColor("#F3EDDD"))  # corazón del mundo: luz cálida
        vignette.setColorAt(0.50, QColor("#E6DFCD"))
        vignette.setColorAt(0.82, QColor("#DBD1B9"))
        vignette.setColorAt(1.0, QColor("#CFC4A8"))  # los bordes se hunden
        self.setBackgroundBrush(QBrush(vignette))
        self.scene_obj = QGraphicsScene(self)
        self.scene_obj.setSceneRect(QRectF(-1600, -1100, 3200, 2200))
        self.setScene(self.scene_obj)
        self._nodes: dict[str, GraphNodeItem] = {}
        self._trees: dict[str, GraphTreeItem] = {}
        self._edges: list[GraphEdgeItem] = []
        self._all_nodes: list[_NodeView] = []
        self._all_edges: list[_EdgeView] = []
        self._all_layers: list[Any] = []
        self._layout_mode_active = "free"
        self._layer_mode_active = False  # compatibility flag for existing B36 toolbar code
        self._ring_visuals: list[_RingVisual] = []
        self._ring_items: dict[str, GraphRingItem] = {}
        self._node_ring_ids: dict[str, str] = {}
        self._selected_ring_id = ""
        self._focused_ring_id = ""
        self._visual_filter = VisualFilterState()
        # BETA1-G06: "fotografía temporal". None = atemporal (se ve todo, como
        # siempre). Un entero = el grafo se filtra al estado del mundo en ese
        # año: solo entidades vivas y relaciones existentes entonces.
        self._view_year: int | None = None
        self._membership: dict[str, str] = {}  # entity_id -> tree_entity_id
        self._pending_source: GraphNodeItem | None = None
        self._drag_source: GraphNodeItem | None = None
        self._drag_target: GraphNodeItem | None = None
        self._drag_origin_view_pos = QPointF()
        self._drag_line: QGraphicsPathItem | None = None
        self._selected_entity_ids: set[str] = set()
        self._selected_relation_ids: set[str] = set()
        # Alt+Drag state for assigning nodes to tree containers
        self._alt_source: GraphNodeItem | None = None
        self._alt_tree_target: GraphTreeItem | None = None
        self._alt_line: QGraphicsLineItem | None = None
        self._alt_origin_view_pos = QPointF()
        # BETA1-B02: keyboard core. Click focus so shortcuts only apply when
        # the user is actually working on the canvas; text inputs in panels
        # keep receiving their own key events untouched.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._space_pan_active = False
        # BETA1-B02 fix: explicit ring chosen via context menu must win over
        # any focused ring while the creation route runs (one-shot override).
        self._context_ring_override = ""
        # BETA1-B02: camera state captured by set_graph for same-layout rebuilds
        self._view_state_to_restore: tuple[QTransform, QPointF] | None = None
        # BETA1-B03: plain left-drag MOVES items (Qt native move). The item
        # being moved is tracked so the release can offer drop-on-tree
        # assignment. Relation creation lives in the context menu only.
        self._moving_item: GraphNodeItem | GraphTreeItem | None = None
        self._move_origin_scene = QPointF()
        # BETA1-G06: un click (press+release sin arrastrar) abre el panel de
        # detalle. Esta bandera evita que el release final de un doble click lo
        # reabra ("pop ups de nuevo").
        self._suppress_release_click = False
        # BETA1-G06: relación presionada — emite en release, no en press.
        self._pressed_edge_id: str = ""
        # BETA1-F05: al ROZAR una rama con el item arrastrado, la física se
        # CONGELA por completo — sin esto, la repulsión pelea contra el gesto
        # de anidar (meter una hoja en una subrama era una lucha).
        self._physics_drag_freeze = False
        self._drop_highlight_tree: GraphTreeItem | None = None
        # BETA1-C02: physics is an OVERLAY flag, never a layout mode
        # (contract: docs/architecture/C01_physics_contract.md). The engine is
        # pure (packages/ui/graph_physics); this bridge packs top-level items,
        # steps on a timer and applies positions. Auto-stop by energy.
        # BETA1-C05 (decisión de producto): SIEMPRE ON por defecto — no hay
        # toggle de usuario; el flag queda como mecanismo interno de
        # seguridad/tests. Cada acción (CRUD, layout, colapso, drop) hace
        # reheat, así la física reacciona a cualquier cambio.
        self._physics_enabled = True
        self._physics_engine = PhysicsEngine()
        # BETA1-L01: presupuesto de frames de la ráfaga de asentamiento (autofreeze).
        # Solo se consume en "modo rendimiento" (grafos grandes); en pequeños la
        # física se detiene por convergencia de energía como siempre.
        self._physics_frames_left = 0
        # Motores locales intrarrama: tree_id → engine en coords del padre
        self._physics_local: dict[str, PhysicsEngine] = {}
        self._physics_timer = QTimer(self)
        self._physics_timer.setInterval(16)  # BETA1-UX2A: ~60 Hz (antes 33 ≈ 30 Hz)
        self._physics_timer.timeout.connect(self._physics_tick)
        # SEM02: animación de germinación (bloom). Timer propio, independiente del
        # físico (que se para por energía). 40 ms ≈ 25 fps.
        self._bloom_items: dict[str, float] = {}  # entity_id -> fase 0..1
        self._bloom_timer = QTimer(self)
        self._bloom_timer.setInterval(40)  # glow breve; su FPS es imperceptible
        self._bloom_timer.timeout.connect(self._bloom_tick)
        # UX5: germinación CONTINUA sobre nodos existentes mientras corre un job de
        # edición (latido que no se autoapaga, a diferencia del bloom). Las entidades
        # seleccionadas «germinan» hasta que el job termina; al aceptar florecen.
        self._germinating: set[str] = set()
        self._germ_pulse = 0.0
        self._germ_timer = QTimer(self)
        self._germ_timer.setInterval(40)
        self._germ_timer.timeout.connect(self._germ_tick)
        # SEM04: semillas germinantes EN el grafo. Data-driven (sobreviven a
        # clear_graph re-renderizándose). job_id -> {ring_id, angle, radius,
        # anchor, phase}; cid -> {pos, mode}. _seed_items: clave
        # 'job:<id>'/'cand:<cid>' -> item vivo. Las semillas-job vivas orbitan
        # su corona como cuerpos del motor (ver _rebuild_physics_world).
        self._job_seeds: dict[str, dict] = {}
        self._candidate_seed_data: dict[str, dict] = {}
        self._seed_items: dict[str, GraphSeedItem] = {}
        self._seed_pulse = 0.0
        self._seed_timer = QTimer(self)
        self._seed_timer.setInterval(40)
        self._seed_timer.timeout.connect(self._seed_tick)
        # BETA1-G08: atmósfera de fondo (hojas + brisa) MUY sutil, detrás de
        # todo. Se pinta en drawBackground (viewport coords) y se pausa cuando
        # el lienzo no está visible.
        self._atmosphere = CanvasAtmosphere(self, ctx=None, count=11)

    def drawBackground(self, painter, rect):  # noqa: N802 (Qt API)
        if not _PERF_LOG:
            super().drawBackground(painter, rect)  # viñeta cálida
            self._atmosphere.paint(painter)
            return
        t0 = time.perf_counter()
        super().drawBackground(painter, rect)  # viñeta cálida
        self._atmosphere.paint(painter)
        self._perf_bg = getattr(self, "_perf_bg", 0.0) + (time.perf_counter() - t0) * 1000.0

    # UX31: transición entre vistas DENTRO del viewport (drawForeground), porque el
    # viewport GPU pinta por encima de cualquier overlay hermano. Un velo de pergamino
    # se desvanece sobre el lienzo al revelar la vista. Fail-soft.
    def play_reveal(self, *, duration_ms: int = 220) -> None:
        try:
            self._reveal_alpha = 1.0
            self._reveal_step = TICK_INTERVAL / max(1, int(duration_ms))
            timer = getattr(self, "_reveal_timer", None)
            if timer is None:
                timer = QTimer(self)
                timer.setInterval(TICK_INTERVAL)
                timer.timeout.connect(self._reveal_tick)
                self._reveal_timer = timer
            if not timer.isActive():
                timer.start()
            self.viewport().update()
        except Exception:  # noqa: BLE001 — el pulido nunca rompe el cambio de vista
            self._reveal_alpha = 0.0

    def _reveal_tick(self) -> None:
        self._reveal_alpha = getattr(self, "_reveal_alpha", 0.0) - getattr(
            self, "_reveal_step", 0.2
        )
        if self._reveal_alpha <= 0.0:
            self._reveal_alpha = 0.0
            timer = getattr(self, "_reveal_timer", None)
            if timer is not None:
                timer.stop()
        self.viewport().update()

    def drawForeground(self, painter, rect):  # noqa: N802 (Qt API)
        super().drawForeground(painter, rect)
        alpha = getattr(self, "_reveal_alpha", 0.0)
        if alpha > 0.0:
            painter.save()
            painter.resetTransform()  # device coords: cubre el viewport entero
            veil = QColor("#E6DFCD")  # pergamino del lienzo
            veil.setAlphaF(max(0.0, min(1.0, alpha)))
            painter.fillRect(self.viewport().rect(), veil)
            painter.restore()

    def paintEvent(self, event):  # noqa: N802 (Qt API)
        if not _PERF_LOG:
            super().paintEvent(event)
            return
        t0 = time.perf_counter()
        super().paintEvent(event)
        dt = (time.perf_counter() - t0) * 1000.0
        self._perf_n = getattr(self, "_perf_n", 0) + 1
        self._perf_sum = getattr(self, "_perf_sum", 0.0) + dt
        self._perf_max = max(getattr(self, "_perf_max", 0.0), dt)
        now = time.perf_counter()
        last = getattr(self, "_perf_last", None)
        if last is None:
            self._perf_last = now
        elif now - last >= 1.0:
            n = self._perf_n
            avg = self._perf_sum / max(1, n)
            bg = getattr(self, "_perf_bg", 0.0) / max(1, n)
            gl = type(self.viewport()).__name__
            phys = "ON" if self._physics_timer.isActive() else "off"
            dpr = self.devicePixelRatioF()
            vp = self.viewport()
            print(
                f"[PERF] paints/s={n} avg={avg:.1f}ms "
                f"(fondo={bg:.1f}ms items={avg - bg:.1f}ms) max={self._perf_max:.1f}ms "
                f"viewport={gl} {vp.width()}x{vp.height()} dpr={dpr:.2f} "
                f"fisica={phys} nodos={len(self._nodes)}",
                flush=True,
            )
            self._perf_n = 0
            self._perf_sum = 0.0
            self._perf_max = 0.0
            self._perf_bg = 0.0
            self._perf_last = now

    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        self._apply_atmosphere_budget()

    def hideEvent(self, event):  # noqa: N802 (Qt API)
        self._atmosphere.stop()
        super().hideEvent(event)

    def _apply_atmosphere_budget(self) -> None:
        """BETA1-L01: pausa la brisa de fondo en grafos grandes. Su timer fuerza
        un repintado COMPLETO del viewport ~18 veces/seg; con cientos de nodos eso
        redibuja todo el grafo de forma continua (causa de lentitud permanente,
        independiente de la física). Decorativa → se sacrifica a partir del umbral."""
        if not self.isVisible():
            return
        if len(self._nodes) + len(self._trees) > ATMOSPHERE_MAX_ITEMS:
            self._atmosphere.stop()
        else:
            self._atmosphere.start()

    def selected_entity_ids(self) -> list[str]:
        return list(self._selected_entity_ids)

    def selected_relation_ids(self) -> list[str]:
        return list(self._selected_relation_ids)

    def selection_payload(self) -> tuple[list[str], list[str]]:
        return self.selected_entity_ids(), self.selected_relation_ids()

    def _emit_selection_changed(self):
        self._apply_relation_emphasis()
        self.graphSelectionChanged.emit(self.selected_entity_ids(), self.selected_relation_ids())

    def clear_selection(self, *, emit: bool = True):
        for item in self._nodes.values():
            item.set_coherence_selected(False)
        for item in self._trees.values():
            item.set_coherence_selected(False)
        self._clear_selection_impl(emit=emit)

    def refresh_all_visibility(self):
        """Central visibility refresh for all edges based on source/target visibility.

        Called after collapse, expand, filters, or any structural change.
        Rule: an edge is visible only if both source and target are visible and relations are enabled.
        """
        for edge in self._edges:
            src_vis = edge.source.isVisible()
            tgt_vis = edge.target.isVisible()
            edge.setVisible(src_vis and tgt_vis and self._visual_filter.show_relations)

    def _clear_selection_impl(self, *, emit: bool = True):
        for item in self._edges:
            item.set_coherence_selected(False)
        # BETA1-B02: also drop ring selection feedback (outline) so clicking
        # the background leaves no ring visually "selected".
        for ring_item in self._ring_items.values():
            if ring_item.isSelected():
                ring_item.setSelected(False)
        self._selected_entity_ids.clear()
        self._selected_relation_ids.clear()
        if emit:
            self._emit_selection_changed()

    def _fit_scale(self) -> float:
        """Escala que enmarca TODO el contenido en el viewport (con un poco de
        aire). Base del suelo de zoom-out adaptativo y de 'ver todo'."""
        rect = self.scene_obj.itemsBoundingRect()
        vp = self.viewport()
        if rect.isEmpty() or vp.width() < 8 or vp.height() < 8:
            return _ZOOM_OUT_FLOOR
        sx = vp.width() / (rect.width() * 1.15)
        sy = vp.height() / (rect.height() * 1.15)
        return max(0.002, min(sx, sy))

    def _min_zoom(self) -> float:
        """Suelo de alejamiento: nunca más restrictivo que el histórico (0.22),
        pero en grafos enormes baja hasta poder enmarcar el conjunto."""
        return min(_ZOOM_OUT_FLOOR, self._fit_scale() * 0.9)

    def wheelEvent(self, event):
        """Smooth bounded zoom under mouse. BETA1-L02: el suelo de alejamiento es
        dinámico, así que en grafos grandes se puede volver al panorama."""
        current = self.transform().m11()
        if event.angleDelta().y() > 0:
            if current >= _ZOOM_MAX:
                event.accept()
                return
            factor = _ZOOM_STEP
        else:
            if current <= self._min_zoom():
                event.accept()
                return
            factor = 1 / _ZOOM_STEP
        self.scale(factor, factor)
        event.accept()

    def _zoom_by(self, factor: float) -> None:
        """Zoom anclado al CENTRO del viewport (para botones/atajos), acotado."""
        current = self.transform().m11()
        target = max(self._min_zoom(), min(_ZOOM_MAX, current * factor))
        if abs(target - current) < 1e-6:
            return
        anchor = self.transformationAnchor()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.scale(target / current, target / current)
        self.setTransformationAnchor(anchor)

    def zoom_in(self) -> None:
        self._zoom_by(_ZOOM_STEP)

    def zoom_out(self) -> None:
        self._zoom_by(1 / _ZOOM_STEP)

    # 'Ver todo' (fit_all) y reset_view ya existen más abajo en esta clase; los
    # atajos de teclado y los botones flotantes (L02) los reutilizan.

    def _item_node_at(self, view_pos) -> GraphNodeItem | GraphTreeItem | None:
        """Find a GraphNodeItem or GraphTreeItem under *view_pos*, ignoring drag overlays."""
        for item in self.items(view_pos.toPoint()):
            check = item
            while check is not None:
                if isinstance(check, (GraphNodeItem, GraphTreeItem)):
                    return check
                check = check.parentItem()
        return None

    def _item_edge_at(self, view_pos) -> GraphEdgeItem | None:
        """Find a GraphEdgeItem under *view_pos*, ignoring drag overlays."""
        for item in self.items(view_pos.toPoint()):
            check = item
            while check is not None:
                if isinstance(check, GraphEdgeItem):
                    return check
                check = check.parentItem()
        return None

    def _item_seed_at(self, view_pos) -> "GraphSeedItem | None":
        """SEM04-fix: semilla germinante (con candidate_id) bajo *view_pos*.

        El view resuelve los clics por hit-testing propio; sin esto, el clic en
        una semilla nunca llegaba a su mousePressEvent ni abría la revisión.
        """
        for item in self.items(view_pos.toPoint()):
            check = item
            while check is not None:
                if isinstance(check, GraphSeedItem) and getattr(check, "candidate_id", ""):
                    return check
                check = check.parentItem()
        return None

    def _topmost_node_or_edge_at(self, view_pos):
        """BETA1-F05: resuelve el item REAL bajo el cursor respetando el
        orden visual (z). Una relación dibujada sobre una rama debe ganar al
        click — antes _item_node_at devolvía la rama aunque la arista
        estuviera encima (z=100), abriendo el panel equivocado.

        Devuelve ("edge", item), ("node", item) o (None, None)."""
        for item in self.items(view_pos.toPoint()):
            check = item
            while check is not None:
                if isinstance(check, GraphEdgeItem):
                    return "edge", check
                if isinstance(check, (GraphNodeItem, GraphTreeItem)):
                    return "node", check
                check = check.parentItem()
        return None, None

    def _item_ring_at(self, view_pos) -> GraphRingItem | None:
        """Find the precise concentric ring under *view_pos* by radius.

        Qt's item lookup can return several QGraphicsPathItem rings for the same
        point because large annular paths overlap in their item shapes/z-order.
        B44 ring activation must use the actual concentric radius, not the first
        item returned by QGraphicsView.items().
        """
        scene_pos = self.mapToScene(view_pos.toPoint())
        radius = math.hypot(scene_pos.x(), scene_pos.y())
        matches: list[GraphRingItem] = []
        for ring_id, item in self._ring_items.items():
            ring = item.ring
            if ring.inner_radius <= radius <= ring.outer_radius:
                matches.append(item)
        if matches:
            return min(matches, key=lambda item: item.ring.outer_radius)
        return None

    def _set_single_node_selection(self, node: GraphNodeItem):
        self.clear_selection(emit=False)
        self._selected_entity_ids.add(node.node.entity_id)
        node.set_coherence_selected(True)
        self._emit_selection_changed()

    def _set_single_edge_selection(self, edge: GraphEdgeItem):
        self.clear_selection(emit=False)
        self._selected_relation_ids.add(edge.edge.relation_id)
        edge.set_coherence_selected(True)
        self._emit_selection_changed()

    def _apply_relation_emphasis(self):
        if not self._selected_entity_ids and not self._selected_relation_ids:
            for edge in self._edges:
                edge.setOpacity(1.0)
            return
        for edge in self._edges:
            related = (
                edge.edge.relation_id in self._selected_relation_ids
                or edge.edge.source_id in self._selected_entity_ids
                or edge.edge.target_id in self._selected_entity_ids
            )
            edge.setOpacity(1.0 if related else 0.22)

    def _toggle_node_selection(self, node: GraphNodeItem):
        entity_id = node.node.entity_id
        if entity_id in self._selected_entity_ids:
            self._selected_entity_ids.remove(entity_id)
            node.set_coherence_selected(False)
        else:
            self._selected_entity_ids.add(entity_id)
            node.set_coherence_selected(True)
        self._emit_selection_changed()

    def _toggle_edge_selection(self, edge: GraphEdgeItem):
        relation_id = edge.edge.relation_id
        if relation_id in self._selected_relation_ids:
            self._selected_relation_ids.remove(relation_id)
            edge.set_coherence_selected(False)
        else:
            self._selected_relation_ids.add(relation_id)
            edge.set_coherence_selected(True)
        self._emit_selection_changed()

    # ── BETA1-C02: physics bridge ────────────────────────────────────────

    def physics_enabled(self) -> bool:
        return self._physics_enabled

    def set_physics_enabled(self, enabled: bool):
        """Toggle physics. Writes EXCLUSIVELY _physics_enabled — never
        _layout_mode (contract C01 §4.1)."""
        enabled = bool(enabled)
        if enabled == self._physics_enabled:
            return
        self._physics_enabled = enabled
        if enabled:
            self._rebuild_physics_world()
            self._physics_engine.reheat()
            self._physics_timer.start()
        else:
            self._physics_timer.stop()

    def _physics_top_level_of(self, entity_id: str):
        """Top-level body owning *entity_id* (itself, or its outermost tree).
        Nested content is never simulated — it travels with its tree."""
        item = self._nodes.get(entity_id) or self._trees.get(entity_id)
        if item is None:
            return None
        while item.parentItem() is not None and isinstance(
            item.parentItem(), (GraphNodeItem, GraphTreeItem)
        ):
            item = item.parentItem()
        return item

    def _physics_effective_ring(self, entity_id: str) -> str:
        """BETA1-C03: anillo efectivo centralizado (rings.resolve_…).

        Capas explícitas reales desde _node_ring_ids (excluyendo la
        asignación sintética a 'Sin clasificar') y herencia por _membership."""
        explicit = {
            eid: rid
            for eid, rid in self._node_ring_ids.items()
            if rid and rid != UNCLASSIFIED_RING_ID
        }
        return resolve_effective_ring_id(
            entity_id,
            explicit_ring_ids=explicit,
            membership=self._membership,
            is_tree=frozenset(self._trees.keys()),
        )

    def _rebuild_physics_world(self):
        """Pack current top-level items + relations into the pure engine."""
        bodies: list[Body] = []
        ring_bands: dict[str, tuple[float, float]] = {}
        concentric = self._layout_mode_active == "concentric_rings"
        if concentric:
            for ring in self._ring_visuals:
                ring_bands[ring.ring_id] = (ring.inner_radius, ring.outer_radius)
        seen: set[int] = set()
        effective_rings: dict[str, str] = {}
        for entity_id, item in {**self._nodes, **self._trees}.items():
            if item.parentItem() is not None:
                continue  # nested: travels with its tree
            if id(item) in seen:
                continue
            seen.add(id(item))
            rect = item.sceneBoundingRect()
            center = rect.center()
            extent = max(rect.width(), rect.height()) / 2.0
            target = None
            band_inner = band_outer = None
            if concentric:
                ring_id = self._physics_effective_ring(entity_id)
                effective_rings[entity_id] = ring_id
                band = ring_bands.get(ring_id)
                if band is None and ring_bands:
                    # Sin anillo y sin banda 'Sin clasificar' dibujada:
                    # zona EXTERIOR al último anillo (C03: nunca al centro)
                    outermost = max(outer for _, outer in ring_bands.values())
                    band = (outermost + 34.0, outermost + 34.0 + 240.0)
                if band is not None:
                    inner, outer = band
                    target = (inner + outer) / 2.0
                    # margen = extensión del item para que su BORDE respete
                    # la corona, no solo su centro
                    band_inner = inner + min(extent, (outer - inner) / 2.0 - 1.0)
                    band_outer = max(band_inner, outer - min(extent, (outer - inner) / 2.0 - 1.0))
            child_count = len(getattr(item, "_child_nodes", []) or [])
            bodies.append(
                Body(
                    body_id=entity_id,
                    x=center.x(),
                    y=center.y(),
                    mass=1.0 + 0.2 * child_count,
                    radius=extent + 18.0,
                    target_radius=target,
                    band_inner=band_inner,
                    band_outer=band_outer,
                )
            )
        # SEM04: semillas-job vivas como cuerpos orbitadores (solo concéntrico).
        # Mantienen velocidad tangencial (orbit_speed) → orbitan su corona y su
        # repulsión empuja a los vecinos (grafo vivo) sin asentarse.
        # SEM04: TODAS las semillas vivas (la germinante del job y las
        # semillas-candidato en revisión) son cuerpos orbitadores idénticos: el
        # candidato hereda el comportamiento de la semilla que lo engendró, no
        # queda estático. Solo en concéntrico.
        if concentric:
            for body_id, ring_id, item in self._live_seed_bodies():
                body = self._build_seed_body(body_id, ring_id, item, ring_bands)
                if body is not None:
                    bodies.append(body)
        springs: list[Spring] = []
        ring_targets = {rid: (b[0] + b[1]) / 2.0 for rid, b in ring_bands.items()}
        for edge_item in self._edges:
            src = self._physics_top_level_of(edge_item.edge.source_id)
            tgt = self._physics_top_level_of(edge_item.edge.target_id)
            if src is None or tgt is None or src is tgt:
                continue
            a = src.node.entity_id
            b = tgt.node.entity_id
            factor = 1.0
            ideal = 230.0
            if concentric:
                ring_a = effective_rings.get(a, "")
                ring_b = effective_rings.get(b, "")
                if ring_a != ring_b:
                    # inter-ring: weak spring, ideal ≈ radial gap (C01 §4.6)
                    factor = 0.3
                    if ring_a in ring_targets and ring_b in ring_targets:
                        ideal = max(230.0, abs(ring_targets[ring_a] - ring_targets[ring_b]))
            springs.append(Spring(a=a, b=b, ideal_length=ideal, strength_factor=factor))
        # Compactación central solo en layout libre (contract C01 §4.4)
        self._physics_engine.center_strength = 0.0006 if self._layout_mode_active == "free" else 0.0
        self._physics_engine.set_world(bodies, springs)
        self._rebuild_local_physics()

    def _rebuild_local_physics(self):
        """BETA1-C05: física intrarrama. Un motor local por rama expandida
        con ≥2 hijos directos, en coordenadas LOCALES del contenedor: los
        hijos se repelen, los muelles internos tiran y un clamp rectangular
        los mantiene bajo la cabecera y dentro del rectángulo."""
        self._physics_local = {}
        for tree_id, tree in self._trees.items():
            children = [c for c in getattr(tree, "_child_nodes", []) if c.isVisible()]
            if len(children) < 2 or getattr(tree, "_collapsed", False):
                continue
            rect = tree.rect()
            bodies: list[Body] = []
            child_ids: dict[str, object] = {}
            for child in children:
                extent = (
                    max(child.boundingRect().width(), child.boundingRect().height()) / 2.0
                    if isinstance(child, GraphTreeItem)
                    else getattr(child, "radius", 58.0)
                )
                cid = child.node.entity_id
                child_ids[cid] = child
                center_x = child.pos().x() + (
                    child.boundingRect().center().x() if isinstance(child, GraphTreeItem) else 0.0
                )
                center_y = child.pos().y() + (
                    child.boundingRect().center().y() if isinstance(child, GraphTreeItem) else 0.0
                )
                bodies.append(
                    Body(
                        body_id=cid,
                        x=center_x,
                        y=center_y,
                        radius=extent + 12.0,
                        bounds=(
                            rect.left() + extent + 10.0,
                            rect.top() + _CONTAINER_HEADER_HEIGHT + extent + 10.0,
                            max(rect.left() + extent + 10.0, rect.right() - extent - 10.0),
                            max(
                                rect.top() + _CONTAINER_HEADER_HEIGHT + extent + 10.0,
                                rect.bottom() - extent - 10.0,
                            ),
                        ),
                    )
                )
            springs: list[Spring] = []
            for edge_item in self._edges:
                a = edge_item.edge.source_id
                b = edge_item.edge.target_id
                if a in child_ids and b in child_ids and a != b:
                    springs.append(Spring(a=a, b=b, ideal_length=150.0))
            engine = PhysicsEngine(repulsion=60_000.0, max_speed=14.0)
            engine.set_world(bodies, springs)
            self._physics_local[tree_id] = engine

    def _apply_local_physics(self, tree_id: str, engine: PhysicsEngine) -> float:
        tree = self._trees.get(tree_id)
        if tree is None or getattr(tree, "_collapsed", False):
            return 0.0
        energy = engine.step()
        for body_id, body in engine.bodies.items():
            if body.pinned:
                continue  # el hijo arrastrado lo lleva el usuario
            child = next((c for c in tree._child_nodes if c.node.entity_id == body_id), None)
            if child is None or not child.isVisible():
                continue
            if isinstance(child, GraphTreeItem):
                rect = child.boundingRect()
                child.setPos(body.x - rect.center().x(), body.y - rect.center().y())
            else:
                child.setPos(body.x, body.y)
        return energy

    def _physics_tick(self):
        # Pan and menu-relation modes pause everything (contract §4.5)
        if self._space_pan_active or self._drag_source is not None:
            return
        # BETA1-F05: congelación total mientras el drag roza una rama —
        # el gesto de anidar gana a cualquier fuerza.
        if self._physics_drag_freeze and self._moving_item is not None:
            return
        # BETA1-C05 (decisión de producto): la física actúa TAMBIÉN durante
        # el arrastre. El item arrastrado va PINNED y su cuerpo se sincroniza
        # en vivo con el cursor: el resto del grafo reacciona a él (muelles y
        # repulsión siguen al elemento mientras lo llevas).
        moving = self._moving_item
        if moving is not None:
            top = moving
            while isinstance(top.parentItem(), (GraphNodeItem, GraphTreeItem)):
                top = top.parentItem()
            top_body = self._physics_engine.bodies.get(top.node.entity_id)
            if top_body is not None:
                center = top.sceneBoundingRect().center()
                top_body.x, top_body.y = center.x(), center.y()
                top_body.vx = top_body.vy = 0.0
                top_body.pinned = True
            parent = moving.parentItem()
            if isinstance(parent, GraphTreeItem):
                local = self._physics_local.get(parent.node.entity_id)
                if local is not None:
                    local_body = local.bodies.get(moving.node.entity_id)
                    if local_body is not None:
                        if isinstance(moving, GraphTreeItem):
                            rect = moving.boundingRect()
                            local_body.x = moving.pos().x() + rect.center().x()
                            local_body.y = moving.pos().y() + rect.center().y()
                        else:
                            local_body.x = moving.pos().x()
                            local_body.y = moving.pos().y()
                        local_body.vx = local_body.vy = 0.0
                        local_body.pinned = True
        energy = self._physics_engine.step()
        for body_id, body in self._physics_engine.bodies.items():
            if body.pinned:
                continue
            item = self._nodes.get(body_id) or self._trees.get(body_id)
            if item is None or item.parentItem() is not None:
                continue
            current = item.sceneBoundingRect().center()
            dx = body.x - current.x()
            dy = body.y - current.y()
            # BETA1-L01: deadband de 0.5px (antes 0.01). Cada moveBy dispara
            # itemChange en cascada + recálculo de las aristas conectadas; mover por
            # desplazamientos sub-píxel (cola del asentamiento) es coste Qt puro
            # imperceptible. Cortarlo reduce drásticamente el trabajo por frame.
            if abs(dx) > 0.5 or abs(dy) > 0.5:
                item.moveBy(dx, dy)
        # SEM04: sincronizar TODAS las semillas vivas (job + candidatos) con su
        # cuerpo orbitador (items top-level, no van por moveBy/_nodes).
        self._sync_seed_items()
        # BETA1-C05: física intrarrama (coords locales; viaja con la rama)
        for tree_id, local_engine in self._physics_local.items():
            energy += self._apply_local_physics(tree_id, local_engine)
        # BETA1-UX feedback: los anillos se reajustan EN VIVO (fluido, como la
        # física), no al soltar. Guardado por delta + sin rebuild de física.
        # BETA1-L01: "modo rendimiento" en grafos grandes. El recálculo de
        # spans por frame es O(n); por encima del umbral se omite (los anillos
        # se reajustan solo al asentarse, abajo) y la física hace una ráfaga
        # ACOTADA en vez de correr en vivo indefinidamente tras cada cambio.
        large = len(self._physics_engine.bodies) > PHYSICS_LIVE_MAX_BODIES
        if self._layout_mode_active == "concentric_rings" and not large:
            self._maybe_live_refresh_spans()
        # Mientras se arrastra, recargar el presupuesto: tras soltar, el grafo
        # dispone de una ráfaga completa para reacomodarse antes de congelarse.
        budget_exhausted = False
        if moving is not None:
            self._physics_frames_left = PHYSICS_SETTLE_FRAME_BUDGET
        elif large and not self._has_live_seed():
            self._physics_frames_left -= 1
            budget_exhausted = self._physics_frames_left <= 0
        settled = (
            energy < self._physics_engine.min_energy
            and moving is None
            and not self._has_live_seed()
        )
        if settled or budget_exhausted:
            # Auto-stop: convergencia por energía o fin del presupuesto (nunca
            # durante un drag — el elemento en mano debe seguir provocando
            # reacción; ni mientras haya semilla viva orbitando).
            self._physics_timer.stop()
            # BETA1-C03: con el grafo en reposo, los anillos se re-ajustan
            # alrededor del contenido (throttled: solo al estabilizarse,
            # nunca por frame — riesgo 3 del contrato C01)
            if self._layout_mode_active == "concentric_rings":
                self._refresh_ring_spans()

    def _physics_reheat(self):
        """Wake physics after ANY structural change (CRUD, layout, colapso,
        drop). Decisión de producto C05: cualquier acción re-activa la
        acomodación — la física reacciona siempre."""
        if not self._physics_enabled:
            return
        self._rebuild_physics_world()
        self._physics_engine.reheat()
        for local_engine in self._physics_local.values():
            local_engine.reheat()
        # BETA1-L01: recargar el presupuesto de asentamiento. En grafos grandes
        # acota la ráfaga (autofreeze); en pequeños es irrelevante (paran por energía).
        self._physics_frames_left = PHYSICS_SETTLE_FRAME_BUDGET
        if not self._physics_timer.isActive():
            self._physics_timer.start()

    # ── BETA1-B02: keyboard core (Delete, Escape, Space+drag) ────────────

    def _is_text_input_focused(self) -> bool:
        """True when a text editor has keyboard focus anywhere in the app.

        Canvas shortcuts must never fire while the user types in a detail
        panel: Space writes spaces, Delete deletes characters, not entities.
        """
        widget = QApplication.focusWidget()
        return isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit))

    def keyPressEvent(self, event):
        if self._is_text_input_focused():
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Space and not event.isAutoRepeat():
            if not self._space_pan_active:
                self._space_pan_active = True
                # Disable item interaction so the native ScrollHandDrag pans
                # even when the drag starts on top of a node/ring.
                self.setInteractive(False)
                self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._request_delete_selection()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self._handle_escape()
            event.accept()
            return
        # BETA1-L02: navegación por teclado. +/= acercar, -/_ alejar, F/Inicio ver todo.
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
            event.accept()
            return
        if key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
            self.zoom_out()
            event.accept()
            return
        if key in (Qt.Key.Key_F, Qt.Key.Key_Home):
            self.reset_to_panorama()  # BETA1-L02c: F SIEMPRE restaura (quita foco + encuadra)
            event.accept()
            return
        # BETA1-L02b: barra de búsqueda flotante (no abre el drawer); el workspace
        # la muestra y le da el foco. Funciona en cualquier vista.
        if key == Qt.Key.Key_D:
            self.searchRequested.emit()
            event.accept()
            return
        # BETA1-L02: saltar entre anillos contiguos (solo en vista concéntrica).
        # [ = hacia dentro (anterior), ] = hacia fuera (siguiente).
        if self._layout_mode_active == "concentric_rings":
            if key in (Qt.Key.Key_BracketLeft, Qt.Key.Key_BraceLeft):
                self.focus_adjacent_ring(-1)
                event.accept()
                return
            if key in (Qt.Key.Key_BracketRight, Qt.Key.Key_BraceRight):
                self.focus_adjacent_ring(1)
                event.accept()
                return
            # BETA1-L02b: teclas 1…9 → anillo 1..9 (índice 0..8); 0 → anillo 10º.
            if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
                if self.focus_ring_by_index(key - Qt.Key.Key_1):
                    event.accept()
                    return
            elif key == Qt.Key.Key_0:
                if self.focus_ring_by_index(9):
                    event.accept()
                    return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            # Always clear pan mode on release, even if focus moved meanwhile,
            # so the canvas can never get stuck in non-interactive state.
            if self._space_pan_active:
                self._space_pan_active = False
                self.setInteractive(True)
                self.viewport().unsetCursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _request_delete_selection(self):
        """Delete current selection through the existing route, after explicit
        confirmation. No selection → no-op (and no dialog)."""
        entity_ids = list(self._selected_entity_ids)
        relation_ids = list(self._selected_relation_ids)
        if not entity_ids and not relation_ids:
            return
        if not self._confirm_delete(entity_ids, relation_ids):
            return
        # Same intent signal as the B01 context menu → workspace._delete_selected
        self.contextDeleteRequested.emit()

    def _confirm_delete(self, entity_ids: list[str], relation_ids: list[str]) -> bool:
        """Modal confirmation. Separated so tests can monkeypatch it."""
        parts = []
        if entity_ids:
            parts.append(f"{len(entity_ids)} elemento(s)")
        if relation_ids:
            parts.append(f"{len(relation_ids)} relación(es)")
        message = f"¿Eliminar {' y '.join(parts)}?\nEsta acción no se puede deshacer."
        result = QMessageBox.question(
            self,
            "Confirmar eliminación",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _handle_escape(self):
        """Escape: cancel transient modes, clear selection, notify workspace."""
        if self._drag_source is not None:
            self._finish_relation_drag(None)
            self.relationCreateRejected.emit("Relación cancelada")
        if self._alt_line is not None:
            self._finish_alt_drag()
        self._pending_source = None
        self._alt_source = None
        self.clear_selection()
        self.escapePressed.emit()

    # ── BETA1-B01: context menus ─────────────────────────────────────────

    def contextMenuEvent(self, event):
        # Never open a menu mid-drag: cancel transient drag state first so the
        # menu cannot corrupt relation/assignment flows.
        if self._drag_source is not None:
            self._finish_relation_drag(None)
        if self._alt_line is not None:
            self._finish_alt_drag()
        self._pending_source = None
        self._alt_source = None
        menu = self._build_context_menu(QPointF(event.pos()))
        if menu is None or menu.isEmpty():
            super().contextMenuEvent(event)
            return
        event.accept()
        menu.exec(event.globalPos())

    def _build_context_menu(self, view_pos) -> QMenu | None:
        """Hit-test *view_pos* and build the QMenu for the element found.

        Priority mirrors left-click handling: node/tree, then edge, then ring,
        then background. The element under the cursor is selected first so
        edit/delete act on what the user sees highlighted.
        """
        # BETA1-F05: prioridad por orden VISUAL — una relación dibujada sobre
        # una rama gana el click derecho (igual que el izquierdo).
        kind, hit = self._topmost_node_or_edge_at(view_pos)
        if kind == "edge":
            if hit.edge.relation_id not in self._selected_relation_ids:
                self._set_single_edge_selection(hit)
            return self._edge_context_menu(hit)
        if kind == "node":
            if hit.node.entity_id not in self._selected_entity_ids:
                self._set_single_node_selection(hit)
            if isinstance(hit, GraphTreeItem):
                return self._tree_context_menu(hit)
            return self._node_context_menu(hit)
        ring = self._item_ring_at(view_pos)
        if ring is not None:
            return self._ring_context_menu(ring)
        return self._background_context_menu()

    def _background_context_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Crear hoja aquí", self.contextCreateEntityRequested.emit)
        menu.addAction("Crear rama aquí", self.contextCreateTreeRequested.emit)
        if self._selected_entity_ids or self._selected_relation_ids:
            self._add_ai_context_menu(menu)
        if self._layout_mode_active == "concentric_rings":
            menu.addSeparator()
            menu.addAction("Crear anillo…", self.ringCreateRequested.emit)
        return menu

    def _add_ai_context_menu(self, menu: QMenu) -> None:
        menu.addSeparator()
        ai_menu = QMenu("IA sobre seleccion", menu)
        menu.addMenu(ai_menu)
        ai_menu.addAction(
            "Sugerir hojas", lambda: self.contextAIActionRequested.emit("suggest_nodes")
        )
        ai_menu.addAction(
            "Sugerir ramas", lambda: self.contextAIActionRequested.emit("suggest_branches")
        )
        ai_menu.addAction(
            "Sugerir relaciones", lambda: self.contextAIActionRequested.emit("suggest_relations")
        )
        ai_menu.addAction(
            "Analizar coherencia", lambda: self.contextAIActionRequested.emit("analyze_coherence")
        )

    def _node_context_menu(self, item: GraphNodeItem) -> QMenu:
        entity_id = item.node.entity_id
        menu = QMenu(self)
        menu.addAction("Editar", lambda: self.entitySelected.emit(entity_id))
        menu.addAction(
            "Crear relación desde aquí",
            lambda: self._begin_context_relation(item),
        )
        # Parent the submenu explicitly: with addMenu("…") PySide leaves the
        # wrapper Python-owned and shiboken deletes the C++ menu when the
        # local reference dies (before exec()). QMenu(title, parent) hands
        # ownership to the parent menu.
        move_menu = QMenu("Mover a rama", menu)
        menu.addMenu(move_menu)
        targets = self._context_target_trees(exclude_id=entity_id)
        if targets:
            for tree_id, tree_name in targets:
                move_menu.addAction(
                    tree_name,
                    lambda _=False, tid=tree_id: self.nodeAssignToTreeRequested.emit(
                        entity_id, tid
                    ),
                )
        else:
            empty = move_menu.addAction("Sin ramas disponibles")
            empty.setEnabled(False)
        # BETA1-B03: ring reassignment through EntityController.update
        ring_targets = self._context_target_rings(exclude_entity=entity_id)
        if ring_targets:
            ring_menu = QMenu("Mover a anillo", menu)
            menu.addMenu(ring_menu)
            for ring_id, ring_name in ring_targets:
                ring_menu.addAction(
                    ring_name,
                    lambda _=False, rid=ring_id: self.nodeAssignToRingRequested.emit(
                        entity_id, rid
                    ),
                )
        else:
            ring_action = menu.addAction("Mover a anillo")
            ring_action.setEnabled(False)
            ring_action.setToolTip("")
        self._add_ai_context_menu(menu)
        menu.addSeparator()
        menu.addAction("Eliminar", self.contextDeleteRequested.emit)
        return menu

    def _tree_context_menu(self, item: GraphTreeItem) -> QMenu:
        tree_id = item.node.entity_id
        menu = QMenu(self)
        menu.addAction("Editar", lambda: self.entitySelected.emit(tree_id))
        menu.addAction(
            "Crear relación desde aquí",
            lambda: self._begin_context_relation(item),
        )
        menu.addAction(
            "Crear hoja dentro",
            lambda: self.contextCreateEntityInTreeRequested.emit(tree_id),
        )
        menu.addAction(
            "Crear subrama",
            lambda: self.contextCreateSubtreeRequested.emit(tree_id),
        )
        ring_targets = self._context_target_rings(exclude_entity=tree_id)
        if ring_targets:
            ring_menu = QMenu("Mover a anillo", menu)
            menu.addMenu(ring_menu)
            for ring_id, ring_name in ring_targets:
                ring_menu.addAction(
                    ring_name,
                    lambda _=False, rid=ring_id: self.nodeAssignToRingRequested.emit(tree_id, rid),
                )
        else:
            ring_action = menu.addAction("Mover a anillo")
            ring_action.setEnabled(False)
            ring_action.setToolTip("")
        self._add_ai_context_menu(menu)
        menu.addSeparator()
        menu.addAction("Eliminar", self.contextDeleteRequested.emit)
        return menu

    def _edge_context_menu(self, item: GraphEdgeItem) -> QMenu:
        relation_id = item.edge.relation_id
        menu = QMenu(self)
        menu.addAction("Editar relación", lambda: self.relationSelected.emit(relation_id))
        self._add_ai_context_menu(menu)
        menu.addSeparator()
        menu.addAction("Eliminar relación", self.contextDeleteRequested.emit)
        return menu

    def _ring_context_menu(self, item: GraphRingItem) -> QMenu:
        ring_id = item.ring.ring_id
        menu = QMenu(self)
        menu.addAction(
            "Crear hoja en este anillo",
            lambda: self._create_in_ring(ring_id, self.contextCreateEntityRequested),
        )
        menu.addAction(
            "Crear rama en este anillo",
            lambda: self._create_in_ring(ring_id, self.contextCreateTreeRequested),
        )
        # BETA1-B03: ring CRUD. The synthetic unclassified ring is not a real
        # world layer, so it cannot be edited/deleted.
        if ring_id != "__unclassified__":
            menu.addSeparator()
            menu.addAction("Editar anillo…", lambda: self.ringEditRequested.emit(ring_id))
            menu.addAction("Crear anillo…", self.ringCreateRequested.emit)
            menu.addAction("Eliminar anillo", lambda: self.ringDeleteRequested.emit(ring_id))
        return menu

    def _create_in_ring(self, ring_id: str, signal):
        # select_ring marks the ring active, so the existing creation route
        # (_with_active_ring_payload in CreationWorkspace) lands the new
        # element in this ring without new persistence logic.
        # The one-shot override guarantees the right-clicked ring wins even
        # when another ring holds focus (active_ring_id prefers focus).
        self.select_ring(ring_id)
        self._context_ring_override = ring_id
        try:
            signal.emit()  # synchronous: creation runs inside this emit
        finally:
            self._context_ring_override = ""

    def _context_target_trees(self, *, exclude_id: str) -> list[tuple[str, str]]:
        """Candidate trees for 'Mover a rama': all trees except self and any
        assignment that would create a containment cycle."""
        targets: list[tuple[str, str]] = []
        for item_id, item in self._nodes.items():
            if not isinstance(item, GraphTreeItem) or item_id == exclude_id:
                continue
            if self.would_create_cycle(exclude_id, item_id):
                continue
            targets.append((item_id, item.node.name or item_id))
        targets.sort(key=lambda pair: pair[1].lower())
        return targets[:20]

    def _context_target_rings(self, *, exclude_entity: str) -> list[tuple[str, str]]:
        """Candidate rings for 'Mover a anillo': every visible ring except the
        synthetic unclassified ring and the entity's current one."""
        current = self._node_ring_ids.get(exclude_entity, "")
        targets: list[tuple[str, str]] = []
        for ring in self._ring_visuals:
            if ring.ring_id in ("__unclassified__", current):
                continue
            targets.append((ring.ring_id, ring.display_name))
        return targets

    def _begin_context_relation(self, source: GraphNodeItem | GraphTreeItem):
        """Start the existing relation-drag flow from a context-menu action.

        The arrow follows the cursor (mouseMoveEvent already handles
        _drag_source) and the next left-click completes or cancels the
        relation — see the early branch in mousePressEvent.
        """
        self._start_relation_drag(source)

    def mousePressEvent(self, event):
        # BETA1-L02c: cualquier clic en el lienzo reclama el foco de teclado, para
        # que los atajos (1…0, F, [ ], d) funcionen también desde la panorámica sin
        # tener que enfocar un anillo antes.
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        # BETA1-B02: in space-pan mode the view is non-interactive and the
        # native ScrollHandDrag must receive the press untouched (no
        # selection, no relation logic).
        if self._space_pan_active:
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            # BETA1-G06: cada press nuevo reabre la posibilidad de "click →
            # panel". El doble click la vuelve a suprimir (ver doubleClick).
            self._suppress_release_click = False
            # BETA1-B01: a relation started from the context menu has
            # _drag_source set without a held button; the next click picks
            # the target (or cancels on background). Normal drags never enter
            # here because the button is already held down.
            if self._drag_source is not None and self._pending_source is None:
                source = self._drag_source
                target = self._item_node_at(event.position())
                self._finish_relation_drag(target)
                if target is None:
                    self.relationCreateRejected.emit("Relación cancelada")
                elif target is source:
                    self.relationCreateRejected.emit(
                        "No se puede crear una relación sobre el mismo elemento"
                    )
                else:
                    self.relationCreateRequested.emit(source.node.entity_id, target.node.entity_id)
                event.accept()
                return
            # SEM04-fix: una semilla germinante bajo el cursor abre su revisión.
            seed = self._item_seed_at(event.position())
            if seed is not None:
                self._seed_clicked(seed.candidate_id)
                event.accept()
                return
            items = self.items(event.position().toPoint())
            _b44trace(
                "mouse_press "
                f"layout={self._layout_mode_active} pos=({event.position().x():.1f},{event.position().y():.1f}) "
                f"scene=({self.mapToScene(event.position().toPoint()).x():.1f},{self.mapToScene(event.position().toPoint()).y():.1f}) "
                f"items={[type(item).__name__ for item in items[:8]]!r}"
            )
            alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            # BETA1-F05: respetar el orden VISUAL — si la relación está
            # dibujada encima de una rama, el click selecciona la relación.
            kind, hit = self._topmost_node_or_edge_at(event.position())
            node = hit if kind == "node" else None
            edge = hit if kind == "edge" else None
            if node is None and edge is None:
                node = self._item_node_at(event.position())

            # Alt+Click on a node or container: start tree-assignment drag
            if alt and node is not None and isinstance(node, (GraphNodeItem, GraphTreeItem)):
                self._alt_source = node
                self._alt_origin_view_pos = event.position()
                event.accept()
                return

            if edge is not None:
                if ctrl:
                    self._toggle_edge_selection(edge)
                    event.accept()
                    return
                self._set_single_edge_selection(edge)
                # BETA1-G06: emitir en release como los nodos para que el doble
                # click suprima el segundo pop. Press2 de un doble click ya
                # tendría _suppress_release_click=True en el doubleClickEvent,
                # así que el release final NO reabrirá el panel.
                self._pressed_edge_id = edge.edge.relation_id
                event.accept()
                return

            if node is not None:
                if ctrl:
                    self._toggle_node_selection(node)
                    event.accept()
                    return
                self._set_single_node_selection(node)
                # BETA1-G06: NO se emite aquí. El panel se abre en el release
                # SOLO si el elemento no se arrastró (click vs drag) — así un
                # click simple abre el detalle sin que arrastrar dispare pop-ups.
                # BETA1-B03: plain drag moves the item (ItemIsMovable does the
                # work once the item receives the press). Relation creation
                # moved to the context menu in B01, so the old drag-to-relate
                # interception is gone. Track the item to support
                # drop-on-tree assignment at release.
                self._moving_item = node
                self._move_origin_scene = QPointF(node.scenePos())
                # BETA1-C05: la física sigue viva durante el arrastre — si el
                # timer estaba dormido por convergencia, despertarlo para que
                # el grafo reaccione al elemento en mano.
                if self._physics_enabled and not self._physics_timer.isActive():
                    self._physics_timer.start()
                super().mousePressEvent(event)
                return
            ring = self._item_ring_at(event.position())
            _b44trace(
                "mouse_press_hit "
                f"node={getattr(getattr(node, 'node', None), 'entity_id', '') if node is not None else ''!r} "
                f"edge={getattr(getattr(edge, 'edge', None), 'relation_id', '') if edge is not None else ''!r} "
                f"ring={getattr(getattr(ring, 'ring', None), 'ring_id', '') if ring is not None else ''!r}"
            )
            if ring is not None:
                self.select_ring(ring.ring.ring_id)
                event.accept()
                return
            self.clear_selection()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # BETA1-G06: el click simple ya abrió el panel en su release. El
            # doble click NO debe reabrirlo (causa de los "pop ups de nuevo"):
            # suprimimos el release-click que cierra esta secuencia.
            self._suppress_release_click = True
            items = self.items(event.position().toPoint())
            _b44trace(
                "mouse_double "
                f"layout={self._layout_mode_active} pos=({event.position().x():.1f},{event.position().y():.1f}) "
                f"items={[type(item).__name__ for item in items[:8]]!r}"
            )
            # BETA1-G06: hojas y relaciones ya abren su panel con un click
            # simple → el doble click no reemite (evita el doble pop). Las
            # RAMAS (GraphTreeItem) caen al super() para conservar su colapso
            # por doble click en la cabecera; el vacío sigue al foco de anillo.
            kind, hit = self._topmost_node_or_edge_at(event.position())
            if kind == "edge" or (kind == "node" and isinstance(hit, GraphNodeItem)):
                event.accept()
                return
            node = self._item_node_at(event.position())
            edge = self._item_edge_at(event.position())
            if node is None and edge is None:
                ring = self._item_ring_at(event.position())
                _b44trace(
                    "mouse_double_hit "
                    f"node='' edge='' ring={getattr(getattr(ring, 'ring', None), 'ring_id', '') if ring is not None else ''!r}"
                )
                if ring is not None:
                    self.select_ring(ring.ring.ring_id)
                    self.focus_ring_scope(ring.ring.ring_id)
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        # BETA1-B02: space-pan passes straight to the native hand-drag
        if self._space_pan_active:
            super().mouseMoveEvent(event)
            return
        # BETA1-F05: durante un drag, si el item roza una rama destino la
        # física se congela y la rama se ilumina — anidar sin pelear.
        if self._moving_item is not None:
            target = self._drop_tree_target(self._moving_item, event.position())
            if target is not self._drop_highlight_tree:
                if self._drop_highlight_tree is not None:
                    self._drop_highlight_tree.set_drag_highlight(False)
                self._drop_highlight_tree = target
                if target is not None:
                    target.set_drag_highlight(True)
            self._physics_drag_freeze = target is not None
        # Alt-drag: moving node into tree container
        if self._alt_source is not None and self._alt_line is None:
            delta = event.position() - self._alt_origin_view_pos
            if abs(delta.x()) + abs(delta.y()) > 10:
                self._start_alt_drag(self._alt_source)
        if self._alt_line is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            tree_target = self._item_tree_at(event.position())
            self._update_alt_drag(scene_pos, tree_target)
            event.accept()
            return

        # BETA1-B03: plain drag no longer starts a relation (it moves the
        # item natively). Relations start from the context menu, which sets
        # _drag_source directly via _begin_context_relation.
        if self._drag_source is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._update_relation_drag(scene_pos, self._item_node_at(event.position()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # BETA1-B02: space-pan release returns to the open-hand cursor
        if self._space_pan_active:
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            super().mouseReleaseEvent(event)
            return
        # Alt-drag release: assign node to tree
        if self._alt_line is not None:
            source_item = self._alt_source
            target_tree = self._item_tree_at(event.position())
            self._finish_alt_drag()
            if target_tree is not None and source_item is not None:
                src_id = source_item.node.entity_id
                tgt_id = target_tree.node.entity_id
                if self.would_create_cycle(src_id, tgt_id):
                    self.relationCreateRejected.emit(
                        "No se puede asignar: crearía un ciclo de contención"
                    )
                else:
                    self.nodeAssignToTreeRequested.emit(src_id, tgt_id)
            event.accept()
            return

        if self._drag_source is not None:
            source = self._drag_source
            target = self._item_node_at(event.position())
            self._finish_relation_drag(target)
            if target is not None:
                if target is source:
                    self.relationCreateRejected.emit(
                        "No se puede crear una relación sobre el mismo elemento"
                    )
                else:
                    self.relationCreateRequested.emit(source.node.entity_id, target.node.entity_id)
            else:
                self.relationCreateRejected.emit("Relación cancelada")
            event.accept()
            return
        # BETA1-B03: finish a native move-drag. If the item was dropped on a
        # tree container, offer assignment through the existing route (same
        # signal as Alt+drag and the context menu).
        moving = self._moving_item
        self._moving_item = None
        # BETA1-F05: limpiar congelación e iluminación de drop
        self._physics_drag_freeze = False
        if self._drop_highlight_tree is not None:
            self._drop_highlight_tree.set_drag_highlight(False)
            self._drop_highlight_tree = None
        if moving is not None and event.button() == Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)  # let Qt close the move grab
            # BETA1-K01: _handle_move_drop puede emitir una señal que reconstruye
            # la escena (refresh → set_graph) y destruir `moving`; capturamos id y
            # posición ANTES de soltar para no tocar un objeto C++ ya borrado.
            moved_entity_id = moving.node.entity_id
            if moving.scenePos() != self._move_origin_scene:
                center = moving.sceneBoundingRect().center()
                self._handle_move_drop(moving, event.position())
                # BETA1-C02: adopt the user's placement and wake physics
                if self._physics_enabled:
                    self._physics_engine.sync_position(moved_entity_id, center.x(), center.y())
                    self._physics_reheat()
            elif not self._suppress_release_click:
                # BETA1-G06: no se movió → fue un click. Abre el panel de
                # detalle de la hoja/rama (el doble click suprime esta rama).
                self.entitySelected.emit(moved_entity_id)
            self._suppress_release_click = False
            self._pressed_edge_id = ""
            return
        # BETA1-G06: edge click → emitir en release con la misma guardia de
        # supresión que los nodos (evita el segundo pop en doble click).
        if self._pressed_edge_id and event.button() == Qt.MouseButton.LeftButton:
            rel_id = self._pressed_edge_id
            self._pressed_edge_id = ""
            if not self._suppress_release_click:
                self.relationSelected.emit(rel_id)
            self._suppress_release_click = False
            return
        self._pending_source = None
        self._alt_source = None
        super().mouseReleaseEvent(event)

    def _handle_move_drop(self, moved: GraphNodeItem | GraphTreeItem, view_pos):
        """BETA1-B03: dropping a moved item onto a tree assigns it to that
        tree — no Alt needed. Drops elsewhere just leave the item moved."""
        target = self._drop_tree_target(moved, view_pos)
        if target is None:
            parent = moved.parentItem()
            if isinstance(parent, GraphTreeItem):
                # BETA1-B03: dropping OUTSIDE the container's own rectangle
                # (pre-refit, children excluded) extracts the item from the
                # branch instead of stretching the branch to swallow it.
                drop_scene = self.mapToScene(view_pos.toPoint())
                parent_rect = parent.mapRectToScene(parent.rect())
                if not parent_rect.contains(drop_scene):
                    self.nodeExtractFromTreeRequested.emit(moved.node.entity_id)
                    return
                # Internal rearrange: refit the whole ancestor chain
                ancestor = parent
                while isinstance(ancestor, GraphTreeItem):
                    if ancestor._child_nodes:
                        ancestor.resize_to_fit_children()
                    ancestor = ancestor.parentItem()
            # BETA1-B03: rings wrap the content wherever the user left it —
            # spans recalc after EVERY move, without repositioning items.
            self._refresh_ring_spans()
            return
        src_id = moved.node.entity_id
        tgt_id = target.node.entity_id
        if self._membership.get(src_id) == tgt_id:
            return
        if self.would_create_cycle(src_id, tgt_id):
            self.relationCreateRejected.emit("No se puede asignar: crearía un ciclo de contención")
            return
        self.nodeAssignToTreeRequested.emit(src_id, tgt_id)

    def _drop_tree_target(self, moved, view_pos) -> GraphTreeItem | None:
        """Tree under *view_pos*, excluding the moved item itself and its
        current ancestor chain (so dragging a child within its own tree is a
        rearrange, not a reassignment)."""
        ancestors: set = set()
        parent = moved.parentItem()
        while parent is not None:
            ancestors.add(parent)
            parent = parent.parentItem()
        for item in self.items(view_pos.toPoint()):
            check = item
            while check is not None:
                if (
                    isinstance(check, GraphTreeItem)
                    and check is not moved
                    and check not in ancestors
                ):
                    return check
                check = check.parentItem()
        return None

    def _start_relation_drag(self, source: GraphNodeItem | GraphTreeItem):
        self._drag_source = source
        self._drag_target = None
        line = QGraphicsPathItem()
        pen = QPen(QColor("#D08770"), 2.5, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line.setPen(pen)
        line.setZValue(3)
        line.setToolTip("")
        self._drag_line = line
        self.scene_obj.addItem(line)
        source.set_drag_highlight(True)

    def _update_relation_drag(
        self, scene_pos: QPointF, target: GraphNodeItem | GraphTreeItem | None
    ):
        if self._drag_source is None or self._drag_line is None:
            return
        start = self._drag_source.scenePos()
        self._drag_line.setPath(self._relation_drag_arrow_path(start, scene_pos))
        if target is self._drag_source:
            target = None
        if target is not self._drag_target:
            if self._drag_target is not None:
                self._drag_target.set_drag_highlight(False)
            self._drag_target = target
            if self._drag_target is not None:
                self._drag_target.set_drag_highlight(True)

    def _relation_drag_arrow_path(self, start: QPointF, end: QPointF) -> QPainterPath:
        path = QPainterPath(start)
        path.lineTo(end)
        line = QLineF(start, end)
        if line.length() > 4:
            angle = math.atan2(-(end.y() - start.y()), end.x() - start.x())
            arrow_size = 16
            p1 = QPointF(
                end.x() - arrow_size * math.cos(angle - math.pi / 6),
                end.y() + arrow_size * math.sin(angle - math.pi / 6),
            )
            p2 = QPointF(
                end.x() - arrow_size * math.cos(angle + math.pi / 6),
                end.y() + arrow_size * math.sin(angle + math.pi / 6),
            )
            path.moveTo(end)
            path.lineTo(p1)
            path.moveTo(end)
            path.lineTo(p2)
        return path

    def _finish_relation_drag(self, target: GraphNodeItem | GraphTreeItem | None):
        if self._drag_source is not None:
            self._drag_source.set_drag_highlight(False)
        if self._drag_target is not None:
            self._drag_target.set_drag_highlight(False)
        if self._drag_line is not None:
            self.scene_obj.removeItem(self._drag_line)
            self._drag_line = None
        self._pending_source = None
        self._drag_source = None
        self._drag_target = None

    def _item_tree_at(self, view_pos) -> GraphTreeItem | None:
        """Find a GraphTreeItem under *view_pos*."""
        for item in self.items(view_pos.toPoint()):
            check = item
            while check is not None:
                if isinstance(check, GraphTreeItem):
                    return check
                check = check.parentItem()
        return None

    def _start_alt_drag(self, source: GraphNodeItem | GraphTreeItem):
        line = QGraphicsLineItem()
        pen = QPen(QColor("#5B8DEF"), 2.5, Qt.PenStyle.DashDotLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line.setPen(pen)
        line.setZValue(3)
        self._alt_line = line
        self.scene_obj.addItem(line)

    def _update_alt_drag(self, scene_pos: QPointF, target: GraphTreeItem | None):
        if self._alt_source is None or self._alt_line is None:
            return
        start = self._alt_source.scenePos()
        self._alt_line.setLine(QLineF(start, scene_pos))
        if target is not self._alt_tree_target:
            if self._alt_tree_target is not None:
                self._alt_tree_target.set_drag_highlight(False)
            self._alt_tree_target = target
            if self._alt_tree_target is not None:
                self._alt_tree_target.set_drag_highlight(True)
        # Visual feedback: red line if would create cycle
        if target is not None and self._alt_source is not None:
            src_id = self._alt_source.node.entity_id
            tgt_id = target.node.entity_id
            if self.would_create_cycle(src_id, tgt_id):
                self._alt_line.setPen(QPen(QColor("#D94040"), 2.5, Qt.PenStyle.DashDotLine))
            else:
                self._alt_line.setPen(QPen(QColor("#5B8DEF"), 2.5, Qt.PenStyle.DashDotLine))

    def _finish_alt_drag(self):
        if self._alt_tree_target is not None:
            self._alt_tree_target.set_drag_highlight(False)
        if self._alt_line is not None:
            self.scene_obj.removeItem(self._alt_line)
            self._alt_line = None
        self._alt_source = None
        self._alt_tree_target = None

    def would_create_cycle(self, child_id: str, parent_tree_id: str) -> bool:
        """Check if adding child_id to parent_tree_id would create a cycle."""
        if child_id == parent_tree_id:
            return True
        current = parent_tree_id
        visited = set()
        while current in self._membership:
            if current == child_id:
                return True
            if current in visited:
                break
            visited.add(current)
            current = self._membership[current]
        return False

    def tree_container_for(self, entity_id: str) -> str | None:
        """Return the tree entity_id that contains entity_id, or None."""
        return self._membership.get(entity_id)

    def _descendant_ids_for_tree(self, tree_id: str) -> set[str]:
        descendants: set[str] = set()
        stack = [tree_id]
        while stack:
            parent = stack.pop()
            for child, current_parent in self._membership.items():
                if current_parent == parent and child not in descendants:
                    descendants.add(child)
                    stack.append(child)
        return descendants

    def _ancestor_tree_ids(self, entity_id: str) -> list[str]:
        ancestors: list[str] = []
        current = self._membership.get(entity_id)
        seen: set[str] = set()
        while current and current not in seen:
            ancestors.append(current)
            seen.add(current)
            current = self._membership.get(current)
        return ancestors

    def _parent_tree_info(self, entity_id: str) -> tuple[str, str, bool]:
        parent_id = self._membership.get(entity_id) or ""
        if not parent_id:
            return "", "", False
        parent_node = next((node for node in self._all_nodes if node.entity_id == parent_id), None)
        parent_name = parent_node.name if parent_node is not None else "Árbol"
        parent_item = self._trees.get(parent_id)
        collapsed = (
            bool(getattr(parent_item, "_collapsed", False)) if parent_item is not None else False
        )
        return parent_id, parent_name, collapsed

    def _node_exists_at_view_year(self, node: _NodeView) -> bool:
        """BETA1-G06: ¿la entidad existe en el año-cámara actual?"""
        if self._view_year is None:
            return True
        return interval_contains_year(node.birth_year, node.death_year, self._view_year)

    def _edge_exists_at_view_year(self, edge: _EdgeView) -> bool:
        """BETA1-G06: existencia EXPLÍCITA de la relación en el año-cámara.

        La existencia derivada (extremos vivos) la garantiza el filtro de nodos
        — aquí solo se aplica el intervalo propio si la relación lo declara.
        """
        if self._view_year is None or edge.birth_year is None:
            return True
        return interval_contains_year(edge.birth_year, edge.death_year, self._view_year)

    def _temporal_snapshot(
        self, nodes: list[_NodeView], edges: list[_EdgeView]
    ) -> tuple[list[_NodeView], list[_EdgeView]]:
        """BETA1-G06: aplica SOLO la cámara temporal (sin filtros visuales).

        Se usa en la rama de foco de anillo, que omite ``_filtered_graph``."""
        if self._view_year is None:
            return list(nodes), list(edges)
        fnodes = [node for node in nodes if self._node_exists_at_view_year(node)]
        visible = {node.entity_id for node in fnodes}
        fedges = [
            edge
            for edge in edges
            if edge.source_id in visible
            and edge.target_id in visible
            and self._edge_exists_at_view_year(edge)
        ]
        return fnodes, fedges

    def set_view_year(self, year: int | None):
        """BETA1-G06: fija el año-cámara (None = atemporal) y reconstruye el
        grafo como la 'fotografía' del mundo en ese momento."""
        new_year = None if year is None else int(year)
        if new_year == self._view_year:
            return
        self._view_year = new_year
        self.set_graph(
            self._all_nodes,
            self._all_edges,
            layout_mode=self._layout_mode_active,
            layers=self._all_layers,
        )

    def view_year(self) -> int | None:
        return self._view_year

    def _node_passes_filter(
        self, node: _NodeView, allowed_tree_ids: set[str] | None = None
    ) -> bool:
        vf = self._visual_filter
        if not self._node_exists_at_view_year(node):
            return False
        if allowed_tree_ids is not None and node.entity_id not in allowed_tree_ids:
            return False
        if vf.focus_entity_ids and node.entity_id not in vf.focus_entity_ids:
            return False
        if vf.entity_types and node.kind.lower() not in vf.entity_types:
            return False
        if vf.layer_ids and (node.layer_id or "") not in vf.layer_ids:
            return False
        if vf.canon_states and node.canon.lower() not in vf.canon_states:
            return False
        if vf.visibility_states and node.visibility.lower() not in vf.visibility_states:
            return False
        return True

    def _edge_passes_filter(self, edge: _EdgeView, visible_node_ids: set[str]) -> bool:
        vf = self._visual_filter
        if edge.source_id not in visible_node_ids or edge.target_id not in visible_node_ids:
            return False
        if not self._edge_exists_at_view_year(edge):
            return False
        if edge.kind.lower() == "contiene":
            return True
        if not vf.show_relations:
            return False
        if vf.relation_families and relation_family(edge.kind) not in vf.relation_families:
            return False
        if vf.relation_types and edge.kind.lower() not in vf.relation_types:
            return False
        return True

    def _filtered_graph(
        self, nodes: list[_NodeView], edges: list[_EdgeView]
    ) -> tuple[list[_NodeView], list[_EdgeView]]:
        # Build membership from the full edge set before applying visual filters.
        self._membership = {
            edge.target_id: edge.source_id for edge in edges if edge.kind.lower() == "contiene"
        }
        tree_scope: set[str] | None = None
        if self._visual_filter.tree_id:
            tree_scope = {self._visual_filter.tree_id} | self._descendant_ids_for_tree(
                self._visual_filter.tree_id
            )
        filtered_nodes = [node for node in nodes if self._node_passes_filter(node, tree_scope)]
        visible_node_ids = {node.entity_id for node in filtered_nodes}
        filtered_edges = [
            edge for edge in edges if self._edge_passes_filter(edge, visible_node_ids)
        ]
        return filtered_nodes, filtered_edges

    def clear_graph(self):
        self.clear_selection(emit=False)
        self.scene_obj.clear()
        self._nodes.clear()
        self._trees.clear()
        self._edges.clear()
        self._ring_visuals.clear()
        self._ring_items.clear()
        self._node_ring_ids.clear()
        self._selected_ring_id = ""
        # SEM04: scene.clear() destruyó también los items de semilla; el modelo de
        # datos persiste, así que se re-renderizan sobre el grafo reconstruido.
        self._seed_items = {}
        self._render_seeds()
        self._emit_selection_changed()

    # ── SEM04: semillas germinantes en el grafo ──────────────────────────────

    def _seed_ring_visual(self, ring_id: str = "") -> "_RingVisual | None":
        """Resuelve el anillo de la semilla por precedencia: id explícito →
        anillo enfocado → anillo seleccionado. None si ninguno está dibujado."""
        for rid in (ring_id, self._focused_ring_id, self._selected_ring_id):
            if not rid:
                continue
            visual = next((r for r in self._ring_visuals if r.ring_id == rid), None)
            if visual is not None:
                return visual
        return None

    def _seed_anchor(self, ring_id: str = "") -> QPointF:
        # Punto en la BANDA del anillo (no su centro): mid-radius centrado en
        # el origen, como los nodos. Centro/viewport solo como último recurso.
        visual = self._seed_ring_visual(ring_id)
        if visual is not None:
            return self._position_for_ring_slot(visual, 0, 1)
        rid = self._focused_ring_id or self._selected_ring_id
        item = self._ring_items.get(rid) if rid else None
        if item is not None:
            return item.sceneBoundingRect().center()
        return self.mapToScene(self.viewport().rect().center())

    def _has_live_seed(self) -> bool:
        """True si hay alguna semilla viva orbitando: la germinante del job o
        cualquier semilla-candidato en revisión (modo 'candidate'). Las que
        animan salida (bloom/wither) no cuentan."""
        if self._job_seeds:
            return True
        return any(d.get("mode") == "candidate" for d in self._candidate_seed_data.values())

    def _live_seed_bodies(self):
        """Itera (body_id, ring_id, item) de todas las semillas vivas: la del
        job y las candidatas en revisión. El candidato orbita igual que la
        semilla que lo engendró (no queda estático)."""
        for job_id, data in self._job_seeds.items():
            yield (
                f"__seed__{job_id}",
                data.get("ring_id", ""),
                self._seed_items.get(f"job:{job_id}"),
            )
        for cid, data in self._candidate_seed_data.items():
            if data.get("mode") != "candidate":
                continue
            yield (
                f"__seed__cand__{cid}",
                data.get("ring_id", ""),
                self._seed_items.get(f"cand:{cid}"),
            )

    def _build_seed_body(self, body_id, ring_id, item, ring_bands):
        """Construye el cuerpo orbitador de una semilla en la banda de su anillo
        (mismas constantes para job y candidato). None si no hay corona."""
        band = ring_bands.get(ring_id)
        if band is None and ring_bands:
            outermost = max(outer for _, outer in ring_bands.values())
            band = (outermost + 34.0, outermost + 34.0 + 240.0)
        if band is None:
            return None
        inner, outer = band
        target = (inner + outer) / 2.0
        ext = GraphSeedItem._R + 6.0
        s_inner = inner + min(ext, (outer - inner) / 2.0 - 1.0)
        s_outer = max(s_inner, outer - min(ext, (outer - inner) / 2.0 - 1.0))
        if item is not None:
            c = item.sceneBoundingRect().center()
            sx, sy = c.x(), c.y()
        else:
            sx, sy = 0.0, target
        return Body(
            body_id=body_id,
            x=sx,
            y=sy,
            mass=0.6,
            radius=ext + 12.0,
            target_radius=target,
            band_inner=s_inner,
            band_outer=s_outer,
            orbit_speed=_SEED_ORBIT_SPEED,
            orbit_drift=_SEED_ORBIT_DRIFT,
            orbit_drift_rate=_SEED_ORBIT_DRIFT_RATE,
        )

    def _sync_seed_items(self) -> None:
        """Sincroniza cada item de semilla viva con su cuerpo orbitador y guarda
        ángulo/radio/posición en el modelo (sobreviven a clear_graph)."""
        for job_id, data in self._job_seeds.items():
            self._sync_seed_one(f"__seed__{job_id}", f"job:{job_id}", data)
        for cid, data in self._candidate_seed_data.items():
            if data.get("mode") != "candidate":
                continue
            self._sync_seed_one(f"__seed__cand__{cid}", f"cand:{cid}", data)

    def _sync_seed_one(self, body_id: str, item_key: str, data: dict) -> None:
        body = self._physics_engine.bodies.get(body_id)
        item = self._seed_items.get(item_key)
        if body is None or item is None:
            return
        item.setPos(body.x, body.y)
        data["angle"] = math.atan2(body.y, body.x)
        data["radius"] = math.hypot(body.x, body.y)
        data["pos"] = QPointF(body.x, body.y)

    def _ensure_seed_physics(self) -> None:
        """Reconstruye el mundo físico (incorpora/retira cuerpos de semilla) y
        mantiene el timer activo mientras haya una semilla viva orbitando
        (germinante o candidato en revisión)."""
        if not self._physics_enabled:
            return
        self._rebuild_physics_world()
        if self._has_live_seed() and not self._physics_timer.isActive():
            self._physics_timer.start()

    def _render_seeds(self) -> None:
        # Recrea los items de semilla desde el modelo de datos (tras un rebuild).
        for job_id, data in self._job_seeds.items():
            it = GraphSeedItem(job_id=job_id)
            # Re-posicionar en su banda (el anillo pudo redimensionarse).
            visual = self._seed_ring_visual(data.get("ring_id", ""))
            if visual is not None:
                radius = (visual.inner_radius + visual.outer_radius) / 2.0
                angle = data.get("angle", math.pi / 2.0)
                it.setPos(math.cos(angle) * radius, math.sin(angle) * radius)
            else:
                it.setPos(data.get("anchor", QPointF(0.0, 0.0)))
            it.restore_phase(data.get("phase", 0.0))
            self.scene_obj.addItem(it)
            self._seed_items[f"job:{job_id}"] = it
        for cid, data in self._candidate_seed_data.items():
            it = GraphSeedItem(candidate_id=cid)
            # Re-posicionar en su banda (orbitan igual que la semilla del job).
            visual = self._seed_ring_visual(data.get("ring_id", ""))
            if visual is not None and "angle" in data:
                radius = (visual.inner_radius + visual.outer_radius) / 2.0
                angle = data.get("angle", math.pi / 2.0)
                it.setPos(math.cos(angle) * radius, math.sin(angle) * radius)
            else:
                it.setPos(data.get("pos", QPointF(0.0, 0.0)))
            it.set_mode(data.get("mode", "candidate"))
            self.scene_obj.addItem(it)
            self._seed_items[f"cand:{cid}"] = it
        self._maybe_run_seed_timer()

    def _maybe_run_seed_timer(self) -> None:
        if self._seed_items and not self._seed_timer.isActive():
            self._seed_timer.start()
        elif not self._seed_items and self._seed_timer.isActive():
            self._seed_timer.stop()

    def _seed_tick(self) -> None:
        self._seed_pulse += 0.18
        done_keys: list[str] = []
        for key, item in list(self._seed_items.items()):
            finished = item.tick(pulse=self._seed_pulse, anim_step=0.06)
            if finished:
                done_keys.append(key)
        for key in done_keys:
            item = self._seed_items.pop(key, None)
            if item is not None:
                self.scene_obj.removeItem(item)
            if key.startswith("cand:"):
                self._candidate_seed_data.pop(key[5:], None)
            elif key.startswith("job:"):
                self._job_seeds.pop(key[4:], None)
        if not self._seed_items:
            self._seed_timer.stop()

    def plant_seed(self, job_id: str, ring_id: str = "") -> None:
        if not job_id or job_id in self._job_seeds:
            return
        visual = self._seed_ring_visual(ring_id)
        if visual is not None:
            radius = (visual.inner_radius + visual.outer_radius) / 2.0
            angle = math.pi / 2.0
            anchor = QPointF(math.cos(angle) * radius, math.sin(angle) * radius)
            rid = visual.ring_id
        else:
            anchor = self._seed_anchor(ring_id)
            radius = None
            angle = (
                math.atan2(anchor.y(), anchor.x()) if (anchor.x() or anchor.y()) else math.pi / 2.0
            )
            rid = ""
        self._job_seeds[job_id] = {
            "ring_id": rid,
            "angle": angle,
            "radius": radius,
            "anchor": anchor,
            "phase": 0.0,
        }
        it = GraphSeedItem(job_id=job_id)
        it.setPos(anchor)
        self.scene_obj.addItem(it)
        self._seed_items[f"job:{job_id}"] = it
        self._maybe_run_seed_timer()
        # Registrar el cuerpo orbitador y (re)arrancar la física.
        self._ensure_seed_physics()

    def advance_seed(self, job_id: str, progress: float) -> None:
        data = self._job_seeds.get(job_id)
        if data is None:
            return
        data["phase"] = max(0.0, min(1.0, float(progress)))
        it = self._seed_items.get(f"job:{job_id}")
        if it is not None:
            it.set_phase(data["phase"])

    def split_seed(
        self, job_id: str, candidate_ids: list[str], ring_ids: dict[str, str] | None = None
    ) -> None:
        # Retira la semilla germinante del job y la sustituye por N
        # semillas-candidato que HEREDAN su órbita/física: el candidato releva a
        # la semilla que lo engendró (no queda estático). Emergen del punto VIVO
        # de la semilla y la física los reparte por la corona.
        data = self._job_seeds.pop(job_id, None)
        planted_ring = data.get("ring_id", "") if data else ""
        job_body = self._physics_engine.bodies.get(f"__seed__{job_id}")
        if job_body is not None:
            handoff = QPointF(job_body.x, job_body.y)
        elif data and data.get("anchor"):
            handoff = data["anchor"]
        else:
            handoff = self._seed_anchor(planted_ring)
        it = self._seed_items.pop(f"job:{job_id}", None)
        if it is not None:
            self.scene_obj.removeItem(it)
        cids = [c for c in (candidate_ids or []) if c]
        ring_map = ring_ids or {}
        # Agrupar por anillo resuelto. El primer grupo releva desde el punto vivo
        # de la semilla; el resto (anillos distintos) cae en su banda.
        by_ring: dict[str, list[str]] = {}
        for cid in cids:
            by_ring.setdefault(ring_map.get(cid) or planted_ring, []).append(cid)
        first = True
        for rid, group in by_ring.items():
            self._place_candidate_seeds(group, rid, handoff, origin=handoff if first else None)
            first = False
        self._maybe_run_seed_timer()
        # Las semillas-candidato siguen vivas y orbitando: la física continúa.
        self._ensure_seed_physics()

    def _place_candidate_seeds(
        self, cids: list[str], ring_id: str, fallback: QPointF, origin: QPointF | None = None
    ) -> None:
        """Crea semillas-candidato ORBITADORAS. Si se da ``origin`` (relevo de la
        semilla-job), emergen de ese punto vivo y la física las reparte por la
        corona; si no, se colocan en la banda de su anillo (o en abanico
        alrededor de ``fallback`` si el anillo no está dibujado)."""
        visual = self._seed_ring_visual(ring_id) if ring_id else None
        n = len(cids)
        for i, cid in enumerate(cids):
            if cid in self._candidate_seed_data:
                continue
            if origin is not None:
                # Relevo: nacen del punto de la semilla con un desfase mínimo
                # determinista (no coincidentes); la repulsión + corona separa.
                off = 0.0 if i == 0 else (7.0 + 4.0 * i)
                a = i * 2.39996  # ángulo dorado
                pos = QPointF(origin.x() + off * math.cos(a), origin.y() + off * math.sin(a))
            elif visual is not None:
                pos = self._position_for_ring_slot(visual, i, n)
            else:
                ang = (2.0 * math.pi * i / n) if n > 1 else 0.0
                radius = 0.0 if n == 1 else 130.0
                pos = QPointF(
                    fallback.x() + radius * math.cos(ang),
                    fallback.y() + radius * math.sin(ang),
                )
            angle = math.atan2(pos.y(), pos.x()) if (pos.x() or pos.y()) else math.pi / 2.0
            self._candidate_seed_data[cid] = {
                "pos": pos,
                "mode": "candidate",
                "ring_id": ring_id,
                "angle": angle,
            }
            seed = GraphSeedItem(candidate_id=cid)
            seed.setPos(pos)
            self.scene_obj.addItem(seed)
            self._seed_items[f"cand:{cid}"] = seed

    def bloom_seed(self, candidate_id: str) -> None:
        data = self._candidate_seed_data.get(candidate_id)
        if data is None:
            return
        data["mode"] = "blooming"
        it = self._seed_items.get(f"cand:{candidate_id}")
        if it is not None:
            it.set_mode("blooming")
        self._maybe_run_seed_timer()
        # Deja de orbitar: su cuerpo se retira y florece en el sitio.
        self._ensure_seed_physics()

    def wither_seed(self, key: str) -> None:
        # key = job_id (germinante) o candidate_id (semilla-candidato).
        if key in self._job_seeds:
            self._job_seeds.pop(key, None)
            it = self._seed_items.get(f"job:{key}")
            if it is not None:
                it.set_mode("withering")
            # Retirar su cuerpo orbitador: la física puede volver a asentarse.
            self._ensure_seed_physics()
            return
        data = self._candidate_seed_data.get(key)
        if data is not None:
            data["mode"] = "withering"
            it = self._seed_items.get(f"cand:{key}")
            if it is not None:
                it.set_mode("withering")
        self._maybe_run_seed_timer()
        # Deja de orbitar: su cuerpo se retira y se marchita en el sitio.
        self._ensure_seed_physics()

    def rehydrate_candidate_seeds(
        self, candidate_ids: list[str], ring_ids: dict[str, str] | None = None
    ) -> None:
        # Asegura una semilla-candidato por candidato pendiente (idempotente).
        # No retira las que están animando salida (bloom/wither).
        wanted = {c for c in (candidate_ids or []) if c}
        for cid in list(self._candidate_seed_data):
            data = self._candidate_seed_data[cid]
            if cid not in wanted and data.get("mode") == "candidate":
                self._candidate_seed_data.pop(cid, None)
                it = self._seed_items.pop(f"cand:{cid}", None)
                if it is not None:
                    self.scene_obj.removeItem(it)
        ring_map = ring_ids or {}
        fallback = self._seed_anchor()
        missing = [c for c in wanted if c not in self._candidate_seed_data]
        by_ring: dict[str, list[str]] = {}
        for cid in missing:
            by_ring.setdefault(ring_map.get(cid, ""), []).append(cid)
        for rid, group in by_ring.items():
            self._place_candidate_seeds(group, rid, fallback)
        self._maybe_run_seed_timer()
        # Los candidatos rehidratados también orbitan: arrancar la física.
        self._ensure_seed_physics()

    def _seed_clicked(self, candidate_id: str) -> None:
        self.seedClicked.emit(candidate_id)

    def _layer_for_node(self, node: _NodeView, layers_by_id: dict[str, Any]):
        return layers_by_id.get(node.layer_id or "")

    def _set_graph_by_layers(
        self, nodes: list[_NodeView], edges: list[_EdgeView], layers: list[Any]
    ):
        self.clear_graph()
        if not nodes:
            return
        visible_layers = [
            layer
            for layer in sort_layers_by_causal_rank(layers or [])
            if getattr(layer, "is_visible", True) and get_causal_rank(layer) is not None
        ]
        layers_by_id = {str(getattr(layer, "id", "")): layer for layer in visible_layers}
        layer_ids_with_nodes = {n.layer_id for n in nodes if n.layer_id}
        if not visible_layers:
            self.set_graph(nodes, edges, layer_mode=False, layers=[])
            return
        ordered_layer_ids = [str(getattr(layer, "id", "")) for layer in visible_layers]
        unknown_nodes = [n for n in nodes if not n.layer_id or n.layer_id not in layers_by_id]
        band_h = 210.0
        band_w = max(900.0, 150.0 * max(3, len(nodes)))
        x0 = -band_w / 2
        for row, layer in enumerate(visible_layers):
            y = row * band_h
            rect = QGraphicsRectItem(x0, y - band_h / 2 + 8, band_w, band_h - 16)
            color = QColor("#F0EDE1" if row % 2 == 0 else "#E9E4D3")
            color.setAlpha(165)
            rect.setBrush(QBrush(color))
            rect.setPen(QPen(QColor("#D8D2BF"), 1.0, Qt.PenStyle.DashLine))
            rect.setZValue(-50)
            self.scene_obj.addItem(rect)
            label = QGraphicsSimpleTextItem(str(getattr(layer, "name", "Capa")))
            label.setBrush(QBrush(QColor("#6F6A42")))
            font = QFont()
            font.setBold(True)
            font.setPointSize(10)
            label.setFont(font)
            label.setPos(x0 + 18, y - band_h / 2 + 18)
            label.setZValue(-49)
            self.scene_obj.addItem(label)
        nodes_by_layer: dict[str, list[_NodeView]] = {lid: [] for lid in ordered_layer_ids}
        for node in nodes:
            if node.layer_id in nodes_by_layer:
                nodes_by_layer[node.layer_id].append(node)
        if unknown_nodes:
            nodes_by_layer.setdefault("__sin_capa__", []).extend(unknown_nodes)
            y = len(visible_layers) * band_h
            rect = QGraphicsRectItem(x0, y - band_h / 2 + 8, band_w, band_h - 16)
            rect.setBrush(QBrush(QColor("#F7F1E8")))
            rect.setPen(QPen(QColor("#D8D2BF"), 1.0, Qt.PenStyle.DashLine))
            rect.setZValue(-50)
            self.scene_obj.addItem(rect)
            label = QGraphicsSimpleTextItem("Sin anillo asignado")
            label.setBrush(QBrush(QColor("#6F6A42")))
            self.scene_obj.addItem(label)
            label.setPos(x0 + 18, y - band_h / 2 + 18)
            ordered_layer_ids.append("__sin_capa__")
        for row, layer_id in enumerate(ordered_layer_ids):
            layer_nodes = nodes_by_layer.get(layer_id, [])
            if not layer_nodes:
                continue
            spacing = min(170.0, band_w / max(1, len(layer_nodes) + 1))
            start_x = -spacing * (len(layer_nodes) - 1) / 2
            y = row * band_h
            for idx, node in enumerate(layer_nodes):
                x = start_x + idx * spacing
                if node.kind.lower() == "contenedor":
                    item = GraphTreeItem(node, x=x, y=y, width=240, height=120)
                    self._trees[node.entity_id] = item
                else:
                    item = GraphNodeItem(node, x=x, y=y)
                self.scene_obj.addItem(item)
                self._nodes[node.entity_id] = item  # type: ignore[assignment]
        self._membership = {
            edge.target_id: edge.source_id for edge in edges if edge.kind.lower() == "contiene"
        }
        seen_edge_ids: set[str] = set()
        for edge in edges:
            edge_id = getattr(edge, "relation_id", "")
            if edge_id and edge_id in seen_edge_ids:
                continue
            if edge_id:
                seen_edge_ids.add(edge_id)
            if edge.kind.lower() == "contiene":
                continue
            source = self._nodes.get(edge.source_id)
            target = self._nodes.get(edge.target_id)
            if not source or not target:
                continue
            source_ring = self._node_ring_ids.get(edge.source_id, "")
            target_ring = self._node_ring_ids.get(edge.target_id, "")
            styled_edge = replace(
                edge,
                inter_ring=bool(source_ring and target_ring and source_ring != target_ring),
                causal=bool(edge.causal or relation_family(edge.kind) == "causal"),
            )
            item = GraphEdgeItem(styled_edge, source, target)
            self.scene_obj.addItem(item)
            self._edges.append(item)
        self._finalize_view(140.0)  # BETA1-B02

    def _ring_color(self, index: int) -> str:
        palette = [
            "#E9D8FD",
            "#DBEAFE",
            "#D1FAE5",
            "#FEF3C7",
            "#FCE7F3",
            "#E0F2FE",
            "#EDE9FE",
            "#FDE68A",
        ]
        return palette[index % len(palette)]

    def _ring_item_size_estimate(self, node: _NodeView, child_count: int = 0) -> float:
        if node.kind.lower() != "contenedor":
            return 124.0
        if child_count <= 0:
            # Fallback for callers without containment info
            entity = getattr(node, "entity", None)
            child_ids = list(
                getattr(entity, "child_entity_ids", [])
                or getattr(entity, "children_ids", [])
                or getattr(entity, "entity_ids", [])
                or []
            )
            child_count = len(child_ids)
        if child_count <= 0:
            return _CONTAINER_MIN_WIDTH
        # BETA1-B03: nested children render inside the tree, so the tree (and
        # therefore its ring) must reserve room for them with slack.
        cols = max(1, min(4, math.ceil(math.sqrt(child_count))))
        rows = math.ceil(child_count / cols)
        estimated_width = max(
            _CONTAINER_MIN_WIDTH,
            cols * 152.0 + (cols - 1) * _CONTAINER_CHILD_SPACING + _CONTAINER_PADDING * 2,
        )
        estimated_height = max(
            _CONTAINER_MIN_HEIGHT,
            _CONTAINER_HEADER_HEIGHT + rows * 132.0 + (rows - 1) * 32.0 + _CONTAINER_PADDING,
        )
        return max(estimated_width, estimated_height)

    def _build_concentric_ring_visuals(
        self,
        nodes: list[_NodeView],
        edges: list[_EdgeView],
        layers: list[Any],
        measured: dict[str, float] | None = None,
    ) -> tuple[list[_RingVisual], dict[str, str]]:
        """Build ephemeral B44 ring visuals and node→ring assignment.

        Uses WorldLayer/Anillo instances already present in the project. No
        persistence or canon mutation is performed here.
        """
        visible_layers = [
            layer
            for layer in sort_layers_by_causal_rank(layers or [])
            if getattr(layer, "is_visible", True)
        ]
        layer_by_id = {
            str(getattr(layer, "id", "")): layer
            for layer in visible_layers
            if str(getattr(layer, "id", ""))
        }
        ordered_ring_ids = [
            str(getattr(layer, "id", ""))
            for layer in visible_layers
            if str(getattr(layer, "id", ""))
        ]

        node_ring_ids: dict[str, str] = {}
        node_ids_by_ring: dict[str, list[str]] = {ring_id: [] for ring_id in ordered_ring_ids}
        unclassified: list[str] = []
        for node in nodes:
            layer_id = node.layer_id or ""
            if layer_id and layer_id in layer_by_id:
                ring_id = layer_id
                node_ids_by_ring.setdefault(ring_id, []).append(node.entity_id)
            else:
                ring_id = "__unclassified__"
                unclassified.append(node.entity_id)
            node_ring_ids[node.entity_id] = ring_id

        if unclassified:
            node_ids_by_ring["__unclassified__"] = unclassified
            ordered_ring_ids.append("__unclassified__")

        relation_ids_by_ring: dict[str, list[str]] = {ring_id: [] for ring_id in ordered_ring_ids}
        for edge in edges:
            if edge.kind.lower() == "contiene":
                continue
            source_ring = node_ring_ids.get(edge.source_id)
            target_ring = node_ring_ids.get(edge.target_id)
            if not source_ring or not target_ring:
                continue
            # B44-T01/T02: basic association only. Advanced inter-ring styling is T06.
            ring_id = source_ring if source_ring == target_ring else source_ring
            if ring_id in relation_ids_by_ring:
                relation_ids_by_ring[ring_id].append(edge.relation_id)

        nodes_by_id = {node.entity_id: node for node in nodes}
        # BETA1-B03: containment info — contained items render INSIDE their
        # tree, so they don't occupy a ring slot of their own, while trees
        # grow with their child count (with slack).
        contains_count: dict[str, int] = {}
        contained_set: set[str] = set()
        for edge in edges:
            if edge.kind.lower() == "contiene":
                contains_count[edge.source_id] = contains_count.get(edge.source_id, 0) + 1
                contained_set.add(edge.target_id)
        visuals: list[_RingVisual] = []
        previous_outer = 0.0
        gap = 34.0
        for index, ring_id in enumerate(ordered_ring_ids):
            item_ids = tuple(node_ids_by_ring.get(ring_id, []))
            ring_nodes = [nodes_by_id[item_id] for item_id in item_ids if item_id in nodes_by_id]
            branch_count = sum(1 for node in ring_nodes if node.kind.lower() == "contenedor")
            leaf_count = max(0, len(ring_nodes) - branch_count)
            relation_ids = tuple(relation_ids_by_ring.get(ring_id, []))
            slotted_nodes = [node for node in ring_nodes if node.entity_id not in contained_set]

            def _extent(node: _NodeView) -> float:
                # BETA1-B03 reactive: a real measured size (tree already
                # nested/resized/collapsed) beats any estimate.
                if measured and node.entity_id in measured:
                    return measured[node.entity_id]
                return self._ring_item_size_estimate(node, contains_count.get(node.entity_id, 0))

            extents = [_extent(node) for node in slotted_nodes]
            slot_total = sum(extents)
            slot_total += max(0, len(slotted_nodes)) * 36.0 + 140.0  # label arc reserve
            required_mid_radius = slot_total / (2 * math.pi) if slotted_nodes else 0.0
            max_extent = max(extents) if extents else 0.0
            # The ring must be at least thick enough to hold its largest item
            # with slack (90px), and grows mildly with crowding.
            content_thickness = (
                max(176.0, max_extent + 90.0)
                + max(0, len(slotted_nodes) - 1) * 16.0
                + branch_count * 24.0
            )
            inner = 42.0 if index == 0 else previous_outer + gap
            outer = max(inner + content_thickness, required_mid_radius + content_thickness / 2.0)
            if outer <= inner:
                outer = inner + content_thickness

            if ring_id == "__unclassified__":
                display_name = "Sin clasificar"
                rank = None
                color = "#ECE7DA"
            else:
                layer = layer_by_id[ring_id]
                display_name = str(getattr(layer, "name", "Anillo"))
                rank = get_causal_rank(layer)
                color = self._ring_color(index)

            relation_count = len(relation_ids)
            count_label = f"{leaf_count} hojas · {branch_count} ramas · {relation_count} relaciones"
            state = (
                "focused"
                if self._focused_ring_id and ring_id == self._focused_ring_id
                else "normal"
            )
            visuals.append(
                _RingVisual(
                    ring_id=ring_id,
                    display_name=display_name,
                    causal_rank=rank,
                    color=color,
                    inner_radius=inner,
                    outer_radius=outer,
                    item_ids=item_ids,
                    relation_ids=relation_ids,
                    count_label=count_label,
                    state=state,
                )
            )
            previous_outer = outer
        return visuals, node_ring_ids

    def _draw_ring_background(self, ring: _RingVisual):
        outer_rect = QRectF(
            -ring.outer_radius, -ring.outer_radius, ring.outer_radius * 2, ring.outer_radius * 2
        )
        inner_rect = QRectF(
            -ring.inner_radius, -ring.inner_radius, ring.inner_radius * 2, ring.inner_radius * 2
        )
        outer_path = QPainterPath()
        outer_path.addEllipse(outer_rect)
        inner_path = QPainterPath()
        inner_path.addEllipse(inner_rect)
        path = outer_path.subtracted(inner_path)
        item = GraphRingItem(ring, path)
        # BETA1-F05 (estética): los anillos NO son bandas de color con
        # contorno — son hendiduras del lienzo: sombras alternas muy
        # tenues, sin borde. Seleccionables igual (el contorno azul de
        # selección sigue viniendo de itemChange).
        ring_index = sum(1 for _ in self._ring_items)
        shade = QColor(92, 90, 62)  # sombra cálida de la paleta
        shade.setAlpha(26 if ring.state == "focused" else (16 if ring_index % 2 == 0 else 8))
        item.setBrush(QBrush(shade))
        pen = QPen(Qt.PenStyle.NoPen)
        item.setPen(pen)
        item._base_pen = QPen(pen)  # restored when the ring is deselected
        item.setZValue(-100)
        self.scene_obj.addItem(item)
        self._ring_items[ring.ring_id] = item

        # BETA1-UX03: profundidad por capas — un BISEL decorativo (hijo no
        # interactivo) tiñe la corona con un gradiente radial: lip interior
        # iluminado → centro neutro → reborde exterior en sombra cálida. Da
        # sensación de hendidura/elevación sin contornos ni efectos gráficos
        # (que cachean el render). El hijo se limpia con el anillo padre y no
        # roba clics, así que la selección sólida del anillo sigue intacta.
        if ring.outer_radius > 0:
            inner_frac = max(0.05, min(0.95, ring.inner_radius / ring.outer_radius))
            focused = ring.state == "focused"
            bevel_grad = QRadialGradient(QPointF(0.0, 0.0), ring.outer_radius)
            lip = QColor("#FCF8EE")
            lip.setAlpha(64 if focused else 46)
            fade = QColor("#FCF8EE")
            fade.setAlpha(0)
            rim = QColor(52, 47, 28)  # sombra cálida base (nunca gris neutro)
            rim.setAlpha(86 if focused else 60)
            bevel_grad.setColorAt(inner_frac, lip)
            bevel_grad.setColorAt(inner_frac + (1.0 - inner_frac) * 0.45, fade)
            bevel_grad.setColorAt(1.0, rim)
            bevel = QGraphicsPathItem(path, item)
            bevel.setBrush(QBrush(bevel_grad))
            bevel.setPen(QPen(Qt.PenStyle.NoPen))
            bevel.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            bevel.setAcceptHoverEvents(False)
            bevel.setZValue(1)  # sobre la banda sólida, bajo la etiqueta (10)

        # BETA1-UX04: etiqueta anclada al BORDE superior del anillo, sobre una
        # píldora de pergamino para que sea legible aunque dos anillos queden
        # cerca (antes los textos largos se solapaban y se volvían ilegibles).
        # La instrucción "doble click" pasa al tooltip; la etiqueta solo nombra.
        item.setToolTip(f"{ring.display_name} — doble click para entrar")
        label_text = f"{ring.display_name} · {ring.count_label}"
        label = QGraphicsSimpleTextItem(_fit_text(label_text, 48), item)
        label.setBrush(QBrush(QColor("#5F5A3D")))
        label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        label.setFont(font)
        lrect = label.boundingRect()
        pad_x, pad_y = 11.0, 4.0
        pill_w = lrect.width() + pad_x * 2
        pill_h = lrect.height() + pad_y * 2
        top_y = -ring.outer_radius + 6
        pill_path = QPainterPath()
        pill_path.addRoundedRect(QRectF(-pill_w / 2, top_y, pill_w, pill_h), pill_h / 2, pill_h / 2)
        pill = QGraphicsPathItem(pill_path, item)
        pill_fill = QColor("#FBF8EF")
        pill_fill.setAlpha(236)
        pill.setBrush(QBrush(pill_fill))
        pill.setPen(QPen(QColor("#D2CAB1"), 1.0))
        pill.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        pill.setAcceptHoverEvents(False)
        pill.setZValue(9)
        label.setPos(-lrect.width() / 2, top_y + pad_y)
        label.setZValue(10)

    def _layout_concentric_rings(
        self, nodes: list[_NodeView], edges: list[_EdgeView], layers: list[Any]
    ) -> bool:
        """BETA1-B03: (re)compute ring visuals from the REAL current item
        sizes, draw the ring backgrounds and place top-level items in their
        slots. Reused by the initial build and by reactive re-layouts
        (collapse/expand), so ring sizes always match the content.

        Returns False when there are no rings to draw (caller falls back)."""
        # Drop previous ring graphics (labels are their Qt children)
        for ring_item in self._ring_items.values():
            self.scene_obj.removeItem(ring_item)
        self._ring_items = {}

        # Measure top-level trees as they really are (nested, resized,
        # possibly collapsed). Leaves keep the standard estimate.
        measured: dict[str, float] = {}
        for entity_id, tree in self._trees.items():
            if tree.parentItem() is None:
                rect = tree.boundingRect()
                measured[entity_id] = max(rect.width(), rect.height())

        self._ring_visuals, self._node_ring_ids = self._build_concentric_ring_visuals(
            nodes, edges, layers, measured=measured
        )
        if not self._ring_visuals:
            return False

        for ring in self._ring_visuals:
            self._draw_ring_background(ring)

        contained_set = {edge.target_id for edge in edges if edge.kind.lower() == "contiene"}
        nodes_by_id = {node.entity_id: node for node in nodes}
        for ring in self._ring_visuals:
            ring_nodes = [
                nodes_by_id[item_id] for item_id in ring.item_ids if item_id in nodes_by_id
            ]
            slotted = [node for node in ring_nodes if node.entity_id not in contained_set]
            for idx, node in enumerate(slotted):
                item = self._nodes.get(node.entity_id)
                if item is None or item.parentItem() is not None:
                    continue
                pos = self._position_for_ring_slot(ring, idx, len(slotted))
                if isinstance(item, GraphTreeItem):
                    # Center the tree's actual rect on the slot
                    rect = item.boundingRect()
                    item.setPos(pos.x() - rect.center().x(), pos.y() - rect.center().y())
                else:
                    item.setPos(pos)
        # Edges may already exist (reactive re-layout): follow the new slots
        for edge_item in self._edges:
            edge_item.update_path()
        return True

    def _relayout_concentric(self):
        """BETA1-B03: reactive ring sizing — called after collapse/expand so
        rings grow/shrink around the content without rebuilding the graph."""
        if self._layout_mode_active != "concentric_rings":
            return
        inputs = getattr(self, "_concentric_inputs", None)
        if not inputs:
            return
        nodes, edges, layers = inputs
        if self._layout_concentric_rings(nodes, edges, layers):
            self._expand_scene_rect_to_content()
            # BETA1-C05: el colapso/expansión cambia la geometría → la
            # física reacciona (reheat completo, incluidos motores locales)
            self._physics_reheat()

    def _compute_span_outers(self) -> list[float]:
        """BETA1-B03: radio exterior requerido por cada anillo para envolver su
        contenido en las posiciones ACTUALES (sin tocar nada). Fuente única de
        la matemática de spans, usada por el reajuste (en vivo y al asentarse)."""
        if self._layout_mode_active != "concentric_rings" or not self._ring_visuals:
            return []
        contained: set[str] = set()
        inputs = getattr(self, "_concentric_inputs", None)
        if inputs:
            _, edges, _ = inputs
            contained = {edge.target_id for edge in edges if edge.kind.lower() == "contiene"}
        outers: list[float] = []
        previous_outer = 0.0
        gap = 34.0
        for index, ring in enumerate(self._ring_visuals):
            inner = 42.0 if index == 0 else previous_outer + gap
            required = inner + 176.0
            for item_id in ring.item_ids:
                if item_id in contained:
                    continue
                item = self._nodes.get(item_id)
                if item is None or item.parentItem() is not None:
                    continue
                rect = item.sceneBoundingRect()
                center_dist = math.hypot(rect.center().x(), rect.center().y())
                extent = max(rect.width(), rect.height()) / 2.0
                required = max(required, center_dist + extent + 60.0)
            outers.append(required)
            previous_outer = required
        return outers

    def _refresh_ring_spans(self, *, rebuild_physics: bool = True):
        """BETA1-B03: resize ring bands around the CURRENT positions and
        sizes of their top-level items, WITHOUT repositioning anything.

        Used after manual moves: _relayout_concentric would snap items back
        to their slots, undoing the user's placement; this only makes each
        ring wide enough to wrap its content wherever it sits.

        BETA1-UX feedback: ``rebuild_physics=False`` permite reajustar las
        bandas EN VIVO cada frame (desde el tick) sin reconstruir el mundo
        físico — el rebuild solo es necesario al asentarse."""
        if self._layout_mode_active != "concentric_rings" or not self._ring_visuals:
            return
        outers = self._compute_span_outers()
        if not outers:
            return
        new_visuals: list[_RingVisual] = []
        previous_outer = 0.0
        gap = 34.0
        for index, (ring, outer) in enumerate(zip(self._ring_visuals, outers)):
            inner = 42.0 if index == 0 else previous_outer + gap
            new_visuals.append(replace(ring, inner_radius=inner, outer_radius=outer))
            previous_outer = outer
        self._ring_visuals = new_visuals
        self._last_span_outers = list(outers)
        selected_ring = self._selected_ring_id
        for ring_item in self._ring_items.values():
            self.scene_obj.removeItem(ring_item)
        self._ring_items = {}
        for ring in self._ring_visuals:
            self._draw_ring_background(ring)
        if selected_ring and selected_ring in self._ring_items:
            self._ring_items[selected_ring].setSelected(True)
        self._expand_scene_rect_to_content()
        # BETA1-C05: re-empaquetar el mundo SIN despertar la simulación (un
        # reheat aquí crearía un bucle stop→spans→reheat→stop). Solo al
        # asentarse (rebuild_physics=True); en vivo se omite.
        if rebuild_physics and self._physics_enabled:
            self._rebuild_physics_world()

    def _maybe_live_refresh_spans(self):
        """BETA1-UX feedback: reajuste FLUIDO de los anillos en cada frame del
        tick (no al soltar). Guarda por delta: solo redibuja si algún radio
        cambió de forma perceptible, y nunca reconstruye la física (evita el
        bucle del contrato C01 §riesgo-3)."""
        if self._layout_mode_active != "concentric_rings" or not self._ring_visuals:
            return
        outers = self._compute_span_outers()
        if not outers:
            return
        prev = getattr(self, "_last_span_outers", None)
        if (
            prev
            and len(prev) == len(outers)
            and all(abs(a - b) < 1.5 for a, b in zip(outers, prev))
        ):
            return  # estable: nada que redibujar
        self._refresh_ring_spans(rebuild_physics=False)

    def _nest_contained_items(self, nodes: list[_NodeView], edges: list[_EdgeView]):
        """BETA1-B03: re-parent contained items into their tree containers.

        Mirrors the free-layout nesting contract for the concentric view:
        children become Qt children of the tree (they render inside it and
        move with it) and trees are resized bottom-up to fit with slack.
        """
        contains_map: dict[str, set[str]] = {}
        for edge in edges:
            if edge.kind.lower() == "contiene":
                contains_map.setdefault(edge.source_id, set()).add(edge.target_id)
        if not contains_map:
            return
        # Leaves-first order so nested containers are sized before parents
        ordered: list[str] = []
        visited: set[str] = set()

        def _visit(container_id: str):
            if container_id in visited:
                return
            visited.add(container_id)
            for child_id in contains_map.get(container_id, ()):  # noqa: B023
                if child_id in self._trees:
                    _visit(child_id)
            ordered.append(container_id)

        for container_id in contains_map:
            if container_id in self._trees:
                _visit(container_id)

        for container_id in ordered:
            tree = self._trees.get(container_id)
            if tree is None:
                continue
            child_ids = contains_map.get(container_id, set())
            leaf_ids = [eid for eid in child_ids if eid in self._nodes and eid not in self._trees]
            nested_tree_ids = [
                eid for eid in child_ids if eid in self._trees and eid != container_id
            ]
            tree_cx = tree._width / 2
            tree_cy = tree._height / 2
            child_radius = max(70, min(160, 50 * len(leaf_ids))) if leaf_ids else 70.0
            for index, entity_id in enumerate(leaf_ids):
                item = self._nodes[entity_id]
                count = max(1, len(leaf_ids))
                if count == 1:
                    cx, cy = tree_cx, tree_cy + _CONTAINER_HEADER_HEIGHT + 60
                else:
                    angle = (2 * math.pi * index) / count
                    cx = tree_cx + math.cos(angle) * child_radius
                    cy = (
                        tree_cy
                        + _CONTAINER_HEADER_HEIGHT
                        + 60
                        + math.sin(angle) * child_radius * 0.5
                    )
                item.setPos(cx, cy)
                tree.add_child_node(item)  # type: ignore[arg-type]
            if nested_tree_ids:
                nested_y = (
                    _CONTAINER_HEADER_HEIGHT + 60 + (child_radius * 2 + 40 if leaf_ids else 0)
                )
                for index, entity_id in enumerate(nested_tree_ids):
                    nested = self._trees[entity_id]
                    spread = max(1, len(nested_tree_ids))
                    width = nested._width
                    nested.setPos(
                        tree_cx + (index - (spread - 1) / 2) * (width + 30), tree_cy + nested_y
                    )
                    tree.add_child_node(nested)  # type: ignore[arg-type]
            if tree._child_nodes:
                tree.resize_to_fit_children()

    def _position_for_ring_slot(self, ring: _RingVisual, index: int, count: int) -> QPointF:
        mid_radius = (ring.inner_radius + ring.outer_radius) / 2.0
        if count <= 1:
            angle = math.pi / 2.0
        else:
            reserved = 0.72  # keep top label arc clear
            span = 2 * math.pi - reserved * 2
            angle = -math.pi / 2 + reserved + (span * index / max(1, count - 1))
        return QPointF(math.cos(angle) * mid_radius, math.sin(angle) * mid_radius)

    def _set_graph_by_concentric_rings(
        self, nodes: list[_NodeView], edges: list[_EdgeView], layers: list[Any]
    ):
        _b44trace(
            "concentric_enter "
            f"nodes={len(nodes or [])} edges={len(edges or [])} layers={len(layers or [])} "
            f"filter_layers={tuple(getattr(self._visual_filter, 'layer_ids', ()))!r} "
            f"filter_focus={tuple(getattr(self._visual_filter, 'focus_entity_ids', ()))!r}"
        )
        self.clear_graph()
        if self._focused_ring_id:
            all_visuals, all_node_ring_ids = self._build_concentric_ring_visuals(
                nodes, edges, layers or []
            )
            focused = next(
                (ring for ring in all_visuals if ring.ring_id == self._focused_ring_id), None
            )
            if focused is None:
                self._focused_ring_id = ""
            else:
                focused_node_ids = {
                    entity_id
                    for entity_id, ring_id in all_node_ring_ids.items()
                    if ring_id == focused.ring_id
                }
                nodes = [node for node in nodes if node.entity_id in focused_node_ids]
                edges = [
                    edge
                    for edge in edges
                    if edge.source_id in focused_node_ids and edge.target_id in focused_node_ids
                ]
                if focused.ring_id != "__unclassified__":
                    layers = [
                        layer
                        for layer in (layers or [])
                        if str(getattr(layer, "id", "")) == focused.ring_id
                    ]
                else:
                    layers = []
        # BETA1-B03 (reactive rings): create ALL items first at a provisional
        # origin, nest contained items into their trees and resize them —
        # only then compute ring radii from the REAL measured sizes. This is
        # what lets rings reserve space with slack and react to growth.
        for node in nodes:
            if node.kind.lower() == "contenedor":
                item = GraphTreeItem(
                    node,
                    x=0.0,
                    y=0.0,
                    width=_CONTAINER_MIN_WIDTH,
                    height=_CONTAINER_MIN_HEIGHT,
                )
                self._trees[node.entity_id] = item
            else:
                item = GraphNodeItem(node, x=0.0, y=0.0)
            self.scene_obj.addItem(item)
            self._nodes[node.entity_id] = item  # type: ignore[assignment]

        # Nest contained items (same visual contract as the free layout:
        # children inside the rectangle, the tree moves with all its content)
        self._nest_contained_items(nodes, edges)

        # Remember inputs so collapse/expand can re-layout reactively
        self._concentric_inputs = (list(nodes), list(edges), list(layers or []))

        laid_out = self._layout_concentric_rings(nodes, edges, layers or [])
        _b44trace(
            "concentric_built "
            f"ring_visuals={len(self._ring_visuals)} ring_ids={[ring.ring_id for ring in self._ring_visuals]!r} "
            f"node_ring_ids={self._node_ring_ids!r}"
        )
        if not laid_out:
            _b44trace(f"concentric_no_rings fallback_to_free={bool(nodes)}")
            if nodes:
                self.set_graph(nodes, edges, layout_mode="free", layers=layers)
            return

        self._membership = {
            edge.target_id: edge.source_id for edge in edges if edge.kind.lower() == "contiene"
        }
        seen_edge_ids: set[str] = set()
        for edge in edges:
            edge_id = getattr(edge, "relation_id", "")
            if edge_id and edge_id in seen_edge_ids:
                continue
            if edge_id:
                seen_edge_ids.add(edge_id)
            if edge.kind.lower() == "contiene":
                continue
            source = self._nodes.get(edge.source_id)
            target = self._nodes.get(edge.target_id)
            if not source or not target:
                continue
            source_ring = self._node_ring_ids.get(edge.source_id, "")
            target_ring = self._node_ring_ids.get(edge.target_id, "")
            styled_edge = replace(
                edge,
                inter_ring=bool(source_ring and target_ring and source_ring != target_ring),
                causal=bool(edge.causal or relation_family(edge.kind) == "causal"),
            )
            item = GraphEdgeItem(styled_edge, source, target)
            self.scene_obj.addItem(item)
            self._edges.append(item)

        # BETA1-B03: register internal edges (tree↔content and content↔content)
        # so collapse/visibility behaves like the free layout.
        for tree in self._trees.values():
            tree.find_internal_edges(self._edges)
            tree.set_canvas_edges(self._edges)

        # BETA1-B02: set_graph returns early for this layout, so the common
        # view finalization (scene rect + camera restore/fit) happens here.
        self._finalize_view(160.0)
        rect = self.scene_obj.itemsBoundingRect()
        _b44trace(
            "concentric_done "
            f"scene_items={len(self.scene_obj.items())} ring_items={len(self._ring_items)} "
            f"nodes_drawn={len(self._nodes)} trees_drawn={len(self._trees)} edges_drawn={len(self._edges)} "
            f"scene_rect_valid={rect.isValid()} scene_rect_empty={rect.isEmpty()}"
        )

    def try_incremental_refresh(
        self,
        nodes: list[_NodeView],
        edges: list[_EdgeView],
        *,
        layer_mode: bool = False,
        layout_mode: str | None = None,
        layers: list[Any] | None = None,
    ) -> bool:
        """BETA1-L01: si el cambio es SOLO edición de atributos de hojas (mismos
        ids, misma contención, mismas capas, sin filtros/focus/cámara temporal),
        actualiza esos items in situ y devuelve True — evitando el rebuild total
        O(N) de ``set_graph`` (~270ms con 1000 nodos). En CUALQUIER otro caso
        (altas, bajas, cambio de layout/contención/contenedor, filtros activos)
        devuelve False y el llamante hace ``set_graph`` completo. Conservador por
        diseño: ante la duda, no toma el atajo."""
        nodes = list(nodes or [])
        edges = list(edges or [])
        layers = list(layers or [])
        if layout_mode is None:
            layout_mode = "layered" if layer_mode else "free"
        if layout_mode not in {"free", "layered", "concentric_rings"}:
            layout_mode = "free"
        # 1. Mismo layout activo y con algo ya dibujado.
        if layout_mode != self._layout_mode_active or (not self._nodes and not self._trees):
            return False
        # 2. Sin filtros / focus de anillo / cámara temporal: lo dibujado == todo.
        if self._view_year is not None or self._focused_ring_id:
            return False
        vf = self._visual_filter
        if getattr(vf, "layer_ids", None) or getattr(vf, "focus_entity_ids", None):
            return False

        # 3. Mismas capas (afectan a bandas/anillos).
        def _layer_ids(seq):
            return [str(getattr(layer, "id", "")) for layer in seq]

        if _layer_ids(layers) != _layer_ids(self._all_layers):
            return False
        # 4. Mismo conjunto de ids (altas/bajas → rebuild completo).
        old_nodes = {n.entity_id: n for n in self._all_nodes}
        new_nodes = {n.entity_id: n for n in nodes}
        if set(old_nodes) != set(new_nodes):
            return False
        old_edges = {e.relation_id: e for e in self._all_edges}
        new_edges = {e.relation_id: e for e in edges}
        if set(old_edges) != set(new_edges):
            return False

        # 5. Contención sin cambios (afecta anidamiento/árboles).
        def _contains(seq):
            return {(e.source_id, e.target_id) for e in seq if e.kind.lower() == "contiene"}

        if _contains(edges) != _contains(self._all_edges):
            return False
        # 6. Las aristas no cambian de atributos (no las reconstruimos in situ).
        for rid, new_e in new_edges.items():
            old_e = old_edges[rid]
            if (
                new_e.kind,
                new_e.label,
                new_e.direction,
                new_e.color,
                new_e.source_id,
                new_e.target_id,
            ) != (
                old_e.kind,
                old_e.label,
                old_e.direction,
                old_e.color,
                old_e.source_id,
                old_e.target_id,
            ):
                return False
        # 7. Recoger hojas con atributos cambiados; contenedores → rebuild.
        changed_leaves: list[tuple[Any, _NodeView]] = []
        for eid, new_n in new_nodes.items():
            old_n = old_nodes[eid]
            if new_n == old_n:
                continue  # _NodeView es frozen: igualdad por valor
            if old_n.kind.lower() == "contenedor" or new_n.kind.lower() == "contenedor":
                return False  # contenedores: estructura/encabezado → set_graph
            item = self._nodes.get(eid)
            if item is None:
                return False  # debería ser una hoja dibujada; por seguridad, fallback
            changed_leaves.append((item, new_n))

        # Verificado: aplicar in situ y sincronizar el estado renderizado.
        for item, new_n in changed_leaves:
            item.apply_view_update(new_n)
        self._all_nodes = nodes
        self._all_edges = edges
        self._all_layers = layers
        return True

    def set_graph(
        self,
        nodes: list[_NodeView],
        edges: list[_EdgeView],
        *,
        layer_mode: bool = False,
        layout_mode: str | None = None,
        layers: list[Any] | None = None,
    ):
        self._all_nodes = list(nodes or [])
        self._all_edges = list(edges or [])
        self._all_layers = list(layers or [])
        if layout_mode is None:
            layout_mode = "layered" if layer_mode else "free"
        if layout_mode not in {"free", "layered", "concentric_rings"}:
            layout_mode = "free"
        # BETA1-B02: rebuilding the same layout (refresh after create/edit/
        # delete) must not reset the user's zoom and pan — constant re-fitting
        # made navigation impossible. Capture the camera now; _finalize_view
        # restores it instead of fitting when the layout didn't change.
        previous_layout = self._layout_mode_active
        self._view_state_to_restore = None
        if layout_mode == previous_layout and self._nodes:
            self._view_state_to_restore = (
                QTransform(self.transform()),
                self.mapToScene(self.viewport().rect().center()),
            )
        self._layout_mode_active = layout_mode
        self._layer_mode_active = layout_mode == "layered"
        if layout_mode == "concentric_rings" and self._focused_ring_id:
            # Ring focus is a concentric-view scope, not a generic visual filter.
            # Build from the full canonical graph so moving an item between rings
            # cannot be hidden by a stale layer filter. The temporal camera
            # (BETA1-G06) still applies — focusing a ring at year N must show
            # that ring's snapshot at year N, not its whole history.
            nodes, edges = self._temporal_snapshot(self._all_nodes, self._all_edges)
        else:
            nodes, edges = self._filtered_graph(self._all_nodes, self._all_edges)
        _b44trace(
            "set_graph "
            f"requested_layout={layout_mode} all_nodes={len(self._all_nodes)} all_edges={len(self._all_edges)} "
            f"filtered_nodes={len(nodes)} filtered_edges={len(edges)} layers={len(self._all_layers)} "
            f"filter_layers={tuple(getattr(self._visual_filter, 'layer_ids', ()))!r} "
            f"filter_focus={tuple(getattr(self._visual_filter, 'focus_entity_ids', ()))!r}"
        )
        if layout_mode == "concentric_rings":
            self._set_graph_by_concentric_rings(nodes, edges, layers or [])
            return
        if layout_mode == "layered":
            self._set_graph_by_layers(nodes, edges, layers or [])
            return
        self.clear_graph()
        if not nodes:
            return

        # ── Separate containers from regular nodes ──
        container_nodes: list[_NodeView] = []
        regular_nodes: list[_NodeView] = []
        for node in nodes:
            if node.kind.lower() == "contenedor":
                container_nodes.append(node)
            else:
                regular_nodes.append(node)

        # ── Build a map of "contiene" relations: container_id -> set of child_ids ──
        contains_map: dict[str, set[str]] = {}
        contained_set: set[str] = set()  # all child entity IDs
        for edge in edges:
            if edge.kind.lower() == "contiene":
                contains_map.setdefault(edge.source_id, set()).add(edge.target_id)
                contained_set.add(edge.target_id)

        # ── Build membership index for cycle detection ──
        self._membership = {}
        for edge in edges:
            if edge.kind.lower() == "contiene":
                self._membership[edge.target_id] = edge.source_id

        # ── Layout parameters ──
        # Non-contained, non-container nodes arranged in a circle
        free_nodes = [n for n in regular_nodes if n.entity_id not in contained_set]
        radius = max(220, min(620, 80 * max(len(free_nodes), len(container_nodes))))
        center = QPointF(0, 0)

        # ── Create regular (non-container) node items ──
        for idx, node in enumerate(regular_nodes):
            angle = (2 * math.pi * idx) / max(1, len(regular_nodes))
            ring = radius if len(regular_nodes) > 1 else 0
            x = center.x() + math.cos(angle) * ring
            y = center.y() + math.sin(angle) * ring * 0.72
            item = GraphNodeItem(node, x=x, y=y)
            self.scene_obj.addItem(item)
            self._nodes[node.entity_id] = item

        # ── Create container (tree) items ──
        # Build dependency graph for bottom-up layout
        container_child_map: dict[str, list[str]] = {}  # parent_id -> [child_container_ids]
        for idx, cnode in enumerate(container_nodes):
            child_ids = contains_map.get(cnode.entity_id, set())
            c_children = [
                n.entity_id
                for n in container_nodes
                if n.entity_id in child_ids and n.entity_id != cnode.entity_id
            ]
            container_child_map[cnode.entity_id] = c_children

        # Topological sort: leaves first, parents later
        sorted_container_ids: list[str] = []
        visited: set[str] = set()

        def _visit(cid: str):
            if cid in visited:
                return
            visited.add(cid)
            for child_cid in container_child_map.get(cid, []):
                _visit(child_cid)
            sorted_container_ids.append(cid)

        for cn in container_nodes:
            _visit(cn.entity_id)
        # sorted_container_ids is now leaves-first

        # Calculate depth for each container (for z-ordering)
        container_depth: dict[str, int] = {}
        for cid in sorted_container_ids:
            child_cids = container_child_map.get(cid, [])
            if child_cids:
                container_depth[cid] = max(container_depth.get(c, 0) for c in child_cids) + 1
            else:
                container_depth[cid] = 0

        # Position containers in outer ring
        for idx, cnode in enumerate(container_nodes):
            c_angle = (2 * math.pi * idx) / max(1, len(container_nodes)) + math.pi / len(
                container_nodes
            )
            c_ring = radius * 1.6 if len(container_nodes) > 1 else 0
            cx = center.x() + math.cos(c_angle) * c_ring
            cy = center.y() + math.sin(c_angle) * c_ring * 0.72
            tree = GraphTreeItem(cnode, x=cx, y=cy)
            tree._DEPTH = container_depth.get(cnode.entity_id, 0)
            tree.setZValue(-10 + tree._DEPTH)  # deeper containers paint first (lower z)
            self.scene_obj.addItem(tree)
            self._trees[cnode.entity_id] = tree
            self._nodes[cnode.entity_id] = tree  # type: ignore[assignment]

        # Populate children bottom-up (leaves first)
        for cnode_id in sorted_container_ids:
            tree = self._trees.get(cnode_id)
            if tree is None:
                continue
            cnode = next((n for n in container_nodes if n.entity_id == cnode_id), None)
            if cnode is None:
                continue
            child_ids = contains_map.get(cnode_id, set())
            all_children = [
                n
                for n in (regular_nodes + container_nodes)
                if n.entity_id in child_ids and n.entity_id != cnode_id
            ]
            child_nodes = [n for n in all_children if n.kind.lower() != "contenedor"]
            container_children = [n for n in all_children if n.kind.lower() == "contenedor"]

            # Get tree center position
            tree_cx = tree._width / 2
            tree_cy = tree._height / 2

            # Layout regular children below header (in parent-local coords)
            child_radius = 70.0
            if child_nodes:
                child_radius = max(70, min(160, 50 * len(child_nodes)))
                for ci, child in enumerate(child_nodes):
                    child_item = self._nodes.get(child.entity_id)
                    if child_item is None:
                        continue
                    n_children = max(1, len(child_nodes))
                    if n_children == 1:
                        child_x = tree_cx
                        child_y = tree_cy + _CONTAINER_HEADER_HEIGHT + 60
                    else:
                        ca = (2 * math.pi * ci) / n_children
                        child_x = tree_cx + math.cos(ca) * child_radius
                        child_y = (
                            tree_cy
                            + _CONTAINER_HEADER_HEIGHT
                            + 60
                            + math.sin(ca) * child_radius * 0.5
                        )
                    # setPos before add_child_node because add_child_node changes parent
                    child_item.setPos(child_x, child_y)
                    tree.add_child_node(child_item)  # type: ignore[arg-type]

            # Layout nested containers below regular children (in parent-local coords)
            if container_children:
                nested_y_offset = (
                    _CONTAINER_HEADER_HEIGHT + 60 + (child_radius * 2 + 40 if child_nodes else 0)
                )
                for nci, nc in enumerate(container_children):
                    nc_item = self._trees.get(nc.entity_id) or self._nodes.get(nc.entity_id)
                    if nc_item is None:
                        continue
                    spread = max(1, len(container_children))
                    nc_w = (
                        nc_item._width
                        if isinstance(nc_item, GraphTreeItem)
                        else _CONTAINER_MIN_WIDTH
                    )
                    nc_x = tree_cx + (nci - (spread - 1) / 2) * (nc_w + 30)
                    nc_y = tree_cy + nested_y_offset
                    # Convert from parent-scene to parent-local coords
                    # The child is currently at scene position from outer ring layout.
                    # We need to compute the local offset.
                    nc_item.setPos(nc_x, nc_y)
                    tree.add_child_node(nc_item)  # type: ignore[arg-type]

            # Resize container to fit all children (bottom-up: children already laid out)
            if tree._child_nodes:
                tree.resize_to_fit_children()

        # ── Create edge items ──
        seen_edge_ids: set[str] = set()
        for edge in edges:
            edge_id = getattr(edge, "relation_id", "")
            if edge_id and edge_id in seen_edge_ids:
                continue
            if edge_id:
                seen_edge_ids.add(edge_id)
            # Skip "contiene" edges — they are rendered by the container visual
            if edge.kind.lower() == "contiene":
                continue
            source = self._nodes.get(edge.source_id)
            target = self._nodes.get(edge.target_id)
            if not source or not target:
                continue
            source_ring = self._node_ring_ids.get(edge.source_id, "")
            target_ring = self._node_ring_ids.get(edge.target_id, "")
            styled_edge = replace(
                edge,
                inter_ring=bool(source_ring and target_ring and source_ring != target_ring),
                causal=bool(edge.causal or relation_family(edge.kind) == "causal"),
            )
            item = GraphEdgeItem(styled_edge, source, target)
            self.scene_obj.addItem(item)
            self._edges.append(item)

        # ── Register internal edges for each container ──
        for tree in self._trees.values():
            tree.find_internal_edges(self._edges)

        # ── Pass canvas edges to all root-level trees for collapse visibility ──
        for tree in self._trees.values():
            tree.set_canvas_edges(self._edges)

        self._finalize_view(140.0)

    def _camera_fit_target(self, rect: QRectF) -> tuple[float, QPointF]:
        """Calcula (escala, centro) que produciría fitInView(rect) SIN moverse:
        encaja, lee el objetivo y restaura el encuadre actual."""
        saved_s = self.transform().m11()
        saved_c = self.mapToScene(self.viewport().rect().center())
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        tgt_s = self.transform().m11()
        tgt_c = self.mapToScene(self.viewport().rect().center())
        self.resetTransform()
        self.scale(saved_s, saved_s)
        self.centerOn(saved_c)
        return tgt_s, tgt_c

    def _apply_camera(self, scale: float, center: QPointF) -> None:
        self.resetTransform()
        self.scale(scale, scale)
        self.centerOn(center)

    def _animate_camera_fit(
        self, rect: QRectF, *, duration_ms: int | None = None, easing=None
    ) -> None:
        """BETA1-UX06: desliza la cámara hasta encajar *rect* (en vez de saltar).

        Se desactiva (instantáneo) si MOTION_ENABLED es False, si la vista no es
        visible o si el viewport aún no tiene tamaño — así tests y capturas
        llegan al encuadre final sin depender del bucle de eventos.

        BETA1-L02c: ``duration_ms``/``easing`` opcionales permiten una transición
        más larga e inmersiva para el foco de anillo, sin tocar el resto de cámaras
        (por defecto ``_CAM_MS`` + ``OutQuint``).
        """
        if not rect.isValid() or rect.isEmpty():
            return
        vp = self.viewport()
        target_s, target_c = self._camera_fit_target(rect)
        if not MOTION_ENABLED or not self.isVisible() or vp.width() < 8 or vp.height() < 8:
            self._apply_camera(target_s, target_c)
            return
        start_s = self.transform().m11() or 0.0001
        start_c = self.mapToScene(vp.rect().center())
        anim = QVariantAnimation(self)
        anim.setDuration(_CAM_MS if duration_ms is None else int(duration_ms))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutQuint if easing is None else easing)

        def _step(value) -> None:
            try:
                t = float(value)
                s = start_s * (target_s / start_s) ** t  # interpolación geométrica
                cx = start_c.x() + (target_c.x() - start_c.x()) * t
                cy = start_c.y() + (target_c.y() - start_c.y()) * t
                self._apply_camera(s, QPointF(cx, cy))
            except Exception:  # noqa: BLE001 - el pulido nunca rompe la navegación
                pass

        anim.valueChanged.connect(_step)
        anim.finished.connect(
            lambda: self._apply_camera(target_s, target_c) if _qt_alive(self) else None
        )
        self._camera_anim = anim  # mantener referencia viva
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _finalize_view(self, margin: float = 140.0):
        """BETA1-B02: common tail for every layout builder.

        Expands the scene rect to the content and then either restores the
        camera captured by set_graph (same-layout rebuild → keep the user's
        zoom/pan) or fits the whole graph (first build / layout change)."""
        self._expand_scene_rect_to_content()
        state = self._view_state_to_restore
        if state is not None:
            self._view_state_to_restore = None
            transform, center = state
            self.setTransform(transform)
            self.centerOn(center)
        else:
            rect = self.scene_obj.itemsBoundingRect()
            if rect.isValid() and not rect.isEmpty():
                self._animate_camera_fit(rect.adjusted(-margin, -margin, margin, margin))
        # BETA1-C02/C05: any (re)build changes bodies/rings → re-pack the
        # engine and wake it. CRITICAL: this must run in BOTH camera paths —
        # the early-return of the restore branch silently skipped reheat on
        # every same-layout rebuild (bug encontrado en la línea base de F).
        # This NEVER touches _physics_enabled (layout and physics orthogonal).
        self._physics_reheat()

    def reveal_entity(self, entity_id: str):
        """BETA1-B02: make an entity visible by scrolling only — no zoom
        change. Used after contextual creation so the new element shows up
        without yanking the camera (focus_entity does a fitInView zoom)."""
        item = self._nodes.get(entity_id) or self._trees.get(entity_id)
        if item is not None:
            self.ensureVisible(item, 120, 120)

    def _expand_scene_rect_to_content(self):
        """BETA1-B02: make the scene rect cover the real content (plus margin)
        so panning — Space+drag, hand-drag, scrollbars — can reach every part
        of the graph. The fixed default rect (3200x2200) was smaller than
        large concentric layouts, which froze navigation near the center.
        Must be called by EVERY layout builder (free/layered/concentric):
        set_graph returns early for layered and concentric modes."""
        content_rect = self.scene_obj.itemsBoundingRect()
        if content_rect.isNull():
            return
        margin = 400.0
        expanded = content_rect.adjusted(-margin, -margin, margin, margin)
        # Never shrink below the historical default so small/free graphs
        # keep their roomy feel.
        expanded = expanded.united(QRectF(-1600, -1100, 3200, 2200))
        self.scene_obj.setSceneRect(expanded)

    def recompute_edge_visibility(self):
        self.refresh_all_visibility()

    def apply_visual_filter(self, filter_state: VisualFilterState):
        self._visual_filter = filter_state
        self.set_graph(
            self._all_nodes,
            self._all_edges,
            layout_mode=self._layout_mode_active,
            layers=self._all_layers,
        )

    def clear_visual_filters(self):
        self.apply_visual_filter(VisualFilterState())

    def get_filter_state(self) -> VisualFilterState:
        return self._visual_filter

    def active_filter_count(self) -> int:
        vf = self._visual_filter
        return sum(
            1
            for active in [
                vf.entity_types,
                vf.relation_types,
                vf.relation_families,
                vf.tree_id,
                vf.layer_ids,
                vf.focus_entity_ids,
                vf.canon_states,
                vf.visibility_states,
                not vf.show_relations,
            ]
            if active
        )

    def center_on_item(self, item: QGraphicsItem):
        rect = item.sceneBoundingRect().adjusted(-180, -160, 180, 160)
        if rect.isValid() and not rect.isEmpty():
            self._animate_camera_fit(rect)

    def focus_node(self, entity_id: str, *, expand_path: bool = True) -> bool:
        if expand_path:
            for ancestor_id in reversed(self._ancestor_tree_ids(entity_id)):
                tree = self._trees.get(ancestor_id)
                if tree is not None and getattr(tree, "_collapsed", False):
                    tree._expand()
        item = self._nodes.get(entity_id) or self._trees.get(entity_id)
        if item is None:
            return False
        self.clear_selection(emit=False)
        self._selected_entity_ids.add(entity_id)
        item.set_coherence_selected(True)
        self.center_on_item(item)
        self._emit_selection_changed()
        return True

    def _bloom_target(self, key: str):
        # SEM02/SEM03: resuelve por id el elemento germinable (nodo, árbol, anillo
        # o arista). Se re-resuelve cada tick para sobrevivir a reconstrucciones.
        item = self._nodes.get(key) or self._trees.get(key) or self._ring_items.get(key)
        if item is not None:
            return item
        return next((e for e in self._edges if e.edge.relation_id == key), None)

    def bloom_item(self, key: str) -> bool:
        # SEM02/SEM03: arranca el glow de germinación sobre un elemento existente.
        if self._bloom_target(key) is None:
            return False
        self._bloom_items[key] = 0.0
        if not self._bloom_timer.isActive():
            self._bloom_timer.start()
        return True

    def _bloom_tick(self) -> None:
        for key in list(self._bloom_items):
            phase = self._bloom_items[key] + 0.05  # ~0.8 s de germinación
            item = self._bloom_target(key)
            if item is None or phase >= 1.0:
                self._bloom_items.pop(key, None)
                if item is not None:
                    item.set_bloom_phase(0.0)  # apagar el glow
                continue
            self._bloom_items[key] = phase
            item.set_bloom_phase(phase)
        if not self._bloom_items:
            self._bloom_timer.stop()

    # ── UX5: germinación continua sobre nodos existentes (job de edición) ──

    def start_node_germination(self, keys) -> bool:
        """Inicia el latido de germinación sobre los nodos indicados (continuo)."""
        started = False
        for key in keys or []:
            k = str(key)
            if self._bloom_target(k) is not None:
                self._germinating.add(k)
                started = True
        if started and not self._germ_timer.isActive():
            self._germ_timer.start()
        return started

    def stop_node_germination(self, keys=None) -> None:
        """Detiene el latido (todos, o solo los indicados) y apaga su glow."""
        targets = list(self._germinating) if keys is None else [str(k) for k in keys]
        for key in targets:
            self._germinating.discard(key)
            item = self._bloom_target(key)
            # No pisar un bloom one-shot en curso (tiene prioridad y se autoapaga).
            if item is not None and key not in self._bloom_items:
                item.set_bloom_phase(0.0)
        if not self._germinating:
            self._germ_timer.stop()

    def _germ_tick(self) -> None:
        self._germ_pulse += 0.18
        latido = 0.25 + 0.30 * (0.5 + 0.5 * math.sin(self._germ_pulse))
        for key in list(self._germinating):
            item = self._bloom_target(key)
            if item is None:
                self._germinating.discard(key)
                continue
            if key in self._bloom_items:
                continue  # un bloom one-shot manda mientras dure
            item.set_bloom_phase(latido)
        if not self._germinating:
            self._germ_timer.stop()

    def focus_tree(self, tree_id: str) -> bool:
        return self.focus_node(tree_id, expand_path=True)

    def focus_relation(self, relation_id: str) -> bool:
        edge = next((edge for edge in self._edges if edge.edge.relation_id == relation_id), None)
        if edge is None:
            return False
        self.clear_selection(emit=False)
        self._selected_relation_ids.add(relation_id)
        edge.set_coherence_selected(True)
        self.center_on_item(edge)
        self._emit_selection_changed()
        return True

    def clear_search_focus(self):
        self.clear_selection()

    def search(self, query: str, *, worldbuilding_active: bool = False) -> list[GraphSearchResult]:
        terms = [term for term in str(query or "").lower().split() if term]
        if not terms:
            return []
        layer_names = {
            str(getattr(layer, "id", "")): str(getattr(layer, "name", ""))
            for layer in self._all_layers
        }
        results: list[GraphSearchResult] = []
        for node in self._all_nodes:
            layer_name = layer_names.get(node.layer_id, "") if worldbuilding_active else ""
            haystack = " ".join([node.name, node.kind, node.subtitle, layer_name]).lower()
            if all(term in haystack for term in terms):
                parent_id, parent_name, collapsed = self._parent_tree_info(node.entity_id)
                item_kind = "tree" if node.kind.lower() == "contenedor" else "entity"
                results.append(
                    GraphSearchResult(
                        item_id=node.entity_id,
                        item_kind=item_kind,
                        title=node.name,
                        type_label=enum_human(node.kind),
                        category="Rama" if item_kind == "tree" else "Entidad",
                        summary=_fit_text(node.subtitle, 90),
                        parent_tree_name=parent_name,
                        parent_tree_id=parent_id,
                        is_inside_collapsed_tree=collapsed,
                    )
                )
        for edge in self._all_edges:
            if edge.kind.lower() == "contiene":
                continue
            source = next(
                (node for node in self._all_nodes if node.entity_id == edge.source_id), None
            )
            target = next(
                (node for node in self._all_nodes if node.entity_id == edge.target_id), None
            )
            title = edge.label or enum_human(edge.kind)
            haystack = " ".join(
                [title, edge.kind, source.name if source else "", target.name if target else ""]
            ).lower()
            if all(term in haystack for term in terms):
                summary = " → ".join(
                    part
                    for part in [
                        source.name if source else "Origen",
                        target.name if target else "Destino",
                    ]
                    if part
                )
                results.append(
                    GraphSearchResult(
                        item_id=edge.relation_id,
                        item_kind="relation",
                        title=title,
                        type_label=enum_human(edge.kind),
                        category="Relación",
                        summary=summary,
                    )
                )
        return results[:40]

    def _ring_display_name(self, ring_id: str) -> str:
        ring = next((ring for ring in self._ring_visuals if ring.ring_id == ring_id), None)
        if ring is not None:
            return ring.display_name
        if ring_id == "__unclassified__":
            return "Sin clasificar"
        layer = next(
            (layer for layer in self._all_layers if str(getattr(layer, "id", "")) == ring_id), None
        )
        return str(getattr(layer, "name", "Anillo")) if layer is not None else "Anillo"

    def active_ring_id(self) -> str:
        """Current ring for contextual creation: context-menu override wins
        (explicit user intent), then focused ring, then selected ring."""
        if self._context_ring_override:
            return self._context_ring_override
        return str(self._focused_ring_id or self._selected_ring_id or "")

    def focused_ring_id(self) -> str:
        return str(self._focused_ring_id or "")

    def select_ring(self, ring_id: str) -> bool:
        _b44trace(
            f"select_ring_request ring_id={ring_id!r} available={[ring.ring_id for ring in self._ring_visuals]!r}"
        )
        if not ring_id:
            _b44trace("select_ring_result ok=False reason=empty_ring_id")
            return False
        ring = next((ring for ring in self._ring_visuals if ring.ring_id == ring_id), None)
        if ring is None:
            _b44trace("select_ring_result ok=False reason=ring_not_found")
            return False
        self.clear_selection(emit=False)
        self._selected_ring_id = ring_id
        # BETA1-B02: only one ring can show selection feedback at a time
        for other in self._ring_items.values():
            if other.isSelected():
                other.setSelected(False)
        item = self._ring_items.get(ring_id)
        if item is not None:
            item.setSelected(True)
            # BETA1-B02: selection must not navigate. center_on_item here did
            # a fitInView (zoom jump) on every ring click, which made manual
            # navigation nearly impossible. Use focus (double click) to dive
            # into a ring; single click only selects.
        self._emit_selection_changed()
        self.ringSelected.emit(ring_id, ring.display_name)
        _b44trace(
            "select_ring_result "
            f"ok=True selected={self._selected_ring_id!r} focused={self._focused_ring_id!r} display={ring.display_name!r}"
        )
        return True

    def focus_ring_scope(self, ring_id: str) -> bool:
        """B44: enter ring focus without mutating canon or assignments."""
        _b44trace(
            "focus_ring_request "
            f"ring_id={ring_id!r} all_nodes={len(self._all_nodes)} all_edges={len(self._all_edges)} all_layers={len(self._all_layers)} "
            f"layout={self._layout_mode_active}"
        )
        if not ring_id:
            _b44trace("focus_ring_result ok=False reason=empty_ring_id")
            return False
        visuals, node_ring_ids = self._build_concentric_ring_visuals(
            self._all_nodes, self._all_edges, self._all_layers
        )
        _b44trace(
            "focus_ring_visuals "
            f"available={[ring.ring_id for ring in visuals]!r} node_ring_ids={node_ring_ids!r}"
        )
        ring = next((ring for ring in visuals if ring.ring_id == ring_id), None)
        if ring is None:
            _b44trace("focus_ring_result ok=False reason=ring_not_found")
            return False
        self._focused_ring_id = ring_id
        # Ring focus is not a generic visual layer filter. Keep independent
        # filter dimensions, but clear stale scope filters that hide nodes after
        # ring reassignment.
        self._visual_filter = replace(
            self._visual_filter, layer_ids=(), focus_entity_ids=(), tree_id=""
        )
        self.set_graph(
            self._all_nodes,
            self._all_edges,
            layout_mode="concentric_rings",
            layers=self._all_layers,
        )
        # BETA1-L02: 'un anillo a la vez' — atenuar el resto (contexto translúcido
        # detrás) y enmarcar la cámara al anillo enfocado.
        self._apply_ring_attenuation(ring_id)
        self._frame_ring(ring)
        self.ringFocused.emit(ring_id, ring.display_name)
        _b44trace(
            "focus_ring_result "
            f"ok=True focused={self._focused_ring_id!r} selected={self._selected_ring_id!r} "
            f"filter_layers={tuple(getattr(self._visual_filter, 'layer_ids', ()))!r} "
            f"filter_focus={tuple(getattr(self._visual_filter, 'focus_entity_ids', ()))!r} "
            f"ring_items={len(self._ring_items)} nodes_drawn={len(self._nodes)}"
        )
        return True

    def clear_ring_focus(self):
        self._focused_ring_id = ""
        self._selected_ring_id = ""
        self._visual_filter = replace(
            self._visual_filter, layer_ids=(), focus_entity_ids=(), tree_id=""
        )
        if self._layout_mode_active == "concentric_rings":
            self.set_graph(
                self._all_nodes,
                self._all_edges,
                layout_mode="concentric_rings",
                layers=self._all_layers,
            )
        self._apply_ring_attenuation("")  # BETA1-L02: restaura opacidad plena
        self.ringFocusCleared.emit()

    # ── BETA1-L02: selector de anillos + navegación 'un anillo a la vez' ──────

    def ring_summaries(self) -> list[dict]:
        """Resumen de anillos para el selector lateral, ordenados de dentro a
        fuera (rango causal). Cada anillo: ring_id, name, count, inner, outer,
        focused. Datos efímeros derivados; nunca canon."""
        if not self._all_layers:
            return []
        visuals, _ = self._build_concentric_ring_visuals(
            self._all_nodes, self._all_edges, self._all_layers
        )
        return [
            {
                "ring_id": ring.ring_id,
                "name": ring.display_name,
                "count": len(ring.item_ids),
                "inner": ring.inner_radius,
                "outer": ring.outer_radius,
                "focused": ring.ring_id == self._focused_ring_id,
            }
            for ring in visuals
        ]

    def _apply_ring_attenuation(self, focused_ring_id: str) -> None:
        """BETA1-L02c: 'un anillo a la vez' con contexto. Atenúa (translúcido) los
        nodos Y los círculos/etiquetas de anillo que NO están en el anillo enfocado
        — los vecinos de dentro y de fuera quedan tenues pero visibles. Sin anillo
        enfocado ('') → todo a opacidad plena."""
        for entity_id, item in {**self._nodes, **self._trees}.items():
            if not focused_ring_id or self._node_ring_ids.get(entity_id, "") == focused_ring_id:
                item.setOpacity(1.0)
            else:
                item.setOpacity(_RING_NEIGHBOR_OPACITY)
        for ring_id, ring_item in self._ring_items.items():
            if not focused_ring_id or ring_id == focused_ring_id:
                ring_item.setOpacity(1.0)
            else:
                ring_item.setOpacity(_RING_NEIGHBOR_OPACITY)

    def _frame_ring(self, ring: _RingVisual) -> None:
        """BETA1-L02c: enmarca la cámara al anillo con una transición inmersiva
        (~600ms, desaceleración profunda) y un margen algo más amplio (proporcional
        a la banda del anillo) para que asomen el vecino de dentro (hacia el centro)
        y el de fuera (por los bordes)."""
        outer = max(float(ring.outer_radius), 80.0)
        band = max(float(ring.outer_radius) - float(ring.inner_radius), 0.0)
        pad = max(60.0, band * _RING_FRAME_PAD_FACTOR)
        edge = outer + pad
        rect = QRectF(-edge, -edge, 2.0 * edge, 2.0 * edge)
        self._animate_camera_fit(
            rect, duration_ms=_RING_FOCUS_CAM_MS, easing=QEasingCurve.Type.OutExpo
        )

    def focus_adjacent_ring(self, step: int) -> bool:
        """Salta al anillo contiguo (siguiente=+1 hacia fuera, anterior=−1 hacia
        dentro) en orden causal. Hace clamp en los extremos. Si no hay foco
        activo, entra por el anillo más interno (siguiente) o el externo (anterior)."""
        summaries = self.ring_summaries()
        if not summaries:
            return False
        order = [s["ring_id"] for s in summaries]
        if self._focused_ring_id in order:
            idx = order.index(self._focused_ring_id)
            target = max(0, min(len(order) - 1, idx + step))
        else:
            target = 0 if step >= 0 else len(order) - 1
        return self.focus_ring_scope(order[target])

    def focus_ring_by_index(self, index: int) -> bool:
        """BETA1-L02b: enfoca el anillo i-ésimo por orden causal (0 = más interno).
        Lo usan las teclas 1…0. Reutiliza focus_ring_scope (cámara + atenuación +
        breadcrumb + resaltado del panel). Fuera de rango o sin anillos → no-op."""
        if self._layout_mode_active != "concentric_rings":
            return False
        summaries = self.ring_summaries()
        if index < 0 or index >= len(summaries):
            return False
        return self.focus_ring_scope(summaries[index]["ring_id"])

    def focus_tree_scope(self, tree_id: str) -> bool:
        ids = {tree_id} | self._descendant_ids_for_tree(tree_id)
        self.apply_visual_filter(VisualFilterState(focus_entity_ids=tuple(sorted(ids))))
        return self.focus_tree(tree_id)

    def focus_neighborhood(self, item_id: str) -> bool:
        ids: set[str] = set()
        relation = next((edge for edge in self._all_edges if edge.relation_id == item_id), None)
        center_relation = ""
        if relation is not None:
            ids.update([relation.source_id, relation.target_id])
            center_relation = item_id
        else:
            ids.add(item_id)
            for edge in self._all_edges:
                if edge.source_id == item_id or edge.target_id == item_id:
                    ids.update([edge.source_id, edge.target_id])
        # Include ancestor containers for entity neighborhoods so nodes inside
        # trees remain visible. Relation focus stays limited to endpoints.
        if relation is None:
            for eid in list(ids):
                current = self._membership.get(eid)
                while current is not None:
                    ids.add(current)
                    current = self._membership.get(current)
        self.apply_visual_filter(VisualFilterState(focus_entity_ids=tuple(sorted(ids))))
        if center_relation:
            return self.focus_relation(center_relation)
        return self.focus_node(item_id)

    def clear_focus_scope(self):
        self.clear_ring_focus()
        self.clear_visual_filters()

    def fit_all(self):
        rect = self.scene_obj.itemsBoundingRect()
        if rect.isValid() and not rect.isEmpty():
            self._animate_camera_fit(rect.adjusted(-140, -140, 140, 140))

    def reset_to_panorama(self) -> None:
        """BETA1-L02c: 'volver al todo' (tecla F). SIEMPRE restaura: quita el foco de
        anillo (devuelve opacidad plena a nodos y anillos, resetea el foco y emite
        ringFocusCleared) y reencuadra el grafo entero. No toca los filtros visuales
        del usuario."""
        self.clear_ring_focus()
        self.fit_all()

    def reset_view(self):
        self.resetTransform()
        self.centerOn(0, 0)

    def center_selection(self) -> bool:
        selected_items = []
        selected_items.extend(
            item for eid, item in self._nodes.items() if eid in self._selected_entity_ids
        )
        selected_items.extend(
            item for eid, item in self._trees.items() if eid in self._selected_entity_ids
        )
        selected_items.extend(
            edge for edge in self._edges if edge.edge.relation_id in self._selected_relation_ids
        )
        if not selected_items:
            return False
        rect = selected_items[0].sceneBoundingRect()
        for item in selected_items[1:]:
            rect = rect.united(item.sceneBoundingRect())
        self._animate_camera_fit(rect.adjusted(-180, -160, 180, 160))
        return True

    def focus_entity(self, entity_id: str):
        self.focus_node(entity_id)


class _EraTimeSlider(QSlider):
    """BETA1-UX feedback: slider de tiempo que dibuja las ERAS proporcionalmente
    a sus años (una franja cálida por era, sobre el groove, con separadores).

    El rango del slider ya es lineal en años (min=primer año, max=último), así
    que mapear start/end de cada era a x es proporcional por construcción.
    """

    _ERA_TINTS = ("#C8A24C", "#7E9568", "#A87C53", "#937083", "#B28A3C")

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._era_segments: list[tuple[int, int]] = []
        self.setMinimumHeight(34)

    def set_eras(self, eras, lo: int, hi: int) -> None:
        segs: list[tuple[int, int]] = []
        for era in eras or []:
            start = _parse_optional_year(getattr(era, "start_year", None))
            if start is None:
                continue
            end = _parse_optional_year(getattr(era, "end_year", None))
            segs.append((int(start), int(hi if end is None else end)))
        self._era_segments = segs
        self.update()

    def paintEvent(self, event):  # noqa: N802 (Qt API)
        super().paintEvent(event)
        lo, hi = self.minimum(), self.maximum()
        if not self._era_segments or hi <= lo:
            return
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderGroove, self
        )
        gx, gw = float(groove.x()), float(groove.width())
        span = float(hi - lo)
        # BETA1-UX feedback: ANTES era un filo de 5 px casi invisible. Ahora es
        # una cinta de eras nítida (un tinte por era, proporcional a sus años)
        # en la parte alta del slider, con separadores que bajan al groove.
        ribbon_y = 3.0
        ribbon_h = 9.0
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            for i, (start, end) in enumerate(self._era_segments):
                x0 = gx + gw * (max(start, lo) - lo) / span
                x1 = gx + gw * (min(end, hi) - lo) / span
                width = max(x1 - x0, 2.0)
                tint = QColor(self._ERA_TINTS[i % len(self._ERA_TINTS)])
                tint.setAlpha(225)
                painter.setPen(QPen(Qt.PenStyle.NoPen))
                painter.setBrush(QBrush(tint))
                painter.drawRoundedRect(QRectF(x0, ribbon_y, width, ribbon_h), 3.0, 3.0)
                # Separador fino entre eras, prolongado hasta el groove.
                painter.setPen(QPen(QColor(120, 112, 82, 150), 1.0))
                painter.drawLine(QPointF(x0, ribbon_y), QPointF(x0, float(groove.bottom())))
            painter.end()
        except Exception:  # noqa: BLE001 - el pulido nunca rompe el slider
            pass


class GraphCanvasWidget(QWidget):
    """B31-T03 graph-first Creation entry."""

    entitySelected = Signal(str)
    relationSelected = Signal(str)
    relationCreateRequested = Signal(str, str)
    graphSelectionChanged = Signal(list, list)
    nodeAssignToTreeRequested = Signal(str, str)
    relationCreateRejected = Signal(str)
    ringSelected = Signal(str, str)
    ringFocused = Signal(str, str)
    ringFocusCleared = Signal()  # BETA1-L02
    searchRequested = Signal()  # BETA1-L02b: tecla 'd' → barra de búsqueda flotante
    candidateClicked = Signal(str)  # SEM04: semilla germinante pulsada en el grafo
    # BETA1-B01: context-menu intents re-exposed from GraphCanvasView
    contextCreateEntityRequested = Signal()
    contextCreateTreeRequested = Signal()
    contextCreateEntityInTreeRequested = Signal(str)
    contextCreateSubtreeRequested = Signal(str)
    contextDeleteRequested = Signal()
    contextAIActionRequested = Signal(str)
    # BETA1-B02
    escapePressed = Signal()
    # BETA1-B03
    nodeAssignToRingRequested = Signal(str, str)
    ringCreateRequested = Signal()
    ringEditRequested = Signal(str)
    ringDeleteRequested = Signal(str)
    nodeExtractFromTreeRequested = Signal(str)

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.ai_controller = None
        stored_mode = str(getattr(ctx, "creation_layout_mode", "free") or "free")
        self._layout_mode = (
            stored_mode if stored_mode in {"free", "layered", "concentric_rings"} else "free"
        )
        self._layer_mode = self._layout_mode == "layered"
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # No header — the graph takes all available space

        # UX24: el vacío GUÍA — una acción crea la primera entidad (misma vía que el
        # menú contextual "crear entidad"), en vez de dejar el lienzo en blanco.
        self.empty = EmptyState(
            "Tu lienzo está por sembrar",
            "Aún no hay entidades en este proyecto. Crea la primera —un personaje, "
            "un lugar, una idea— y el grafo empezará a crecer.",
            action_text="Crear primera entidad",
            on_action=self.contextCreateEntityRequested.emit,
        )
        # UX34: tarjeta sólida contenida (no full-bleed con borde de puntos), para que
        # respire y se lea como una pieza "de producto" centrada en el lienzo.
        self.empty.setMaximumWidth(460)
        self.empty.setStyleSheet(
            f"QFrame#card {{ background: {SURFACE_HI}; border: 1px solid {LINE}; "
            f"border-radius: {RADIUS_LG}px; }}"
        )
        # UX34: glifo botánico cálido por encima del título.
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("creation", size=44, color=GOLD_DEEP))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setStyleSheet("background: transparent; border: none;")
        self.empty.layout.insertWidget(0, glyph)
        # UX34: título + mensaje centrados (presentación tipo "hero" del vacío).
        if getattr(self.empty, "title", None) is not None:
            self.empty.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if getattr(self.empty, "subtitle", None) is not None:
            self.empty.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.empty.subtitle.setStyleSheet(
                f"color: {INK_MUTED}; background: transparent; border: none;"
            )
        # UX34: el botón NO se reestiliza — usa el estilo global #primaryButton (marrón/oro,
        # esquinas redondeadas RADIUS_MD, texto legible), igual que el resto de botones.

        # UX34: la invitación es un OVERLAY flotante (hijo del widget, no del layout),
        # como `_time_bar`. Así puede superponerse sobre el canvas con anillos en modo
        # concéntrico ("anillos + invitación encima") o cubrir el lienzo en otros modos.
        # Mouse-transparente para que los clics en las zonas vacías lleguen al canvas
        # detrás; la tarjeta y su botón sí reciben sus propios clics.
        self._empty_host = QWidget(self)
        self._empty_host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._empty_host.setStyleSheet("background: transparent;")
        _eh = QVBoxLayout(self._empty_host)
        _eh.setContentsMargins(SPACE_2XL, SPACE_2XL, SPACE_2XL, SPACE_2XL)
        _eh.addStretch(1)
        _erow = QHBoxLayout()
        _erow.addStretch(1)
        _erow.addWidget(self.empty)
        _erow.addStretch(1)
        _eh.addLayout(_erow)
        _eh.addStretch(1)
        self._empty_host.hide()

        self.canvas = GraphCanvasView()
        self.canvas._atmosphere.set_context(self.ctx)  # BETA1-G08: respeta movimiento reducido
        self.canvas.entitySelected.connect(self._entity_selected)
        self.canvas.relationSelected.connect(self._relation_selected)
        self.canvas.relationCreateRequested.connect(self.relationCreateRequested.emit)
        self.canvas.relationCreateRejected.connect(self.relationCreateRejected.emit)
        self.canvas.graphSelectionChanged.connect(self.graphSelectionChanged.emit)
        self.canvas.nodeAssignToTreeRequested.connect(self.nodeAssignToTreeRequested.emit)
        self.canvas.ringSelected.connect(self.ringSelected.emit)
        self.canvas.ringFocused.connect(self.ringFocused.emit)
        self.canvas.ringFocusCleared.connect(self.ringFocusCleared.emit)
        self.canvas.searchRequested.connect(self.searchRequested.emit)  # BETA1-L02b
        self.canvas.seedClicked.connect(self.candidateClicked.emit)  # SEM04
        # BETA1-B01: context-menu intents
        self.canvas.contextCreateEntityRequested.connect(self.contextCreateEntityRequested.emit)
        self.canvas.contextCreateTreeRequested.connect(self.contextCreateTreeRequested.emit)
        self.canvas.contextCreateEntityInTreeRequested.connect(
            self.contextCreateEntityInTreeRequested.emit
        )
        self.canvas.contextCreateSubtreeRequested.connect(self.contextCreateSubtreeRequested.emit)
        self.canvas.contextDeleteRequested.connect(self.contextDeleteRequested.emit)
        self.canvas.contextAIActionRequested.connect(self.contextAIActionRequested.emit)
        # BETA1-B02
        self.canvas.escapePressed.connect(self.escapePressed.emit)
        # BETA1-B03
        self.canvas.nodeAssignToRingRequested.connect(self.nodeAssignToRingRequested.emit)
        self.canvas.ringCreateRequested.connect(self.ringCreateRequested.emit)
        self.canvas.ringEditRequested.connect(self.ringEditRequested.emit)
        self.canvas.ringDeleteRequested.connect(self.ringDeleteRequested.emit)
        self.canvas.nodeExtractFromTreeRequested.connect(self.nodeExtractFromTreeRequested.emit)
        layout.addWidget(self.canvas, 1)
        self.canvas.setVisible(False)

        # BETA1-G06: scrubber temporal — la "máquina del tiempo" del grafo
        # concéntrico. Overlay flotante (no en el layout) sobre el lienzo.
        self._time_year_range = (0, 0)
        self._time_present_year = 0
        self._time_bar = self._build_time_bar()
        self._time_bar.setVisible(False)

    # ── BETA1-G06: scrubber temporal ──────────────────────────────────────

    def _build_time_bar(self) -> QFrame:
        """Barra flotante para 'fotografiar' el grafo en cualquier año."""
        bar = QFrame(self)
        bar.setObjectName("timeScrubber")
        bar.setStyleSheet(
            f"QFrame#timeScrubber {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 17px; }}"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 5, 10, 5)
        row.setSpacing(8)

        self._time_toggle = QPushButton()
        self._time_toggle.setCheckable(True)
        self._time_toggle.setToolTip("Recorrer el tiempo: ver el grafo tal como estaba en un año")
        self._time_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._time_toggle.setFixedSize(30, 30)
        self._time_toggle.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; border-radius: 15px; }} "
            f"QPushButton:hover {{ background: {GOLD_TINT}; }} "
            f"QPushButton:checked {{ background: {GOLD}; }}"
        )
        icons.set_button_icon(self._time_toggle, "chronology", color=INK_SOFT, size=16)
        self._time_toggle.toggled.connect(self._on_time_toggle)
        row.addWidget(self._time_toggle)

        self._time_slider = _EraTimeSlider(Qt.Orientation.Horizontal)
        self._time_slider.setObjectName("timeSlider")
        self._time_slider.setEnabled(False)
        self._time_slider.setMinimumWidth(220)
        self._time_slider.setStyleSheet(
            f"QSlider#timeSlider::groove:horizontal {{ height: 4px; border-radius: 2px; background: {LINE}; }} "
            f"QSlider#timeSlider::sub-page:horizontal {{ background: {GOLD_SOFT}; border-radius: 2px; }} "
            f"QSlider#timeSlider::handle:horizontal {{ background: {GOLD}; border: 2px solid {SURFACE_HI}; "
            f"width: 14px; height: 14px; margin: -6px 0; border-radius: 9px; }} "
            f"QSlider#timeSlider::handle:horizontal:hover {{ background: {GOLD_DEEP}; }} "
            f"QSlider#timeSlider:disabled {{ }} "
            f"QSlider#timeSlider::handle:horizontal:disabled {{ background: {LINE}; border-color: {SURFACE_HI}; }}"
        )
        self._time_slider.valueChanged.connect(self._on_time_slider)
        row.addWidget(self._time_slider, 1)

        self._time_readout = QLabel("Todo el tiempo")
        self._time_readout.setStyleSheet(
            f"color: {INK_STRONG}; font-size: 12px; font-weight: 600; background: transparent; border: none;"
        )
        self._time_readout.setMinimumWidth(120)
        self._time_readout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        row.addWidget(self._time_readout)

        self._time_present_btn = QPushButton("Presente")
        self._time_present_btn.setToolTip("Saltar al año presente del mundo")
        self._time_present_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._time_present_btn.setFixedHeight(26)
        self._time_present_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {LINE}; "
            f"border-radius: 12px; padding: 2px 10px; color: {INK_SOFT}; font-size: 11px; font-weight: 600; }} "
            f"QPushButton:hover {{ background: {GOLD_TINT}; border-color: {GOLD_SOFT}; color: {INK_STRONG}; }}"
        )
        self._time_present_btn.clicked.connect(self._on_time_present)
        row.addWidget(self._time_present_btn)
        bar.adjustSize()
        bar.raise_()
        return bar

    def _project_year_bounds(self, project) -> tuple[int, int, int]:
        """(min_year, max_year, present_year) a partir del calendario y las vidas."""
        # BETA1-UX feedback: usar eras/presente EFECTIVOS (derivados del
        # calendario completo si el dominio no las tiene), igual que la
        # cronológica, para que el slider abarque el rango real del mundo.
        present = effective_present_year(project)
        years: list[int] = [present]
        for era in effective_eras(project):
            start = _parse_optional_year(getattr(era, "start_year", None))
            if start is not None:
                years.append(start)
            end = _parse_optional_year(getattr(era, "end_year", None))
            if end is not None:
                years.append(end)
        for entity in list(getattr(project, "entities", []) or []):
            birth = _parse_optional_year(getattr(entity, "birth_year", None))
            if birth is not None:
                years.append(birth)
            death = _parse_optional_year(getattr(entity, "death_year", None))
            if death is not None:
                years.append(death)
        for hito in list(getattr(project, "causal_milestones", []) or []):
            year = _parse_optional_year(getattr(hito, "year", None))
            if year is not None:
                years.append(year)
        lo, hi = min(years), max(years)
        return lo, max(hi, present), present

    def _era_name_for_year(self, project, year: int) -> str:
        for era in effective_eras(project):
            start = _parse_optional_year(getattr(era, "start_year", None))
            if start is None or year < start:
                continue
            end = _parse_optional_year(getattr(era, "end_year", None))
            if end is None or year < end:
                return str(getattr(era, "name", "") or "")
        return ""

    def _sync_time_bar(self):
        """Recalcula el rango del scrubber con el proyecto actual."""
        project = self._project()
        if project is None:
            self._time_bar.setVisible(False)
            return
        lo, hi, present = self._project_year_bounds(project)
        self._time_year_range = (lo, hi)
        self._time_present_year = present
        block = self._time_slider.blockSignals(True)
        self._time_slider.setMinimum(lo)
        self._time_slider.setMaximum(max(hi, lo))
        # BETA1-UX feedback: pinta las eras proporcionalmente en el slider.
        if hasattr(self._time_slider, "set_eras"):
            self._time_slider.set_eras(effective_eras(project), lo, max(hi, lo))
        current = self.canvas.view_year()
        if current is not None:
            self._time_slider.setValue(max(lo, min(hi, current)))
        elif lo <= present <= hi:
            self._time_slider.setValue(present)
        self._time_slider.blockSignals(block)
        self._time_slider.setEnabled(self._time_toggle.isChecked() and hi > lo)
        self._update_time_readout()

    def _update_time_readout(self):
        year = self.canvas.view_year()
        if year is None:
            self._time_readout.setText("Todo el tiempo")
            return
        project = self._project()
        era = self._era_name_for_year(project, year) if project is not None else ""
        suffix = f" · {era}" if era else ""
        self._time_readout.setText(f"Año {year}{suffix}")

    def _on_time_toggle(self, checked: bool):
        if checked:
            lo, hi = self._time_year_range
            self._time_slider.setEnabled(hi > lo)
            self.canvas.set_view_year(int(self._time_slider.value()))
        else:
            self._time_slider.setEnabled(False)
            self.canvas.set_view_year(None)
        self._update_time_readout()

    def _on_time_slider(self, value: int):
        if self._time_toggle.isChecked():
            self.canvas.set_view_year(int(value))
            self._update_time_readout()

    def _on_time_present(self):
        lo, hi = self._time_year_range
        present = max(lo, min(hi, self._time_present_year))
        if not self._time_toggle.isChecked():
            self._time_toggle.setChecked(True)  # activa modo temporal (dispara set_view_year)
        block = self._time_slider.blockSignals(True)
        self._time_slider.setValue(present)
        self._time_slider.blockSignals(block)
        self.canvas.set_view_year(present)
        self._update_time_readout()

    def set_view_year(self, year: int | None):
        self.canvas.set_view_year(year)
        self._update_time_readout()

    def view_year(self) -> int | None:
        return self.canvas.view_year()

    def _position_time_bar(self):
        bar = getattr(self, "_time_bar", None)
        if bar is None:
            return
        width = max(420, min(self.width() - 80, 760))
        bar.setFixedWidth(width)
        bar.move((self.width() - width) // 2, 14)
        bar.raise_()

    def resizeEvent(self, event):  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        if getattr(self, "_empty_host", None) is not None and self._empty_host.isVisible():
            self._position_empty_overlay()
        self._position_time_bar()

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def set_ai_controller(self, ai_controller):
        self.ai_controller = ai_controller

    def selected_entity_ids(self) -> list[str]:
        return self.canvas.selected_entity_ids()

    # BETA1-C02: physics overlay (orthogonal to layout mode)
    def physics_enabled(self) -> bool:
        return self.canvas.physics_enabled()

    def set_physics_enabled(self, enabled: bool):
        self.canvas.set_physics_enabled(enabled)

    def selected_relation_ids(self) -> list[str]:
        return self.canvas.selected_relation_ids()

    def clear_selection(self):
        self.canvas.clear_selection()

    def search(self, query: str) -> list[GraphSearchResult]:
        project = self._project()
        return self.canvas.search(
            query,
            worldbuilding_active=bool(getattr(project, "worldbuilding_active", False))
            if project is not None
            else False,
        )

    def focus_node(self, entity_id: str) -> bool:
        ok = self.canvas.focus_node(entity_id)
        if ok:
            self._entity_selected(entity_id)
        return ok

    def bloom_node(self, entity_id: str) -> bool:
        # SEM02: enfoca el nodo recién germinado y dispara el glow dorado.
        ok = self.canvas.focus_node(entity_id)
        if ok:
            self._entity_selected(entity_id)
            self.canvas.bloom_item(entity_id)
        return ok

    def focus_tree(self, tree_id: str) -> bool:
        ok = self.canvas.focus_tree(tree_id)
        if ok:
            self._entity_selected(tree_id)
        return ok

    def focus_relation(self, relation_id: str) -> bool:
        ok = self.canvas.focus_relation(relation_id)
        if ok:
            self._relation_selected(relation_id)
        return ok

    def start_node_germination(self, entity_ids) -> bool:
        # UX5: germina (latido continuo) las entidades en edición durante el job.
        return self.canvas.start_node_germination(entity_ids)

    def stop_node_germination(self, entity_ids=None) -> None:
        # UX5: detiene el latido al terminar/fallar el job.
        self.canvas.stop_node_germination(entity_ids)

    def bloom_relation(self, relation_id: str) -> bool:
        # SEM03: enfoca la relación recién germinada y dispara el glow de la arista.
        ok = self.canvas.focus_relation(relation_id)
        if ok:
            self._relation_selected(relation_id)
            self.canvas.bloom_item(relation_id)
        return ok

    def bloom_ring(self, ring_id: str) -> bool:
        # SEM03: germina el anillo recién creado (pulso dorado en la banda).
        return self.canvas.bloom_item(ring_id)

    # ── SEM04: semillas germinantes en el grafo (delegan en GraphCanvasView) ──

    def plant_seed(self, job_id: str, ring_id: str = "") -> None:
        self.canvas.plant_seed(job_id, ring_id)

    def advance_seed(self, job_id: str, progress: float) -> None:
        self.canvas.advance_seed(job_id, progress)

    def split_seed(
        self, job_id: str, candidate_ids: list[str], ring_ids: dict[str, str] | None = None
    ) -> None:
        self.canvas.split_seed(job_id, candidate_ids, ring_ids)

    def bloom_seed(self, candidate_id: str) -> None:
        self.canvas.bloom_seed(candidate_id)

    def wither_seed(self, key: str) -> None:
        self.canvas.wither_seed(key)

    def play_reveal(self, *, duration_ms: int = 220) -> None:
        # UX31: delega el revelado de transición en la vista (dentro del viewport GPU).
        self.canvas.play_reveal(duration_ms=duration_ms)

    def rehydrate_candidate_seeds(
        self, candidate_ids: list[str], ring_ids: dict[str, str] | None = None
    ) -> None:
        self.canvas.rehydrate_candidate_seeds(candidate_ids, ring_ids)

    def center_on_item(self, item):
        self.canvas.center_on_item(item)

    def clear_search_focus(self):
        self.canvas.clear_search_focus()

    def apply_visual_filter(self, filter_state: VisualFilterState):
        self.canvas.apply_visual_filter(filter_state)

    def clear_visual_filters(self):
        self.canvas.clear_visual_filters()

    def get_filter_state(self) -> VisualFilterState:
        return self.canvas.get_filter_state()

    def recompute_edge_visibility(self):
        self.canvas.recompute_edge_visibility()

    def active_filter_count(self) -> int:
        return self.canvas.active_filter_count()

    def focus_tree_scope(self, tree_id: str) -> bool:
        ok = self.canvas.focus_tree_scope(tree_id)
        if ok:
            self._entity_selected(tree_id)
        return ok

    def focus_ring_scope(self, ring_id: str) -> bool:
        _b44trace(f"widget_focus_ring_request ring_id={ring_id!r} layout={self._layout_mode!r}")
        ok = self.canvas.focus_ring_scope(ring_id)
        _b44trace(
            "widget_focus_ring_result "
            f"ok={ok} layout={self._layout_mode!r} canvas_layout={self.canvas._layout_mode_active!r} "
            f"ring_items={len(self.canvas._ring_items)} nodes={len(self.canvas._nodes)}"
        )
        if ok:
            self._layout_mode = "concentric_rings"
            self._layer_mode = False
            self.ctx.creation_layout_mode = "concentric_rings"
            self.ctx.save_preferences()
        return ok

    def ring_summaries(self) -> list[dict]:
        return self.canvas.ring_summaries()

    def focus_adjacent_ring(self, step: int) -> bool:
        ok = self.canvas.focus_adjacent_ring(step)
        if ok:
            self._layout_mode = "concentric_rings"
            self._layer_mode = False
            self.ctx.creation_layout_mode = "concentric_rings"
            self.ctx.save_preferences()
        return ok

    def focus_canvas(self) -> None:
        """BETA1-L02c: da el foco de teclado a la VISTA interna (no al wrapper), para
        que los atajos del lienzo respondan sin que el usuario tenga que clicar."""
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def focused_ring_id(self) -> str:
        return str(getattr(self.canvas, "_focused_ring_id", ""))

    def active_ring_id(self) -> str:
        return self.canvas.active_ring_id() if hasattr(self.canvas, "active_ring_id") else ""

    def ring_visual_by_id(self, ring_id: str):
        return next(
            (ring for ring in getattr(self.canvas, "_ring_visuals", []) if ring.ring_id == ring_id),
            None,
        )

    def focus_neighborhood(self, item_id: str) -> bool:
        ok = self.canvas.focus_neighborhood(item_id)
        if ok:
            if item_id in {rel.relation_id for rel in self.canvas._all_edges}:
                self._relation_selected(item_id)
            else:
                self._entity_selected(item_id)
        return ok

    def clear_focus_scope(self):
        self.canvas.clear_focus_scope()
        self.ctx.creation_focused_ring_id = ""
        self.ctx.save_preferences()

    def fit_all(self):
        self.canvas.fit_all()

    def zoom_in(self):
        self.canvas.zoom_in()

    def zoom_out(self):
        self.canvas.zoom_out()

    def reset_view(self):
        self.canvas.reset_view()

    def center_selection(self) -> bool:
        return self.canvas.center_selection()

    def run_graph_ai_action(self, action_type: str):
        if self.ai_controller is None:
            return
        project = self._project()
        entity_ids = [
            getattr(entity, "id", "")
            for entity in getattr(project, "entities", []) or []
            if getattr(entity, "id", "")
        ]
        relation_ids = [
            getattr(relation, "id", "")
            for relation in getattr(project, "relations", []) or []
            if getattr(relation, "id", "")
        ]
        self.ai_controller.graph_action(
            action_type, entity_ids=entity_ids, relation_ids=relation_ids
        )
        self.refresh()

    def _entity_selected(self, entity_id: str):
        self.ctx.selected_entity_id = entity_id
        self.entitySelected.emit(entity_id)
        if self._advanced_mode:
            self.ctx.log("info", f"Nodo seleccionado: {entity_id}")
        else:
            self.ctx.log("info", "Nodo seleccionado")

    def _relation_selected(self, relation_id: str):
        setattr(self.ctx, "selected_relation_id", relation_id)
        self.relationSelected.emit(relation_id)
        if self._advanced_mode:
            self.ctx.log("info", f"Relación seleccionada: {relation_id}")
        else:
            self.ctx.log("info", "Relación seleccionada")

    def _fit_all(self):
        rect = self.canvas.scene_obj.itemsBoundingRect()
        if rect.isValid() and not rect.isEmpty():
            self.canvas.fitInView(
                rect.adjusted(-140, -140, 140, 140), Qt.AspectRatioMode.KeepAspectRatio
            )

    def _effective_world_layers(self, project) -> list[Any]:
        """Return visual-only layers for anillo layouts without mutating canon.

        New BETA1 projects can have no `project.world_layers` yet. In that
        state the concentric canvas stays empty until the user explicitly
        creates a ring or applies the suggested template.
        """
        project_layers = list(getattr(project, "world_layers", []) or [])
        defaults = default_world_layers()
        if not project_layers:
            return []

        default_by_id = {str(getattr(layer, "id", "")): layer for layer in defaults}
        effective: list[Any] = []
        for layer in project_layers:
            layer_id = str(getattr(layer, "id", ""))
            default = default_by_id.get(layer_id)
            if (
                default is not None
                and get_causal_rank(layer) is None
                and get_causal_rank(default) is not None
            ):
                metadata = dict(getattr(default, "metadata", {}) or {})
                metadata.update(dict(getattr(layer, "metadata", {}) or {}))
                effective.append(replace(layer, metadata=metadata))
            else:
                effective.append(layer)
        return effective

    def _position_empty_overlay(self) -> None:
        """Cubre todo el widget con el overlay de la invitación y lo eleva sobre el
        canvas (la tarjeta queda centrada por sus stretches)."""
        host = getattr(self, "_empty_host", None)
        if host is None:
            return
        host.setGeometry(self.rect())
        host.raise_()

    def _set_empty_visible(self, visible: bool) -> None:
        """Muestra/oculta la invitación de estado vacío. Alterna el overlay flotante
        (que se eleva sobre el canvas) y la propia tarjeta (para que
        ``self.empty.isHidden()`` siga reflejando el estado — contrato de tests)."""
        self.empty.setVisible(visible)
        self._empty_host.setVisible(visible)
        if visible:
            self._position_empty_overlay()

    def refresh(self):
        project = self._project()
        if project is None:
            _b44trace(f"widget_refresh project=None layout={self._layout_mode!r}")
            self.canvas.clear_graph()
            self.canvas.setVisible(False)
            self._set_empty_visible(True)
            self._time_bar.setVisible(False)
            return
        entities = []
        seen_entity_ids: set[str] = set()
        for entity in getattr(project, "entities", []) or []:
            entity_id = getattr(entity, "id", "")
            if not entity_id or entity_id in seen_entity_ids:
                continue
            seen_entity_ids.add(entity_id)
            entities.append(_entity_view(entity))
        relations = []
        seen_relation_ids: set[str] = set()
        for relation in getattr(project, "relations", []) or []:
            relation_id = getattr(relation, "id", "")
            if not relation_id or relation_id in seen_relation_ids:
                continue
            seen_relation_ids.add(relation_id)
            relations.append(_relation_view(relation))
        # B40-FIX: do not inject pending AI candidates into the graph canvas as
        # visual nodes. They are not canon, are not removable through the normal
        # entity deletion flow, and in new projects they look like auto-created
        # empty entities. Candidate review/acceptance belongs in the candidate
        # tray or explicit AI suggestion UI; only accepted/canonical entities and
        # relations are rendered here.
        _b44trace(
            "widget_refresh_data "
            f"layout={self._layout_mode!r} entities={len(entities)} relations={len(relations)} "
            f"project_layers={len(getattr(project, 'world_layers', []) or [])} "
            f"canvas_visible_before={self.canvas.isVisible()} empty_visible_before={self.empty.isVisible()}"
        )
        # UX34: sin entidades, la invitación ("Crear primera entidad") SIEMPRE aparece,
        # pero el modo concéntrico muestra además los ANILLOS detrás (decisión del
        # usuario: "anillos + invitación encima"). En los demás modos no hay nada que
        # dibujar, así que la invitación ocupa el lienzo entero.
        if not entities and self._layout_mode == "concentric_rings":
            layers = self._effective_world_layers(project)
            self.canvas.set_graph([], [], layout_mode=self._layout_mode, layers=layers)
            self.canvas.setVisible(True)
            self._sync_time_bar()
            self._time_bar.setVisible(True)
            self._position_time_bar()
            self._set_empty_visible(True)  # overlay sobre los anillos
            self._position_time_bar()  # la barra superior queda por encima del overlay
            return
        if not entities:
            self.canvas.clear_graph()
            self.canvas.setVisible(False)
            self._set_empty_visible(True)
            self._time_bar.setVisible(False)
            return
        self._set_empty_visible(False)
        self.canvas.setVisible(True)
        # _layer_mode is controlled only by explicit user action (Anillos button).
        # Do NOT derive it from project.worldbuilding_active here — that flag
        # means "worldbuilding feature is available", not "show layer bands".
        layers = (
            self._effective_world_layers(project)
            if self._layout_mode in {"layered", "concentric_rings"}
            else []
        )
        _b44trace(
            "widget_refresh_before_set_graph "
            f"layout={self._layout_mode!r} effective_layers={len(layers)} layer_ids={[str(getattr(layer, 'id', '')) for layer in layers]!r}"
        )
        # BETA1-L01: atajo incremental para ediciones de atributos (mismos ids,
        # misma estructura) — actualiza items in situ y evita el rebuild O(N).
        # Si no aplica, cae al set_graph completo de siempre.
        if not self.canvas.try_incremental_refresh(
            entities, relations, layout_mode=self._layout_mode, layers=layers
        ):
            self.canvas.set_graph(entities, relations, layout_mode=self._layout_mode, layers=layers)
        # BETA1-L01: ajustar la brisa de fondo al tamaño del grafo recién pintado.
        self.canvas._apply_atmosphere_budget()
        # BETA1-G06: el scrubber refleja el calendario actual y se muestra
        # sobre el lienzo concéntrico (se oculta con él en la vista cronológica).
        self._sync_time_bar()
        self._time_bar.setVisible(True)
        self._position_time_bar()
        _b44trace(
            "widget_refresh_after_set_graph "
            f"canvas_layout={self.canvas._layout_mode_active!r} canvas_visible={self.canvas.isVisible()} empty_visible={self.empty.isVisible()} "
            f"ring_items={len(self.canvas._ring_items)} ring_visuals={len(self.canvas._ring_visuals)} nodes_drawn={len(self.canvas._nodes)}"
        )

    def set_layout_mode(self, layout_mode: str):
        requested = layout_mode
        if layout_mode not in {"free", "layered", "concentric_rings"}:
            layout_mode = "free"
        _b44trace(
            "widget_set_layout_mode "
            f"requested={requested!r} normalized={layout_mode!r} previous={self._layout_mode!r} "
            f"ctx_previous={getattr(self.ctx, 'creation_layout_mode', '')!r}"
        )
        self._layout_mode = layout_mode
        self._layer_mode = layout_mode == "layered"
        self.ctx.creation_layout_mode = layout_mode
        if layout_mode != "concentric_rings":
            self.ctx.creation_focused_ring_id = ""
            self.canvas.clear_ring_focus()
        self.ctx.save_preferences()
        self.refresh()

    def set_worldbuilding_active(self, active: bool):
        # Compatibility with existing B36 toolbar: this toggles the layered bands
        # view, not the project worldbuilding feature flag.
        self.set_layout_mode("layered" if active else "free")

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
