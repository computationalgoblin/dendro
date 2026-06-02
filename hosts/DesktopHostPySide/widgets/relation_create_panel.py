"""Internal relation creation prompt for B31-T06."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import enum_human
from packages.domain.relation import RelationType


class RelationCreatePanel(QWidget):
    """RightDrawer content used after drag-to-relate."""

    def __init__(self, source_label: str, target_label: str, *, on_create, on_cancel=None):
        super().__init__()
        self.on_create = on_create
        self.on_cancel = on_cancel
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        title = QLabel("Crear relación")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ECEFF4;")
        layout.addWidget(title)

        summary = QLabel(f"{source_label} → {target_label}")
        summary.setObjectName("mutedLabel")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        box = QGroupBox("Tipo y descripción")
        form = QFormLayout(box)
        self.type_combo = QComboBox()
        for relation_type in RelationType:
            self.type_combo.addItem(enum_human(relation_type.value), relation_type.value)
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(120)
        form.addRow("Tipo:", self.type_combo)
        form.addRow("Descripción:", self.description_edit)
        layout.addWidget(box)

        note = QLabel("La relación se creará mediante el servicio de aplicación y aparecerá en el grafo al guardar.")
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        actions = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self._cancel)
        create_btn = QPushButton("Crear relación")
        create_btn.setObjectName("primaryButton")
        create_btn.clicked.connect(self._create)
        actions.addWidget(cancel_btn)
        actions.addStretch()
        actions.addWidget(create_btn)
        layout.addLayout(actions)
        layout.addStretch()

    def _create(self):
        self.on_create(self.type_combo.currentData(), self.description_edit.toPlainText().strip())

    def _cancel(self):
        if self.on_cancel is not None:
            self.on_cancel()
