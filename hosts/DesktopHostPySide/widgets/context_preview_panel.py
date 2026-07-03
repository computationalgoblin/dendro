"""UX3 · Vista previa de contexto editable.

Muestra, ANTES de enviar a la IA, qué se va a mandar (canon, candidatos, RAG,
cronología…) por secciones e items, con tokens estimados, y deja al usuario
EXCLUIR lo que no quiera. Las secciones fijas/sagradas aparecen marcadas y no se
pueden desmarcar. No muta nada: solo recoge las exclusiones y las entrega al
workspace, que las pasa al job real al crear.

El dato de entrada es el dict que devuelve
``packages.application.prompt_assembler.build_context_preview`` (vía
``AIJobService.preview_context``).
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    INK,
    INK_INVERSE,
    INK_MUTED,
    INK_STRONG,
    LINE,
    RADIUS_MD,
    SURFACE_HI,
    Badge,
    SectionHeader,
    make_scroll_area,
)


class ContextPreviewPanel(QWidget):
    """Panel del RightDrawer con la vista previa editable del contexto."""

    def __init__(
        self,
        preview: dict,
        *,
        on_apply: Callable[[list[str], list[str]], None],
        on_refresh: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_apply = on_apply
        self._on_refresh = on_refresh
        # checkbox por sección excluible y por item (key/ref_id → checkbox).
        self._section_checks: dict[str, QCheckBox] = {}
        self._item_checks: dict[str, QCheckBox] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(10)

        root.addWidget(
            SectionHeader(
                "Vista previa del contexto",
                "Esto es lo que recibirá la IA. Desmarca lo que no quieras enviar; "
                "lo marcado en oro es fijo.",
            )
        )
        root.addWidget(self._budget_bar(preview))

        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)
        for section in preview.get("sections") or []:
            col.addWidget(self._section_row(section))
        col.addStretch(1)
        root.addWidget(make_scroll_area(content), 1)

        root.addLayout(self._buttons())

    # -- construcción -------------------------------------------------------

    def _budget_bar(self, preview: dict) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        tier = str(preview.get("tier") or "—")
        row.addWidget(Badge(f"tier · {tier}", "gold"))
        total = int(preview.get("total_tokens") or 0)
        budget = int(preview.get("input_budget") or 0)
        tone = "warning" if budget and total > budget else "info"
        row.addWidget(Badge(f"{total} / {budget} tokens", tone))
        row.addStretch(1)
        return box

    def _section_row(self, section: dict) -> QWidget:
        key = str(section.get("key") or "")
        fixed = bool(section.get("fixed"))
        label = str(section.get("label") or key)
        est = int(section.get("est_tokens") or 0)

        box = QWidget()
        box.setObjectName("previewSection")
        box.setStyleSheet(
            f"QWidget#previewSection {{ background: {SURFACE_HI}; "
            f"border: 1px solid {LINE}; border-radius: {RADIUS_MD}px; }}"
        )
        outer = QVBoxLayout(box)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(8)
        check = QCheckBox(label)
        check.setChecked(True)
        check.setEnabled(not fixed)
        if fixed:
            check.setToolTip("Sección fija: siempre se envía.")
            check.setStyleSheet(f"color: {GOLD_DEEP}; font-weight: 700;")
        else:
            self._section_checks[key] = check
        head.addWidget(check, 1)
        head.addWidget(Badge(f"{est} tok", "neutral"))
        if section.get("truncado"):
            head.addWidget(Badge("recortado", "warning"))
        outer.addLayout(head)

        for item in section.get("items") or []:
            outer.addWidget(self._item_row(item))
        return box

    def _item_row(self, item: dict) -> QWidget:
        ref_id = str(item.get("ref_id") or "")
        kind = str(item.get("kind") or "")
        est = int(item.get("est_tokens") or 0)
        text = str(item.get("text") or "")

        box = QWidget()
        row = QVBoxLayout(box)
        row.setContentsMargins(18, 0, 0, 0)
        row.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(6)
        check = QCheckBox(kind or "item")
        check.setChecked(True)
        check.setStyleSheet(f"color: {INK}; font-size: 12px;")
        if ref_id:
            self._item_checks[ref_id] = check
        else:
            check.setEnabled(False)
        top.addWidget(check, 1)
        top.addWidget(Badge(f"{est}", "neutral"))
        row.addLayout(top)
        if text:
            preview_label = QLabel(text)
            preview_label.setWordWrap(True)
            preview_label.setStyleSheet(
                f"color: {INK_MUTED}; font-size: 11px; margin-left: 22px;"
            )
            row.addWidget(preview_label)
        return box

    def _buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        if self._on_refresh is not None:
            refresh = QPushButton("Re-previsualizar")
            refresh.setStyleSheet(
                f"QPushButton {{ background: {SURFACE_HI}; color: {GOLD_DEEP}; "
                f"border: 1px solid {GOLD_SOFT}; border-radius: 16px; "
                f"min-height: 32px; padding: 0 14px; font-size: 12px; font-weight: 700; }} "
                f"QPushButton:hover {{ background: {GOLD_SOFT}; color: {INK_STRONG}; }}"
            )
            refresh.clicked.connect(lambda: self._on_refresh())
            row.addWidget(refresh)
        row.addStretch(1)
        apply_btn = QPushButton("Crear con esta selección")
        apply_btn.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; color: {INK_INVERSE}; border: none; "
            f"border-radius: 16px; min-height: 34px; padding: 0 16px; "
            f"font-size: 12px; font-weight: 700; }} "
            f"QPushButton:hover {{ background: {GOLD_DEEP}; }}"
        )
        apply_btn.clicked.connect(self._emit_apply)
        row.addWidget(apply_btn)
        return row

    # -- estado -------------------------------------------------------------

    def excluded(self) -> tuple[list[str], list[str]]:
        """(secciones, item_ids) desmarcados por el usuario."""
        sections = [k for k, c in self._section_checks.items() if not c.isChecked()]
        items = [rid for rid, c in self._item_checks.items() if not c.isChecked()]
        return sections, items

    def _emit_apply(self) -> None:
        sections, items = self.excluded()
        self._on_apply(sections, items)
