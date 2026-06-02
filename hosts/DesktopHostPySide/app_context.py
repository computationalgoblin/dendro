"""AppContext — shared UI state (B27.1-T01/B31-T11)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


PREFERENCES_PATH = Path.home() / ".narrative-architect" / "desktop_preferences.json"


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

    def __post_init__(self):
        self.load_preferences()

    def load_preferences(self) -> None:
        """Load user UI preferences from a local profile file."""
        try:
            if not PREFERENCES_PATH.exists():
                return
            data = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
            self.advanced_mode = bool(data.get("advanced_mode", False))
            self.current_audience = str(data.get("current_audience", self.current_audience) or "gm")
        except Exception:
            # UI preferences are non-critical; keep defaults if unreadable.
            self.advanced_mode = False

    def save_preferences(self) -> None:
        """Persist user UI preferences without touching project persistence."""
        try:
            PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "advanced_mode": bool(self.advanced_mode),
                "current_audience": self.current_audience,
            }
            PREFERENCES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            self.log("error", f"No se pudieron guardar preferencias UI: {exc}")

    def set_advanced_mode(self, enabled: bool) -> None:
        """Update advanced mode and persist it between app sessions."""
        self.advanced_mode = bool(enabled)
        self.save_preferences()

    def log(self, level: str, msg: str):
        entry = f"[{level.upper()}] {msg}"
        self.log_messages.append(entry)
        if len(self.log_messages) > 200:
            self.log_messages = self.log_messages[-100:]
        if self.log_sink is not None:
            self.log_sink(entry)
