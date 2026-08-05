"""Visor/EDITOR editorial de la wiki de Memoria (BETA2-MEM-10 + BETA-MULTIAGENT2-FIX-11).

Función de PROYECTO (no del flujo de Creación): consultar, **escribir**, crear,
borrar y regenerar páginas de la wiki. Leer/escribir/crear/borrar funcionan SIN
IA (servicio determinista); regenerar requiere proveedor IA y muestra un diff
revisable antes de sustituir (``MemoryRevisionProposal``). La UI nunca escribe
persistencia: todo pasa por ``NarrativeMemoryService`` / ``MemoryAIService``, y
el guardado a disco se PIDE (``ctx.request_save_silent``), no se hace aquí.

FIX-11 (fase C): antes el cuerpo era ``setReadOnly(True)`` («lo escribe Regar»),
``_save`` ni siquiera mandaba ``cuerpo=`` y no había forma de crear una página:
quien no usa IA no podía usar la wiki. Ahora el cuerpo se edita, hay «Nueva
página» (elección del elemento POR NOMBRE) y las páginas se listan por el nombre
del elemento, no por ``entity:<uuid>``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
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
from packages.domain.narrative_memory import MemoryFreshness, MemoryOrigin, MemoryTargetKind
from packages.domain.result import Error, Ok

_FRESHNESS_LABEL = {
    MemoryFreshness.REGADA.value: "vigente",
    MemoryFreshness.FALTA_REGAR.value: "falta regar",
    MemoryFreshness.SECADA.value: "secada",
    MemoryFreshness.SIN_MEMORIA.value: "sin memoria",
}

_KIND_LABEL = {
    MemoryTargetKind.PROJECT.value: "Proyecto",
    MemoryTargetKind.ENTITY.value: "Elemento",
    MemoryTargetKind.BRANCH.value: "Rama",
    MemoryTargetKind.RELATION.value: "Relación",
    MemoryTargetKind.MILESTONE.value: "Hito",
    MemoryTargetKind.RING.value: "Anillo",
}


def _entity_name(project, entity_id: str) -> str:
    if project is None or not entity_id:
        return ""
    getter = getattr(project, "entity_by_id", None)
    entity = getter(entity_id) if callable(getter) else None
    return str(getattr(entity, "name", "") or "") if entity is not None else ""


def element_label(project, kind: str, target_id: str) -> str:
    """Nombre humano del elemento de una página (o un rastro corto si ya no existe).

    FIX-11: función de módulo para que la comparta la pantalla «Salud del proyecto»
    (el lint tampoco puede enseñar uuids en la cara del usuario).
    """
    kind = str(kind)
    if kind == MemoryTargetKind.PROJECT.value or not target_id:
        return str(getattr(project, "name", "") or "Proyecto")
    if project is not None:
        if kind in (MemoryTargetKind.ENTITY.value, MemoryTargetKind.BRANCH.value):
            name = _entity_name(project, target_id)
            if name:
                return name
        elif kind == MemoryTargetKind.RELATION.value:
            getter = getattr(project, "relation_by_id", None)
            relation = getter(target_id) if callable(getter) else None
            if relation is not None:
                src = _entity_name(project, getattr(relation, "source_id", "")) or "?"
                tgt = _entity_name(project, getattr(relation, "target_id", "")) or "?"
                return f"{src} → {tgt}"
        elif kind == MemoryTargetKind.MILESTONE.value:
            for hito in getattr(project, "causal_milestones", []) or []:
                if getattr(hito, "id", "") == target_id:
                    return str(getattr(hito, "title", "") or "Hito sin título")
        elif kind == MemoryTargetKind.RING.value:
            for layer in getattr(project, "world_layers", []) or []:
                if getattr(layer, "id", "") == target_id:
                    return str(getattr(layer, "name", "") or "Anillo")
    # Página huérfana: el elemento ya no existe. Se dice, no se enseña el uuid.
    return f"(elemento eliminado · {target_id[:8]})"


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
    """Visor/editor de la wiki de Memoria del proyecto (Configuración)."""

    def __init__(
        self,
        memory_service: Any,
        memory_ai_service: Any = None,
        ctx: Any = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.memory_service = memory_service
        self.memory_ai_service = memory_ai_service
        self.ctx = ctx
        self._current_key: tuple[str, str, str] | None = None
        self._regen_worker: _RegenWorker | None = None
        # FIX-07 (criterio 4): recuento de enlaces de la última regeneración, para
        # que lo descartado no se pierda en silencio. (clave de página, conteos).
        self._last_refs: tuple[tuple[str, str, str], dict] | None = None

        root = QHBoxLayout(self)

        # Izquierda: lista de páginas (global + por elemento) + «Nueva página».
        left = QVBoxLayout()
        left.addWidget(overline_label("PÁGINAS DE LA WIKI"))
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_select)
        left.addWidget(self.list, 1)

        self.new_page_btn = QPushButton("Nueva página")
        self.new_page_btn.setToolTip(
            "Crea a mano la página de un elemento del proyecto (no necesita IA)."
        )
        self.new_page_btn.clicked.connect(self._toggle_new_page)
        left.addWidget(self.new_page_btn)

        self.new_page_row = QWidget(self)
        row_layout = QHBoxLayout(self.new_page_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        self.new_page_combo = QComboBox()
        self.new_page_combo.setToolTip("Elige el elemento por su nombre")
        row_layout.addWidget(self.new_page_combo, 1)
        self.create_page_btn = QPushButton("Crear")
        self.create_page_btn.clicked.connect(self._confirm_new_page)
        row_layout.addWidget(self.create_page_btn)
        self.new_page_row.setVisible(False)
        left.addWidget(self.new_page_row)
        root.addLayout(left, 1)

        # Derecha: visor editorial de la página seleccionada.
        right = QVBoxLayout()
        self.header = QLabel("Selecciona una página")
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

        # FIX-11 (fase C): el CUERPO de la página de wiki se EDITA. La escribe la
        # IA al Regar, pero también la mano del autor: sin proveedor de IA esta es
        # la única forma de tener wiki, y el servicio ya la soportaba entera.
        right.addWidget(overline_label("CUERPO (PÁGINA WIKI)"))
        self.cuerpo = QTextEdit()
        self.cuerpo.setPlaceholderText(
            "Escribe aquí la página: qué es, qué hace, qué la contradice…"
        )
        self.cuerpo.setStyleSheet(
            f"QTextEdit {{ font-family: {FONT_SERIF}; font-size: 13px; color: {INK_STRONG}; "
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

    # ── nombres legibles (nunca uuid en la cara del usuario) ─────────────

    def _project(self):
        ps = getattr(self.memory_service, "project_service", None)
        return getattr(ps, "active_project", None)

    def _entity_name(self, entity_id: str) -> str:
        return _entity_name(self._project(), entity_id)

    def element_label(self, kind: str, target_id: str) -> str:
        """Nombre humano del elemento de una página (o un rastro corto si ya no existe)."""
        return element_label(self._project(), kind, target_id)

    def _page_title(self, block) -> str:
        kind = block.target_kind.value
        label = self.element_label(kind, block.target_id)
        prefix = _KIND_LABEL.get(kind, "Página")
        if kind == MemoryTargetKind.PROJECT.value or not block.target_id:
            return f"{label} (visión global)"
        return f"{label} · {prefix.lower()}"

    # ── datos ────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        result = self.memory_service.list_memories()
        blocks = result.value if isinstance(result, Ok) else []
        for block in blocks:
            fresh = _FRESHNESS_LABEL.get(block.freshness.value, block.freshness.value)
            item = QListWidgetItem(f"{self._page_title(block)}  ·  {fresh}")
            item.setData(Qt.ItemDataRole.UserRole, block.target_key())
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._refresh_new_page_combo()

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

    def select_page(self, key) -> bool:
        """Selecciona la página (kind, target_id, context). Usado por Salud del proyecto."""
        if key is None:
            return False
        wanted = tuple(key)
        for row in range(self.list.count()):
            item = self.list.item(row)
            if tuple(item.data(Qt.ItemDataRole.UserRole)) == wanted:
                self.list.setCurrentRow(row)
                return True
        return False

    def _refs_note(self) -> str:
        """Qué pasó con los enlaces en la última regeneración de ESTA página.

        FIX-07 (criterio 4): la app resuelve los enlaces contra el canon antes de
        persistirlos y tira los que no existen. Ese descarte se DICE — la lección
        de G2-03 es que lo que se cae en silencio se convierte en una mentira
        silenciosa. Solo aparece cuando hubo algo que contar.
        """
        if self._last_refs is None or self._last_refs[0] != self._current_key:
            return ""
        conteos = self._last_refs[1] or {}
        ambiguos = int(conteos.get("ambiguos", 0) or 0)
        descartados = int(conteos.get("descartados", 0) or 0)
        if not ambiguos and not descartados:
            return ""
        partes = []
        if descartados:
            partes.append(f"{descartados} sin elemento en el canon")
        if ambiguos:
            partes.append(f"{ambiguos} con nombre duplicado")
        return f" · última regeneración: {', '.join(partes)} (enlaces descartados)"

    def _load(self) -> None:
        block = self._current_block()
        has_pending = bool(block and block.pending_revision is not None)
        if block is None:
            self.header.setText("Selecciona una página")
            self.freshness.setText("")
            self.resumen.setPlainText("")
            self.cuerpo.setPlainText("")
        else:
            self.header.setText(self._page_title(block))
            origin = getattr(getattr(block, "origin", None), "value", "")
            autoria = (
                "escrita a mano"
                if origin == MemoryOrigin.USUARIO.value
                else f"origen: {origin}"
            )
            self.freshness.setText(
                f"Estado: {_FRESHNESS_LABEL.get(block.freshness.value, block.freshness.value)}"
                f" · {autoria} · Fuentes: {len(block.citations)}"
                f" · Enlaces: {len(block.wikilinks)}{self._refs_note()}"
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

    # ── nueva página (sin IA) ────────────────────────────────────────────

    def _existing_keys(self) -> set[tuple[str, str, str]]:
        return {block.target_key() for block in self._blocks()}

    def available_targets(self) -> list[tuple[str, str, str]]:
        """Elementos del proyecto SIN página todavía: [(etiqueta, kind, target_id)]."""
        proj = self._project()
        existing = self._existing_keys()
        targets: list[tuple[str, str, str]] = []

        def _add(kind: str, target_id: str, label: str) -> None:
            if (kind, target_id, "") in existing:
                return
            targets.append((label, kind, target_id))

        if proj is None:
            return targets
        _add(
            MemoryTargetKind.PROJECT.value,
            "",
            f"Proyecto · {getattr(proj, 'name', '') or 'visión global'}",
        )
        for entity in getattr(proj, "entities", []) or []:
            name = str(getattr(entity, "name", "") or "sin nombre")
            _add(MemoryTargetKind.ENTITY.value, getattr(entity, "id", ""), f"{name}")
        for relation in getattr(proj, "relations", []) or []:
            src = self._entity_name(getattr(relation, "source_id", "")) or "?"
            tgt = self._entity_name(getattr(relation, "target_id", "")) or "?"
            _add(
                MemoryTargetKind.RELATION.value,
                getattr(relation, "id", ""),
                f"{src} → {tgt} · relación",
            )
        for hito in getattr(proj, "causal_milestones", []) or []:
            title = str(getattr(hito, "title", "") or "hito sin título")
            _add(MemoryTargetKind.MILESTONE.value, getattr(hito, "id", ""), f"{title} · hito")
        for layer in getattr(proj, "world_layers", []) or []:
            name = str(getattr(layer, "name", "") or "anillo")
            _add(MemoryTargetKind.RING.value, getattr(layer, "id", ""), f"{name} · anillo")
        return targets

    def _refresh_new_page_combo(self) -> None:
        combo = getattr(self, "new_page_combo", None)
        if combo is None:
            return
        combo.blockSignals(True)
        combo.clear()
        for label, kind, target_id in self.available_targets():
            combo.addItem(label, (kind, target_id))
        combo.blockSignals(False)
        enabled = combo.count() > 0
        self.create_page_btn.setEnabled(enabled)
        if not enabled:
            self.create_page_btn.setToolTip("Todos los elementos tienen ya su página.")

    def _toggle_new_page(self) -> None:
        self._refresh_new_page_combo()
        # isHidden(), no isVisible(): el marcador explícito no depende de que la
        # ventana esté mostrada (isVisible() es False mientras el panel no se pinta).
        self.new_page_row.setVisible(self.new_page_row.isHidden())

    def _confirm_new_page(self) -> None:
        data = self.new_page_combo.currentData()
        if not data:
            return
        kind, target_id = data
        self.create_page(kind, target_id)

    def create_page(self, kind: str, target_id: str, context: str = "") -> bool:
        """Crea (a mano, sin IA) la página del elemento y la deja seleccionada."""
        result = self.memory_service.upsert_memory(
            MemoryTargetKind(kind),
            target_id,
            context,
            resumen_editorial="",
            cuerpo="",
            origin=MemoryOrigin.USUARIO,
            causa="página creada a mano desde la wiki",
        )
        if not isinstance(result, Ok):
            QMessageBox.warning(
                self, "Nueva página", str(getattr(result, "error", "No se pudo crear la página"))
            )
            return False
        self._request_save()
        self.new_page_row.setVisible(False)
        self.refresh()
        self._current_key = (str(kind), str(target_id), str(context))
        self.select_page(self._current_key)
        self._load()
        return True

    # ── acciones (vía servicio) ──────────────────────────────────────────

    def _request_save(self) -> None:
        """Programa el guardado a disco (la UI nunca escribe persistencia)."""
        ctx = getattr(self, "ctx", None)
        if ctx is None:
            return
        save = getattr(ctx, "request_save_silent", None)
        if callable(save):
            save()
            return
        deferred = getattr(ctx, "request_save_debounced", None)
        if callable(deferred):
            deferred()

    def _save(self) -> None:
        if self._current_key is None:
            return
        kind, tid, ctx = self._current_key
        result = self.memory_service.upsert_memory(
            MemoryTargetKind(kind),
            tid,
            ctx,
            resumen_editorial=self.resumen.toPlainText(),
            cuerpo=self.cuerpo.toPlainText(),
            origin=MemoryOrigin.USUARIO,
            # FIX-11 (criterio 4): lo que acaba de escribir la mano del autor está
            # VIGENTE. Además de ser honesto, es lo que impide que Regar la pise
            # (``watering_service`` no regenera una página REGADA). La vía
            # explícita para reescribirla sigue siendo «Regenerar con IA».
            freshness=MemoryFreshness.REGADA,
            causa="edición manual desde la wiki",
        )
        if not isinstance(result, Ok):
            QMessageBox.warning(
                self, "Guardar página", str(getattr(result, "error", "No se pudo guardar"))
            )
            return
        # FIX-11: la edición manual PROGRAMA guardado a disco. Antes vivía solo en
        # memoria hasta que otra mutación cualquiera disparaba el autoguardado.
        self._request_save()
        self.refresh()
        self.select_page(self._current_key)

    def _delete(self) -> None:
        if self._current_key is None:
            return
        confirm = QMessageBox.question(
            self,
            "Borrar página",
            "¿Borrar esta página de la wiki? (No afecta al canon.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        kind, tid, ctx = self._current_key
        self.memory_service.delete_memory(MemoryTargetKind(kind), tid, ctx)
        self._request_save()
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
        # FIX-07: guarda el recuento de enlaces resueltos/ambiguos/descartados de
        # esta regeneración para poder contarlo en la cabecera de la página.
        conteos = result.value.get("refs") if isinstance(result.value, dict) else None
        self._last_refs = (self._current_key, dict(conteos)) if conteos else None
        self.refresh()
        self._reselect()
        self._load()

    def _accept_proposal(self) -> None:
        if self._current_key is None:
            return
        kind, tid, ctx = self._current_key
        self.memory_service.apply_revision_proposal(MemoryTargetKind(kind), tid, ctx)
        self._request_save()
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


__all__ = ["MemoryViewerPanel", "element_label"]
