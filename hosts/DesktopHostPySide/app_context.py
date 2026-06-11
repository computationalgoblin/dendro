"""AppContext — shared UI state (B27.1-T01/B31-T11)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


def _default_preferences_path() -> Path:
    """Return the app/user settings path, separated from project files."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Dendro" / "settings.json"
    return Path.home() / ".narrative-architect" / "desktop_preferences.json"


PREFERENCES_PATH = _default_preferences_path()


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
    left_drawer: Any = None  # LeftDrawer reference (set by MainWindow)

    # Appearance preferences (B31-UX-FIX-02-T04)
    font_size: str = "medium"  # small, medium, large
    font_family: str = "Georgia"
    fullscreen: bool = False
    dark_mode: bool = False
    animation_intensity: str = "normal"  # low, normal, high
    language: str = "es"  # es, en

    # AI/app preferences persisted outside project files
    ai_provider: str = "simulated"
    ai_base_url: str = ""
    ai_model: str = ""
    ai_api_key: str = ""
    ai_timeout: str = "300"
    ai_temperature: float = 0.7
    last_project_path: str = ""
    recent_projects: list[str] = field(default_factory=list)
    creation_layout_mode: str = "concentric_rings"
    creation_focused_ring_id: str = ""

    def __post_init__(self):
        self.load_preferences()

    def _apply_ai_environment(self) -> None:
        """Mirror persisted AI settings into the legacy provider env vars."""
        os.environ["NARRATIVE_AI_PROVIDER"] = self.ai_provider or "simulated"
        os.environ["NARRATIVE_AI_BASE_URL"] = self.ai_base_url or ""
        os.environ["NARRATIVE_AI_MODEL"] = self.ai_model or ""
        os.environ["NARRATIVE_AI_TIMEOUT"] = str(self.ai_timeout or "300")
        if self.ai_api_key:
            os.environ["NARRATIVE_AI_API_KEY"] = self.ai_api_key

    def remember_project(self, path: str | None) -> None:
        """Persist the last opened/saved project path and a short recents list."""
        if not path:
            return
        normalized = str(Path(path).expanduser())
        self.last_project_path = normalized
        recents = [p for p in self.recent_projects if p != normalized]
        recents.insert(0, normalized)
        self.recent_projects = recents[:8]
        self.save_preferences()

    def forget_missing_project(self, path: str | None = None) -> None:
        missing = str(path or self.last_project_path or "")
        if missing and self.last_project_path == missing:
            self.last_project_path = ""
        self.recent_projects = [p for p in self.recent_projects if p != missing]
        self.save_preferences()

    def load_preferences(self) -> None:
        """Load user UI preferences from a local profile file."""
        try:
            if not PREFERENCES_PATH.exists():
                self._apply_ai_environment()
                return
            data = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
            self.advanced_mode = bool(data.get("advanced_mode", False))
            self.current_audience = str(data.get("current_audience", self.current_audience) or "gm")
            # Appearance preferences (B31-UX-FIX-02-T04)
            self.font_size = str(data.get("font_size", self.font_size)) or "medium"
            self.font_family = str(data.get("font_family", self.font_family)) or "Georgia"
            self.fullscreen = bool(data.get("fullscreen", False))
            self.dark_mode = bool(data.get("dark_mode", False))
            self.animation_intensity = str(data.get("animation_intensity", self.animation_intensity)) or "normal"
            self.language = str(data.get("language", self.language)) or "es"
            self.ai_provider = str(data.get("ai_provider", self.ai_provider)) or "simulated"
            self.ai_base_url = str(data.get("ai_base_url", self.ai_base_url)) or ""
            self.ai_model = str(data.get("ai_model", self.ai_model)) or ""
            self.ai_api_key = str(data.get("ai_api_key", self.ai_api_key)) or ""
            self.ai_timeout = str(data.get("ai_timeout", self.ai_timeout)) or "300"
            try:
                self.ai_temperature = float(data.get("ai_temperature", self.ai_temperature))
            except Exception:
                self.ai_temperature = 0.7
            self.last_project_path = str(data.get("last_project_path", self.last_project_path)) or ""
            self.recent_projects = [str(p) for p in (data.get("recent_projects", []) or []) if p]
            # BETA1-B05: Creation always starts from the concentric layout.
            # Older persisted preferences may contain "free" or "layered";
            # those are session choices, not the app default.
            self.creation_layout_mode = "concentric_rings"
            self.creation_focused_ring_id = str(data.get("creation_focused_ring_id", self.creation_focused_ring_id)) or ""
            self._apply_ai_environment()
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
                "font_size": self.font_size,
                "font_family": self.font_family,
                "fullscreen": self.fullscreen,
                "dark_mode": self.dark_mode,
                "animation_intensity": self.animation_intensity,
                "language": self.language,
                "ai_provider": self.ai_provider,
                "ai_base_url": self.ai_base_url,
                "ai_model": self.ai_model,
                "ai_api_key": self.ai_api_key,
                "ai_timeout": self.ai_timeout,
                "ai_temperature": self.ai_temperature,
                "last_project_path": self.last_project_path,
                "recent_projects": list(self.recent_projects or [])[:8],
                "creation_layout_mode": self.creation_layout_mode,
                "creation_focused_ring_id": self.creation_focused_ring_id,
            }
            self._apply_ai_environment()
            PREFERENCES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                PREFERENCES_PATH.chmod(0o600)
            except Exception:
                pass
        except Exception as exc:
            self.log("error", f"No se pudieron guardar preferencias UI: {exc}")

    def animation_duration(self, base_ms: int) -> int:
        """Scale animation duration by intensity preference."""
        multipliers = {"low": 0.5, "normal": 1.0, "high": 1.8}
        return int(base_ms * multipliers.get(self.animation_intensity, 1.0))

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
