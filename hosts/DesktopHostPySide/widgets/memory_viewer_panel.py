"""Visor editorial de Memoria en Configuración de proyecto (BETA2-MEM-10).

Función de PROYECTO (no del flujo de Creación): consultar, editar, borrar y
regenerar la Memoria. Lee/edita/borra funcionan SIN IA (servicio determinista);
regenerar requiere proveedor IA y muestra un diff revisable antes de sustituir
(``MemoryRevisionProposal``). La UI nunca escribe persistencia: todo pasa por
``NarrativeMemoryService`` / ``MemoryAIService``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    FONT_SERIF,
    GOLD,
    INK_MUTED,
    INK_STRONG,
    LINE_SOFT,
    overline_label,
)
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_safe_slot, track_worker
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.result import Error, Ok

_FRESHNESS_LABEL = {
    MemoryFreshness.REGADA.value: "vigente",
    MemoryFreshness.FALTA_REGAR.value: "falta regar",
    MemoryFreshness.SECADA.value: "secada",
    MemoryFreshness.SIN_MEMORIA.value: "sin memoria",
}


def _humanize_regen_error(result) -> str:
    raw = str(getattr(result, "error", "") or "Error desconocido")
    try:
        from hosts.DesktopHostPySide.widgets.settings_panels import _human_error

        return _human_error(raw)
    except Exception:  # noqa: BLE001 — si el helper no está, el error crudo sirve
        return raw


class _RegenWorker(QThread):
    """Corre ``update_memory`` FUERA del hilo de UI (BETA-CIERRE WS-F / B2).

    Antes se llamaba síncronamente desde el slot del botón: una llamada bloqueante al
    proveedor (hasta el timeout, 300 s) congelaba la app entera («No responde»). Ahora
    va en su propio QThread, registrado para el apagado ordenado (``track_worker``).
    """

    done = Signal(object)  # emite el Result (Ok/Error)

    def __init__(self, service: Any, kind: MemoryTargetKind, target_id: str, context: str) -> None:
        super().__init__()
        self._service = service
        self._kind = kind
        self._target_id = target_id
        self._context = context

    def run(self) -> None:
        try:
            result = self._service.update_memory(
                self._kind, self._target_id, self._context, mode="regen"
            )
        except Exception as exc:  # noqa: BLE001 — el hilo nunca debe romper el flujo
            result = Error(str(exc))
        self.done.emit(result)


class MemoryViewerPanel(QWidget):
    """Visor/editor de la Memoria del proyecto (Configuración)."""

    def __init__(self, memory_service: Any, memory_ai_service: Any = None, parent=None) -> None:
        super().__init__(parent)
        self.memory_service = memory_service
        self.memory_ai_service = memory_ai_service
        self._current_key: tuple[str, str, str] | None = None
        self._regen_worker: _RegenWorker | None = None

        root = QHBoxLayout(self)

        # Izquierda: lista de Memorias (global + por elemento).
        left = QVBoxLayout()
        left.addWidget(overline_label("MEMORIAS DEL PROYECTO"))
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_select)
        left.addWidget(self.list, 1)
        root.addLayout(left, 1)

        # Derecha: visor editorial del bloque seleccionado.
        right = QVBoxLayout()
        self.header = QLabel("Selecciona una Memoria")
        self.header.setStyleSheet(f"color: {INK_STRONG}; font-weight: 700;")
        right.addWidget(self.header)
        self.freshness = QLabel("")
        self.freshness.setStyleSheet(f"color: {INK_MUTED}; font-size: 11px;")
        right.addWidget(self.freshness)
        right.addWidget(overline_label("RESUMEN EDITORIAL"))
        self.resumen = QTextEdit()
        self.resumen.setStyleSheet(
            f"QTextEdit {{ font-family: {FONT_SERIF}; font-size: 14px; color: {INK_STRONG}; "
            f"border: 1px solid {LINE_SOFT}; border-radius: 8px; padding: 8px; }}"
        )
        right.addWidget(self.resumen, 1)

        # WS-K: el CUERPO de la página de wiki (lo que la IA mantiene y navega) también
        # se muestra — antes solo se veía la línea de lead, ocultando lo que el usuario
        # pagó por generar. Solo lectura: el cuerpo lo escribe Regar, no se edita a mano.
        right.addWidget(overline_label("CUERPO (PÁGINA WIKI)"))
        self.cuerpo = QTextEdit()
        self.cuerpo.setReadOnly(True)
        self.cuerpo.setStyleSheet(
            f"QTextEdit {{ font-family: {FONT_SERIF}; font-size: 13px; color: {INK_MUTED}; "
            f"border: 1px solid {LINE_SOFT}; border-radius: 8px; padding: 8px; }}"
        )
        right.addWidget(self.cuerpo, 1)

        # Diff de regeneración (oculto salvo cuando hay propuesta pendiente).
        self.diff_box = QLabel("")
        self.diff_box.setWordWrap(True)
        self.diff_box.setStyleSheet(
            f"background: #FFF8E6; border: 1px solid {GOLD}; border-radius: 8px; padding: 8px;"
        )
        self.diff_box.setVisible(False)
        right.addWidget(self.diff_box)

        actions = QHBoxLayout()
        self.save_btn = QPushButton("Guardar")
        self.save_btn.clicked.connect(self._save)
        self.delete_btn = QPushButton("Borrar")
        self.delete_btn.clicked.connect(self._delete)
        self.regen_btn = QPushButton("Regenerar con IA")
        self.regen_btn.clicked.connect(self._regenerate)
        self.accept_btn = QPushButton("Aceptar cambio")
        self.accept_btn.clicked.connect(self._accept_proposal)
        self.accept_btn.setVisible(False)
        self.discard_btn = QPushButton("Descartar cambio")
        self.discard_btn.clicked.connect(self._discard_proposal)
        self.discard_btn.setVisible(False)
        for b in (
            self.save_btn,
            self.delete_btn,
            self.regen_btn,
            self.accept_btn,
            self.discard_btn,
        ):
            actions.addWidget(b)
        actions.addStretch(1)
        right.addLayout(actions)
        root.addLayout(right, 2)

        self._ai_available = memory_ai_service is not None
        if not self._ai_available:
            self.regen_btn.setEnabled(False)
            self.regen_btn.setToolTip("Configura un proveedor de IA para regenerar Memoria.")
        self.refresh()

    # ── datos ────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        result = self.memory_service.list_memories()
        blocks = result.value if isinstance(result, Ok) else []
        for block in blocks:
            fresh = _FRESHNESS_LABEL.get(block.freshness.value, block.freshness.value)
            name = (
                "Proyecto"
                if not block.target_id
                else f"{block.target_kind.value}:{block.target_id}"
            )
            item = QListWidgetItem(f"{name}  ·  {fresh}")
            item.setData(Qt.ItemDataRole.UserRole, block.target_key())
            self.list.addItem(item)
        self.list.blockSignals(False)

    def _blocks(self):
        result = self.memory_service.list_memories()
        return result.value if isinstance(result, Ok) else []

    def _current_block(self):
        if self._current_key is None:
            return None
        for block in self._blocks():
            if block.target_key() == self._current_key:
                return block
        return None

    def _on_select(self, row: int) -> None:
        item = self.list.item(row) if row >= 0 else None
        self._current_key = tuple(item.data(Qt.ItemDataRole.UserRole)) if item else None
        self._load()

    def _load(self) -> None:
        block = self._current_block()
        has_pending = bool(block and block.pending_revision is not None)
        if block is None:
            self.header.setText("Selecciona una Memoria")
            self.freshness.setText("")
            self.resumen.setPlainText("")
            self.cuerpo.setPlainText("")
        else:
            name = (
                "Proyecto"
                if not block.target_id
                else f"{block.target_kind.value}:{block.target_id}"
            )
            self.header.setText(name)
            self.freshness.setText(
                f"Estado: {_FRESHNESS_LABEL.get(block.freshness.value, block.freshness.value)}"
                f" · Fuentes: {len(block.citations)}"
            )
            self.resumen.setPlainText(block.resumen_editorial)
            self.cuerpo.setPlainText(getattr(block, "cuerpo", "") or "")
        # Diff de propuesta pendiente.
        self.diff_box.setVisible(has_pending)
        self.accept_btn.setVisible(has_pending)
        self.discard_btn.setVisible(has_pending)
        if has_pending:
            after = block.pending_revision.after.get("resumen_editorial", "")
            self.diff_box.setText(
                f"PROPUESTA IA (revisa antes de sustituir):\n\nAntes:\n{block.resumen_editorial}"
                f"\n\nDespués:\n{after}"
            )

    # ── acciones (vía servicio) ──────────────────────────────────────────

    def _save(self) -> None:
        if self._current_key is None:
            return
        kind, tid, ctx = self._current_key
        self.memory_service.upsert_memory(
            MemoryTargetKind(kind),
            tid,
            ctx,
            resumen_editorial=self.resumen.toPlainText(),
            causa="edición manual desde Configuración",
        )
        self.refresh()

    def _delete(self) -> None:
        if self._current_key is None:
            return
        confirm = QMessageBox.question(
            self,
            "Borrar Memoria",
            "¿Borrar esta Memoria? (No afecta al canon.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        kind, tid, ctx = self._current_key
        self.memory_service.delete_memory(MemoryTargetKind(kind), tid, ctx)
        self._current_key = None
        self.refresh()
        self._load()

    def _regenerate(self) -> None:
        # WS-F/B2: el trabajo de IA va FUERA del hilo de UI para no congelar la app.
        if self._current_key is None or self.memory_ai_service is None:
            return
        if self._regen_worker is not None:
            return  # ya hay una regeneración en curso
        kind, tid, ctx = self._current_key
        self._set_regen_busy(True)
        worker = _RegenWorker(self.memory_ai_service, MemoryTargetKind(kind), tid, ctx)
        worker.done.connect(self._on_regen_done)
        worker.finished.connect(worker.deleteLater)
        self._regen_worker = worker
        track_worker(worker)
        worker.start()

    def _set_regen_busy(self, busy: bool) -> None:
        self.regen_btn.setText("Regenerando…" if busy else "Regenerar con IA")
        self.regen_btn.setEnabled(not busy and self._ai_available)
        self.save_btn.setEnabled(not busy)
        self.delete_btn.setEnabled(not busy)

    @_qt_safe_slot
    def _on_regen_done(self, result) -> None:
        self._regen_worker = None
        self._set_regen_busy(False)
        if not isinstance(result, Ok):
            QMessageBox.warning(self, "Regenerar Memoria", _humanize_regen_error(result))
            return
        self.refresh()
        self._reselect()
        self._load()

    def _accept_proposal(self) -> None:
        if self._current_key is None:
            return
        kind, tid, ctx = self._current_key
        self.memory_service.apply_revision_proposal(MemoryTargetKind(kind), tid, ctx)
        self.refresh()
        self._reselect()
        self._load()

    def _discard_proposal(self) -> None:
        if self._current_key is None:
            return
        kind, tid, ctx = self._current_key
        self.memory_service.discard_revision_proposal(MemoryTargetKind(kind), tid, ctx)
        self._load()

    def _reselect(self) -> None:
        for row in range(self.list.count()):
            item = self.list.item(row)
            if tuple(item.data(Qt.ItemDataRole.UserRole)) == self._current_key:
                self.list.blockSignals(True)
                self.list.setCurrentRow(row)
                self.list.blockSignals(False)
                return


__all__ = ["MemoryViewerPanel"]
