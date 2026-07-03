"""Joint coherence panel for selected graph subgraphs.

Analysis and repair suggestions are review-only until the user explicitly accepts
a patch. No new nodes or relations are created here.
"""
from __future__ import annotations

import json
import re
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_safe_slot, track_worker
from hosts.DesktopHostPySide.widgets.design_system import SectionHeader
from packages.domain.result import Error


_PATCH_RE = re.compile(r"<PATCH_JSON>\s*(\{.*?\})\s*</PATCH_JSON>", re.DOTALL)
_ALLOWED_ENTITY_FIELDS = {"brief_description", "extended_description", "private_notes", "exportable_notes", "tags"}
_ALLOWED_RELATION_FIELDS = {"description", "temporality", "causality", "conditions", "source"}


class _CoherenceAIWorker(QThread):
    """Runs coherence AI actions in background; emits finished(text, error)."""

    finished = Signal(str, str)

    def __init__(
        self,
        ai_controller,
        mode: str,
        *,
        entity_ids: list[str],
        relation_ids: list[str],
        language: str,
        proposal: str = "",
        prompt_hint: str = "",
    ):
        super().__init__()
        self.ai_controller = ai_controller
        self.mode = mode
        self.entity_ids = list(entity_ids or [])
        self.relation_ids = list(relation_ids or [])
        self.language = language
        self.proposal = proposal
        self.prompt_hint = prompt_hint

    def run(self):
        try:
            if self.mode == "repair":
                result = self.ai_controller.repair_coherence(
                    self.entity_ids,
                    self.relation_ids,
                    proposal=self.proposal,
                    prompt_hint=self.prompt_hint,
                    language=self.language,
                )
            else:
                result = self.ai_controller.analyze_coherence(
                    self.entity_ids,
                    self.relation_ids,
                    prompt_hint=self.prompt_hint,
                    language=self.language,
                )
            if isinstance(result, Error):
                self.finished.emit("", result.error)
                return
            self.finished.emit(result.value.raw_text, "")
        except Exception as exc:  # pragma: no cover - UI defensive boundary
            self.finished.emit("", str(exc))


