"""SessionController — wraps session/live/post services (B27.1-T04)."""
from __future__ import annotations

from packages.application.session_service import SessionService
from packages.application.live_mode_service import LiveModeService
from packages.application.post_session_service import PostSessionService
from packages.application.secrets_service import SecretsService
from packages.application.entity_service import EntityService


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
        return self.ss.list_sessions() if self.ps.active_project else []

    def create(self, data):
        return self.ss.create_session(data)

    def add_scene(self, sid, data, target="planned"):
        return self.ss.add_scene(sid, data, target=target)

    def remove_scene(self, sid, scene_id, target="planned"):
        return self.ss.remove_scene(sid, scene_id, target=target)

    def reorder_scene(self, sid, scene_id, new_order, target="planned"):
        return self.ss.reorder_scene(sid, scene_id, new_order, target=target)

    def link_entity(self, sid, eid, role):
        return self.ss.link_entity(sid, eid, role)

    def link_clue(self, sid, cid):
        return self.ss.link_clue(sid, cid)

    def link_secret(self, sid, secret_id):
        return self.ss.link_secret(sid, secret_id)

    def link_faction(self, sid, fid):
        return self.ss.link_faction(sid, fid)

    def link_clock(self, sid, cid):
        return self.ss.link_clock(sid, cid)

    def check(self, sid):
        return self.ss.check_continuity(sid)

    def issues(self, sid):
        return self.ss.get_relevant_issues(sid)

    def suggest_material(self, sid, hint="", audience="author"):
        return self.ss.suggest_material(sid, hint=hint, audience=audience)
