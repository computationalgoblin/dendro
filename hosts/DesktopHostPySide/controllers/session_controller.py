"""SessionController — wraps session/live/post services (B27.1-T04)."""
from __future__ import annotations

from packages.application.session_service import SessionService
from packages.application.live_mode_service import LiveModeService
from packages.application.post_session_service import PostSessionService
from packages.application.secrets_service import SecretsService
from packages.application.entity_service import EntityService
from hosts.DesktopHostPySide.app_trace import _apptrace


class SessionController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("SessionController requires project_service")
        self.ps = project_service
        self.ss = SessionService(project_service=self.ps)
        self.sec = SecretsService(project_service=self.ps)
        self.es = EntityService(project_service=self.ps)
        self.ls = LiveModeService(project_service=self.ps, session_service=self.ss, secrets_service=self.sec, entity_service=self.es)
        self.ps2 = PostSessionService(project_service=self.ps, session_service=self.ss)

    def list_all(self):
        _apptrace(f"CTRL SessionController.list_all"[:120])
        return self.ss.list_sessions() if self.ps.active_project else []

    def create(self, data):
        _apptrace(f"CTRL SessionController.create data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        return self.ss.create_session(data)

    def get(self, sid):
        _apptrace(f"CTRL SessionController.get sid={sid!r}"[:120])
        return self.ss.get_session(sid)

    def update(self, sid, data):
        _apptrace(f"CTRL SessionController.update sid={sid!r}"[:120])
        return self.ss.update_session(sid, data)

    def add_scene(self, sid, data, target="planned"):
        _apptrace(f"CTRL SessionController.add_scene sid={sid!r} target={target!r}"[:120])
        return self.ss.add_scene(sid, data, target=target)

    def remove_scene(self, sid, scene_id, target="planned"):
        _apptrace(f"CTRL SessionController.remove_scene sid={sid!r} scene_id={scene_id!r}"[:120])
        return self.ss.remove_scene(sid, scene_id, target=target)

    def reorder_scene(self, sid, scene_id, new_order, target="planned"):
        _apptrace(f"CTRL SessionController.reorder_scene sid={sid!r} scene_id={scene_id!r}"[:120])
        return self.ss.reorder_scene(sid, scene_id, new_order, target=target)

    def link_entity(self, sid, eid, role):
        _apptrace(f"CTRL SessionController.link_entity sid={sid!r} eid={eid!r} role={role!r}"[:120])
        return self.ss.link_entity(sid, eid, role)

    def link_clue(self, sid, cid):
        _apptrace(f"CTRL SessionController.link_clue sid={sid!r} cid={cid!r}"[:120])
        return self.ss.link_clue(sid, cid)

    def link_secret(self, sid, secret_id):
        _apptrace(f"CTRL SessionController.link_secret sid={sid!r} secret_id={secret_id!r}"[:120])
        return self.ss.link_secret(sid, secret_id)

    def link_faction(self, sid, fid):
        _apptrace(f"CTRL SessionController.link_faction sid={sid!r} fid={fid!r}"[:120])
        return self.ss.link_faction(sid, fid)

    def link_clock(self, sid, cid):
        _apptrace(f"CTRL SessionController.link_clock sid={sid!r} cid={cid!r}"[:120])
        return self.ss.link_clock(sid, cid)

    def check(self, sid):
        _apptrace(f"CTRL SessionController.check sid={sid!r}"[:120])
        return self.ss.check_continuity(sid)

    def issues(self, sid):
        _apptrace(f"CTRL SessionController.issues sid={sid!r}"[:120])
        return self.ss.get_relevant_issues(sid)

    def suggest_material(self, sid, hint="", audience="author"):
        _apptrace(f"CTRL SessionController.suggest_material sid={sid!r}"[:120])
        return self.ss.suggest_material(sid, hint=hint, audience=audience)
