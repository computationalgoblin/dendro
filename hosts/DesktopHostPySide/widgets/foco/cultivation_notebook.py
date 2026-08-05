"""Cuaderno de cultivo (BETA2-FOCO-26): el riego GUÍA desde el propio editor.

Bloque compacto montado ARRIBA del formulario de la entidad en el Modo Foco:

1. Franja de estado (chip regada/falta_regar/secada + nota stale/secada).
2. Cuatro barras métricas compactas (tooltips = explicación por métrica).
3. Tarjeta «Siguiente paso»: la métrica más DÉBIL de la última lectura decide
   la acción recomendada (CTA «Sugerir X · métrica NN» + porqué + riesgos como
   chips); nunca regada ⇒ «Regar ahora»; lectura antigua ⇒ «Regar de nuevo».
4. «Informe vigente»: el summary COMPLETO de la última lectura (serif).
5. «Historial de riegos (N)»: cada lectura con su informe ÍNTEGRO (antes el
   drawer lo truncaba a 60 caracteres).

Solo EMITE señales (``waterRequested``/``suggestRequested``/``pauseToggled``);
el workspace ejecuta por servicios — la UI nunca escribe persistencia. Pintura
plana con QSS del sistema — PROHIBIDO QGraphicsEffect (regla del repo).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    FONT_SERIF,
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK_INVERSE,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE_SOFT,
    RADIUS_SM,
    SAGE,
    SPACE_XS,
    SURFACE_HI,
    overline_label,
    TYPE_CAPTION_PX,
    TYPE_LABEL_PX,
    TYPE_SUBHEAD_PX,
)

# BETA2-JARDIN-04: umbral y decisión del «siguiente paso» compartidos con el
# chip de la cabecera de Foco — una sola fuente de verdad.
from hosts.DesktopHostPySide.widgets.field_help import metric_tooltip
from packages.application.watering_guidance import WEAK_THRESHOLD, next_step

_METRICS = (
    ("arraigo", "Arraigo"),
    ("nutrida", "Nutrida"),
    ("iluminada", "Iluminada"),
    ("relevancia", "Relevancia"),
)

# UI2-15: icono SVG identificador de cada métrica (strip y Cuaderno).
_METRIC_ICONS = {
    "arraigo": "metric_arraigo",
    "nutrida": "metric_nutrida",
    "iluminada": "metric_iluminada",
    "relevancia": "metric_relevancia",
}


def _risk_row(text: str, parent: QWidget) -> QWidget:
    """UI2-15: fila de riesgo [icono alert + texto] — sin glifos Unicode."""
    row = QWidget(parent)
    box = QHBoxLayout(row)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(5)
    glyph = QLabel(row)
    glyph.setPixmap(icons.pixmap("alert", size=12, color=GOLD_DEEP))
    glyph.setFixedSize(14, 14)
    glyph.setStyleSheet("background: transparent; border: none;")
    box.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
    label = QLabel(text, row)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color: {INK_SOFT}; font-size: {TYPE_CAPTION_PX}px; background: transparent; border: none;"
    )
    box.addWidget(label, 1)
    return row

# BETA-AUDIT-08: este diccionario y `_METRICS` son paralelos salvo en su 4.ª clave, y
# ahí nacía la confusión: las barras muestran `relevancia` (la fija el USUARIO y la IA
# tiene prohibido evaluarla) mientras que aquí la 4.ª es `calidad`, que no es ninguna
# barra sino la pasada general de pulido cuando las tres métricas están sanas.
# Llamarla «calidad narrativa» la disfrazaba de métrica y dejaba tres nombres para dos
# conceptos. Se le da un nombre de ACCIÓN, que es lo que realmente es.
_SUGGEST_LABELS = {
    "arraigo": "Sugerir arraigo",
    "nutrida": "Sugerir nutrición",
    "iluminada": "Sugerir iluminación",
    "calidad": "Sugerir mejoras",
}

_STATUS_STYLES = {
    "regada": (SAGE, "Regada"),
    "falta_regar": (GOLD_DEEP, "Falta regar"),
    "secada": (INK_MUTED, "Secada"),
}


class CultivationNotebook(QWidget):
    """Guía de cultivo de la entidad en foco, embebida en el editor."""

    waterRequested = Signal()  # noqa: N815 — convención Qt de señales
    suggestRequested = Signal(str)  # noqa: N815 — métrica a reparar
    pauseToggled = Signal(bool)  # noqa: N815 — True = Secar, False = Cultivar
    # BETA2-MEM-09: acción sobre una incidencia de Memoria (entity_id, issue_id, estado).
    memoryIssueAction = Signal(str, str, str)  # noqa: N815

    def __init__(
        self,
        watering_service: Any = None,
        parent: QWidget | None = None,
        *,
        history_provider: Any = None,
    ) -> None:
        super().__init__(parent)
        self.watering_service = watering_service
        # BETA2-PLAY-18: provider(entity_id) → lista de HistoryEntry de
        # observaciones del recorrido (solo lectura; la UI no toca persistencia).
        self.history_provider = history_provider
        self._entity_id = ""
        self._status = ""
        # BETA-MULTIAGENT2-FIX-06 (G2-08): hay un lote de riego EN VUELO. Es un CAMPO
        # del widget, no un `setEnabled` suelto: `refresh()`/`_set_step` se llaman a
        # cada paso del lote y devolvían el botón a la vida, invitando a pagar dos veces.
        self._batch_running = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACE_XS)
        layout.setSpacing(6)

        # 1) Franja de estado + acciones mínimas.
        status_row = QHBoxLayout()
        self.status_chip = QLabel("", self)
        self.status_chip.setStyleSheet(
            f"QLabel {{ border-radius: {RADIUS_SM}px; padding: 2px 10px; color: {INK_INVERSE}; "
            f"font-weight: 700; font-size: {TYPE_CAPTION_PX}px; }}"
        )
        status_row.addWidget(self.status_chip)
        self.state_note = QLabel("", self)
        self.state_note.setWordWrap(True)
        self.state_note.setStyleSheet(
            f"color: {INK_MUTED}; background: transparent; font-size: {TYPE_CAPTION_PX}px;"
        )
        status_row.addWidget(self.state_note, 1)
        # BETA2-FOCO-37: Regar/Secar/Cultivar se movieron a la franja de cultivo
        # (CultivationStrip, iconos minimalistas). El Cuaderno conserva la tarjeta
        # «Siguiente paso» (Sugerir / regar guiado).
        layout.addLayout(status_row)

        # 2) Barras métricas — UNA por fila (BETA2-PULIDO-03): el patrón del
        # drawer de riego, que no se solapa a ningún ancho. Labels 78/56 px
        # (el pct absorbe «NN% ·ant.») y barra de 10 px con chunk = altura/2.
        self.bars: dict[str, tuple[QProgressBar, QLabel]] = {}
        for metric_key, label_text in _METRICS:
            metrics_row = QHBoxLayout()
            metrics_row.setSpacing(8)
            # UI2-15: icono SVG identificador de la métrica (mismo set que la
            # franja del pie de la tarjeta), con tooltip.
            metric_glyph = QLabel(self)
            metric_glyph.setPixmap(
                icons.pixmap(_METRIC_ICONS[metric_key], size=14, color=INK_SOFT)
            )
            metric_glyph.setFixedSize(16, 16)
            metric_glyph.setStyleSheet("background: transparent; border: none;")
            # BETA-AUDIT-06: el tooltip repetía la etiqueta («Arraigo» → «Arraigo»),
            # que no dice nada a quien no conoce ya la palabra. Ahora define.
            metric_glyph.setToolTip(metric_tooltip(metric_key, label_text))
            metrics_row.addWidget(metric_glyph)
            name_label = QLabel(label_text, self)
            name_label.setToolTip(metric_tooltip(metric_key, label_text))
            name_label.setFixedWidth(78)
            name_label.setStyleSheet(
                f"color: {INK_SOFT}; background: transparent; font-size: {TYPE_CAPTION_PX}px;"
            )
            metrics_row.addWidget(name_label)
            bar = QProgressBar(self)
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            bar.setStyleSheet(
                f"QProgressBar {{ background: {GOLD_TINT}; border: 1px solid {LINE_SOFT}; "
                "border-radius: 5px; } "
                f"QProgressBar::chunk {{ background: {GOLD}; border-radius: 5px; }}"
            )
            metrics_row.addWidget(bar, 1)
            pct_label = QLabel("—", self)
            pct_label.setFixedWidth(56)
            pct_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            pct_label.setStyleSheet(
                f"color: {INK_STRONG}; background: transparent; font-size: {TYPE_CAPTION_PX}px;"
            )
            metrics_row.addWidget(pct_label)
            layout.addLayout(metrics_row)
            self.bars[metric_key] = (bar, pct_label)

        # 3) Tarjeta «Siguiente paso» — la dirección que pide el usuario.
        self.next_step_card = QFrame(self)
        self.next_step_card.setObjectName("nextStepCard")
        self.next_step_card.setStyleSheet(
            f"QFrame#nextStepCard {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 10px; }}"
        )
        card_layout = QVBoxLayout(self.next_step_card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(4)
        step_title = overline_label("Siguiente paso", color=GOLD_DEEP, parent=self.next_step_card)
        card_layout.addWidget(step_title)
        self.step_reason = QLabel("", self.next_step_card)
        self.step_reason.setWordWrap(True)
        self.step_reason.setStyleSheet(
            f"color: {INK_STRONG}; background: transparent; border: none;"
        )
        card_layout.addWidget(self.step_reason)
        # UI2-15: riesgos como filas [icono alert + texto], sin glifos Unicode.
        self.risk_box = QWidget(self.next_step_card)
        self._risk_layout = QVBoxLayout(self.risk_box)
        self._risk_layout.setContentsMargins(0, 0, 0, 0)
        self._risk_layout.setSpacing(2)
        self.risk_box.hide()
        card_layout.addWidget(self.risk_box)
        self.step_button = QPushButton("", self.next_step_card)
        self.step_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.step_button.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px dashed {GOLD}; "
            f"border-radius: 8px; color: {GOLD_DEEP}; font-weight: 600; "
            "padding: 5px 10px; }"
        )
        self.step_button.clicked.connect(self._on_step_clicked)
        card_layout.addWidget(self.step_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.next_step_card)
        self._step_action: tuple[str, str] = ("", "")  # (kind, metric)

        # 4) Informe vigente — UI2-15: texto serif PROTAGONISTA, directo (sin
        # sección colapsable que lo escondiera tras un toggle ruidoso).
        self.report_title = overline_label("Informe vigente", color=GOLD_DEEP, parent=self)
        layout.addWidget(self.report_title)
        self.report_label = QLabel("", self)
        self.report_label.setWordWrap(True)
        self.report_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.report_label.setStyleSheet(
            f"color: {INK_STRONG}; background: transparent; "
            f"font-family: {FONT_SERIF}; font-size: {TYPE_SUBHEAD_PX}px;"
        )
        layout.addWidget(self.report_label)

        # 5) Historial — UI2-15: toggle plano discreto (chevron), plegado por
        # defecto; texto ÍNTEGRO por lectura al desplegar.
        self.history_toggle = QPushButton("Historial de riegos", self)
        self.history_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.history_toggle.setCheckable(True)
        self.history_toggle.setChecked(False)
        self.history_toggle.setIcon(icons.icon("expand", color=INK_MUTED, size=12))
        self.history_toggle.setIconSize(QSize(12, 12))
        self.history_toggle.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {INK_MUTED}; "
            f"font-size: {TYPE_CAPTION_PX}px; font-weight: 600; text-align: left; padding: 2px 0; }} "
            f"QPushButton:hover {{ color: {INK_STRONG}; }}"
        )
        self.history_toggle.toggled.connect(self._on_history_toggled)
        layout.addWidget(self.history_toggle)
        self.history_body = QWidget(self)
        self.history_layout = QVBoxLayout(self.history_body)
        self.history_layout.setContentsMargins(0, 2, 0, 0)
        self.history_layout.setSpacing(6)
        self.history_body.hide()
        layout.addWidget(self.history_body)

        # 6) BETA2-PLAY-18: observaciones del recorrido cronológico — mismas
        # afordancias que el historial de riegos (toggle plano, plegado).
        self.obs_toggle = QPushButton("Observaciones del recorrido", self)
        self.obs_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.obs_toggle.setCheckable(True)
        self.obs_toggle.setChecked(False)
        self.obs_toggle.setIcon(icons.icon("expand", color=INK_MUTED, size=12))
        self.obs_toggle.setIconSize(QSize(12, 12))
        self.obs_toggle.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {INK_MUTED}; "
            f"font-size: {TYPE_CAPTION_PX}px; font-weight: 600; text-align: left; padding: 2px 0; }} "
            f"QPushButton:hover {{ color: {INK_STRONG}; }}"
        )
        self.obs_toggle.toggled.connect(self._on_obs_toggled)
        self.obs_toggle.hide()
        layout.addWidget(self.obs_toggle)
        self.obs_body = QWidget(self)
        self.obs_layout = QVBoxLayout(self.obs_body)
        self.obs_layout.setContentsMargins(0, 2, 0, 0)
        self.obs_layout.setSpacing(6)
        self.obs_body.hide()
        layout.addWidget(self.obs_body)

        divider = QFrame(self)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {LINE_SOFT};")
        layout.addWidget(divider)

        # BETA2-MEM-09: sección de Memoria del elemento DENTRO de Cultivo (no un
        # panel técnico aparte). El host provee el bloque vía set_memory_provider.
        from hosts.DesktopHostPySide.widgets.foco.memory_section import MemorySection

        self._memory_provider = None
        self.memory_section = MemorySection(self)
        self.memory_section.issueAction.connect(
            lambda iid, st: self.memoryIssueAction.emit(self._entity_id, iid, st)
        )
        layout.addWidget(self.memory_section)

    # ------------------------------------------------------------------

    def set_memory_provider(self, provider) -> None:
        """provider(entity_id) → NarrativeMemory | None (lo llama el host)."""
        self._memory_provider = provider
        self.refresh_memory()

    def refresh_memory(self) -> None:
        block = None
        if self._memory_provider is not None and self._entity_id:
            try:
                block = self._memory_provider(self._entity_id)
            except Exception:  # noqa: BLE001 — la Memoria nunca rompe el cuaderno
                block = None
        self.memory_section.render(block)

    def set_entity(self, entity_id: str) -> None:
        self._entity_id = str(entity_id or "")
        self.refresh()
        self.refresh_memory()

    def set_watering_running(self, running: bool) -> None:
        """UI2-05: mientras el lote riega ESTA entidad, la franja lo dice (el
        estado real vuelve con refresh()). El botón Regar vive ahora en la
        CultivationStrip (FOCO-37); aquí solo se refleja el estado."""
        running = bool(running)
        if running:
            self.status_chip.setText("Regando…")
            self.status_chip.setStyleSheet(
                f"QLabel {{ background: {SAGE}; border-radius: {RADIUS_SM}px; "
                f"padding: 2px 10px; color: {INK_INVERSE}; font-weight: 700; "
                f"font-size: {TYPE_CAPTION_PX}px; }}"
            )
            self.state_note.setText("La IA está leyendo y diagnosticando esta entidad.")
        else:
            self.refresh()

    def entity_id(self) -> str:
        return self._entity_id

    def current_status(self) -> str:
        return self._status

    def _toggle_pause(self) -> None:
        self.pauseToggled.emit(self._status != "secada")

    def _on_step_clicked(self) -> None:
        kind, metric = self._step_action
        if kind == "water":
            self.waterRequested.emit()
        elif kind == "suggest" and metric:
            self.suggestRequested.emit(metric)
        elif kind == "resume":
            self.pauseToggled.emit(False)

    def _set_step(self, kind: str, metric: str, reason: str, button_text: str) -> None:
        self._step_action = (kind, metric)
        self.step_reason.setText(reason)
        self.step_button.setText(button_text)
        self.step_button.setVisible(bool(button_text))
        self._apply_batch_running()

    def set_batch_running(self, running: bool) -> None:
        """BETA-MULTIAGENT2-FIX-06 (G2-08): el disparador «Regar ahora» se apaga
        mientras hay un lote en vuelo y vuelve solo al terminar.

        La tester de 58 años lo dijo así: la app «deja activo el botón "Regar ahora"
        mientras trabaja, invitándome a pagar dos veces»."""
        self._batch_running = bool(running)
        self._apply_batch_running()

    def batch_running(self) -> bool:
        return bool(self._batch_running)

    def _apply_batch_running(self) -> None:
        button = getattr(self, "step_button", None)
        if button is None:
            return
        try:
            if self._batch_running:
                button.setEnabled(False)
                button.setToolTip("Hay un riego en curso; espera a que termine.")
            else:
                button.setEnabled(True)
                button.setToolTip("")
        except RuntimeError:  # widget Qt ya destruido
            pass

    def _on_history_toggled(self, expanded: bool) -> None:
        """UI2-15: pliegue plano del historial (chevron expand/collapse)."""
        self.history_body.setVisible(bool(expanded))
        self.history_toggle.setIcon(
            icons.icon("collapse" if expanded else "expand", color=INK_MUTED, size=12)
        )

    def _on_obs_toggled(self, expanded: bool) -> None:
        """PLAY-18: pliegue plano de las observaciones del recorrido."""
        self.obs_body.setVisible(bool(expanded))
        self.obs_toggle.setIcon(
            icons.icon("collapse" if expanded else "expand", color=INK_MUTED, size=12)
        )

    def _clear_observations(self) -> None:
        while self.obs_layout.count():
            item = self.obs_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_observations(self) -> None:
        """PLAY-18: pinta las observaciones del recorrido de la entidad en foco."""
        self._clear_observations()
        provider = self.history_provider
        entries = []
        if callable(provider) and self._entity_id:
            try:
                entries = list(provider(self._entity_id) or [])
            except Exception:  # noqa: BLE001 — la sección es best-effort
                entries = []
        self.obs_toggle.setText(f"Observaciones del recorrido ({len(entries)})")
        self.obs_toggle.setVisible(bool(entries))
        self.obs_body.setVisible(bool(entries) and self.obs_toggle.isChecked())
        for entry in entries:
            frame = QFrame(self)
            frame.setStyleSheet(
                f"QFrame {{ border: 1px solid {LINE_SOFT}; border-radius: 8px; "
                "background: rgba(255,255,255,0.45); }"
            )
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(8, 6, 8, 6)
            frame_layout.setSpacing(3)
            created = getattr(entry, "timestamp", None) or getattr(entry, "created_at", None)
            stamp = str(created)[:10] if created else ""
            head = QLabel(f"{stamp} · recorrido cronológico".strip(" ·"), frame)
            head.setStyleSheet(
                f"color: {INK_SOFT}; font-size: {TYPE_CAPTION_PX}px; font-weight: 600; "
                "background: transparent; border: none;"
            )
            frame_layout.addWidget(head)
            text = str(getattr(entry, "reason", "") or getattr(entry, "description", "") or "")
            if text:
                body = QLabel(text, frame)
                body.setWordWrap(True)
                body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                body.setStyleSheet(
                    f"color: {INK_STRONG}; background: transparent; border: none; "
                    f"font-family: {FONT_SERIF}; font-size: {TYPE_LABEL_PX}px;"
                )
                frame_layout.addWidget(body)
            self.obs_layout.addWidget(frame)

    def risk_texts(self) -> list[str]:
        """UI2-15: textos de riesgo vigentes (para consumidores y tests)."""
        texts: list[str] = []
        for index in range(self._risk_layout.count()):
            row = self._risk_layout.itemAt(index).widget()
            if row is None:
                continue
            for label in row.findChildren(QLabel):
                if label.text():
                    texts.append(label.text())
        return texts

    def _set_risks(self, risks: list[str]) -> None:
        while self._risk_layout.count():
            item = self._risk_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for risk in risks:
            self._risk_layout.addWidget(_risk_row(str(risk), self.risk_box))
        self.risk_box.setVisible(bool(risks))

    def _clear_history(self) -> None:
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refresh(self) -> None:  # noqa: PLR0912, PLR0915 — render plano de estados
        service = self.watering_service
        if service is None or not self._entity_id:
            self.hide()
            return
        report_result = service.status_of(self._entity_id)
        report = getattr(report_result, "value", None)
        if report is None:
            self.hide()
            return
        self.show()
        self._status = report.status
        color, text = _STATUS_STYLES.get(report.status, (INK_MUTED, report.status))
        self.status_chip.setText(text)
        self.status_chip.setStyleSheet(
            f"QLabel {{ background: {color}; border-radius: {RADIUS_SM}px; padding: 2px 10px; "
            f"color: {INK_INVERSE}; font-weight: 700; font-size: {TYPE_CAPTION_PX}px; }}"
        )
        notes: list[str] = []
        if report.last_error:
            notes.append(f"Último intento fallido: {report.last_error}")
        if report.stale and report.latest is not None:
            notes.append("Lectura antigua: hubo cambios desde el último riego.")
        self.state_note.setText(" ".join(notes))

        latest = report.latest
        for metric_key, (bar, pct_label) in self.bars.items():
            score = None if latest is None else latest.scores.get(metric_key)
            if score is None:
                bar.setValue(0)
                pct_label.setText("—")
                bar.setEnabled(False)
            else:
                bar.setValue(int(score))
                pct_label.setText(f"{int(score)}%{' ·ant.' if report.stale else ''}")
                bar.setEnabled(not report.stale and report.status != "secada")
            if latest is not None:
                bar.setToolTip(latest.metric_explanations.get(metric_key, ""))

        # Tarjeta «Siguiente paso»: decisión guiada por el estado + métrica débil.
        risks = list(latest.risks) if latest is not None else []
        self._set_risks(risks)  # UI2-15: filas con icono alert (SVG)
        # JARDIN-04: la decisión vive en watering_guidance.next_step (misma
        # fuente que el chip de la cabecera); aquí solo se traduce a textos.
        step = next_step(report, threshold=WEAK_THRESHOLD)
        kind = step.kind if step is not None else ""
        if kind == "resume":
            self._set_step(
                "resume",
                "",
                "Esta entidad está SECADA: no recibe avisos ni diagnósticos. "
                "Cultivarla la devuelve al ciclo de riego.",
                "Cultivar (volver al ciclo)",
            )
        elif kind == "water" and latest is None:
            self._set_step(
                "water",
                "",
                "Nunca regada: riega para obtener métricas, informe y dirección.",
                "Regar ahora",
            )
        elif kind == "water":
            self._set_step(
                "water",
                "",
                "La lectura no está al día (hubo cambios o la entidad volvió al "
                "ciclo). Riega de nuevo para actualizar métricas e informe.",
                "Regar de nuevo",
            )
        elif kind == "suggest":
            label = dict(_METRICS).get(step.metric, step.metric)
            self._set_step(
                "suggest",
                step.metric,
                f"{label} débil ({step.score}). {step.reason}".strip(),
                f"{_SUGGEST_LABELS[step.metric]} · {label.lower()} {step.score}",
            )
        else:
            self._set_step(
                "suggest",
                "calidad",
                "Métricas sanas. Puedes pulir la ficha con una pasada de sugerencias.",
                _SUGGEST_LABELS["calidad"],
            )

        # Informe vigente (completo, serif protagonista — UI2-15).
        if latest is not None and latest.summary:
            self.report_label.setText(latest.summary)
            self.report_title.show()
            self.report_label.show()
        else:
            self.report_title.hide()
            self.report_label.hide()

        # Historial íntegro (plegado por defecto, toggle plano — UI2-15).
        self._clear_history()
        history = getattr(service.history_for(self._entity_id), "value", None) or []
        self.history_toggle.setText(f"Historial de riegos ({len(history)})")
        self.history_toggle.setVisible(bool(history))
        self.history_body.setVisible(bool(history) and self.history_toggle.isChecked())
        for diagnostic in history:
            entry = QFrame(self)
            entry.setStyleSheet(
                f"QFrame {{ border: 1px solid {LINE_SOFT}; border-radius: 8px; "
                "background: rgba(255,255,255,0.45); }"
            )
            entry_layout = QVBoxLayout(entry)
            entry_layout.setContentsMargins(8, 6, 8, 6)
            entry_layout.setSpacing(3)
            stamp = diagnostic.created_at.date().isoformat()
            if diagnostic.error:
                head_text = f"{stamp} · FALLO ({diagnostic.origin})"
                body_text = diagnostic.error
            else:
                scores = " · ".join(
                    f"{label} {int(diagnostic.scores.get(key, 0) or 0)}"
                    for key, label in _METRICS
                    if diagnostic.scores.get(key) is not None
                )
                head_text = (
                    f"{stamp} · regada ({diagnostic.origin}) · coste "
                    f"{diagnostic.cost_class}" + (f" · {scores}" if scores else "")
                )
                body_text = diagnostic.summary
            head = QLabel(head_text, entry)
            head.setWordWrap(True)
            head.setStyleSheet(
                f"color: {INK_SOFT}; font-size: {TYPE_CAPTION_PX}px; font-weight: 600; "
                "background: transparent; border: none;"
            )
            entry_layout.addWidget(head)
            if body_text:
                body = QLabel(body_text, entry)
                body.setWordWrap(True)
                body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                body.setStyleSheet(
                    f"color: {INK_STRONG}; background: transparent; border: none; "
                    f"font-family: {FONT_SERIF}; font-size: {TYPE_LABEL_PX}px;"
                )
                entry_layout.addWidget(body)
            for risk_text in diagnostic.risks or []:
                entry_layout.addWidget(_risk_row(str(risk_text), entry))  # UI2-15
            self.history_layout.addWidget(entry)

        # PLAY-18: observaciones del recorrido cronológico (traza, no riego).
        self._refresh_observations()
