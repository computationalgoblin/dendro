"""SessionController — wraps session/live/post services (B27.1-T04)."""
from packages.application.session_service import SessionService
from packages.application.live_mode_service import LiveModeService
from packages.application.post_session_service import PostSessionService
from packages.application.project_service import ProjectService

class SessionController:
    def __init__(self, project_service=None):
        self.ps = project_service or ProjectService(store=store)
        self.ss = SessionService(project_service=self.ps)
        self.ls = LiveModeService(project_service=self.ps, session_service=self.ss)
        self.ps2 = PostSessionService(project_service=self.ps, session_service=self.ss)

    def list_all(self): return self.ss.list_sessions() if self.ps.active_project else []
    def create(self, data): return self.ss.create_session(data)
