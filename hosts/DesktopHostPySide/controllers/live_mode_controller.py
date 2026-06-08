from packages.application.live_mode_service import LiveModeService
from hosts.DesktopHostPySide.app_trace import _apptrace


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

    def activate(self, sid):
        _apptrace(f"CTRL LiveModeController.activate sid={sid!r}"[:120])
        return self.svc.activate_session(sid)

    def note(self, sid, text):
        _apptrace(f"CTRL LiveModeController.note sid={sid!r} text={text!r}"[:120])
        return self.svc.quick_note(sid, text)

    def decision(self, sid, text):
        _apptrace(f"CTRL LiveModeController.decision sid={sid!r}"[:120])
        return self.svc.register_player_decision(sid, text)

    def event(self, sid, text):
        _apptrace(f"CTRL LiveModeController.event sid={sid!r}"[:120])
        return self.svc.register_event(sid, text)

    def consequence(self, sid, text):
        _apptrace(f"CTRL LiveModeController.consequence sid={sid!r}"[:120])
        return self.svc.register_consequence(sid, text)

    def entity(self, sid, name, etype):
        _apptrace(f"CTRL LiveModeController.entity sid={sid!r} name={name!r} etype={etype!r}"[:120])
        return self.svc.create_provisional_entity(sid, name, etype)

    def relation(self, sid, source_id, target_id, relation_type):
        _apptrace(f"CTRL LiveModeController.relation sid={sid!r} src={source_id!r} tgt={target_id!r}"[:120])
        return self.svc.create_provisional_relation(sid, source_id, target_id, relation_type)

    def clue_deliver(self, sid, cid, state="entregada"):
        _apptrace(f"CTRL LiveModeController.clue_deliver sid={sid!r} cid={cid!r}"[:120])
        return self.svc.mark_clue_delivered(sid, cid, state)

    def secret_reveal(self, sid, secret_id, state="parcialmente_revelado"):
        _apptrace(f"CTRL LiveModeController.secret_reveal sid={sid!r} secret_id={secret_id!r}"[:120])
        return self.svc.mark_secret_revealed(sid, secret_id, state)

    def improvise(self, sid, hint="", save=False):
        _apptrace(f"CTRL LiveModeController.improvise sid={sid!r}"[:120])
        return self.svc.improvise(sid, hint, save)

    def done(self, sid):
        _apptrace(f"CTRL LiveModeController.done sid={sid!r}"[:120])
        return self.svc.prepare_post_session(sid)

    def query_clues(self, sid):
        _apptrace(f"CTRL LiveModeController.query_clues sid={sid!r}"[:120])
        return self.svc.query_clues(sid)

    def query_secrets(self, sid):
        _apptrace(f"CTRL LiveModeController.query_secrets sid={sid!r}"[:120])
        return self.svc.query_secrets(sid)
