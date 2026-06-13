"""Temporary prompt trace HTML for RAG beta debugging (E05).

This module is intentionally simple and removable. It writes model-facing
prompts to an ignored file under ai_outputs so the desktop host can open it in
an external browser while testing RAG.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from threading import RLock
from typing import Any
import json
import re


DEFAULT_PROMPT_TRACE_PATH = Path("ai_outputs") / "rag_prompt_debug.html"


@dataclass
class AIPromptDebugEntry:
    job_id: str
    created_at: str
    updated_at: str
    status: str
    provider: str
    prompt: str
    system_prompt: str
    model_user_message: str
    plan: dict[str, Any] = field(default_factory=dict)
    context_pack: dict[str, Any] = field(default_factory=dict)
    response_text: str = ""
    error: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "provider": self.provider,
            "prompt": self.prompt,
            "system_prompt": self.system_prompt,
            "model_user_message": self.model_user_message,
            "plan": dict(self.plan),
            "context_pack": dict(self.context_pack),
            "response_text": self.response_text,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
        }


class AIPromptDebugTraceStore:
    """In-memory ring buffer mirrored to an autorefreshing HTML file."""

    def __init__(
        self,
        output_path: str | Path | None = None,
        *,
        max_entries: int = 40,
        enabled: bool = True,
    ):
        self.output_path = Path(output_path or DEFAULT_PROMPT_TRACE_PATH)
        self.max_entries = max(1, int(max_entries or 40))
        self.enabled = bool(enabled)
        self._entries: list[AIPromptDebugEntry] = []
        self._lock = RLock()

    @classmethod
    def default(cls) -> "AIPromptDebugTraceStore":
        return cls(DEFAULT_PROMPT_TRACE_PATH)

    @property
    def entries(self) -> list[AIPromptDebugEntry]:
        with self._lock:
            return list(self._entries)

    def record_request(
        self,
        *,
        job_id: str,
        provider: str,
        prompt: str,
        system_prompt: str,
        model_user_message: str,
        plan: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        payload = _json_object(model_user_message)
        context = payload.get("contexto_autorizado", {}) if isinstance(payload, dict) else {}
        context_pack = context.get("rag_context_pack", {}) if isinstance(context, dict) else {}
        now = _now_iso()
        entry = AIPromptDebugEntry(
            job_id=str(job_id),
            created_at=now,
            updated_at=now,
            status="processing",
            provider=str(provider or "ai"),
            prompt=str(prompt or ""),
            system_prompt=_redact(system_prompt),
            model_user_message=_redact(model_user_message),
            plan=dict(plan or payload.get("plan") or {}),
            context_pack=dict(context_pack or {}),
        )
        with self._lock:
            self._entries = [item for item in self._entries if item.job_id != entry.job_id]
            self._entries.append(entry)
            self._entries = self._entries[-self.max_entries :]
            self.write_page()

    def record_response(
        self,
        job_id: str,
        *,
        status: str,
        response_text: str = "",
        error: str = "",
        elapsed_ms: float = 0.0,
    ) -> None:
        if not self.enabled:
            return
        with self._lock:
            entry = next((item for item in self._entries if item.job_id == str(job_id)), None)
            if entry is None:
                return
            entry.status = str(status or entry.status)
            entry.response_text = _redact(response_text)
            entry.error = _redact(error)
            entry.elapsed_ms = max(0.0, float(elapsed_ms or 0.0))
            entry.updated_at = _now_iso()
            self.write_page()

    def write_page(self) -> Path:
        if not self.enabled:
            return self.output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(self.to_html(), encoding="utf-8")
        return self.output_path

    def to_html(self) -> str:
        entries = list(reversed(self._entries))
        body = "\n".join(_entry_html(entry) for entry in entries)
        if not body:
            body = "<p class='empty'>No hay prompts trazados todavia.</p>"
        return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="2">
  <title>Dendro RAG Prompt Debug</title>
  <style>
    body {{ margin: 0; padding: 24px; font-family: Segoe UI, Arial, sans-serif; background: #f5f3ea; color: #25251d; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; }}
    .note {{ color: #68644f; margin-bottom: 18px; }}
    .entry {{ background: white; border: 1px solid #d8d2bd; border-radius: 8px; padding: 16px; margin: 14px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}
    .meta {{ display: flex; gap: 10px; flex-wrap: wrap; color: #625f4f; font-size: 12px; margin-bottom: 10px; }}
    .status {{ font-weight: 700; padding: 2px 8px; border-radius: 999px; background: #ece6ce; }}
    .status.ok {{ background: #dfead8; color: #315f2d; }}
    .status.error {{ background: #f0d6d1; color: #8d2b22; }}
    details {{ margin-top: 10px; }}
    summary {{ cursor: pointer; font-weight: 700; color: #4d4a35; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #25251d; color: #f6f1df; padding: 12px; border-radius: 6px; font-size: 12px; line-height: 1.45; }}
    ul {{ margin-top: 6px; }}
    .empty {{ color: #68644f; }}
  </style>
</head>
<body>
  <h1>Dendro RAG Prompt Debug</h1>
  <div class="note">Temporal para beta. Muestra prompts, contexto autorizado, ContextPack, rationale declarativo y errores. No muestra razonamiento interno oculto del modelo.</div>
  {body}
</body>
</html>
"""