class CoherencePanel(QWidget):
    """Right-drawer panel for subgraph coherence analysis and repair."""

    def __init__(
        self,
        ctx: AppContext,
        ai_controller,
        entity_controller,
        relation_controller,
        *,
        entity_ids: list[str],
        relation_ids: list[str],
        on_saved=None,
    ):
        super().__init__()
        self.ctx = ctx
        self.ai_controller = ai_controller
        self.entity_controller = entity_controller
        self.relation_controller = relation_controller
        self.entity_ids = list(entity_ids or [])
        self.relation_ids = list(relation_ids or [])
        self.on_saved = on_saved
        self._repair_text = ""
        self._worker: _CoherenceAIWorker | None = None
        self._build()
        # Restore pending repair from ctx if re-opening same selection
        self._restore_pending_repair()
        self._run_analysis()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(SectionHeader("Coherencia conjunta", "Informe IA no canon sobre la selección del grafo."))

        count = f"{len(self.entity_ids)} nodo(s), {len(self.relation_ids)} relación(es)"
        self.selection_label = QLabel(f"Selección: {count}")
        self.selection_label.setObjectName("mutedLabel")
        layout.addWidget(self.selection_label)

        self.status = QLabel("Analizando coherencia…")
        self.status.setWordWrap(True)
        self.status.setObjectName("mutedLabel")
        layout.addWidget(self.status)

        self.report = QTextEdit()
        self.report.setReadOnly(True)
        self.report.setPlaceholderText("Aquí aparecerá el informe: veredicto, contradicciones, huecos de motivación y oportunidades.")
        self.report.setMinimumHeight(260)
        layout.addWidget(self.report, 1)

        layout.addWidget(QLabel("Motivo/propuesta para reparar"))
        self.proposal = QComboBox()
        self.proposal.addItems([
            "deuda",
            "chantaje",
            "alianza táctica",
            "lealtad real",
            "servidumbre forzada",
            "pacto temporal",
            "manipulación",
            "dependencia mutua",
            "reescribir con canon actual",
        ])
        layout.addWidget(self.proposal)

        self.extra = QTextEdit()
        self.extra.setPlaceholderText("Instrucción opcional del autor para orientar la reparación.")
        self.extra.setMinimumHeight(70)
        layout.addWidget(self.extra)

        row = QHBoxLayout()
        self.repair_btn = QPushButton("Generar reparación")
        self.repair_btn.setObjectName("primaryButton")
        self.repair_btn.clicked.connect(self._run_repair)
        self.discard_btn = QPushButton("Descartar sugerencia")
        self.discard_btn.clicked.connect(self._discard_repair)
        row.addWidget(self.repair_btn)
        row.addWidget(self.discard_btn)
        layout.addLayout(row)

        self.repair_preview = QTextEdit()
        self.repair_preview.setReadOnly(False)
        self.repair_preview.setPlaceholderText("La reparación aparecerá aquí como sugerencia IA diferenciada del canon.\nPuedes editar el texto antes de aceptar.")
        self.repair_preview.setMinimumHeight(170)
        layout.addWidget(self.repair_preview)

        accept_row = QHBoxLayout()
        accept_row.addStretch(1)
        self.accept_btn = QPushButton("Aceptar y aplicar reparación")
        self.accept_btn.setObjectName("primaryButton")
        self.accept_btn.clicked.connect(self._accept_repair)
        accept_row.addWidget(self.accept_btn)
        layout.addLayout(accept_row)

    def _language(self) -> str:
        pc = getattr(self.ctx, "project_controller", None)
        project = pc.ps.active_project if pc else None
        return str(getattr(project, "primary_language", "es") or "es")

    def _set_busy(self, busy: bool):
        self.repair_btn.setEnabled(not busy)
        self.discard_btn.setEnabled(not busy)
        self.accept_btn.setEnabled(not busy)

    def _run_analysis(self):
        if self.ai_controller is None:
            self.status.setText("IA no disponible para analizar coherencia.")
            return
        self._set_busy(True)
        self.status.setText("Analizando coherencia…")
        self._worker = _CoherenceAIWorker(
            self.ai_controller,
            "analysis",
            entity_ids=self.entity_ids,
            relation_ids=self.relation_ids,
            language=self._language(),
        )
        self._worker.finished.connect(self._on_analysis_finished)
        track_worker(self._worker)  # sobrevive al panel; se para al cerrar la app
        self._worker.start()

    @_qt_safe_slot
    def _on_analysis_finished(self, text: str, error: str):
        self._set_busy(False)
        if error:
            self.status.setText(error)
            return
        self.report.setPlainText(text)
        self.status.setText("Informe generado. No se ha modificado contenido.")

    def _run_repair(self):
        if self.ai_controller is None:
            self.status.setText("IA no disponible para generar reparación.")
            return
        self.status.setText("Generando reparación como sugerencia…")
        self._set_busy(True)
        proposal = self.proposal.currentText().strip()
        prompt_hint = self.extra.toPlainText().strip()
        self._worker = _CoherenceAIWorker(
            self.ai_controller,
            "repair",
            entity_ids=self.entity_ids,
            relation_ids=self.relation_ids,
            proposal=proposal,
            prompt_hint=prompt_hint,
            language=self._language(),
        )
        self._worker.finished.connect(self._on_repair_finished)
        track_worker(self._worker)  # sobrevive al panel; se para al cerrar la app
        self._worker.start()

    @_qt_safe_slot
    def _on_repair_finished(self, text: str, error: str):
        self._set_busy(False)
        if error:
            self.status.setText(error)
            return
        self._repair_text = text
        self.repair_preview.setPlainText(self._repair_text)
        self._stash_repair()
        self.status.setText("Reparación generada como sugerencia. Aún no se ha aplicado al canon.")

    def _discard_repair(self):
        self._repair_text = ""
        self.repair_preview.clear()
        self._clear_stash()
        self.status.setText("Sugerencia descartada. No se cambió nada.")

    def _extract_patch(self) -> dict[str, Any] | None:
        text = self._repair_text or self.repair_preview.toPlainText()
        match = _PATCH_RE.search(text)
        if not match:
            return None
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _accept_repair(self):
        patch = self._extract_patch()
        if not patch:
            self.status.setText("No se encontró un bloque <PATCH_JSON> válido en la reparación.")
            return
        changed = 0
        selected_entities = set(self.entity_ids)
        selected_relations = set(self.relation_ids)
        for item in patch.get("entities") or []:
            if not isinstance(item, dict):
                continue
            entity_id = str(item.get("id") or "")
            if entity_id not in selected_entities:
                continue
            data = {k: v for k, v in item.items() if k in _ALLOWED_ENTITY_FIELDS}
            if not data:
                continue
            result = self.entity_controller.update(entity_id, data)
            if isinstance(result, Error):
                self.status.setText(result.error)
                return
            changed += 1
        for item in patch.get("relations") or []:
            if not isinstance(item, dict):
                continue
            relation_id = str(item.get("id") or "")
            if relation_id not in selected_relations:
                continue
            data = {k: v for k, v in item.items() if k in _ALLOWED_RELATION_FIELDS}
            if not data:
                continue
            result = self.relation_controller.update(relation_id, data)
            if isinstance(result, Error):
                self.status.setText(result.error)
                return
            changed += 1
        if changed == 0:
            self.status.setText("La reparación no contiene cambios aplicables a la selección actual.")
            return
        # Clear stash since repair was accepted
        self._clear_stash()
        if self.on_saved:
            self.on_saved()
        self.status.setText(f"Reparación aceptada y aplicada a {changed} elemento(s) seleccionado(s).")

    # ── Repair persistence (survives drawer close/reopen) ──────────────

    def _stash_key(self) -> str:
        """Key for storing pending repair in ctx."""
        return f"_pending_coherence_repair::{':'.join(sorted(self.entity_ids))}"

    def _stash_repair(self):
        """Save current repair text to ctx so it survives drawer close."""
        text = self._repair_text or self.repair_preview.toPlainText()
        if text.strip():
            setattr(self.ctx, self._stash_key(), text)
        else:
            self._clear_stash()

    def _restore_pending_repair(self):
        """Restore repair text from previous session if selection matches."""
        stashed = getattr(self.ctx, self._stash_key(), None)
        if stashed:
            self._repair_text = stashed
            self.repair_preview.setPlainText(stashed)
            self.status.setText("Reparación restaurada de sesión anterior. Revisa y acepta o descarta.")

    def _clear_stash(self):
        key = self._stash_key()
        if hasattr(self.ctx, key):
            delattr(self.ctx, key)
