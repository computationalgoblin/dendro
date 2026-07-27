"""BETA2-STRUCT: panel de proyecto «Ajustes estructurales».

Lista tres clases de propuesta, todas revisables (§17 read-only, aceptar/rechazar):
- **Movimientos de anillo** (`ring_move`): detector determinista sobre la potencia atribuida
  por la IA al Regar. Se derivan en lectura (`service.analyze()`).
- **Excepciones ascendentes** (`ascending_exception`, STRUCT-05): detector determinista sobre
  relaciones no-causales bajo→alto con extremo inferior de potencia alta (§16). También
  derive-on-read.
- **Estructura de anillos** (`ring_create`/`ring_merge`): la IA propone bajo demanda (botón
  «Proponer estructura») crear anillos que faltan o fusionar redundantes — tarea holística y
  abstracta que se delega en la IA (`service.propose_ring_structure()`).

La ACEPTACIÓN se enruta por el pipeline de candidatos existente (el host materializa el Candidato
y llama a `CandidateController.accept`). La IA nunca escribe canon; el usuario acepta.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import PanelScaffold
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_safe_slot, track_worker
from packages.domain.result import Ok

_STRUCTURE_KINDS = frozenset({"ring_create", "ring_merge"})


class _ProposeWorker(QThread):
    """SHIP-07: «Proponer estructura» llama al proveedor (HTTP bloqueante, hasta
    300 s). Correrlo aquí evita congelar toda la ventana."""

    done = Signal(object)  # Result | Exception

    def __init__(self, service: Any) -> None:
        super().__init__()
        self._service = service

    def run(self) -> None:  # pragma: no cover - hilo
        try:
            self.done.emit(self._service.propose_ring_structure())
        except Exception as exc:  # noqa: BLE001 — el hilo nunca revienta la UI
            self.done.emit(exc)


class StructureReviewPanel(QWidget):
    """Panel de proyecto: movimientos de anillo (deterministas) + estructura (IA)."""

    def __init__(
        self,
        service: Any,
        *,
        on_accept: Callable[[Any], None],
        on_close: Callable[[], None] | None = None,
        log: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._on_accept = on_accept
        self._on_close = on_close
        self._log = log
        self._status_text = ""
        self._proposing = False  # SHIP-07: propuesta IA en vuelo (botón deshabilitado)
        self._propose_worker: _ProposeWorker | None = None
        self.setMinimumWidth(480)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._build()

    def _close(self) -> None:
        if self._on_close:
            self._on_close()

    # ── datos ────────────────────────────────────────────────────────────

    def _findings(self) -> list[Any]:
        res = self._service.analyze()
        return list(res.value) if isinstance(res, Ok) else []

    def _structures(self) -> list[Any]:
        return list(self._service.structure_proposals())

    # ── construcción ─────────────────────────────────────────────────────

    def _build(self) -> None:
        while self._outer.count():
            item = self._outer.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        findings = self._findings()
        structures = self._structures()
        total = len(findings) + len(structures)
        scaffold = PanelScaffold("Ajustes estructurales", badge=str(total), badge_tone="gold")
        self._outer.addWidget(scaffold)
        body = scaffold.body

        top = QHBoxLayout()
        propose = QPushButton(
            "Proponiendo…" if self._proposing else "✨ Proponer estructura (IA)"
        )
        propose.setToolTip("La IA propone crear/fusionar anillos (necesita proveedor)")
        propose.setEnabled(not self._proposing)  # SHIP-07: sin doble disparo mientras corre
        propose.clicked.connect(self._propose_structure)
        top.addWidget(propose)
        top.addStretch(1)
        close = QPushButton("Cerrar")
        close.setToolTip("Cerrar el panel")
        close.clicked.connect(self._close)
        top.addWidget(close)
        body.addLayout(top)

        if self._status_text:
            status = QLabel(self._status_text)
            status.setObjectName("mutedLabel")
            status.setWordWrap(True)
            body.addWidget(status)

        if total == 0:
            empty = QLabel(
                "No hay ajustes estructurales pendientes.\n"
                "Riega entidades para que la IA atribuya su potencial (aparecerán movimientos de "
                "anillo), o pulsa «Proponer estructura» para que proponga crear/fusionar anillos."
            )
            empty.setObjectName("mutedLabel")
            empty.setWordWrap(True)
            body.addWidget(empty)
            body.addStretch(1)
            return

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        rows = QVBoxLayout(holder)
        rows.setContentsMargins(0, 0, 0, 0)
        moves = [f for f in findings if getattr(f, "kind", "") != "ascending_exception"]
        ascents = [f for f in findings if getattr(f, "kind", "") == "ascending_exception"]
        if structures:
            rows.addWidget(self._section_label("Estructura de anillos (IA)"))
            for finding in structures:
                rows.addWidget(self._row(finding, structure=True))
        if moves:
            rows.addWidget(self._section_label("Reubicaciones por potencial"))
            for finding in moves:
                rows.addWidget(self._row(finding, structure=False))
        if ascents:
            rows.addWidget(self._section_label("Excepciones ascendentes"))
            for finding in ascents:
                rows.addWidget(self._row(finding, structure=False))
        rows.addStretch(1)
        scroll.setWidget(holder)
        body.addWidget(scroll, 1)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("overline")
        return label

    def _row(self, finding: Any, *, structure: bool) -> QWidget:
        frame = QFrame()
        frame.setObjectName("card")
        col = QVBoxLayout(frame)
        title = QLabel(getattr(finding, "title", "") or "Ajuste estructural")
        title.setObjectName("h3")
        title.setWordWrap(True)
        col.addWidget(title)
        justification = QLabel(self._service.baseline_justification(finding))
        justification.setObjectName("mutedLabel")
        justification.setWordWrap(True)
        col.addWidget(justification)

        actions = QHBoxLayout()
        refine = QPushButton("✨ Afinar (IA)")
        refine.setToolTip("Redacta la justificación con IA si hay proveedor configurado")
        refine.clicked.connect(lambda: self._refine(finding, justification))
        actions.addWidget(refine)
        actions.addStretch(1)
        if not structure:
            postpone = QPushButton("Aplazar")
            postpone.clicked.connect(lambda: self._postpone(finding))
            actions.addWidget(postpone)
        reject = QPushButton("Rechazar")
        reject.clicked.connect(lambda: self._reject(finding, structure=structure))
        accept = QPushButton("Aceptar")
        accept.setObjectName("primaryButton")
        accept.clicked.connect(lambda: self._accept(finding, structure=structure))
        actions.addWidget(reject)
        actions.addWidget(accept)
        col.addLayout(actions)
        return frame

    # ── acciones ─────────────────────────────────────────────────────────

    def _propose_structure(self) -> None:
        # SHIP-07: la llamada al proveedor va en un hilo — antes era síncrona y
        # congelaba toda la ventana (hasta 300 s) sin ningún indicador.
        if self._proposing:
            return
        self._proposing = True
        self._status_text = "Proponiendo estructura… la IA está pensando (puede tardar)."
        self._build()
        worker = _ProposeWorker(self._service)
        worker.done.connect(self._on_propose_done)
        worker.finished.connect(worker.deleteLater)
        self._propose_worker = worker
        # WS-F: registrar para el apagado ordenado; sin esto, cerrar la app (o el panel)
        # con la llamada HTTP en vuelo destruía un QThread corriendo → aborto del proceso.
        track_worker(worker)
        worker.start()

    @_qt_safe_slot
    def _on_propose_done(self, res: Any) -> None:
        self._proposing = False
        if isinstance(res, Ok):
            n = len(res.value)
            self._status_text = (
                f"La IA propuso {n} cambio(s) de estructura."
                if n
                else "La IA no ve cambios de estructura necesarios ahora mismo."
            )
        elif isinstance(res, Exception):
            self._status_text = f"No se pudo proponer estructura: {res}"
        else:
            self._status_text = getattr(res, "error", "No se pudo proponer estructura.")
        self._build()

    def _refine(self, finding: Any, label: QLabel) -> None:
        res = self._service.enrich_justification(finding)
        if isinstance(res, Ok) and res.value:
            label.setText(res.value)

    def _accept(self, finding: Any, *, structure: bool) -> None:
        try:
            self._on_accept(finding)
        except Exception as exc:  # noqa: BLE001 — nunca deja el panel roto
            if self._log:
                self._log("error", f"No se pudo aplicar el ajuste estructural: {exc}")
        if structure:
            self._service.discard_structure_proposal(getattr(finding, "fingerprint", ""))
        self._build()

    def _postpone(self, finding: Any) -> None:
        self._service.postpone(getattr(finding, "fingerprint", ""))
        self._build()

    def _reject(self, finding: Any, *, structure: bool) -> None:
        fingerprint = getattr(finding, "fingerprint", "")
        if structure:
            self._service.discard_structure_proposal(fingerprint)
        else:
            self._service.dismiss(fingerprint)
        self._build()