def _entry_html(entry: AIPromptDebugEntry) -> str:
    state_class = "ok" if entry.status == "ok" else "error" if entry.status == "error" else "processing"
    reasoning = _visible_reasoning(entry)
    response = entry.response_text or entry.error or ""
    return f"""<section class="entry">
  <h2>{escape(entry.prompt or "Prompt sin titulo")}</h2>
  <div class="meta">
    <span class="status {state_class}">{escape(entry.status)}</span>
    <span>job: {escape(entry.job_id)}</span>
    <span>provider: {escape(entry.provider)}</span>
    <span>actualizado: {escape(entry.updated_at)}</span>
    <span>duracion: {entry.elapsed_ms:.0f} ms</span>
  </div>
  <details open><summary>Razonamiento visible de depuracion</summary>{reasoning}</details>
  <details open><summary>ContextPack RAG</summary><pre>{escape(_pretty(entry.context_pack))}</pre></details>
  <details><summary>Payload enviado al modelo</summary><pre>{escape(_pretty_text(entry.model_user_message))}</pre></details>
  <details><summary>Prompt de sistema</summary><pre>{escape(entry.system_prompt)}</pre></details>
  <details {'open' if response else ''}><summary>Respuesta / error</summary><pre>{escape(response)}</pre></details>
</section>"""


def _visible_reasoning(entry: AIPromptDebugEntry) -> str:
    plan = entry.plan or {}
    intent = plan.get("intent", {}) if isinstance(plan.get("intent"), dict) else {}
    rows: list[str] = []
    rationale = intent.get("rationale") or plan.get("rationale")
    if rationale:
        rows.append(f"<li>Planner rationale: {escape(str(rationale))}</li>")
    for action in intent.get("actions", []) if isinstance(intent.get("actions"), list) else []:
        if isinstance(action, dict) and action.get("rationale"):
            rows.append(f"<li>Accion {escape(str(action.get('type', '')))}: {escape(str(action['rationale']))}</li>")
    for item in (entry.context_pack or {}).get("items", []) if isinstance(entry.context_pack, dict) else []:
        if isinstance(item, dict):
            label = f"{item.get('kind', '')}:{item.get('ref_id', '')}"
            reason = item.get("reason", "")
            priority = item.get("priority", "")
            rows.append(f"<li>RAG {escape(label)} [{escape(str(priority))}]: {escape(str(reason))}</li>")
    if not rows:
        rows.append("<li>Sin rationale declarativo disponible todavia.</li>")
    return "<ul>" + "".join(rows) + "</ul>"


def _pretty_text(text: str) -> str:
    parsed = _json_object(text)
    if parsed:
        return _pretty(parsed)
    return text


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)


def _json_object(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text or "{}")
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _redact(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", value)
    value = re.sub(r"sk-[A-Za-z0-9._\-]+", "[REDACTED]", value)
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["AIPromptDebugEntry", "AIPromptDebugTraceStore", "DEFAULT_PROMPT_TRACE_PATH"]
