"""AppContext — shared UI state (B27.1-T01)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AppContext:
    project_controller: ProjectController | None = None
    selected_entity_id: str | None = None
    selected_relation_id: str | None = None
    selected_session_id: str | None = None
    selected_candidate_id: str | None = None
    selected_campaign_id: str | None = None
    current_audience: str = "gm"
    log_messages: list[str] = field(default_factory=list)
    log_sink: Callable[[str], None] | None = None
    advanced_mode: bool = False
    drawer: Any = None  # RightDrawer reference (set by MainWindow)

    def log(self, level: str, msg: str):
        entry = f"[{level.upper()}] {msg}"
        self.log_messages.append(entry)
        if len(self.log_messages) > 200:
            self.log_messages = self.log_messages[-100:]
        if self.log_sink is not None:
            self.log_sink(entry)
