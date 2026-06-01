from packages.application.live_mode_service import LiveModeService


class LiveModeController:
    def __init__(self, project_service=None, session_service=None, secrets_service=None, entity_service=None):
        self.ps = project_service
        self.ss = session_service
        self.svc = LiveModeService(
            project_service=self.ps,
            session_service=self.ss,
            secrets_service=secrets_service,
            entity_service=entity_service,
        )

    def activate(self, sid): return self.svc.activate_session(sid)
    def note(self, sid, text): return self.svc.quick_note(sid, text)
    def decision(self, sid, text): return self.svc.register_player_decision(sid, text)
    def event(self, sid, text): return self.svc.register_event(sid, text)
    def consequence(self, sid, text): return self.svc.register_consequence(sid, text)
    def entity(self, sid, name, etype): return self.svc.create_provisional_entity(sid, name, etype)
    def relation(self, sid, source_id, target_id, relation_type): return self.svc.create_provisional_relation(sid, source_id, target_id, relation_type)
    def clue_deliver(self, sid, cid, state="entregada"): return self.svc.mark_clue_delivered(sid, cid, state)
    def secret_reveal(self, sid, secret_id, state="parcialmente_revelado"): return self.svc.mark_secret_revealed(sid, secret_id, state)
    def improvise(self, sid, hint="", save=False): return self.svc.improvise(sid, hint, save)
    def done(self, sid): return self.svc.prepare_post_session(sid)
    def query_clues(self, sid): return self.svc.query_clues(sid)
    def query_secrets(self, sid): return self.svc.query_secrets(sid)
