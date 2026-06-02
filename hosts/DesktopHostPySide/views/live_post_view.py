"""LivePostView — live mode + post-session actions (B27.3/B31)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
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
        self.session_sel = QComboBox()
        layout.addWidget(QLabel("Sesión:"))
        layout.addWidget(self.session_sel)
        btn_r = QPushButton("Refrescar sesiones")
        btn_r.clicked.connect(self.refresh)
        layout.addWidget(btn_r)

        tabs = QTabWidget()
        live = QWidget()
        ll = QVBoxLayout(live)
        for label, handler in [
            ("Open/Activate", self._live_open),
            ("Quick Note", self._live_note),
            ("Player Decision", self._live_decide),
            ("Event", self._live_event),
            ("Consequence", self._live_consequence),
            ("Entity (provisional)", self._live_entity),
            ("Relation (provisional)", self._live_relation),
            ("Clue Deliver", self._live_clue),
            ("Secret Reveal", self._live_secret),
            ("Improvise", self._live_improvise),
            ("Done", self._live_done),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            ll.addWidget(btn)
        self.live_output = QTextEdit()
        self.live_output.setReadOnly(True)
        self.live_output.setMaximumHeight(110)
        ll.addWidget(self.live_output)
        tabs.addTab(live, "Live")

        post = QWidget()
        pl = QVBoxLayout(post)
        for label, handler in [
            ("Close Session", self._post_close),
            ("Private summary", self._post_private_summary),
            ("Player summary", self._post_public_summary),
            ("Generate Candidates", self._post_candidates),
            ("Accept", self._post_accept),
            ("Reject", self._post_reject),
            ("Source", self._post_source),
            ("Seeds", self._post_seeds),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            pl.addWidget(btn)
        self.cand_combo = QComboBox()
        pl.addWidget(QLabel("Candidate:"))
        pl.addWidget(self.cand_combo)
        self.post_output = QTextEdit()
        self.post_output.setReadOnly(True)
        self.post_output.setMaximumHeight(110)
        pl.addWidget(self.post_output)
        tabs.addTab(post, "Post")
        layout.addWidget(tabs)

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
        if sid:
            self.ctx.selected_session_id = sid
            self._show_result(self.live_output, self.lmc.activate(sid), lambda session: f"Activated: {session.name}")

    def _live_note(self):
        sid = self._sid()
        if sid:
            self._prompt_text("Quick Note", "Text:", lambda text: self._show_result(self.live_output, self.lmc.note(sid, text), lambda _: "Note added"))

    def _live_decide(self):
        sid = self._sid()
        if sid:
            self._prompt_text("Player Decision", "Text:", lambda text: self._show_result(self.live_output, self.lmc.decision(sid, text), lambda _: "Player decision registered"))

    def _live_event(self):
        sid = self._sid()
        if sid:
            self._prompt_text("Event", "Text:", lambda text: self._show_result(self.live_output, self.lmc.event(sid, text), lambda _: "Event registered"))

    def _live_consequence(self):
        sid = self._sid()
        if sid:
            self._prompt_text("Consequence", "Text:", lambda text: self._show_result(self.live_output, self.lmc.consequence(sid, text), lambda _: "Consequence registered"))

    def _live_entity(self):
        sid = self._sid()
        if sid:
            result = self.lmc.entity(sid, "Improvised NPC", "personaje")
            self._show_result(self.live_output, result, lambda entity: f"Created entity: {entity.name}")

    def _live_relation(self):
        sid = self._sid()
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
        if not sid:
            return
        clues = self.lmc.query_clues(sid)
        if isinstance(clues, Error) or not clues.value:
            self.live_output.setText("No clues linked to session")
            return
        options = [(clue.content[:50], clue.id) for clue in clues.value]
        self._prompt_select("Deliver Clue", "Clue:", options, lambda clue_id: self._show_result(self.live_output, self.lmc.clue_deliver(sid, clue_id, "entregada"), lambda _: "Delivered clue"))

    def _live_secret(self):
        sid = self._sid()
        if not sid:
            return
        secrets = self.lmc.query_secrets(sid)
        if isinstance(secrets, Error) or not secrets.value:
            self.live_output.setText("No secrets linked to session")
            return
        options = [(secret.content[:50], secret.id) for secret in secrets.value]
        self._prompt_select("Reveal Secret", "Secret:", options, lambda secret_id: self._show_result(self.live_output, self.lmc.secret_reveal(sid, secret_id, "parcialmente_revelado"), lambda _: "Revealed secret"))

    def _live_improvise(self):
        sid = self._sid()
        if sid:
            result = self.lmc.improvise(sid, "fantasy scene", True)
            self._show_result(self.live_output, result, lambda data: f"{data.get('name', '?')}\n{data.get('description', '?')}")

    def _live_done(self):
        sid = self._sid()
        if sid:
            result = self.lmc.done(sid)
            self._show_result(
                self.live_output,
                result,
                lambda data: f"Post material: notes={len(data.get('quick_notes', []))}, events={len(data.get('events', []))}, clues={len(data.get('clues_delivered', []))}, secrets={len(data.get('secrets_revealed', []))}",
            )

    def _post_close(self):
        sid = self._sid()
        if sid:
            self._show_result(self.post_output, self.psc.close(sid), lambda session: f"Closed: {session.state.value}")

    def _post_private_summary(self):
        sid = self._sid()
        if sid:
            self._show_result(self.post_output, self.psc.private_summary(sid), lambda text: text)

    def _post_public_summary(self):
        sid = self._sid()
        if sid:
            self._show_result(self.post_output, self.psc.public_summary(sid), lambda text: text)

    def _post_candidates(self):
        sid = self._sid()
        if not sid:
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
        if cid:
            self._show_result(self.post_output, self.psc.accept_candidate(cid), lambda entity: f"Accepted: {entity.name}")

    def _post_reject(self):
        cid = self.cand_combo.currentData()
        if cid:
            self._show_result(self.post_output, self.psc.reject_candidate(cid), lambda _: "Rejected")

    def _post_source(self):
        sid = self._sid()
        if sid:
            self._show_result(self.post_output, self.psc.source(sid), lambda source: f"Source: {source.title}")

    def _post_seeds(self):
        sid = self._sid()
        if sid:
            self._show_result(self.post_output, self.psc.seeds(sid), lambda seeds: str(seeds))
