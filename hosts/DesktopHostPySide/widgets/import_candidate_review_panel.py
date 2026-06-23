"""ImportCandidateReviewPanel — ficha de detalle editable de un candidato (I18).

Revisa un ``ImportCandidate`` como un mini panel de detalle: badge de tipo
(Hoja/Rama/Relación/Anillo), nombre, resumen, cuerpo y ubicación (anillo/rama).
Es editable a fondo; al aceptar, guarda las ediciones y aplica a canon como
borrador en un paso. Para candidatos que enriquecen una entidad existente,
muestra un aviso y aceptar enriquece esa entidad.

No escribe persistencia directamente: delega en el ImportController.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.candidate_review_panel import candidate_body_text
from hosts.DesktopHostPySide.widgets.design_system import Badge, SectionHeader
from packages.domain.result import Error

# kind → (etiqueta de tipo, tono del badge)
_KIND_LABELS: dict[str, tuple[str, str]] = {
    "entity": ("Hoja", "info"),
    "branch": ("Rama", "gold"),
    "relation": ("Relación", "neutral"),
    "ring_suggestion": ("Anillo", "warning"),
    "milestone": ("Hito", "neutral"),
    "merge_suggestion": ("Fusión", "neutral"),
    "import_issue": ("Duda/conflicto", "danger"),
}


def candidate_kind(candidate: Any) -> str:
    payload = getattr(candidate, "proposed_data", {}) or {}
    kind = str(payload.get("kind") or "").strip().lower()
    if kind:
        return kind
    ctype = str(getattr(candidate, "candidate_type", "") or "")
    return {
        "relacion": "relation",
        "anillo": "ring_suggestion",
        "incidencia": "import_issue",
        "fusion": "merge_suggestion",
    }.get(ctype, "entity")


class ImportCandidateReviewPanel(QWidget):
    def __init__(
        self,
        candidate: Any,
        controller: Any,
        project: Any = None,
        *,
        basket_id: str,
        on_decision: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.candidate = candidate
        self.controller = controller
        self.project = project
        self.basket_id = basket_id
        self.on_decision = on_decision
        self._kind = candidate_kind(candidate)
        payload = getattr(candidate, "proposed_data", {}) or {}

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        label, tone = _KIND_LABELS.get(self._kind, ("Candidato", "neutral"))
        header = QHBoxLayout()
        header.addWidget(Badge(label, tone))
        header.addStretch()
        layout.addLayout(header)
        layout.addWidget(SectionHeader("Revisar candidato"))

        # Aviso de enriquecimiento de canon existente.
        if payload.get("presentation_kind") == "enrich_existing":
            target = self._target_name(payload.get("enrich_target_id"))
            banner = QLabel(f"⚠ Enriquece a una entidad existente: {target}")
            banner.setObjectName("mutedLabel")
            banner.setWordWrap(True)
            layout.addWidget(banner)

        # Nombre.
        layout.addWidget(QLabel("Nombre"))
        self.name_edit = QLineEdit(
            str(payload.get("name") or payload.get("title") or payload.get("ring_name") or "")
        )
        layout.addWidget(self.name_edit)

        # Relación: extremos (solo lectura) + tipo.
        self.rel_type_edit: QLineEdit | None = None
        if self._kind == "relation":
            src = str(payload.get("source_name") or payload.get("source_id") or "?")
            tgt = str(payload.get("target_name") or payload.get("target_id") or "?")
            ends = QLabel(f"{src}  →  {tgt}")
            ends.setObjectName("mutedLabel")
            layout.addWidget(ends)
            layout.addWidget(QLabel("Tipo de relación"))
            self.rel_type_edit = QLineEdit(str(payload.get("relation_type") or ""))
            layout.addWidget(self.rel_type_edit)

        # Subtipo (entity_type / branch_type) para hojas y ramas.
        self.subtype_edit: QLineEdit | None = None
        if self._kind in {"entity", "branch"}:
            layout.addWidget(QLabel("Tipo (subtipo)"))
            self.subtype_edit = QLineEdit(
                str(payload.get("entity_type") or payload.get("branch_type") or "")
            )
            layout.addWidget(self.subtype_edit)

        # Resumen.
        layout.addWidget(QLabel("Resumen"))
        self.summary_edit = QTextEdit(
            str(payload.get("summary") or payload.get("brief_description") or "")
        )
        self.summary_edit.setMaximumHeight(70)
        layout.addWidget(self.summary_edit)

        # Cuerpo.
        layout.addWidget(QLabel("Cuerpo"))
        self.body_edit = QTextEdit(candidate_body_text(payload))
        self.body_edit.setMinimumHeight(180)
        layout.addWidget(self.body_edit, stretch=1)

        # Ubicación: anillo (capa) — para hojas/ramas/anillos.
        self.ring_combo: QComboBox | None = None
        if self._kind in {"entity", "branch", "ring_suggestion"}:
            layout.addWidget(QLabel("Anillo (ubicación)"))
            self.ring_combo = QComboBox()
            self.ring_combo.addItem("— Sin anillo —", "")
            current = str(payload.get("ring_id") or payload.get("layer_id") or "")
            for layer in self._sorted_layers():
                self.ring_combo.addItem(
                    str(getattr(layer, "name", "Anillo")), str(getattr(layer, "id", ""))
                )
            idx = self.ring_combo.findData(current)
            if idx >= 0:
                self.ring_combo.setCurrentIndex(idx)
            layout.addWidget(self.ring_combo)

        # Acciones.
        self.status = QLabel("")
        self.status.setObjectName("mutedLabel")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        actions = QHBoxLayout()
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self._close)
        reject_btn = QPushButton("Rechazar")
        reject_btn.clicked.connect(self._reject)
        accept_btn = QPushButton("Aceptar")
        accept_btn.setObjectName("primaryButton")
        accept_btn.clicked.connect(self._accept)
        actions.addWidget(close_btn)
        actions.addStretch()
        actions.addWidget(reject_btn)
        actions.addWidget(accept_btn)
        layout.addLayout(actions)

    # ── helpers ──────────────────────────────────────────────────────────

    def _sorted_layers(self) -> list:
        layers = list(getattr(self.project, "world_layers", []) or [])
        return sorted(layers, key=lambda wl: getattr(wl, "order", 0))

    def _target_name(self, target_id: Any) -> str:
        for entity in getattr(self.project, "entities", []) or []:
            if getattr(entity, "id", "") == target_id:
                return str(getattr(entity, "name", "") or target_id)
        return str(target_id or "?")

    def _collect_edits(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name_edit.text().strip(),
            "kind": self._kind,
            "summary": self.summary_edit.toPlainText().strip(),
            "body": self.body_edit.toPlainText().strip(),
        }
        if self.subtype_edit is not None:
            value = self.subtype_edit.text().strip()
            if self._kind == "branch":
                data["branch_type"] = value or "contenedor"
            else:
                data["entity_type"] = value or "nota"
        if self.rel_type_edit is not None:
            data["relation_type"] = self.rel_type_edit.text().strip()
        if self.ring_combo is not None:
            ring_id = self.ring_combo.currentData()
            if ring_id:
                data["ring_id"] = ring_id
                data["layer_id"] = ring_id
        return data

    # ── acciones ─────────────────────────────────────────────────────────

    def _accept(self):
        # 1) Persistir ediciones en el candidato (vía servicio, no UI directa).
        edited = self.controller.edit(self.basket_id, self.candidate.id, self._collect_edits())
        if isinstance(edited, Error):
            self.status.setText(f"No se pudo guardar la edición: {edited.error}")
            return
        # 2) Aplicar a canon como borrador en un paso.
        result = self.controller.apply_to_canon(self.basket_id, self.candidate.id)
        if isinstance(result, Error):
            self.status.setText(f"No se pudo aceptar: {result.error}")
            return
        self.status.setText("Aceptado: en canon como borrador.")
        if self.on_decision:
            self.on_decision(self.candidate.id, "accept")

    def _reject(self):
        result = self.controller.reject(self.basket_id, self.candidate.id)
        if isinstance(result, Error):
            self.status.setText(f"No se pudo rechazar: {result.error}")
            return
        self.status.setText("Rechazado.")
        if self.on_decision:
            self.on_decision(self.candidate.id, "reject")

    def _close(self):
        if self.on_decision:
            self.on_decision(self.candidate.id, "close")
