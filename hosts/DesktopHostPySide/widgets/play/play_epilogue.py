"""PLAY-09: epílogo inmersivo — el informe del recorrido como cierre narrativo.

Tarjeta que presenta el ``ChronologyWalkReport`` con nombres humanos (títulos
de hito resueltos desde el proyecto, no ids), los problemas aplazados y los
próximos pasos. Vive dentro de ``PlayView`` sustituyendo a la escena cuando el
recorrido termina. Sin QGraphicsEffect (regla del repo).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

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
    TYPE_BODY_PX,
    TYPE_CAPTION_PX,
    TYPE_OVERLINE_PX,
)


def _overline(text: str, color: str = INK_MUTED) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {color}; font-size: {TYPE_OVERLINE_PX}px; font-weight: 700; "
        "letter-spacing: 2px; background: transparent;"
    )
    return label


class PlayEpilogueCard(QFrame):
    """Cierre del recorrido: veredicto, hitos revisados, aplazados y pasos."""

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumWidth(720)
        self.setMinimumWidth(420)
        self.setStyleSheet(
            f"QFrame {{ background: {SURFACE_HI}; border: 1px solid {LINE_SOFT}; "
            f"border-radius: {RADIUS_LG}px; }} QLabel {{ border: none; }}"
        )
        card = QVBoxLayout(self)
        card.setContentsMargins(SPACE_LG * 2, SPACE_LG * 2, SPACE_LG * 2, SPACE_LG * 2)
        card.setSpacing(SPACE_MD)

        header = _overline("EPÍLOGO DEL RECORRIDO", GOLD_SOFT)
        card.addWidget(header, 0, Qt.AlignmentFlag.AlignHCenter)

        self.verdict_label = QLabel("")
        self.verdict_label.setWordWrap(True)
        self.verdict_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.verdict_label.setStyleSheet(
            f"color: {INK_STRONG}; font-family: Georgia, serif; font-size: 22px; "
            "font-weight: 700; background: transparent;"
        )
        card.addWidget(self.verdict_label)

        body = QWidget(self)
        body_box = QVBoxLayout(body)
        body_box.setContentsMargins(0, 0, 0, 0)
        body_box.setSpacing(SPACE_SM)
        self._body_box = body_box
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.setWidget(body)
        scroll.setMaximumHeight(360)
        card.addWidget(scroll)

        self.close_btn = QPushButton("Volver al lienzo")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(
            f"QPushButton {{ background: {GOLD_TINT}; border: 1px solid {GOLD_SOFT}; "
            f"border-radius: 14px; color: {INK_STRONG}; font-weight: 700; padding: 8px 22px; }}"
        )
        self.close_btn.clicked.connect(self.closed.emit)
        card.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignHCenter)

    # ── contenido ───────────────────────────────────────────────────────
    def show_report(self, report: Any, project: Any) -> None:
        self.verdict_label.setText(str(getattr(report, "verdict", "") or ""))
        box = self._body_box
        while box.count():
            item = box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        titles = self._milestone_titles(project)

        analyzed = [str(mid) for mid in getattr(report, "milestones_analyzed", []) or []]
        if analyzed:
            box.addWidget(_overline("HITOS REVISADOS"))
            lines = "<br/>".join(f"• {titles.get(mid, mid[:8])}" for mid in analyzed)
            box.addWidget(self._body_label(lines))

        deferred = list((getattr(report, "metadata", {}) or {}).get("deferred_problems") or [])
        if deferred:
            box.addWidget(_overline("INCOHERENCIAS APLAZADAS"))
            lines = "<br/>".join(
                f"• {p.get('title') or p.get('kind') or 'Problema'} "
                f"({titles.get(str(p.get('milestone_id') or ''), '¿hito?')})"
                for p in deferred
            )
            box.addWidget(self._body_label(lines))

        candidates = list(getattr(report, "candidates_created", []) or [])
        caption = QLabel(f"Candidatos creados durante el recorrido: {len(candidates)}")
        caption.setStyleSheet(
            f"color: {INK_MUTED}; font-size: {TYPE_CAPTION_PX}px; background: transparent;"
        )
        box.addWidget(caption)

        steps = [s for s in (getattr(report, "recommended_next_steps", []) or []) if str(s).strip()]
        if steps:
            box.addWidget(_overline("PRÓXIMOS PASOS"))
            box.addWidget(self._body_label("<br/>".join(f"• {s}" for s in steps)))
        box.addStretch(1)

    @staticmethod
    def _milestone_titles(project: Any) -> dict[str, str]:
        titles: dict[str, str] = {}
        for hito in getattr(project, "causal_milestones", []) or []:
            year = getattr(hito, "year", None)
            title = str(getattr(hito, "title", "") or "")
            titles[str(hito.id)] = f"{title} ({year})" if year is not None else title
        return titles

    @staticmethod
    def _body_label(html: str) -> QLabel:
        label = QLabel(html)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {INK_SOFT}; font-size: {TYPE_BODY_PX}px; background: transparent;"
        )
        return label


__all__ = ["PlayEpilogueCard"]
