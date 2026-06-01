"""LivePostView — live mode + post-session tabs (B27.1-T04)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
                                QLineEdit, QTextEdit, QLabel, QComboBox)
from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.session_controller import SessionController
from packages.domain.result import Error

class LivePostView(QWidget):
    def __init__(self, ctx: AppContext, sc: SessionController):
        super().__init__(); self.ctx = ctx; self.sc = sc; self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        self.session_sel = QComboBox()
        layout.addWidget(QLabel("Sesión:")); layout.addWidget(self.session_sel)
        btn_r = QPushButton("Refrescar sesiones"); btn_r.clicked.connect(self._refresh_sessions); layout.addWidget(btn_r)

        tabs = QTabWidget()

        # Live tab
        live = QWidget(); ll = QVBoxLayout(live)
        btns_live = [("Open/Activate", self._live_open), ("Quick Note", self._live_note),
                     ("Player Decision", self._live_decide), ("Event", self._live_event),
                     ("Consequence", self._live_consequence), ("Entity (provisional)", self._live_entity),
                     ("Clue Deliver", self._live_clue), ("Secret Reveal", self._live_secret),
                     ("Improvise", self._live_improvise), ("Done", self._live_done)]
        for label, fn in btns_live:
            b = QPushButton(label); b.clicked.connect(fn); ll.addWidget(b)
        self.live_output = QTextEdit(); self.live_output.setReadOnly(True); self.live_output.setMaximumHeight(80)
        ll.addWidget(self.live_output)
        tabs.addTab(live, "Live")

        # Post tab
        post = QWidget(); pl = QVBoxLayout(post)
        btns_post = [("Close Session", self._post_close), ("Generate Candidates", self._post_candidates),
                     ("Accept", self._post_accept), ("Reject", self._post_reject),
                     ("Source", self._post_source), ("Seeds", self._post_seeds)]
        for label, fn in btns_post:
            b = QPushButton(label); b.clicked.connect(fn); pl.addWidget(b)
        self.cand_combo = QComboBox(); pl.addWidget(QLabel("Candidate:")); pl.addWidget(self.cand_combo)
        self.post_output = QTextEdit(); self.post_output.setReadOnly(True); self.post_output.setMaximumHeight(80)
        pl.addWidget(self.post_output)
        tabs.addTab(post, "Post")

        layout.addWidget(tabs)

    def _refresh_sessions(self):
        self.session_sel.clear()
        for s in self.sc.list_all(): self.session_sel.addItem(f"{s.name} ({s.id[:8]})", s.id)
        if self.ctx.selected_session_id:
            idx = self.session_sel.findData(self.ctx.selected_session_id)
            if idx >= 0: self.session_sel.setCurrentIndex(idx)

    def _sid(self): return self.session_sel.currentData()

    def _live_open(self):
        sid = self._sid()
        if sid:
            r = self.sc.ls.activate_session(sid)
            self.live_output.setText(f"Activated: {r.value.name}" if not isinstance(r, Error) else f"Error: {r.error}")

    def _live_note(self):
        sid = self._sid(); text = "Quick note"
        if sid:
            r = self.sc.ls.quick_note(sid, text)
            self.live_output.setText("Note added" if not isinstance(r, Error) else f"Error: {r.error}")

    def _live_decide(self): self.live_output.setText("TODO: dialog for text input")
    def _live_event(self): self.live_output.setText("TODO: dialog for text input")
    def _live_consequence(self): self.live_output.setText("TODO: dialog for text input")

    def _live_entity(self):
        sid = self._sid()
        if sid:
            r = self.sc.ls.create_provisional_entity(sid, "Improvised NPC", "personaje")
            self.live_output.setText(f"Created: {r.value.name} ({r.value.id[:8]})" if not isinstance(r, Error) else f"Error: {r.error}")
            self.ctx.log("info", f"Provisional entity created")

    def _live_clue(self):
        sid = self._sid()
        if sid:
            r = self.sc.ls.mark_clue_delivered(sid, "any_clue", "entregada") if hasattr(self.sc.ls, 'mark_clue_delivered') else Error("TODO: clue selector")
            self.live_output.setText("Delivered" if not isinstance(r, Error) else f"Error/TODO: {r.error if isinstance(r, Error) else 'ok'}")

    def _live_secret(self): self.live_output.setText("TODO: secret selector")

    def _live_improvise(self):
        sid = self._sid()
        if sid:
            r = self.sc.ls.improvise(sid, "fantasy scene")
            if isinstance(r, Error): self.live_output.setText(f"Error: {r.error}")
            else:
                v = r.value; self.live_output.setText(f"Name: {v.get('name','?')}\nDesc: {v.get('description','?')}")

    def _live_done(self):
        sid = self._sid()
        if sid:
            r = self.sc.ls.prepare_post_session(sid)
            self.live_output.setText(f"Post material prepared" if not isinstance(r, Error) else f"Error: {r.error}")

    def _post_close(self):
        sid = self._sid()
        if sid:
            r = self.sc.ps2.close_session(sid)
            self.post_output.setText(f"Closed: {r.value.state.value}" if not isinstance(r, Error) else f"Error: {r.error}")

    def _post_candidates(self):
        sid = self._sid()
        if sid:
            r = self.sc.ps2.convert_live_to_candidates(sid)
            if isinstance(r, Error): self.post_output.setText(f"Error: {r.error}")
            else:
                self.cand_combo.clear()
                for c in r.value: self.cand_combo.addItem(f"{c.title} ({c.id[:8]})", c.id)
                self.post_output.setText(f"Generated {len(r.value)} candidates")

    def _post_accept(self):
        cid = self.cand_combo.currentData()
        if cid and hasattr(self.sc.ps, 'candidate_service'):
            self.sc.ps.candidate_service.accept_candidate(cid)
            self.post_output.setText(f"Accepted {cid}")
        else: self.post_output.setText("No candidate selected or service unavailable")

    def _post_reject(self):
        cid = self.cand_combo.currentData()
        if cid and hasattr(self.sc.ps, 'candidate_service'):
            self.sc.ps.candidate_service.reject_candidate(cid)
            self.post_output.setText(f"Rejected {cid}")

    def _post_source(self):
        sid = self._sid()
        if sid:
            r = self.sc.ps2.create_session_source(sid)
            self.post_output.setText(f"Source created" if not isinstance(r, Error) else f"Error: {r.error}")

    def _post_seeds(self):
        sid = self._sid()
        if sid:
            seeds = self.sc.ps2.generate_next_session_seeds(sid)
            self.post_output.setText("\n".join(seeds[:5]))
