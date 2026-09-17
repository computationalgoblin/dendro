"""AppContext — shared UI state (B27.1-T01/B31-T11)."""
from __future__ import annotations

import json
import logging
import os
import platform
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable


def _default_preferences_path() -> Path:
    """Return the app/user settings path, separated from project files."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Dendro" / "settings.json"
    return Path.home() / ".narrative-architect" / "desktop_preferences.json"


PREFERENCES_PATH = _default_preferences_path()


def _log_dir() -> Path:
    """Carpeta de datos para logs y crash log (WS-O)."""
    return Path.home() / ".narrative-architect"


_FILE_LOGGER: logging.Logger | None = None


def _file_logger() -> logging.Logger:
    """Logger rotativo a ``~/.narrative-architect/dendro.log`` (lazy singleton, WS-O).

    Antes ``ctx.log`` solo llenaba una lista en RAM + un widget oculto: los fallos
    (incluidos los errores del proveedor de IA, la señal nº1 de la beta) no dejaban
    rastro que un tester pudiera adjuntar. Ahora persisten en un fichero rotativo con
    un sello de versión/OS al arrancar, para correlacionar reportes entre builds.
    """
    global _FILE_LOGGER
    if _FILE_LOGGER is not None:
        return _FILE_LOGGER
    logger = logging.getLogger("dendro.app")
    logger.handlers.clear()  # idempotente: sin handlers duplicados si se reinicializa
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        directory = _log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            directory / "dendro.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        try:
            from packages.domain.config import AppConfig

            version = AppConfig().app_version
        except Exception:
            version = "?"
        logger.info("=== Dendro %s | %s ===", version, platform.platform())
    except Exception:
        pass  # sin fichero de log la app sigue funcionando igual
    _FILE_LOGGER = logger
    return logger


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
    # UX13: salida de avisos transitorios (toasts). La fija MainWindow; si no hay
    # sink, notify() degrada a log y la UI no se rompe (CLI/tests).
    notify_sink: Callable[[str, str], None] | None = None
    # WS-O: salida de avisos de recuperación PERSISTENTES (banner con «Abrir
    # registro» + de-dup). La fija MainWindow; sin sink, degrada a notify/log.
    recovery_sink: Callable[[str], None] | None = None
    advanced_mode: bool = False
    drawer: Any = None  # RightDrawer reference (set by MainWindow)
    left_drawer: Any = None  # LeftDrawer reference (set by MainWindow)
    ai_prompt_trace_store: Any = None
    # UX33: guardado SIN UI ruidosa (sin toast/refresh/cierre de cajón ni diálogo). Lo fija MainWindow.
    request_save_silent: Callable[[], bool] | None = None
    # SHIP-01: abre el panel de Ajustes de IA in-app desde cualquier vista (lo fija
    # MainWindow). Fail-soft: si es None, la UI degrada a texto sin botón.
    open_ai_settings: Callable[[], None] | None = None
    # BETA-AUDIT-01: programa un guardado a disco DIFERIDO (coalescente). Lo fija
    # MainWindow y lo llaman los controladores tras cada mutación asentada.
    request_save_debounced: Callable[[], None] | None = None
    # ¿Hay cambios en memoria que aún no están en disco? Lo publica MainWindow para
    # que la píldora «Guardar» diga la verdad en vez de afirmar siempre lo mismo.
    unsaved_changes: bool = False
    on_save_state_changed: Callable[[bool], None] | None = None

    # Appearance preferences (B31-UX-FIX-02-T04)
    font_size: str = "medium"  # small, medium, large
    font_family: str = "Georgia"
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
    # BETA1-UX36: contenedores que el usuario expandió en la cronología (el resto
    # arranca colapsado). Estado de UI, no de proyecto → vive aquí, sin migración.
    creation_chrono_expanded_ids: list[str] = field(default_factory=list)

    # BETA2-FIX-14 (G2-30). Sin anotación de tipo a propósito: NO es un
    # campo del dataclass (no debe aparecer en `__init__`), es estado de proceso.
    #: True si esta app puso `NARRATIVE_AI_API_KEY` en el entorno (y puede quitarla).
    _ai_key_exported = False

    #: Proveedores que CONSUMEN la clave (ver `openai_compatible_provider.get_provider`).
    _PROVEEDORES_CON_CLAVE = ("openai_compatible", "openai")

    def __post_init__(self):
        self.load_preferences()

    def provider_consumes_api_key(self) -> bool:
        """¿El proveedor configurado llega a usar `NARRATIVE_AI_API_KEY`?

        `simulated` nunca la usa. El resto la usa si es un proveedor conocido o si
        hay `base_url` (que es la otra puerta de `get_provider`).
        """
        provider = (self.ai_provider or "simulated").strip().lower()
        if provider == "simulated":
            return False
        return provider in self._PROVEEDORES_CON_CLAVE or bool((self.ai_base_url or "").strip())

    def forget_api_key(self) -> None:
        """BETA2-FIX-14 (G2-30): retira la clave del disco Y del proceso.

        No había NINGUNA forma de retirarla: `_save_ia_env` solo la escribía cuando
        el campo traía texto y nunca la borraba al cambiar a `simulated`.
        """
        self.ai_api_key = ""
        os.environ.pop("NARRATIVE_AI_API_KEY", None)
        self._ai_key_exported = False
        self.save_preferences()

    def _apply_ai_environment(self) -> None:
        """Vuelca los ajustes de IA persistidos a las variables de entorno.

        BETA2-FIX-14 (G2-30): la clave SOLO viaja al entorno si el
        proveedor configurado la consume. Antes se exportaba sin mirar el proveedor,
        en CADA arranque y en CADA guardado: apagar la IA (`simulated`) no apagaba
        nada, la clave seguía en el entorno del proceso. Ahora, además, al apagar se
        RETIRA lo que esta app hubiera exportado — apagar apaga de verdad.

        Una `NARRATIVE_AI_API_KEY` que el usuario haya puesto a mano en su entorno
        se respeta: ni se toca ni se persiste en `settings.json`.
        """
        os.environ["NARRATIVE_AI_PROVIDER"] = self.ai_provider or "simulated"
        os.environ["NARRATIVE_AI_BASE_URL"] = self.ai_base_url or ""
        os.environ["NARRATIVE_AI_MODEL"] = self.ai_model or ""
        os.environ["NARRATIVE_AI_TIMEOUT"] = str(self.ai_timeout or "300")
        if self.ai_api_key and self.provider_consumes_api_key():
            os.environ["NARRATIVE_AI_API_KEY"] = self.ai_api_key
            self._ai_key_exported = True
            return
        actual = os.environ.get("NARRATIVE_AI_API_KEY")
        nuestra = bool(self._ai_key_exported) or (
            actual is not None and self.ai_api_key and actual == self.ai_api_key
        )
        if actual is not None and nuestra:
            os.environ.pop("NARRATIVE_AI_API_KEY", None)
        self._ai_key_exported = False

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
            self.creation_chrono_expanded_ids = [
                str(i) for i in (data.get("creation_chrono_expanded_ids", []) or []) if str(i)
            ]
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
                "creation_chrono_expanded_ids": list(self.creation_chrono_expanded_ids or []),
            }
            self._apply_ai_environment()
            PREFERENCES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            # BETA2-FIX-14 (G2-30): el `chmod(0o600)` solo restringe de
            # verdad en POSIX. En Windows `Path.chmod` mueve el bit de solo-lectura
            # y NO toca las ACL: ahí no protege nada, así que ni se intenta (dejarlo
            # sugería una protección que en la plataforma de la beta no existe).
            # La clave sigue en claro en el fichero: cifrarla exige una dependencia
            # de terceros (keyring/DPAPI) y el repo no tiene ninguna — decisión
            # aparte. Mientras tanto, «Olvidar la clave» (`forget_api_key`) es la
            # salida honesta para quien no quiera dejarla en disco.
            if os.name == "posix":
                try:
                    PREFERENCES_PATH.chmod(0o600)
                except OSError:
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

    def data_dir(self) -> Path:
        """Carpeta de datos del usuario (log de app + crash log). WS-O."""
        return _log_dir()

    def log(self, level: str, msg: str):
        entry = f"[{level.upper()}] {msg}"
        self.log_messages.append(entry)
        if len(self.log_messages) > 200:
            self.log_messages = self.log_messages[-100:]
        # WS-O: persistir también en fichero rotativo para diagnosticar reportes de beta.
        try:
            _file_logger().log(logging.ERROR if level.lower() == "error" else logging.INFO, msg)
        except Exception:
            pass
        if self.log_sink is not None:
            self.log_sink(entry)

    def notify(self, message: str, kind: str = "info") -> None:
        """UX13: aviso transitorio (toast) además de registrarlo en el log.

        kind ∈ {success, info, error}. Fail-soft: sin sink (CLI/tests) solo loguea.
        """
        level = {"success": "info", "error": "error"}.get(kind, "info")
        self.log(level, message)
        if self.notify_sink is not None:
            try:
                self.notify_sink(message, kind)
            except Exception:  # noqa: BLE001 - el aviso nunca rompe el flujo
                pass

    def notify_recovery(self, message: str) -> None:
        """WS-O: aviso de recuperación PERSISTENTE (banner con «Abrir registro»),
        para fallos serios (apertura/guardado). Fail-soft: sin sink, cae a
        ``notify(..., "error")``; siempre queda traza en el log."""
        self.log("error", message)
        if self.recovery_sink is not None:
            try:
                self.recovery_sink(message)
                return
            except Exception:  # noqa: BLE001 - el aviso nunca rompe el flujo
                pass
        if self.notify_sink is not None:
            try:
                self.notify_sink(message, "error")
            except Exception:  # noqa: BLE001
                pass
