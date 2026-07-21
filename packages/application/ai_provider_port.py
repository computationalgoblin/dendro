"""Puerto de IA de la capa application (DC-AUDIT-03).

El contrato ``AIProvider`` y la utilidad pura ``provider_chat`` viven aquí:
son interfaz + ayuda de invocación sin dependencia alguna de infraestructura.
Las implementaciones concretas (``SimulatedAIProvider``, proveedor
OpenAI-compatible) siguen en ``packages.infrastructure.ai_provider``, que
importa este puerto (dirección legal infrastructure → application) y lo
re-exporta por compatibilidad.

``resolve_provider`` cierra la inversión: resuelve la factoría concreta por
import dinámico (cacheado), de modo que application nunca importa
infrastructure estáticamente y el guard de capas queda sin excepciones.
"""

from __future__ import annotations

import importlib
import inspect
from abc import ABC, abstractmethod
from types import ModuleType


def provider_chat(
    provider,
    system_prompt: str,
    user_message: str,
    *,
    timeout=None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = False,
):
    """Call ``provider.chat`` tolerating older / narrower chat() signatures.

    BETA1-AI01 added temperature/max_tokens/json_mode, but test doubles and
    third-party providers may not accept them. We pass only the kwargs the
    callee actually declares (or all of them if it has ``**kwargs``), so the new
    params are applied when supported and skipped otherwise — without masking a
    real TypeError raised inside the provider.
    """
    fn = provider.chat
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        params = {}
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    kwargs: dict = {}
    for name, value in (
        ("timeout", timeout),
        ("temperature", temperature),
        ("max_tokens", max_tokens),
        ("json_mode", json_mode),
    ):
        if has_var_kw or name in params:
            kwargs[name] = value
    return fn(system_prompt, user_message, **kwargs)


class AIProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    # BETA1-AI01: callers can tune generation per intent and ask for JSON.
    # Defaults keep every existing `chat(system, user, timeout)` call working.
    def chat(
        self,
        system_prompt: str,
        user_message: str,
        timeout=None,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ):
        """Direct chat with a custom system prompt. Returns ``(text, error)``.

        - ``temperature`` / ``max_tokens``: per-intent generation params. ``None``
          means "provider default". Subclasses that ignore them keep working.
        - ``json_mode``: request a strict JSON object response when the provider
          supports it (e.g. OpenAI ``response_format``).
        """
        return None, "Not implemented"


# ---------------------------------------------------------------------------
# Resolución dinámica de la factoría concreta (raíz de composición)
# ---------------------------------------------------------------------------

_infra_module: ModuleType | None = None


def _infrastructure_ai_module() -> ModuleType:
    """Import dinámico y cacheado de ``packages.infrastructure.ai_provider``.

    Se cachea el módulo (no el proveedor): cada ``resolve_provider`` sigue
    delegando en ``create_provider``, que decide la instancia.
    """
    global _infra_module
    if _infra_module is None:
        _infra_module = importlib.import_module("packages.infrastructure.ai_provider")
    return _infra_module


def resolve_provider(name: str | None = None, config: dict | None = None) -> AIProvider:
    """Resuelve un proveedor concreto sin acoplar application a infrastructure.

    Semántica IDÉNTICA a ``create_provider``: sin ``name`` (o "simulated") se
    obtiene el proveedor simulado local; con otro nombre, la selección por
    entorno (``NARRATIVE_AI_*``). El flujo "sin IA real" no cambia: los jobs
    siguen fallando claro aguas arriba ("IA no configurada") cuando el
    proveedor efectivo es el simulado y no está permitido (invariante D05).

    Si la capa de infraestructura no está disponible (instalación recortada),
    falla claro en lugar de fingir éxito.
    """
    try:
        module = _infrastructure_ai_module()
    except ImportError as exc:  # pragma: no cover — infra siempre acompaña al paquete
        raise RuntimeError(
            "IA no configurada: la capa de infraestructura de proveedores no está "
            f"disponible ({exc})"
        ) from exc
    return module.create_provider(name if name is not None else "simulated", config)


__all__ = ["AIProvider", "provider_chat", "resolve_provider"]
