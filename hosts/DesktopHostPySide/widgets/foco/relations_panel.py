"""UI2-06: pestaña «Relaciones» de la tarjeta central del Foco.

La lista viva de relaciones clicables (FOCO-20) sale de NodeDetailPanel y pasa
a ser un panel propio: todas las relaciones de la entidad centrada, una fila-
botón por relación (clic → panel adyacente/dual con la relación en medio) y el
«+» que abre el flujo de crear relación del rail. Solo lectura del proyecto:
nada de aquí muta persistencia.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK_INVERSE,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE_SOFT,
    SPACE_MD,
    enum_human,
    overline_label,
)


def _enum_value(value, default: str = "") -> str:
    raw = getattr(value, "value", value)
    return str(raw) if raw else default


def relation_entries_for(project, entity_id: str) -> list[tuple[str, str]]:
    """[(relation_id, «→ tipo · nombre»)] para todas las relaciones de la
    entidad, con glifo de dirección y marca de fantasma (lógica FOCO-20)."""
    if project is None or not entity_id:
        return []
    by_id = {getattr(e, "id", None): e for e in (getattr(project, "entities", []) or [])}
    entries: list[tuple[str, str]] = []
    for relation in getattr(project, "relations", []) or []:
        src = getattr(relation, "source_id", "")
        tgt = getattr(relation, "target_id", "")
        if entity_id not in {src, tgt}:
            continue
        outgoing = src == entity_id
        other = by_id.get(tgt if outgoing else src)
        # BETA2-FIX-12 (G2-16), pregunta abierta nº4: la escotilla de
        # texto libre (`custom_metadata["custom_relation_label"]`, que escribe el
        # combo editable del panel de relación) tenía CINCO apariciones en el
        # repo y las cinco en el fichero que la escribía: ni el Foco, ni el Mapa,
        # ni la IA sabían nunca cómo llamaba el autor a ese vínculo. Con la
        # familia de parentesco en el dominio pierde casi todo su motivo, pero
        # mientras exista tiene que VIAJAR al menos a la lista que el usuario lee.
        meta = getattr(relation, "custom_metadata", {}) or {}
        etiqueta_libre = str(meta.get("custom_relation_label") or "").strip()
        kind_text = etiqueta_libre or enum_human(
            _enum_value(getattr(relation, "relation_type", None), "relación")
        )
        relation_id = str(getattr(relation, "id", "") or "")
        direction = _enum_value(getattr(relation, "direction", None), "")
        glyph = "↔" if direction == "bidireccional" else ("→" if outgoing else "←")
        ghost_mark = (
            "  ·  fantasma"
            if _enum_value(getattr(relation, "canon_state", None), "") == "fantasma"
            else ""
        )
        other_name = getattr(other, "name", "?") if other else "Elemento vinculado"
        entries.append((relation_id, f"{glyph}  {kind_text} · {other_name}{ghost_mark}"))
    return entries


class FocoRelationsPanel(QWidget):
    """Lista real de relaciones (todas, clicables, sin tope)."""

    def __init__(
        self,
        ctx,
        entity_id: str,
        *,
        on_open_relation=None,
        on_create_relation=None,
        on_create_related=None,
        on_delete_relation=None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.ctx = ctx
        self.entity_id = str(entity_id or "")
        self.on_open_relation = on_open_relation
        self.on_create_relation = on_create_relation
        self.on_create_related = on_create_related
        # WS-E: eliminar una relación desde el Foco (vía callback → controller en
        # el workspace; el panel NO escribe persistencia). None = sin botón ×.
        self.on_delete_relation = on_delete_relation

        box = QVBoxLayout(self)
        box.setContentsMargins(0, SPACE_MD, 0, 0)
        box.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)
        header.addWidget(overline_label("Relaciones"))
        header.addStretch(1)
        self.add_relation_btn = QToolButton()
        self.add_relation_btn.setText("+")
        self.add_relation_btn.setToolTip("Crear relación desde esta entidad")
        self.add_relation_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_relation_btn.setStyleSheet(
            f"QToolButton {{ border: 1px solid {LINE_SOFT}; border-radius: 10px; "
            f"background: transparent; color: {INK_SOFT}; font-size: 14px; "
            f"padding: 0 7px; }} "
            f"QToolButton:hover {{ border-color: {GOLD}; color: {INK_STRONG}; }}"
        )
        self.add_relation_btn.setVisible(callable(self.on_create_relation))
        if callable(self.on_create_relation):
            self.add_relation_btn.clicked.connect(lambda: self.on_create_relation())
        header.addWidget(self.add_relation_btn)

        # BETA2-FOCO-27: segundo botón — CREAR una entidad nueva ya relacionada con
        # la del foco (reusa el flujo `create_related` del rail de la izquierda).
        # El «+» de arriba relaciona con una EXISTENTE; este crea una NUEVA.
        self.add_related_btn = QToolButton()
        self.add_related_btn.setIcon(
            icons.icon("tool_create_related", color=INK_SOFT, size=14)
        )
        self.add_related_btn.setIconSize(QSize(14, 14))
        self.add_related_btn.setToolTip("Crear entidad nueva relacionada")
        self.add_related_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_related_btn.setStyleSheet(
            f"QToolButton {{ border: 1px solid {LINE_SOFT}; border-radius: 10px; "
            f"background: transparent; padding: 2px 6px; }} "
            f"QToolButton:hover {{ border-color: {GOLD}; }}"
        )
        self.add_related_btn.setVisible(callable(self.on_create_related))
        if callable(self.on_create_related):
            self.add_related_btn.clicked.connect(lambda: self.on_create_related())
        header.addWidget(self.add_related_btn)
        box.addLayout(header)

        self._relations_rows = QVBoxLayout()
        self._relations_rows.setSpacing(2)
        box.addLayout(self._relations_rows)
        self.relations_empty_label = QLabel("Sin relaciones todavía.")
        self.relations_empty_label.setStyleSheet(
            f"color: {INK_MUTED}; background: transparent; font-style: italic;"
        )
        box.addWidget(self.relations_empty_label)
        box.addStretch(1)
        self.refresh()

    # ── datos ──────────────────────────────────────────────────────────────

    def _project(self):
        pc = getattr(self.ctx, "project_controller", None)
        return pc.ps.active_project if pc else None

    def refresh(self) -> None:
        self._rebuild_relation_rows(relation_entries_for(self._project(), self.entity_id))

    def _rebuild_relation_rows(self, entries: list[tuple[str, str]]) -> None:
        """entries = [(relation_id, texto)] — una fila-botón por relación."""
        rows = self._relations_rows
        while rows.count():
            item = rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.relations_empty_label.setVisible(not entries)
        can_delete = callable(self.on_delete_relation)
        for relation_id, text in entries:
            row = QPushButton(text)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.setFixedHeight(28)
            # UI2-13: cápsula dorada (gramática de chips accionables de la
            # casa); clic → modo dual (entidad | relación | entidad).
            row.setStyleSheet(
                f"QPushButton {{ background: {GOLD_TINT}; color: {GOLD_DEEP}; "
                f"border: 1px solid {GOLD_SOFT}; border-radius: 14px; "
                "text-align: left; padding: 3px 14px; font-size: 13px; } "
                f"QPushButton:hover {{ background: {GOLD_SOFT}; color: {INK_INVERSE}; }}"
            )
            if relation_id:
                row.clicked.connect(lambda _=False, rid=relation_id: self._on_relation_link(rid))
            if not (can_delete and relation_id):
                rows.addWidget(row)  # sin borrado → cápsula suelta (compat FOCO-20)
                continue
            # WS-E: con callback de borrado, la fila lleva la cápsula + un «×».
            line = QWidget()
            line_box = QHBoxLayout(line)
            line_box.setContentsMargins(0, 0, 0, 0)
            line_box.setSpacing(4)
            line_box.addWidget(row, 1)
            del_btn = QToolButton()
            del_btn.setText("×")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setFixedHeight(28)
            del_btn.setToolTip("Eliminar esta relación")
            del_btn.setStyleSheet(
                f"QToolButton {{ border: 1px solid {LINE_SOFT}; border-radius: 14px; "
                f"background: transparent; color: {INK_MUTED}; font-size: 15px; "
                f"padding: 0 8px; }} "
                f"QToolButton:hover {{ border-color: {GOLD}; color: {INK_STRONG}; }}"
            )
            del_btn.clicked.connect(
                lambda _=False, rid=relation_id: self._on_relation_delete(rid)
            )
            line_box.addWidget(del_btn, 0)
            rows.addWidget(line)

    def _on_relation_link(self, relation_id: str) -> None:
        """Una relación de la lista se abre en su panel adyacente/dual."""
        if callable(self.on_open_relation) and relation_id:
            self.on_open_relation(relation_id)

    def _on_relation_delete(self, relation_id: str) -> None:
        """WS-E: delega el borrado (confirmación + controller) al workspace."""
        if callable(self.on_delete_relation) and relation_id:
            self.on_delete_relation(relation_id)


__all__ = ["FocoRelationsPanel", "relation_entries_for"]
