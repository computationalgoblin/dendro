"""BaseSlideDrawer — lógica compartida del cajón deslizante (izquierdo/derecho).

`RightDrawer` y `LeftDrawer` son espejos: misma animación de ancho, mismo ciclo
abrir → cerrar → limpiar contenido. Antes vivían como dos copias casi idénticas
que se desincronizaban: un arreglo de robustez aplicado a uno NO llegaba al otro
y la UI se descolocaba (p.ej. el cajón izquierdo "desaparecía de golpe" al cerrar
porque solo el derecho animaba el suelo de ancho). Toda esa mecánica vive AQUÍ
una sola vez; las subclases solo aportan el estilo de su lado.

Contratos que dependen de los atributos internos (tests UX09/UXFB): `_animation`
(QPropertyAnimation viva durante/tras abrir-cerrar), `_target_width`,
`maximumWidth()` que alcanza el objetivo / 0, y curva+duración por dirección.
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    EASING_ENTER,
    MOTION_BASE,
    MOTION_SLOW,
    install_wheel_guard,
)
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_alive


class BaseSlideDrawer(QFrame):
    """Cajón deslizante reutilizable. No instanciar directamente: usar
    `LeftDrawer` / `RightDrawer`, que definen el estilo del lado."""

    # ── Parámetros de subclase (ancho/cabecera) ──────────────────────────────
    OBJECT_NAME = "slideDrawer"
    # Lado al que se ancla el cajón en modo OVERLAY ("right" → crece desde el
    # borde derecho; "left" → desde el izquierdo). Lo fija cada subclase.
    ANCHOR = "right"
    WIDTH_FRACTION = 0.44
    WIDTH_MIN = 520
    WIDTH_MAX = 680
    HEADER_HEIGHT = 48
    HEADER_MARGINS = (16, 7, 12, 7)
    CLOSE_ICON_COLOR = "#6F6A42"
    CLOSE_ICON_SIZE = 13

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName(self.OBJECT_NAME)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._parent_ref = parent
        self._target_width = self._compute_target_width()
        self.setMinimumWidth(0)
        self.setMaximumWidth(0)
        # OVERLAY: el cajón flota sobre el área central (no vive en un layout) y
        # se posiciona por geometría. `_area_provider`, inyectado por MainWindow,
        # devuelve el rectángulo (coords del padre) que el cajón puede cubrir —el
        # área del grafo MENOS la command bar—; sin él, cae al rect del padre.
        # El alto lo fija `_apply_overlay_geometry`, NO `setFixedHeight` (fijarlo
        # chocaría con el alto reservado del rect y taparía la command bar).
        self._area_provider = None  # type: ignore[var-annotated]
        self.setStyleSheet(self._frame_style())

        # Layout raíz: cabecera + contenido desplazable
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        # Cabecera (con padre explícito: el guard estático lo exige)
        header = QFrame(self)
        header.setStyleSheet(self._header_style())
        header.setFixedHeight(self.HEADER_HEIGHT)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(*self.HEADER_MARGINS)

        self._title = QLabel("")
        self._title.setStyleSheet(self._title_style())
        h_layout.addWidget(self._title)
        h_layout.addStretch()

        self._close_btn = QPushButton()
        self._close_btn.setFixedSize(30, 30)
        self._close_btn.setStyleSheet(self._close_btn_style())
        icons.set_button_icon(
            self._close_btn, "close",
            color=self.CLOSE_ICON_COLOR, size=self.CLOSE_ICON_SIZE,
        )
        self._close_btn.clicked.connect(self.close)
        self._close_btn.setVisible(False)
        h_layout.addWidget(self._close_btn)

        self._root.addWidget(header)

        # Área desplazable: el contenido fluye en vertical, nunca scroll
        # horizontal (evita que el lado quede cortado).
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(self._scroll_style())
        vp_style = self._viewport_style()
        if vp_style:
            self._scroll.viewport().setStyleSheet(vp_style)
        self._root.addWidget(self._scroll, stretch=1)

        self._content: QWidget | None = None
        self._animation: QPropertyAnimation | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

    # ── Hooks de estilo (sobrescritos por cada lado) ─────────────────────────
    def _frame_style(self) -> str:
        return f"QFrame#{self.OBJECT_NAME} {{ border-radius: 0px; }}"

    def _header_style(self) -> str:
        return ""

    def _title_style(self) -> str:
        return "font-weight: 700; background: transparent; border: none;"

    def _close_btn_style(self) -> str:
        return "QPushButton { background: transparent; }"

    def _scroll_style(self) -> str:
        return "background: transparent;"

    def _viewport_style(self) -> str:
        return ""

    # ── Animación y ciclo de vida ────────────────────────────────────────────
    def _cancel_animation(self) -> None:
        if self._animation is None:
            return
        animation = self._animation
        self._animation = None
        animation.stop()

    def _compute_target_width(self) -> int:
        """Ancho proporcional al padre, acotado a [WIDTH_MIN, WIDTH_MAX]."""
        pw = 0
        if self._parent_ref is not None:
            pw = self._parent_ref.width()
        # Antes del primer layout, parent.width() es 0: cae a la pantalla o al
        # mínimo de MainWindow.
        if pw < 200:
            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    pw = screen.availableGeometry().width()
            if pw < 200:
                pw = 1180
        target = int(pw * self.WIDTH_FRACTION)
        return max(self.WIDTH_MIN, min(self.WIDTH_MAX, target))

    def update_target_width(self) -> None:
        """Recalcula el ancho objetivo (llamar al redimensionar el padre)."""
        self._target_width = self._compute_target_width()

    # ── Posicionamiento overlay ───────────────────────────────────────────────
    def set_area_provider(self, provider) -> None:
        """Inyecta el proveedor del área overlay (callable → QRect en coords del
        padre). MainWindow lo usa para que el cajón termine encima de la barra."""
        self._area_provider = provider

    def _overlay_area(self) -> QRect:
        """Rectángulo —coords del padre— donde el cajón se despliega. Con
        proveedor: área del grafo (sin command bar). Sin él: todo el padre."""
        if self._area_provider is not None:
            return self._area_provider()
        parent = self.parentWidget()
        if parent is not None:
            return parent.rect()
        return QRect(0, 0, self._target_width, 800)

    def _apply_overlay_geometry(self, width: int) -> None:
        """Coloca el cajón anclado a su lado, con `width` actual, ocupando el alto
        del área overlay. Se llama frame a frame durante la animación y al
        reposicionar (resize de ventana / cambio de página)."""
        area = self._overlay_area()
        w = max(0, int(width))
        x = area.x() + area.width() - w if self.ANCHOR == "right" else area.x()
        self.setGeometry(x, area.y(), w, area.height())

    def reposition(self) -> None:
        """Reaplica la geometría overlay con el ancho actual (sin reanimar)."""
        self._apply_overlay_geometry(self.maximumWidth())

    def _replace_content(self, widget: QWidget | None) -> None:
        """Quita el contenido actual (ocultar → takeWidget → reparentar →
        deleteLater) y monta `widget` si no es None. Reparentar antes de borrar
        evita que Qt deje el viejo widget colgando en el scroll.

        BETA1-K01: el panel anterior (o el entrante) puede haber sido ya destruido
        por Qt (deleteLater/reparentado externo); se guarda cada acceso con
        `_qt_alive` para no tocar un objeto C++ borrado (libshiboken)."""
        if self._content is not None:
            old = self._content
            self._content = None
            if _qt_alive(old):
                old.hide()
            # takeWidget() es seguro aunque el widget ya esté muerto.
            taken = self._scroll.takeWidget()
            victim = taken if taken is not None else old
            if _qt_alive(victim):
                victim.setParent(self)
                victim.deleteLater()
        if widget is not None:
            if not _qt_alive(widget):
                # Panel entrante ya destruido: el cajón queda vacío en vez de crashear.
                self._content = None
                return
            self._content = widget
            self._scroll.setWidget(widget)
            install_wheel_guard(widget)  # la rueda no cambia combos/spin/slider
            widget.show()

    def set_content(self, widget: QWidget, title: str = "") -> None:
        """Fija el contenido del cajón."""
        self._cancel_animation()
        self._replace_content(widget)
        self._title.setText(title)

    def open(self) -> None:
        """Muestra el cajón con animación de entrada (presencia: OutQuint)."""
        self._cancel_animation()
        self.update_target_width()
        self._close_btn.setVisible(True)
        # Ya visible con el ancho correcto: solo asegura el ancho, sin reanimar.
        if self.isVisible() and self.maximumWidth() >= self._target_width - 10:
            self.setMinimumWidth(self._target_width)
            self.setMaximumWidth(self._target_width)
            self._apply_overlay_geometry(self._target_width)
            self.show()
            self.raise_()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self.setMinimumWidth(0)
        self.setMaximumWidth(0)
        self._apply_overlay_geometry(0)
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._animate_width(0, self._target_width)

    def close(self) -> None:
        """Oculta el cajón con animación de salida (más directa: OutCubic)."""
        if not self.isVisible():
            return
        self._close_btn.setVisible(False)
        self._animate_width(self.maximumWidth(), 0, cleanup=True)

    def _animate_width(self, start: int, end: int, *, cleanup: bool = False) -> None:
        self._cancel_animation()

        # Apertura con presencia (OutQuint, más larga); cierre algo más rápido y
        # directo (OutCubic). Coherente con el glide del canvas.
        opening = end > start
        animation = QPropertyAnimation(self, b"maximumWidth")
        animation.setDuration(MOTION_SLOW if opening else MOTION_BASE)
        animation.setStartValue(max(0, int(start)))
        animation.setEndValue(max(0, int(end)))
        animation.setEasingCurve(EASING_ENTER if opening else QEasingCurve.Type.OutCubic)
        self._animation = animation

        # Mantener minimumWidth EN LOCKSTEP con maximumWidth en AMBAS direcciones.
        # Si al cerrar el suelo se quedaba en el ancho completo, el ancho real
        # quedaba clavado a tope hasta el último frame y el cajón "desaparecía de
        # golpe" dejando hueco. Animando el suelo a la par, el ancho real se
        # encoge frame a frame (apertura y cierre igual de fluidos).
        # OVERLAY: el cajón no está en un layout, así que el ancho real se aplica
        # por geometría frame a frame (anclado a su lado), no por el sistema de
        # layout. setMinimumWidth se mantiene EN LOCKSTEP antes de la geometría
        # para preservar el contrato de paridad de cierre (UX6).
        self.setMinimumWidth(max(0, int(start)))
        self._apply_overlay_geometry(int(start))

        def _on_value(v: int) -> None:
            self.setMinimumWidth(max(0, int(v)))
            self._apply_overlay_geometry(int(v))

        animation.valueChanged.connect(_on_value)

        if cleanup:
            def finish_close():
                # Guarda de carrera: si entre medias se lanzó otra animación
                # (abrir/cerrar rápido), esta finalización es obsoleta.
                if self._animation is not animation:
                    return
                self.setMinimumWidth(0)
                self.setMaximumWidth(0)
                self.hide()
                self._replace_content(None)
                self._animation = None
            animation.finished.connect(finish_close)
        else:
            def finish_open():
                if self._animation is animation:
                    self._animation = None
            animation.finished.connect(finish_open)
        animation.start()

    def keyPressEvent(self, event):  # noqa: N802 (Qt API)
        """Cerrar con Escape."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
