"""PlayView: modo Play inmersivo de la Creación Cronológica (BETA2-PLAY).

La historia se recorre hito a hito como una experiencia: cada hito es una
«escena» a pantalla completa — era + año + título + retratos de las entidades
afectadas + descripción. La vista es hermana de Mapa/Cronología/Foco y se
conmuta con ``set_active_view("play")``.

Política de capa: PlayView NO habla con servicios. El workspace le inyecta
escenas (dicts deterministas de ``ChronologyWalkService.step_scene``) y los
resultados del análisis IA, y recibe señales (salir, continuar, detener…).
Sin QGraphicsEffect (regla del repo): los estados se expresan con contraste,
bordes y color, nunca con efectos de sombra/opacidad.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets import portrait_cache
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_SOFT,
    GOLD_TINT,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE_SOFT,
    RADIUS_LG,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SURFACE_HI,
    SURFACE_PALE,
    TYPE_BODY_PX,
    TYPE_CAPTION_PX,
    TYPE_OVERLINE_PX,
    BusyIndicator,
    ElidedLabel,
)
from hosts.DesktopHostPySide.widgets.play.play_epilogue import PlayEpilogueCard
from packages.application.portrait_crop import parse_crop

# Tinta fría para la escena congelada (problema duro): marco y rótulos.
_FROST_INK = "#5C7A8A"
_FROST_LINE = "#9FB6C2"

_PORTRAIT_PX = 72
_CARD_MAX_W = 720


def _overline(text: str, color: str = INK_MUTED) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {color}; font-size: {TYPE_OVERLINE_PX}px; font-weight: 700; "
        "letter-spacing: 2px; background: transparent;"
    )
    return label


class _PortraitChip(QWidget):
    """Retrato circular de una entidad afectada + nombre debajo.

    Sin imagen → inicial sobre disco pergamino (mismo lenguaje que el Foco).
    Con ``on_remove``, el menú contextual permite quitarla del hito (PLAY-06).
    """

    def __init__(self, name: str, pixmap=None, parent=None, on_remove=None):
        super().__init__(parent)
        self._on_remove = on_remove
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        disc = QLabel(self)
        disc.setFixedSize(_PORTRAIT_PX, _PORTRAIT_PX)
        disc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if pixmap is not None:
            disc.setPixmap(
                pixmap.scaled(
                    _PORTRAIT_PX,
                    _PORTRAIT_PX,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            disc.setStyleSheet(
                f"border: 2px solid {GOLD_SOFT}; border-radius: {_PORTRAIT_PX // 2}px;"
            )
        else:
            initial = (name or "?").strip()[:1].upper() or "?"
            disc.setText(initial)
            disc.setStyleSheet(
                f"background: {GOLD_TINT}; color: {INK_STRONG}; "
                f"border: 2px solid {GOLD_SOFT}; border-radius: {_PORTRAIT_PX // 2}px; "
                "font-family: Georgia, serif; font-size: 26px; font-weight: 700;"
            )
        disc.setScaledContents(pixmap is not None)
        column.addWidget(disc, 0, Qt.AlignmentFlag.AlignHCenter)
        caption = ElidedLabel(name)
        caption.setMaximumWidth(_PORTRAIT_PX + 24)
        caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        caption.setStyleSheet(
            f"color: {INK_SOFT}; font-size: {TYPE_CAPTION_PX}px; background: transparent;"
        )
        column.addWidget(caption, 0, Qt.AlignmentFlag.AlignHCenter)

    def contextMenuEvent(self, event):  # noqa: N802 (firma Qt)
        if self._on_remove is None:
            return
        menu = QMenu(self)
        menu.addAction("Quitar del hito", self._on_remove)
        menu.popup(event.globalPos())


class PlayView(QWidget):
    """Escena inmersiva del recorrido cronológico (una por hito)."""

    exitRequested = Signal()
    continueRequested = Signal()
    stopRequested = Signal()
    # PLAY-06: (milestone_id, patch) — la escena es editable; el canon lo
    # escribe el workspace vía CausalMilestoneController (nunca la vista).
    editCommitted = Signal(str, dict)
    # PLAY-07: aplazar los problemas del hito / aplicar candidatos aceptados.
    deferRequested = Signal()
    applyRequested = Signal(list)  # [{"candidate_id": str}]
    # PLAY-12: relanzar el análisis del paso (descarta el intento en vuelo).
    retryRequested = Signal()

    def __init__(
        self,
        project_provider: Callable[[], Any] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._project_provider = project_provider
        self._assets_root = None
        self._scene: dict[str, Any] = {}
        self._frozen = False
        self._busy = False
        self._analyzed = False
        # PLAY-05: desvíos causales — pila efímera (no se persiste) + proveedor
        # de escenas inyectado por el workspace, y análisis cacheado del hito
        # actual para reponerlo al volver del desvío.
        self._scene_getter: Callable[[str | None], dict | None] | None = None
        self._detour_stack: list[str] = []
        self._cached_analysis: dict[str, Any] | None = None
        self._last_analysis: dict[str, Any] | None = None
        self.cause_chips: list[QPushButton] = []
        self.consequence_chips: list[QPushButton] = []
        self._change_checks: list[tuple[QCheckBox, str]] = []
        self._link_popover = None  # PLAY-14: referencia viva del popover
        # PLAY-17: revisión de propuestas — descriptores por candidato, factory
        # opaco de preview (lo inyecta el workspace con sus controllers) y las
        # ediciones del usuario capturadas por candidato antes de aplicar.
        self._change_descriptors: dict[str, dict[str, Any]] = {}
        self._review_edits: dict[str, dict[str, Any]] = {}
        self._preview_factory: Callable[[dict], tuple[Any, Callable[[], dict]]] | None = None
        self._review_cid: str = ""
        self._review_payload_getter: Callable[[], dict] | None = None
        self.setStyleSheet(f"PlayView {{ background: {SURFACE_PALE}; }}")
        self.setAutoFillBackground(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
        root.setSpacing(SPACE_MD)

        # ── cabecera: salir · progreso ─────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(SPACE_MD)
        self.exit_btn = QPushButton("← Salir del recorrido")
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {LINE_SOFT}; "
            f"border-radius: 14px; color: {INK_SOFT}; padding: 6px 14px; }} "
            f"QPushButton:hover {{ background: {GOLD_TINT}; color: {INK_STRONG}; }}"
        )
        self.exit_btn.clicked.connect(self.exitRequested.emit)
        header.addWidget(self.exit_btn)
        # PLAY-05: migas del desvío causal (visible solo en modo «visita»).
        self.back_btn = QPushButton("↩ Volver al recorrido")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setVisible(False)
        self.back_btn.setStyleSheet(
            f"QPushButton {{ background: {GOLD_TINT}; border: 1px solid {GOLD_SOFT}; "
            f"border-radius: 14px; color: {INK_STRONG}; padding: 6px 14px; font-weight: 700; }}"
        )
        self.back_btn.clicked.connect(self._return_to_walk)
        header.addWidget(self.back_btn)
        header.addStretch(1)
        self.progress_label = _overline("")
        header.addWidget(self.progress_label)
        root.addLayout(header)

        root.addStretch(1)

        # ── tarjeta de escena ──────────────────────────────────────────
        card_row = QHBoxLayout()
        card_row.addStretch(1)
        self.scene_card = QFrame(self)
        self.scene_card.setMaximumWidth(_CARD_MAX_W)
        self.scene_card.setMinimumWidth(420)
        self._apply_card_style(frozen=False)
        card = QVBoxLayout(self.scene_card)
        card.setContentsMargins(SPACE_LG * 2, SPACE_LG * 2, SPACE_LG * 2, SPACE_LG * 2)
        card.setSpacing(SPACE_MD)

        self.era_label = _overline("")
        card.addWidget(self.era_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.year_label = QLabel("")
        self.year_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.year_label.setStyleSheet(
            f"color: {GOLD_SOFT}; font-family: Georgia, serif; font-size: 34px; "
            "font-weight: 700; background: transparent;"
        )
        card.addWidget(self.year_label)
        self.year_edit = QLineEdit()
        self.year_edit.setVisible(False)
        self.year_edit.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.year_edit.setPlaceholderText("Año (vacío = por datar)")
        self.year_edit.editingFinished.connect(lambda: self._commit_edit("year"))
        card.addWidget(self.year_edit)

        self.title_label = QLabel("")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.title_label.setStyleSheet(
            f"color: {INK_STRONG}; font-family: Georgia, serif; font-size: 26px; "
            "font-weight: 700; background: transparent;"
        )
        card.addWidget(self.title_label)
        self.title_edit = QLineEdit()
        self.title_edit.setVisible(False)
        self.title_edit.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.title_edit.setStyleSheet("font-family: Georgia, serif; font-size: 20px;")
        self.title_edit.editingFinished.connect(lambda: self._commit_edit("title"))
        card.addWidget(self.title_edit)

        self.portraits_row = QWidget(self.scene_card)
        portraits_layout = QHBoxLayout(self.portraits_row)
        portraits_layout.setContentsMargins(0, SPACE_SM, 0, SPACE_SM)
        portraits_layout.setSpacing(SPACE_MD)
        portraits_layout.addStretch(1)
        portraits_layout.addStretch(1)
        card.addWidget(self.portraits_row)

        # PLAY-06: vincular otra entidad al hito desde la propia escena.
        self.link_entity_btn = QPushButton("+ Vincular entidad")
        self.link_entity_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link_entity_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px dashed {GOLD_SOFT}; "
            f"border-radius: 12px; color: {INK_MUTED}; padding: 4px 12px; "
            f"font-size: {TYPE_CAPTION_PX + 1}px; }} "
            f"QPushButton:hover {{ color: {INK_STRONG}; background: {GOLD_TINT}; }}"
        )
        self.link_entity_btn.clicked.connect(self._open_link_popover)
        card.addWidget(self.link_entity_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self.desc_label = QLabel("")
        self.desc_label.setWordWrap(True)
        self.desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.desc_label.setStyleSheet(
            f"color: {INK_SOFT}; font-size: {TYPE_BODY_PX + 1}px; "
            "background: transparent;"
        )
        self.desc_scroll = QScrollArea()
        self.desc_scroll.setWidgetResizable(True)
        self.desc_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.desc_scroll.setStyleSheet("background: transparent;")
        self.desc_scroll.setWidget(self.desc_label)
        self.desc_scroll.setMaximumHeight(220)
        card.addWidget(self.desc_scroll)
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setVisible(False)
        self.desc_edit.setMaximumHeight(220)
        self.desc_edit.installEventFilter(self)  # FocusOut = commit
        card.addWidget(self.desc_edit)

        # PLAY-06: clic sobre título/año/descripción = editar in situ.
        for editable in (self.title_label, self.year_label, self.desc_label):
            editable.installEventFilter(self)
            editable.setCursor(Qt.CursorShape.IBeamCursor)

        # PLAY-05: causas y consecuencias como enlaces navegables (desvíos).
        self.links_row = QWidget(self.scene_card)
        links_layout = QHBoxLayout(self.links_row)
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.setSpacing(SPACE_LG)
        self._causes_box = self._link_group(links_layout, "CAUSAS")
        self._consequences_box = self._link_group(links_layout, "CONSECUENCIAS")
        self.links_row.setVisible(False)
        card.addWidget(self.links_row)

        # Lectura editorial del paso (llega con el análisis IA).
        self.reading_overline = _overline("LECTURA EDITORIAL", GOLD_SOFT)
        self.reading_overline.setVisible(False)
        card.addWidget(self.reading_overline)
        self.reading_label = QLabel("")
        self.reading_label.setWordWrap(True)
        self.reading_label.setVisible(False)
        self.reading_label.setStyleSheet(
            f"color: {INK_SOFT}; font-size: {TYPE_BODY_PX}px; font-style: italic; "
            "background: transparent;"
        )
        card.addWidget(self.reading_label)

        # Incoherencias del hito (congelan la escena si son duras).
        self.issues_frame = QFrame(self.scene_card)
        self.issues_frame.setVisible(False)
        self.issues_frame.setStyleSheet(
            f"QFrame {{ background: transparent; border: 1px solid {_FROST_LINE}; "
            "border-radius: 10px; } QLabel { border: none; }"
        )
        issues_box = QVBoxLayout(self.issues_frame)
        issues_box.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        issues_box.setSpacing(4)
        issues_box.addWidget(_overline("INCOHERENCIAS DETECTADAS", _FROST_INK))
        self._issues_box = issues_box
        card.addWidget(self.issues_frame)

        # PLAY-07: correcciones propuestas por la IA (candidatos del paso).
        self.changes_frame = QFrame(self.scene_card)
        self.changes_frame.setVisible(False)
        self.changes_frame.setStyleSheet(
            f"QFrame {{ background: transparent; border: 1px solid {GOLD_SOFT}; "
            "border-radius: 10px; } QLabel, QCheckBox { border: none; }"
        )
        changes_box = QVBoxLayout(self.changes_frame)
        changes_box.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM)
        changes_box.setSpacing(4)
        changes_box.addWidget(_overline("CORRECCIONES PROPUESTAS", GOLD_SOFT))
        self._changes_box = changes_box
        card.addWidget(self.changes_frame)

        # PLAY-07: acciones sobre el problema (corregir aplicando / aplazar).
        actions_row = QHBoxLayout()
        actions_row.setSpacing(SPACE_SM)
        actions_row.addStretch(1)
        self.defer_btn = QPushButton("Aplazar y continuar")
        self.defer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.defer_btn.setVisible(False)
        self.defer_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {_FROST_LINE}; "
            f"border-radius: 12px; color: {_FROST_INK}; padding: 5px 14px; }} "
            f"QPushButton:hover {{ background: {GOLD_TINT}; }}"
        )
        self.defer_btn.clicked.connect(self.deferRequested.emit)
        actions_row.addWidget(self.defer_btn)
        self.apply_btn = QPushButton("Aplicar seleccionadas")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.setVisible(False)
        self.apply_btn.setStyleSheet(
            f"QPushButton {{ background: {GOLD_TINT}; border: 1px solid {GOLD_SOFT}; "
            f"border-radius: 12px; color: {INK_STRONG}; padding: 5px 14px; font-weight: 700; }}"
        )
        self.apply_btn.clicked.connect(self._emit_apply)
        actions_row.addWidget(self.apply_btn)
        actions_row.addStretch(1)
        card.addLayout(actions_row)

        # Línea de estado (analizando / congelado / error) + indicador de
        # actividad (PLAY-11: el progreso del análisis debe ser inequívoco).
        status_row = QHBoxLayout()
        status_row.setSpacing(SPACE_SM)
        status_row.addStretch(1)
        self.busy_indicator = BusyIndicator(diameter=20, parent=self.scene_card)
        status_row.addWidget(self.busy_indicator, 0, Qt.AlignmentFlag.AlignVCenter)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.status_label.setStyleSheet(
            f"color: {INK_MUTED}; font-size: {TYPE_CAPTION_PX}px; background: transparent;"
        )
        status_row.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignVCenter)
        # PLAY-12: reintento visible cuando la IA tarda o falla.
        self.retry_btn = QPushButton("Reintentar")
        self.retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_btn.setVisible(False)
        self.retry_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {GOLD_SOFT}; "
            f"border-radius: 12px; color: {INK_STRONG}; padding: 4px 12px; "
            f"font-size: {TYPE_CAPTION_PX + 1}px; font-weight: 700; }} "
            f"QPushButton:hover {{ background: {GOLD_TINT}; }}"
        )
        self.retry_btn.clicked.connect(self.retryRequested.emit)
        status_row.addWidget(self.retry_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        status_row.addStretch(1)
        card.addLayout(status_row)

        card_row.addWidget(self.scene_card)
        # PLAY-09: el epílogo sustituye a la escena al terminar el recorrido.
        self.epilogue_card = PlayEpilogueCard(self)
        self.epilogue_card.setVisible(False)
        self.epilogue_card.closed.connect(self.exitRequested.emit)
        card_row.addWidget(self.epilogue_card)
        # PLAY-17: la revisión de una propuesta sustituye a la escena (mismo
        # patrón de swap que el epílogo); monta el panel de edición en preview.
        self.review_card = self._build_review_card()
        self.review_card.setVisible(False)
        card_row.addWidget(self.review_card)
        card_row.addStretch(1)
        root.addLayout(card_row)

        root.addStretch(1)

        # ── pie: detener · continuar ───────────────────────────────────
        footer = QHBoxLayout()
        footer.setSpacing(SPACE_MD)
        footer.addStretch(1)
        self.stop_btn = QPushButton("Detener recorrido")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {LINE_SOFT}; "
            f"border-radius: 14px; color: {INK_MUTED}; padding: 8px 16px; }} "
            f"QPushButton:hover {{ color: {INK_STRONG}; }}"
        )
        self.stop_btn.clicked.connect(self.stopRequested.emit)
        footer.addWidget(self.stop_btn)
        self.continue_btn = QPushButton("Continuar ▶")
        self.continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.continue_btn.setStyleSheet(
            f"QPushButton {{ background: {GOLD_TINT}; border: 1px solid {GOLD_SOFT}; "
            f"border-radius: 14px; color: {INK_STRONG}; font-weight: 700; "
            "padding: 8px 22px; } "
            f"QPushButton:disabled {{ background: transparent; color: {INK_MUTED}; }}"
        )
        self.continue_btn.setEnabled(False)  # se habilita al terminar el análisis del paso
        self.continue_btn.clicked.connect(self.continueRequested.emit)
        footer.addWidget(self.continue_btn)
        root.addLayout(footer)

    def _link_group(self, parent_layout: QHBoxLayout, caption: str) -> QVBoxLayout:
        group = QWidget(self.links_row)
        box = QVBoxLayout(group)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        box.addWidget(_overline(caption))
        parent_layout.addWidget(group, 1)
        return box

    # ── PLAY-17: tarjeta de revisión de propuestas ─────────────────────
    def _build_review_card(self) -> QFrame:
        card = QFrame(self)
        card.setMinimumWidth(460)
        card.setMaximumWidth(760)
        card.setStyleSheet(
            f"QFrame#reviewCard {{ background: {SURFACE_HI}; border: 1px solid {LINE_SOFT}; "
            f"border-radius: {RADIUS_LG}px; }}"
        )
        card.setObjectName("reviewCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
        box.setSpacing(SPACE_MD)
        self.review_title = _overline("REVISAR PROPUESTA", GOLD_SOFT)
        box.addWidget(self.review_title)
        self.review_scroll = QScrollArea(card)
        self.review_scroll.setWidgetResizable(True)
        self.review_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.review_scroll.setStyleSheet("background: transparent;")
        box.addWidget(self.review_scroll, 1)
        actions = QHBoxLayout()
        actions.setSpacing(SPACE_SM)
        self.review_reject_btn = QPushButton("Rechazar")
        self.review_reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.review_reject_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {LINE_SOFT}; "
            f"border-radius: 12px; color: {INK_MUTED}; padding: 6px 14px; }} "
            f"QPushButton:hover {{ color: {INK_STRONG}; }}"
        )
        self.review_reject_btn.clicked.connect(self._reject_review)
        actions.addWidget(self.review_reject_btn)
        actions.addStretch(1)
        self.review_accept_btn = QPushButton("Aceptar (con mis cambios)")
        self.review_accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.review_accept_btn.setStyleSheet(
            f"QPushButton {{ background: {GOLD_TINT}; border: 1px solid {GOLD_SOFT}; "
            f"border-radius: 12px; color: {INK_STRONG}; font-weight: 700; padding: 6px 16px; }}"
        )
        self.review_accept_btn.clicked.connect(self._accept_review)
        actions.addWidget(self.review_accept_btn)
        box.addLayout(actions)
        return card

    def set_preview_factory(
        self, factory: Callable[[dict], tuple[Any, Callable[[], dict]]] | None
    ) -> None:
        """Inyecta el constructor de preview (workspace → panel real + getter).

        ``factory(descriptor)`` devuelve ``(widget, get_payload)``: el panel de
        edición en modo preview y un callable que devuelve el diff editado.
        PlayView nunca conoce controllers ni services — solo el widget opaco.
        """
        self._preview_factory = factory

    def _open_review(self, cid: str) -> None:
        if self._busy or self.is_visiting or self._preview_factory is None:
            return
        descriptor = self._change_descriptors.get(cid)
        if descriptor is None:
            return
        built = self._preview_factory(descriptor)
        if not built:
            return
        widget, get_payload = built
        old = self.review_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self.review_scroll.setWidget(widget)
        self._review_cid = cid
        self._review_payload_getter = get_payload
        self.review_title.setText(
            f"REVISAR — {descriptor.get('header', 'Propuesta')}".upper()
        )
        self.scene_card.setVisible(False)
        self.review_card.setVisible(True)

    def _close_review(self) -> None:
        self.review_card.setVisible(False)
        self.scene_card.setVisible(True)
        old = self.review_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._review_cid = ""
        self._review_payload_getter = None

    def _accept_review(self) -> None:
        """Guarda el diff editado como edited_data del candidato y vuelve."""
        cid = self._review_cid
        if cid and self._review_payload_getter is not None:
            fields = dict(self._review_payload_getter() or {})
            # apply_step hace merge SHALLOW sobre proposed_data: edited_data debe
            # traer el edit_fields COMPLETO (diff contra canon), no un parcial.
            self._review_edits[cid] = {"edit_fields": fields}
            for check, check_cid in self._change_checks:
                if check_cid == cid:
                    check.setChecked(True)
        self._close_review()

    def _reject_review(self) -> None:
        """Descarta la propuesta: desmarca su casilla y vuelve a la escena."""
        cid = self._review_cid
        self._review_edits.pop(cid, None)
        for check, check_cid in self._change_checks:
            if check_cid == cid:
                check.setChecked(False)
        self._close_review()

    # ── estilo ─────────────────────────────────────────────────────────
    def _apply_card_style(self, *, frozen: bool) -> None:
        border = _FROST_LINE if frozen else LINE_SOFT
        width = 2 if frozen else 1
        self.scene_card.setStyleSheet(
            f"QFrame {{ background: {SURFACE_HI}; border: {width}px solid {border}; "
            f"border-radius: {RADIUS_LG}px; }} QLabel {{ border: none; }}"
        )

    # ── escena ─────────────────────────────────────────────────────────
    def set_assets_root(self, assets_root) -> None:
        self._assets_root = assets_root

    def current_scene(self) -> dict[str, Any]:
        return dict(self._scene)

    def show_epilogue(self, report: Any, project: Any) -> None:
        """PLAY-09: cierre inmersivo — el informe sustituye a la escena."""
        self.scene_card.setVisible(False)
        self.back_btn.setVisible(False)
        self.continue_btn.setVisible(False)
        self.stop_btn.setVisible(False)
        self.progress_label.setText("FIN DEL RECORRIDO")
        self.epilogue_card.show_report(report, project)
        self.epilogue_card.setVisible(True)

    def show_scene(self, scene: dict[str, Any]) -> None:
        """Renderiza la escena determinista de un hito (sin IA)."""
        self._scene = dict(scene or {})
        # PLAY-09: una escena nueva devuelve la vista al modo recorrido.
        self.epilogue_card.setVisible(False)
        # PLAY-17: cierra cualquier revisión abierta al cambiar de escena.
        if self.review_card.isVisible():
            self._close_review()
        self.scene_card.setVisible(True)
        self.continue_btn.setVisible(True)
        self.stop_btn.setVisible(True)
        hito = dict(self._scene.get("hito") or {})
        era_name = str(self._scene.get("era_name") or "")
        self.era_label.setText(era_name.upper() if era_name else "SIN ERA")
        year = hito.get("year")
        self.year_label.setText("Por datar" if year is None else f"Año {year}")
        self.title_label.setText(str(hito.get("title") or "(sin título)"))
        self.desc_label.setText(str(hito.get("description") or ""))
        position = self._scene.get("position")
        total = self._scene.get("total")
        visiting = self._scene.get("is_current") is False
        progress = f"HITO {position} DE {total}" if position and total else ""
        if visiting and progress:
            progress = f"VISITA — {progress}"
        self.progress_label.setText(progress)
        self.back_btn.setVisible(bool(self._detour_stack))
        self._rebuild_portraits(list(hito.get("affected_entity_ids") or []))
        self._rebuild_links(
            list(self._scene.get("causes") or []),
            list(self._scene.get("consequences") or []),
        )
        # Nueva escena: estado limpio hasta que llegue su análisis.
        self._busy = False
        self._analyzed = False
        # Editores inline abiertos se descartan (la escena manda).
        self.title_edit.setVisible(False)
        self.title_label.setVisible(True)
        self.year_edit.setVisible(False)
        self.year_label.setVisible(True)
        self.desc_edit.setVisible(False)
        self.desc_scroll.setVisible(True)
        self.link_entity_btn.setVisible(self._scene.get("is_current") is not False)
        self.reading_overline.setVisible(False)
        self.reading_label.setVisible(False)
        self.reading_label.setText("")
        self._clear_issues()
        self.set_changes([])
        self.defer_btn.setVisible(False)
        self.retry_btn.setVisible(False)
        self.status_label.setVisible(False)
        self.status_label.setText("")
        self._set_frozen(False)
        self._update_actions()

    def _rebuild_portraits(self, entity_ids: list[str]) -> None:
        layout = self.portraits_row.layout()
        # Vaciar conservando los stretch de los extremos.
        while layout.count() > 2:
            item = layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        project = self._project_provider() if self._project_provider else None
        insert_at = 1
        for entity_id in entity_ids:
            entity = project.entity_by_id(entity_id) if project is not None else None
            if entity is None:
                continue
            name = str(getattr(entity, "name", "") or "")
            pixmap = self._portrait_pixmap(entity)
            chip = _PortraitChip(
                name, pixmap, on_remove=lambda eid=entity_id: self._unlink_entity(eid)
            )
            layout.insertWidget(insert_at, chip)
            insert_at += 1

    # ── PLAY-06: edición inline (canon SIEMPRE vía workspace/servicio) ──
    def eventFilter(self, obj, event):  # noqa: N802 (firma Qt)
        if event.type() == QEvent.Type.MouseButtonPress:
            if obj is self.title_label:
                self._start_edit("title")
            elif obj is self.year_label:
                self._start_edit("year")
            elif obj is self.desc_label:
                self._start_edit("description")
        elif event.type() == QEvent.Type.FocusOut and obj is self.desc_edit:
            self._commit_edit("description")
        return super().eventFilter(obj, event)

    def _current_milestone_id(self) -> str:
        return str((self._scene.get("hito") or {}).get("id") or "")

    def _start_edit(self, field: str) -> None:
        """Convierte el dato en editor in situ. En visita o análisis, no."""
        if self._busy or self.is_visiting or not self._current_milestone_id():
            return
        hito = dict(self._scene.get("hito") or {})
        if field == "title":
            self.title_edit.setText(str(hito.get("title") or ""))
            self.title_label.setVisible(False)
            self.title_edit.setVisible(True)
            self.title_edit.setFocus()
            self.title_edit.selectAll()
        elif field == "year":
            year = hito.get("year")
            self.year_edit.setText("" if year is None else str(year))
            self.year_label.setVisible(False)
            self.year_edit.setVisible(True)
            self.year_edit.setFocus()
            self.year_edit.selectAll()
        elif field == "description":
            self.desc_edit.setPlainText(str(hito.get("description") or ""))
            self.desc_scroll.setVisible(False)
            self.desc_edit.setVisible(True)
            self.desc_edit.setFocus()

    def _commit_edit(self, field: str) -> None:
        mid = self._current_milestone_id()
        if not mid:
            return
        patch: dict[str, Any] = {}
        if field == "title" and not self.title_edit.isHidden():
            self.title_edit.setVisible(False)
            self.title_label.setVisible(True)
            text = self.title_edit.text().strip()
            if text and text != str((self._scene.get("hito") or {}).get("title") or ""):
                patch["title"] = text
                self.title_label.setText(text)
        elif field == "year" and not self.year_edit.isHidden():
            self.year_edit.setVisible(False)
            self.year_label.setVisible(True)
            raw = self.year_edit.text().strip()
            old = (self._scene.get("hito") or {}).get("year")
            if raw == "":
                if old is not None:
                    patch["year"] = None
                    self.year_label.setText("Por datar")
            else:
                try:
                    year = int(raw)
                except ValueError:
                    return  # entrada inválida: se descarta sin tocar canon
                if year != old:
                    patch["year"] = year
                    self.year_label.setText(f"Año {year}")
        elif field == "description" and not self.desc_edit.isHidden():
            self.desc_edit.setVisible(False)
            self.desc_scroll.setVisible(True)
            text = self.desc_edit.toPlainText().strip()
            if text != str((self._scene.get("hito") or {}).get("description") or ""):
                patch["description"] = text
                self.desc_label.setText(text)
        if patch:
            hito = dict(self._scene.get("hito") or {})
            hito.update(patch)
            self._scene["hito"] = hito  # eco local; el refresh del canon manda
            self.editCommitted.emit(mid, patch)

    def _show_gate_hint(self, message: str) -> None:
        """PLAY-14: por qué una acción no está disponible — nunca silencio."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            f"color: {INK_MUTED}; font-size: {TYPE_CAPTION_PX}px; background: transparent;"
        )
        self.status_label.setVisible(True)

    def _open_link_popover(self) -> None:
        if self._busy:
            self._show_gate_hint("Espera a que termine el análisis para vincular entidades")
            return
        if self.is_visiting:
            self._show_gate_hint("Termina la visita para editar este hito")
            return
        if self._project_provider is None:
            return
        project = self._project_provider()
        if project is None:
            return
        from hosts.DesktopHostPySide.widgets.foco.foco_popover import EntitySearchPopover

        previous = self._link_popover
        if previous is not None:
            try:
                previous.close()
                previous.deleteLater()
            except Exception:  # noqa: BLE001 — cerrar el previo es mejor-esfuerzo
                pass
        affected = set((self._scene.get("hito") or {}).get("affected_entity_ids") or [])
        # PLAY-14: referencia de INSTANCIA obligatoria — un Qt.Popup sin
        # referencia Python viva se recolecta y «no funciona» (patrón FocoView).
        self._link_popover = EntitySearchPopover(
            entities_provider=lambda: list(getattr(project, "entities", []) or []),
            on_pick=self._link_entity,
            exclude_ids=affected,
            placeholder="Vincular entidad al hito…",
            parent=self,
        )
        # Ancla centrada → posicionamiento centrado (open_below es para anclas
        # pegadas al borde derecho y desplazaba el popover fuera de sitio).
        self._link_popover.open_below_top_center(self.link_entity_btn)

    def _link_entity(self, entity_id: str) -> None:
        mid = self._current_milestone_id()
        if not mid or not entity_id:
            return
        affected = list((self._scene.get("hito") or {}).get("affected_entity_ids") or [])
        if entity_id in affected:
            return
        affected.append(entity_id)
        self.editCommitted.emit(mid, {"affected_entity_ids": affected})

    def _unlink_entity(self, entity_id: str) -> None:
        mid = self._current_milestone_id()
        if not mid:
            return
        affected = [
            eid
            for eid in (self._scene.get("hito") or {}).get("affected_entity_ids") or []
            if eid != entity_id
        ]
        self.editCommitted.emit(mid, {"affected_entity_ids": affected})

    # ── PLAY-05: desvíos causales (pila cliente, sesión intacta) ────────
    def set_scene_getter(self, getter: Callable[[str | None], dict | None]) -> None:
        """Inyecta el proveedor de escenas (workspace → ``ctrl.scene``)."""
        self._scene_getter = getter

    def _rebuild_links(self, causes: list[dict], consequences: list[dict]) -> None:
        self.cause_chips = self._fill_link_box(self._causes_box, causes)
        self.consequence_chips = self._fill_link_box(self._consequences_box, consequences)
        self.links_row.setVisible(bool(self.cause_chips or self.consequence_chips))

    def _fill_link_box(self, box: QVBoxLayout, briefs: list[dict]) -> list[QPushButton]:
        while box.count() > 1:  # conserva el overline
            item = box.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        chips: list[QPushButton] = []
        for brief in briefs:
            title = str(brief.get("title") or "(sin título)")
            year = brief.get("year")
            text = f"{title} · {year}" if year is not None else title
            chip = QPushButton(text)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 1px solid {GOLD_SOFT}; "
                f"border-radius: 12px; color: {INK_SOFT}; padding: 4px 12px; "
                f"font-size: {TYPE_CAPTION_PX + 1}px; text-align: left; }} "
                f"QPushButton:hover {{ background: {GOLD_TINT}; color: {INK_STRONG}; }}"
            )
            mid = str(brief.get("id") or "")
            chip.clicked.connect(lambda _=False, m=mid: self._open_detour(m))
            box.addWidget(chip)
            chips.append(chip)
        return chips

    def _open_detour(self, milestone_id: str) -> None:
        """Visita la escena de un hito vinculado SIN tocar la sesión."""
        if self._busy or self._scene_getter is None or not milestone_id:
            return
        scene = self._scene_getter(milestone_id)
        if not scene:
            return
        if scene.get("is_current"):
            self._return_to_walk()
            return
        if not self._detour_stack and self._analyzed:
            # Guarda el análisis del hito actual para reponerlo al volver.
            self._cached_analysis = self._last_analysis
        current_id = str((self._scene.get("hito") or {}).get("id") or "")
        self._detour_stack.append(current_id)
        self.show_scene(scene)

    def _return_to_walk(self) -> None:
        """Vuelve al hito actual del recorrido (pop de toda la pila)."""
        if self._scene_getter is None:
            return
        self._detour_stack.clear()
        scene = self._scene_getter(None)
        if scene:
            self.show_scene(scene)
        cached = self._cached_analysis
        if cached is not None:
            walk = dict(cached.get("walk") or {})
            current_id = str((self._scene.get("hito") or {}).get("id") or "")
            if str(walk.get("milestone_id") or "") == current_id:
                self.show_analysis(cached)

    @property
    def is_visiting(self) -> bool:
        return bool(self._detour_stack)

    def _portrait_pixmap(self, entity: Any):
        meta = dict(getattr(entity, "custom_metadata", {}) or {})
        stored = str(meta.get("_image_path", "") or "")
        if not stored:
            return None
        resolved = portrait_cache.resolve_stored(self._assets_root, stored)
        raw_crop = meta.get("_image_crop")
        crop = parse_crop(raw_crop).as_tuple() if raw_crop else None
        return portrait_cache.portrait_pixmap(resolved, crop, _PORTRAIT_PX)

    # ── ciclo del paso: analizando → análisis → (congelado | continuar) ──
    def set_busy(self, busy: bool, message: str = "La IA está leyendo este hito…") -> None:
        self._busy = bool(busy)
        if self._busy:
            self.retry_btn.setVisible(False)  # PLAY-12: intento fresco
            # PLAY-11: estado prominente — texto a tamaño cuerpo, no caption.
            self.status_label.setText(message)
            self.status_label.setStyleSheet(
                f"color: {GOLD_SOFT}; font-size: {TYPE_BODY_PX}px; font-weight: 700; "
                "background: transparent;"
            )
            self.status_label.setVisible(True)
        else:
            self.status_label.setVisible(False)
            self.status_label.setText("")
        self._update_actions()

    def show_analysis(self, result: dict[str, Any]) -> None:
        """Pliega en la escena el resultado del análisis del paso (dict walk)."""
        self._busy = False
        self._analyzed = True
        self.retry_btn.setVisible(False)  # PLAY-12: el análisis llegó — sin aviso
        result = dict(result or {})
        self._last_analysis = result
        self._cached_analysis = None  # un análisis fresco supersede al cacheado
        walk = dict(result.get("walk") or {})
        payload = dict(result.get("model_payload") or {})
        reading = str(result.get("summary") or payload.get("summary") or "").strip()
        self.reading_overline.setVisible(bool(reading))
        self.reading_label.setVisible(bool(reading))
        self.reading_label.setText(reading)
        milestone_id = str(walk.get("milestone_id") or "")
        problems = [
            dict(p)
            for p in (walk.get("open_problems") or [])
            if str(p.get("milestone_id") or "") == milestone_id
        ]
        self._populate_issues(problems)
        stopped = bool(walk.get("stopped"))
        self._set_frozen(stopped)
        self.defer_btn.setVisible(stopped)  # PLAY-07: aplazar solo ante parada dura
        if stopped:
            reason = str(walk.get("stop_reason") or "Un problema duro detiene el recorrido")
            self.status_label.setText(f"Escena congelada — {reason}")
            self.status_label.setStyleSheet(
                f"color: {_FROST_INK}; font-size: {TYPE_CAPTION_PX}px; font-weight: 700; "
                "background: transparent;"
            )
            self.status_label.setVisible(True)
        else:
            self.status_label.setVisible(False)
        self._update_actions()

    def show_waiting_notice(self, message: str) -> None:
        """PLAY-12: la IA tarda — aviso informativo SIN cancelar nada.

        El análisis sigue en vuelo (busy intacto); si llega, ``show_analysis``
        limpia el aviso. «Reintentar» queda visible para quien no quiera esperar.
        """
        self.status_label.setText(str(message))
        self.status_label.setStyleSheet(
            f"color: {INK_SOFT}; font-size: {TYPE_BODY_PX}px; background: transparent;"
        )
        self.status_label.setVisible(True)
        self.retry_btn.setVisible(True)

    def show_error(self, message: str) -> None:
        """Fallo del análisis (p. ej. sin proveedor): la escena sigue legible."""
        self._busy = False
        self._analyzed = False
        self.status_label.setText(str(message))
        self.status_label.setStyleSheet(
            "color: #A3552E; font-size: 11px; font-weight: 700; background: transparent;"
        )
        self.status_label.setVisible(True)
        self.retry_btn.setVisible(True)  # PLAY-12: el fallo siempre ofrece reintento
        self._update_actions()

    # ── PLAY-07: candidatos del paso + aplazar ──────────────────────────
    def set_changes(self, changes: list[dict[str, Any]]) -> None:
        """Tarjetas aceptar/rechazar de las correcciones propuestas del paso.

        Cada propuesta de EDICIÓN revisable (patch multi-campo) gana un botón
        «Revisar» que abre el preview del panel real (PLAY-17).
        """
        box = self._changes_box
        while box.count() > 1:  # conserva el overline
            item = box.takeAt(1)
            layout_item = item.layout()
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif layout_item is not None:
                self._clear_layout(layout_item)
        self._change_checks: list[tuple[QCheckBox, str]] = []
        self._change_descriptors = {}
        self._review_edits = {}
        for change in changes or []:
            cid = str(change.get("candidate_id") or "")
            if not cid:
                continue
            self._change_descriptors[cid] = dict(change)
            row = QHBoxLayout()
            row.setSpacing(SPACE_SM)
            check = QCheckBox(str(change.get("header") or "Cambio propuesto"))
            check.setChecked(True)
            check.setStyleSheet(
                f"color: {INK_STRONG}; font-size: {TYPE_CAPTION_PX + 1}px; "
                "background: transparent;"
            )
            row.addWidget(check, 1)
            if change.get("reviewable"):
                review = QPushButton("Revisar")
                review.setCursor(Qt.CursorShape.PointingHandCursor)
                review.setStyleSheet(
                    f"QPushButton {{ background: transparent; border: 1px solid {GOLD_SOFT}; "
                    f"border-radius: 10px; color: {INK_STRONG}; padding: 2px 10px; "
                    f"font-size: {TYPE_CAPTION_PX}px; }} "
                    f"QPushButton:hover {{ background: {GOLD_TINT}; }}"
                )
                review.clicked.connect(lambda _=False, c=cid: self._open_review(c))
                row.addWidget(review)
            box.addLayout(row)
            self._change_checks.append((check, cid))
        has_changes = bool(self._change_checks)
        self.changes_frame.setVisible(has_changes)
        self.apply_btn.setVisible(has_changes)

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _emit_apply(self) -> None:
        items = []
        for check, cid in self._change_checks:
            if not check.isChecked():
                continue
            item = {"candidate_id": cid}
            # PLAY-17: si el usuario revisó/editó la propuesta, su diff viaja
            # como edited_data por el mismo bloque atómico (apply_step).
            if cid in self._review_edits:
                item["edited_data"] = self._review_edits[cid]
            items.append(item)
        if items:
            self.applyRequested.emit(items)

    def mark_deferred(self) -> None:
        """El usuario aplazó: descongela dejando marca visible del aplazado."""
        self._frozen = False
        self._analyzed = True
        self._apply_card_style(frozen=False)
        self.defer_btn.setVisible(False)
        walk = dict((self._last_analysis or {}).get("walk") or {})
        mid = self._current_milestone_id()
        problems = [
            {**dict(p), "deferred": True}
            for p in (walk.get("open_problems") or [])
            if str(p.get("milestone_id") or "") == mid
        ]
        self._populate_issues(problems)
        self.status_label.setText("Incoherencias aplazadas — reaparecerán en el informe final")
        self.status_label.setStyleSheet(
            f"color: {INK_MUTED}; font-size: {TYPE_CAPTION_PX}px; background: transparent;"
        )
        self.status_label.setVisible(True)
        self._update_actions()

    def mark_applied(self, count: int) -> None:
        """Se aplicaron correcciones: el paso queda resuelto y se puede seguir."""
        self._frozen = False
        self._analyzed = True
        self._apply_card_style(frozen=False)
        self.defer_btn.setVisible(False)
        self._clear_issues()
        self.set_changes([])
        self.status_label.setText(f"{count} cambio(s) aplicado(s) al canon")
        self.status_label.setStyleSheet(
            f"color: {GOLD_SOFT}; font-size: {TYPE_CAPTION_PX}px; font-weight: 700; "
            "background: transparent;"
        )
        self.status_label.setVisible(True)
        self._update_actions()

    def _clear_issues(self) -> None:
        box = self._issues_box
        while box.count() > 1:  # conserva el overline
            item = box.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.issues_frame.setVisible(False)

    def _populate_issues(self, problems: list[dict[str, Any]]) -> None:
        self._clear_issues()
        if not problems:
            return
        for problem in problems:
            title = str(problem.get("title") or problem.get("kind") or "Incoherencia")
            if problem.get("deferred"):
                title += "  (aplazada)"
            entry = QLabel(f"<b>{title}</b><br/>{problem.get('description') or ''}")
            entry.setWordWrap(True)
            entry.setStyleSheet(
                f"color: {INK_STRONG}; font-size: {TYPE_CAPTION_PX + 1}px; "
                "background: transparent;"
            )
            self._issues_box.addWidget(entry)
        self.issues_frame.setVisible(True)

    def _set_frozen(self, frozen: bool) -> None:
        self._frozen = bool(frozen)
        self._apply_card_style(frozen=self._frozen)

    def _update_actions(self) -> None:
        # Continuar solo con un análisis limpio del paso; congelado o en
        # análisis, el avance espera (Aplazar/Corregir llegan en PLAY-07).
        self.continue_btn.setEnabled(self._analyzed and not self._frozen and not self._busy)
        self.stop_btn.setEnabled(not self._busy)
        # PLAY-11: el ciclo entero se refleja en el indicador y el botón —
        # imposible no ver que la IA trabaja; imposible un giro huérfano.
        self.continue_btn.setText("Analizando…" if self._busy else "Continuar ▶")
        if self._busy:
            self.busy_indicator.start()
        else:
            self.busy_indicator.stop()

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    @property
    def is_busy(self) -> bool:
        return self._busy


__all__ = ["PlayView"]
