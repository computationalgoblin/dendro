from packages.application.candidate_service import CandidateService
from packages.application.post_session_service import PostSessionService
from hosts.DesktopHostPySide.app_trace import _apptrace


class PostSessionController:
    def __init__(self, project_service=None, session_service=None):
        self.ps = project_service
        self.ss = session_service
        self.svc = PostSessionService(project_service=self.ps, session_service=self.ss)
        self.candidates = CandidateService(project_service=self.ps) if self.ps is not None else None

    def close(self, sid):
        _apptrace(f"CTRL PostSessionController.close sid={sid!r}"[:120])
        return self.svc.close_session(sid)

    def generate_candidates(self, sid):
        _apptrace(f"CTRL PostSessionController.generate_candidates sid={sid!r}"[:120])
        return self.svc.convert_live_to_candidates(sid)

    def private_summary(self, sid):
        _apptrace(f"CTRL PostSessionController.private_summary sid={sid!r}"[:120])
        return self.svc.generate_private_summary(sid)

    def public_summary(self, sid):
        _apptrace(f"CTRL PostSessionController.public_summary sid={sid!r}"[:120])
        return self.svc.generate_public_summary(sid)

    def source(self, sid):
        _apptrace(f"CTRL PostSessionController.source sid={sid!r}"[:120])
        return self.svc.create_session_source(sid)

    def seeds(self, sid):
        _apptrace(f"CTRL PostSessionController.seeds sid={sid!r}"[:120])
        return self.svc.generate_next_session_seeds(sid)

    def accept_candidate(self, cid):
        _apptrace(f"CTRL PostSessionController.accept_candidate cid={cid!r}"[:120])
        return self.candidates.accept_candidate(cid) if self.candidates else None

    def reject_candidate(self, cid):
        _apptrace(f"CTRL PostSessionController.reject_candidate cid={cid!r}"[:120])
        return self.candidates.reject_candidate(cid) if self.candidates else None
