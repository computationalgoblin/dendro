"""LivePostView — live mode + post-session actions (B27.3/B31)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.session_controller import SessionController
from hosts.DesktopHostPySide.widgets.drawer_forms import DrawerSelectPrompt, DrawerTextPrompt
from hosts.DesktopHostPySide.widgets.design_system import Badge, Card, EmptyState, SectionHeader
from packages.domain.result import Error


class LivePostView(QWidget):
    def __init__(self, ctx: AppContext, sc: SessionController, lmc=None, psc=None):
        super().__init__()
        self.ctx = ctx
        self.sc = sc
        self.lmc = lmc
        self.psc = psc
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(SectionHeader(
            "En vivo / Post",
            "Dirección de sesión dentro de la ventana principal. La IA es opcional; los candidatos post-sesión son revisables."
        ))

        session_row = QHBoxLayout()
        session_row.addWidget(QLabel("Sesión:"))
        self.session_sel = QComboBox()
        session_row.addWidget(self.session_sel, 1)
        btn_r = QPushButton("Refrescar")
        btn_r.clicked.connect(self.refresh)
        session_row.addWidget(btn_r)
        layout.addLayout(session_row)

        self.tabs = QTabWidget()
        live = QWidget()
        ll = QVBoxLayout(live)
        ll.setContentsMargins(12, 12, 12, 12)
        live_card = Card("Sesión activa", "Registra notas, decisiones, eventos y consecuencias sin salir del espacio narrativo.")
        status_row = live_card.add_row()
        self.live_status = QLabel("Pendiente de activar")
        self.live_status.setObjectName("mutedLabel")
        status_row.addWidget(Badge("Live", "info"))
        status_row.addWidget(self.live_status, 1)
        control_specs = [
            ("Activar", self._live_open, "success"),
            ("Nota rápida", self._live_note, "info"),
            ("Decisión PJ", self._live_decide, "info"),
            ("Evento", self._live_event, "warning"),
            ("Consecuencia", self._live_consequence, "warning"),
            ("Entregar pista", self._live_clue, "success"),
            ("Revelar secreto", self._live_secret, "danger"),
            ("Improvisar", self._live_improvise, "info"),
            ("Cerrar live", self._live_done, "neutral"),
        ]
        row = live_card.add_row()
        for idx, (label, handler, _tone) in enumerate(control_specs):
            if idx and idx % 3 == 0:
                row = live_card.add_row()
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            row.addWidget(btn)
        self.live_output = QTextEdit()
        self.live_output.setReadOnly(True)
        self.live_output.setPlaceholderText("Aquí aparecerá el último resultado live.")
        self.live_output.setMaximumHeight(130)
        live_card.layout.addWidget(self.live_output)
        ll.addWidget(live_card)
        ll.addWidget(EmptyState("Material provisional", "Entidades/relaciones improvisadas siguen en los servicios live existentes y pasan por revisión post-sesión."))
        ll.addStretch()
        self.tabs.addTab(live, "Live")

        post = QWidget()
        pl = QVBoxLayout(post)
        pl.setContentsMargins(12, 12, 12, 12)
        post_card = Card("Post-sesión", "Genera resúmenes, semillas y candidatos revisables desde el material live registrado.")
        post_row = post_card.add_row()
        for idx, (label, handler) in enumerate([
            ("Cerrar sesión", self._post_close),
            ("Resumen GM", self._post_private_summary),
            ("Resumen jugadores", self._post_public_summary),
            ("Generar candidatos", self._post_candidates),
            ("Fuente", self._post_source),
            ("Semillas", self._post_seeds),
        ]):
            if idx and idx % 3 == 0:
                post_row = post_card.add_row()
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            post_row.addWidget(btn)
        cand_row = post_card.add_row()
        cand_row.addWidget(QLabel("Candidato:"))
        self.cand_combo = QComboBox()
        cand_row.addWidget(self.cand_combo, 1)
        accept_btn = QPushButton("Aceptar")
        accept_btn.clicked.connect(self._post_accept)
        reject_btn = QPushButton("Rechazar")
        reject_btn.clicked.connect(self._post_reject)
        cand_row.addWidget(accept_btn)
        cand_row.addWidget(reject_btn)
        self.post_output = QTextEdit()
        self.post_output.setReadOnly(True)
        self.post_output.setPlaceholderText("Aquí aparecerán resumen, semillas o candidatos generados.")
        self.post_output.setMaximumHeight(150)
        post_card.layout.addWidget(self.post_output)
        pl.addWidget(post_card)
        pl.addWidget(EmptyState("IA opcional", "Si no hay proveedor IA, los servicios generan material determinista desde notas, eventos y consecuencias."))
        pl.addStretch()
        self.tabs.addTab(post, "Post")
        layout.addWidget(self.tabs, 1)

    def _sid(self):
        return self.session_sel.currentData()

    def _show_result(self, output, result, success_label):
        if isinstance(result, Error):
            output.setText(f"Error: {result.error}")
            self.ctx.log("error", result.error)
            return None
        output.setText(success_label(result.value))
        return result.value

    def _prompt_text(self, title: str, label: str, callback):
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = DrawerTextPrompt(self.ctx, title, label, callback)
        drawer.set_content(form, title=title)
        drawer.open()

    def _prompt_select(self, title: str, label: str, options, callback):
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = DrawerSelectPrompt(self.ctx, title, label, options, callback)
        drawer.set_content(form, title=title)
        drawer.open()

    def refresh(self):
        current = self._sid()
        self.session_sel.clear()
        for session in self.sc.list_all():
            self.session_sel.addItem(session.name, session.id)
        target = self.ctx.selected_session_id or current
        if target:
            idx = self.session_sel.findData(target)
            if idx >= 0:
                self.session_sel.setCurrentIndex(idx)

    def _live_open(self):
        sid = self._sid()
        if sid and self.lmc is not None:
            self.ctx.selected_session_id = sid
            self._show_result(self.live_output, self.lmc.activate(sid), lambda session: f"Activada: {session.name}")
            self.live_status.setText("Activa")
        elif self.lmc is None:
            self.live_output.setText("Servicio live no disponible; la aplicación sigue funcionando sin IA/live opcional.")

    def _live_note(self):
        sid = self._sid()
        if sid and self.lmc is not None:
            self._prompt_text("Quick Note", "Text:", lambda text: self._show_result(self.live_output, self.lmc.note(sid, text), lambda _: "Note added"))

    def _live_decide(self):
        sid = self._sid()
        if sid and self.lmc is not None:
            self._prompt_text("Player Decision", "Text:", lambda text: self._show_result(self.live_output, self.lmc.decision(sid, text), lambda _: "Player decision registered"))

    def _live_event(self):
        sid = self._sid()
        if sid and self.lmc is not None:
            self._prompt_text("Event", "Text:", lambda text: self._show_result(self.live_output, self.lmc.event(sid, text), lambda _: "Event registered"))

    def _live_consequence(self):
        sid = self._sid()
        if sid and self.lmc is not None:
            self._prompt_text("Consequence", "Text:", lambda text: self._show_result(self.live_output, self.lmc.consequence(sid, text), lambda _: "Consequence registered"))

    def _live_entity(self):
        sid = self._sid()
        if sid and self.lmc is not None:
            result = self.lmc.entity(sid, "Improvised NPC", "personaje")
            self._show_result(self.live_output, result, lambda entity: f"Created entity: {entity.name}")

    def _live_relation(self):
        sid = self._sid()
        if self.lmc is None:
            self.live_output.setText("Servicio live no disponible.")
            return
        project = self.sc.ps.active_project
        if not sid or project is None or len(project.entities) < 2:
            self.live_output.setText("Need at least two entities")
            return
        src = project.entities[0].id
        tgt = project.entities[1].id
        result = self.lmc.relation(sid, src, tgt, "es_aliado_de")
        self._show_result(self.live_output, result, lambda _: "Created relation")

    def _live_clue(self):
        sid = self._sid()
        if not sid or self.lmc is None:
            self.live_output.setText("Servicio live no disponible o sesión no seleccionada.")
            return
        clues = self.lmc.query_clues(sid)
        if isinstance(clues, Error) or not clues.value:
            self.live_output.setText("No clues linked to session")
            return
        options = [(clue.content[:50], clue.id) for clue in clues.value]
        self._prompt_select("Deliver Clue", "Clue:", options, lambda clue_id: self._show_result(self.live_output, self.lmc.clue_deliver(sid, clue_id, "entregada"), lambda _: "Delivered clue"))

    def _live_secret(self):
        sid = self._sid()
        if not sid or self.lmc is None:
            self.live_output.setText("Servicio live no disponible o sesión no seleccionada.")
            return
        secrets = self.lmc.query_secrets(sid)
        if isinstance(secrets, Error) or not secrets.value:
            self.live_output.setText("No secrets linked to session")
            return
        options = [(secret.content[:50], secret.id) for secret in secrets.value]
        self._prompt_select("Reveal Secret", "Secret:", options, lambda secret_id: self._show_result(self.live_output, self.lmc.secret_reveal(sid, secret_id, "parcialmente_revelado"), lambda _: "Revealed secret"))

    def _live_improvise(self):
        sid = self._sid()
        if sid and self.lmc is not None:
            result = self.lmc.improvise(sid, "fantasy scene", True)
            self._show_result(self.live_output, result, lambda data: f"{data.get('name', '?')}\n{data.get('description', '?')}")

    def _live_done(self):
        sid = self._sid()
        if sid and self.lmc is not None:
            result = self.lmc.done(sid)
            self._show_result(
                self.live_output,
                result,
                lambda data: f"Post material: notes={len(data.get('quick_notes', []))}, events={len(data.get('events', []))}, clues={len(data.get('clues_delivered', []))}, secrets={len(data.get('secrets_revealed', []))}",
            )

    def _post_close(self):
        sid = self._sid()
        if sid and self.psc is not None:
            self._show_result(self.post_output, self.psc.close(sid), lambda session: f"Closed: {session.state.value}")

    def _post_private_summary(self):
        sid = self._sid()
        if sid and self.psc is not None:
            self._show_result(self.post_output, self.psc.private_summary(sid), lambda text: text)

    def _post_public_summary(self):
        sid = self._sid()
        if sid and self.psc is not None:
            self._show_result(self.post_output, self.psc.public_summary(sid), lambda text: text)

    def _post_candidates(self):
        sid = self._sid()
        if not sid or self.psc is None:
            self.post_output.setText("Servicio post-sesión no disponible o sesión no seleccionada.")
            return
        first = self.psc.generate_candidates(sid)
        if isinstance(first, Error):
            self.post_output.setText(f"Error: {first.error}")
            self.ctx.log("error", first.error)
            return
        second = self.psc.generate_candidates(sid)
        self.cand_combo.clear()
        if not isinstance(second, Error):
            for c in second.value:
                self.cand_combo.addItem(c.title, c.id)
        self.post_output.setText("Candidates generated")

    def _post_accept(self):
        cid = self.cand_combo.currentData()
        if cid and self.psc is not None:
            self._show_result(self.post_output, self.psc.accept_candidate(cid), lambda entity: f"Accepted: {entity.name}")

    def _post_reject(self):
        cid = self.cand_combo.currentData()
        if cid and self.psc is not None:
            self._show_result(self.post_output, self.psc.reject_candidate(cid), lambda _: "Rejected")

    def _post_source(self):
        sid = self._sid()
        if sid and self.psc is not None:
            self._show_result(self.post_output, self.psc.source(sid), lambda source: f"Source: {source.title}")

    def _post_seeds(self):
        sid = self._sid()
        if sid and self.psc is not None:
            self._show_result(self.post_output, self.psc.seeds(sid), lambda seeds: str(seeds))
