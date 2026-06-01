"""AppContext — shared UI state (B27.1-T01)."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class AppContext:
    project_controller: ProjectController | None = None
    selected_entity_id: str | None = None
    selected_session_id: str | None = None
    selected_candidate_id: str | None = None
    current_audience: str = "gm"
    log_messages: list[str] = field(default_factory=list)

    def log(self, level: str, msg: str):
        self.log_messages.append(f"[{level.upper()}] {msg}")
        if len(self.log_messages) > 200: self.log_messages = self.log_messages[-100:]
