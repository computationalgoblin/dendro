"""SecretsController — wraps SecretsService for Desktop UI."""
from __future__ import annotations

from packages.application.secrets_service import SecretsService


class SecretsController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("SecretsController requires project_service")
        self.ps = project_service
        self.svc = SecretsService(project_service=self.ps)

    def list_secrets(self, state=None):
        return self.svc.list_secrets(state=state)

    def list_clues(self, state=None):
        return self.svc.list_clues(state=state)

    def get_secret(self, secret_id):
        return self.svc.get_secret(secret_id)

    def get_clue(self, clue_id):
        return self.svc.get_clue(clue_id)

    def create_secret(self, data):
        return self.svc.create_secret(data)

    def create_clue(self, data):
        return self.svc.create_clue(data)

    def reveal_secret(self, secret_id, state, session_id=None, form=None, force=False):
        return self.svc.reveal_secret(secret_id, state, session_id=session_id, form=form, force=force)

    def deliver_clue(self, clue_id, state="entregada", session_id=None, character_ids=None):
        return self.svc.deliver_clue(clue_id, state=state, session_id=session_id, character_ids=character_ids)

    def run_validation(self):
        return self.svc.run_secret_validation()
