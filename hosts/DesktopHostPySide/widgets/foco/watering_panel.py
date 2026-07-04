"""Drawer de riego (BETA2-FOCO-12): estado, métricas, informe, historial y Sugerir X.

Contenido del drawer derecho DEDICADO al riego en el Modo Foco. Aquí los
porcentajes SÍ son numéricos (en el lienzo las métricas son solo gráficas).
Estados: nunca-regada sin métricas; obsoleta con la última lectura atenuada;
secada apagada con la lectura conservada; fallo de lote con causa trazable.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_DEEP,
    GOLD_TINT,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE_SOFT,
    SAGE,
)

WEAK_THRESHOLD = 60  # métrica "débil" → habilita Sugerir X (spec)

_METRICS = (
    ("arraigo", "Arraigo"),
    ("nutrida", "Nutrida"),
    ("iluminada", "Iluminada"),
    ("relevancia", "Relevancia"),
)

_SUGGESTS = (
    ("arraigo", "Sugerir arraigo"),
    ("nutrida", "Sugerir nutrición"),
    ("iluminada", "Sugerir iluminación"),
    ("calidad", "Sugerir calidad narrativa"),
)

_STATUS_STYLES = {
    "regada": (SAGE, "Regada — diagnóstico vigente"),
    "falta_regar": (GOLD_DEEP, "Falta regar"),
    "secada": (INK_MUTED, "Secada — fuera del ciclo"),
}


class WateringPanel(QWidget):
    """Panel del drawer: todo el ciclo de riego de la entidad en foco."""

    waterRequested = Signal()  # noqa: N815 — convención Qt de señales
    pauseToggled = Signal(bool)  # noqa: N815 — True = Secar, False = Cultivar
    suggestRequested = Signal(str)  # noqa: N815 — métrica a reparar
    cancelBatchRequested = Signal()  # noqa: N815 — cancelar lote ENTRE pasos
    reviewRequested = Signal(str)  # noqa: N815 — tarjeta de Semilla textual ⇒ revisión

    def __init__(self, watering_service: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.watering_service = watering_service
        self._entity_id = ""
        self._status = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.status_chip = QLabel("", self)
        self.status_chip.setStyleSheet(
            "QLabel { border-radius: 10px; padding: 4px 10px; color: #FCF8EC; font-weight: 700; }"
        )
        layout.addWidget(self.status_chip)
        self.state_note = QLabel("", self)
        self.state_note.setWordWrap(True)
        self.state_note.setStyleSheet(f"color: {INK_MUTED}; background: transparent;")
        layout.addWidget(self.state_note)

        self.bars: dict[str, tuple[QProgressBar, QLabel]] = {}
        for metric_key, label_text in _METRICS:
            row = QHBoxLayout()
            name_label = QLabel(label_text, self)
            name_label.setFixedWidth(78)
            name_label.setStyleSheet(f"color: {INK_SOFT}; background: transparent;")
            row.addWidget(name_label)
            bar = QProgressBar(self)
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            bar.setStyleSheet(
                f"QProgressBar {{ background: {GOLD_TINT}; border: 1px solid {LINE_SOFT}; "
                "border-radius: 5px; } "
                f"QProgressBar::chunk {{ background: {GOLD}; border-radius: 5px; }}"
            )
            row.addWidget(bar, 1)
            pct_label = QLabel("—", self)
            pct_label.setFixedWidth(56)
            pct_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            pct_label.setStyleSheet(f"color: {INK_STRONG}; background: transparent;")
            row.addWidget(pct_label)
            layout.addLayout(row)
            self.bars[metric_key] = (bar, pct_label)

        self.summary_label = QLabel("", self)
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(f"color: {INK_STRONG}; background: transparent;")
        layout.addWidget(self.summary_label)
        self.risks_label = QLabel("", self)
        self.risks_label.setWordWrap(True)
        self.risks_label.setStyleSheet(f"color: {INK_SOFT}; background: transparent;")
        layout.addWidget(self.risks_label)
        self.context_label = QLabel("", self)
        self.context_label.setWordWrap(True)
        self.context_label.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self.context_label)

        actions = QHBoxLayout()
        self.water_button = QPushButton("Regar", self)
        self.water_button.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; border: none; border-radius: 10px; "
            "color: #FCF8EC; font-weight: 700; padding: 6px 14px; }"
        )
        self.water_button.clicked.connect(self.waterRequested)
        actions.addWidget(self.water_button)
        self.pause_button = QPushButton("Secar", self)
        self.pause_button.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {LINE_SOFT}; "
            f"border-radius: 10px; color: {INK_SOFT}; padding: 6px 12px; }}"
        )
        self.pause_button.clicked.connect(self._toggle_pause)
        actions.addWidget(self.pause_button)
        self.cancel_button = QPushButton("Cancelar riego", self)
        self.cancel_button.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {GOLD_DEEP}; "
            f"border-radius: 10px; color: {GOLD_DEEP}; padding: 6px 12px; }}"
        )
        self.cancel_button.clicked.connect(self.cancelBatchRequested)
        self.cancel_button.hide()
        actions.addWidget(self.cancel_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.suggest_buttons: dict[str, QPushButton] = {}
        for metric_key, label_text in _SUGGESTS:
            button = QPushButton(label_text, self)
            button.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 1px dashed {GOLD}; "
                f"border-radius: 8px; color: {GOLD_DEEP}; padding: 4px 8px; }} "
                "QPushButton:disabled { border-color: #E3DCC8; color: #B8B5A8; }"
            )
            button.clicked.connect(lambda _=False, m=metric_key: self.suggestRequested.emit(m))
            layout.addWidget(button)
            self.suggest_buttons[metric_key] = button

        history_title = QLabel("Historial de riegos", self)
        history_title.setStyleSheet(
            f"color: {INK_SOFT}; font-weight: 600; background: transparent;"
        )
        layout.addWidget(history_title)
        self.history_list = QListWidget(self)
        self.history_list.setMaximumHeight(150)
        self.history_list.setStyleSheet(
            f"QListWidget {{ background: transparent; border: 1px solid {LINE_SOFT}; "
            f"border-radius: 8px; color: {INK_SOFT}; font-size: 11px; }}"
        )
        layout.addWidget(self.history_list)

        # FOCO-13: tarjetas de preview de Semillas de edición textual.
        self.cards_layout = QVBoxLayout()
        layout.addLayout(self.cards_layout)
        layout.addStretch(1)

    # ------------------------------------------------------------------

    def set_entity(self, entity_id: str) -> None:
        self._entity_id = str(entity_id or "")
        self.refresh()

    def entity_id(self) -> str:
        return self._entity_id

    def current_status(self) -> str:
        return self._status

    def set_text_cards(self, candidates: list[Any]) -> None:
        """FOCO-13: Semillas de edición TEXTUAL de la entidad en foco.

        Aparecen como tarjetas con preview del cambio (no en el lienzo); el
        botón «Revisar» abre el flujo humano existente de aceptar/rechazar.
        """
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._card_ids: list[str] = []
        for candidate in candidates or []:
            candidate_id = str(getattr(candidate, "id", "") or "")
            if candidate_id:
                self._card_ids.append(candidate_id)
        if not self._card_ids:
            return
        # BETA2-UX-07: en vez de N tarjetas-entrada (una superficie de revisión
        # duplicada), un único resumen «Revisar semillas» con conteo; la revisión
        # detallada ocurre en la superficie primaria (semillas del lienzo).
        n = len(self._card_ids)
        card = QWidget(self)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(4)
        card.setStyleSheet(
            f"QWidget {{ border: 1px dashed {GOLD}; border-radius: 10px; "
            "background: rgba(255,255,255,0.5); }"
        )
        plural = "semilla de texto pendiente" if n == 1 else "semillas de texto pendientes"
        title_label = QLabel(f"🌱 {n} {plural}", card)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(
            f"color: {INK_STRONG}; font-weight: 600; border: none; background: transparent;"
        )
        card_layout.addWidget(title_label)
        review_button = QPushButton("Revisar", card)
        review_button.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; border: none; border-radius: 8px; "
            "color: #FCF8EC; padding: 4px 10px; }"
        )
        # Abre la más antigua; el resto se revisa en la superficie primaria.
        review_button.clicked.connect(
            lambda _=False: self.reviewRequested.emit(self._card_ids[0])
        )
        card_layout.addWidget(review_button, 0, Qt.AlignmentFlag.AlignRight)
        self.cards_layout.addWidget(card)

    def card_ids(self) -> list[str]:
        return list(getattr(self, "_card_ids", []))

    def set_batch_running(self, running: bool, progress_text: str = "") -> None:
        self.cancel_button.setVisible(bool(running))
        self.water_button.setEnabled(not running)
        if running and progress_text:
            self.state_note.setText(progress_text)

    def _toggle_pause(self) -> None:
        # True = Secar (si está en ciclo), False = Cultivar (si está secada).
        self.pauseToggled.emit(self._status != "secada")

    def refresh(self) -> None:  # noqa: PLR0912 — render plano de estados
        service = self.watering_service
        if service is None or not self._entity_id:
            self.status_chip.setText("Sin entidad en foco")
            self.status_chip.setStyleSheet(
                f"QLabel {{ background: {INK_MUTED}; border-radius: 10px; "
                "padding: 4px 10px; color: #FCF8EC; }"
            )
            return
        report_result = service.status_of(self._entity_id)
        report = getattr(report_result, "value", None)
        if report is None:
            self.status_chip.setText("Entidad no disponible")
            return
        self._status = report.status
        color, text = _STATUS_STYLES.get(report.status, (INK_MUTED, report.status))
        if report.status == "falta_regar" and report.latest is None and not report.last_error:
            text = "Falta regar — nunca regada"
        self.status_chip.setText(text)
        self.status_chip.setStyleSheet(
            f"QLabel {{ background: {color}; border-radius: 10px; "
            "padding: 4px 10px; color: #FCF8EC; font-weight: 700; }"
        )

        notes: list[str] = []
        if report.last_error:
            notes.append(f"Último intento fallido: {report.last_error}")
        if report.stale and report.latest is not None:
            notes.append("Lectura antigua (atenuada): hubo cambios desde el último riego.")
        if report.status == "secada":
            notes.append("No recibe avisos ni se invalida. Cultivar la devuelve al ciclo.")
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
                suffix = " ·ant." if report.stale else ""
                pct_label.setText(f"{int(score)}%{suffix}")
                bar.setEnabled(not report.stale and report.status != "secada")
        if latest is not None:
            self.summary_label.setText(latest.summary)
            explanations = latest.metric_explanations
            for metric_key, (bar, _pct) in self.bars.items():
                bar.setToolTip(explanations.get(metric_key, ""))
            self.risks_label.setText(
                ("Riesgos: " + "; ".join(latest.risks)) if latest.risks else ""
            )
            manifest = latest.context_manifest or {}
            self.context_label.setText(
                "Contexto usado: "
                f"{len(manifest.get('entity_ids') or [])} entidad(es), "
                f"~{manifest.get('estimated_tokens', '?')} tokens · "
                f"{latest.provider or 's/proveedor'} {latest.model or ''} · "
                f"coste {latest.cost_class}"
            )
        else:
            self.summary_label.setText("Sin métricas: esta entidad nunca fue regada.")
            self.risks_label.setText("")
            self.context_label.setText("")

        is_paused = report.status == "secada"
        self.pause_button.setText("Cultivar" if is_paused else "Secar")
        self.water_button.setEnabled(not is_paused)
        for metric_key, button in self.suggest_buttons.items():
            if latest is None:
                button.setEnabled(False)
            elif metric_key == "calidad":
                button.setEnabled(not is_paused)
            else:
                score = latest.scores.get(metric_key)
                button.setEnabled(
                    not is_paused and score is not None and int(score) < WEAK_THRESHOLD
                )

        self.history_list.clear()
        history_result = service.history_for(self._entity_id)
        for diagnostic in getattr(history_result, "value", None) or []:
            stamp = diagnostic.created_at.date().isoformat()
            if diagnostic.error:
                line = f"{stamp} · FALLO ({diagnostic.origin}) · {diagnostic.error}"
            else:
                line = (
                    f"{stamp} · regada ({diagnostic.origin}) · coste {diagnostic.cost_class} · "
                    f"{diagnostic.summary[:60]}"
                )
            self.history_list.addItem(line)
