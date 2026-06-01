from packages.application.live_mode_service import LiveModeService
class LiveModeController:
    def __init__(self, project_service=None, session_service=None): self.ps = project_service; self.ss = session_service; self.svc = LiveModeService(project_service=self.ps, session_service=self.ss)
    def activate(self, sid): return self.svc.activate_session(sid)
    def note(self, sid, text): return self.svc.quick_note(sid, text)
    def entity(self, sid, name, etype): return self.svc.create_provisional_entity(sid, name, etype)
    def clue_deliver(self, sid, cid): return self.svc.mark_clue_delivered(sid, cid, "entregada")
    def secret_reveal(self, sid, sid2): return self.svc.mark_secret_revealed(sid, sid2, "parcialmente_revelado")
    def improvise(self, sid, hint="", save=False): return self.svc.improvise(sid, hint, save)
    def done(self, sid): return self.svc.prepare_post_session(sid)
    def query(self, sid, what): return getattr(self.svc, f"query_{what}")(sid) if hasattr(self.svc, f"query_{what}") else []
