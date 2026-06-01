from packages.application.post_session_service import PostSessionService
class PostSessionController:
    def __init__(self, project_service=None, session_service=None): self.ps = project_service; self.ss = session_service; self.svc = PostSessionService(project_service=self.ps, session_service=self.ss)
    def close(self, sid): return self.svc.close_session(sid)
    def candidates(self, sid): return self.svc.convert_live_to_candidates(sid)
    def private_summary(self, sid): return self.svc.generate_private_summary(sid)
    def public_summary(self, sid): return self.svc.generate_public_summary(sid)
    def source(self, sid): return self.svc.create_session_source(sid)
    def seeds(self, sid): return self.svc.generate_next_session_seeds(sid)
