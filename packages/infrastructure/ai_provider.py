"""Implementaciones de proveedor de IA + factoría (B15-T02).

DC-AUDIT-03: el contrato ``AIProvider`` y ``provider_chat`` viven ahora en el
puerto de application (``packages.application.ai_provider_port``); aquí se
re-exportan por compatibilidad (infrastructure → application es dirección
legal) y quedan las implementaciones concretas + ``create_provider``, que la
capa application resuelve por import dinámico (``resolve_provider``).
"""

from __future__ import annotations

from packages.application.ai_provider_port import AIProvider, provider_chat

__all__ = ["AIProvider", "SimulatedAIProvider", "create_provider", "provider_chat"]


class SimulatedAIProvider(AIProvider):
    provider_name = "simulated"

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
        """Deterministic local chat fallback for UI smoke tests.

        It returns text only and never creates candidates. The wording mirrors
        the user's instruction enough to reveal routing bugs without using a key.
        """
        lower = (system_prompt + "\n" + user_message).lower()
        if "fosco" in lower:
            return (
                "Fosco atravesó caminos de polvo, posadas medio olvidadas y fronteras donde cada promesa "
                "tenía un precio. Sus aventuras no nacieron de la gloria, sino de una obstinación tranquila: "
                "seguir adelante incluso cuando el mapa dejaba de ser fiable. En cada viaje ganó una cicatriz, "
                "una historia y una deuda pendiente que todavía tira de él hacia el próximo umbral.",
                None,
            )
        if "english" in lower or "respond in english" in lower:
            return ("Draft a focused narrative passage from the selected entity, respecting its current name, type, and project tone.", None)
        return (
            "Desarrolla el contenido de la entidad seleccionada con un tono coherente con el proyecto, "
            "aprovechando el nombre, el tipo y el texto ya escrito sin crear nodos ni relaciones nuevas.",
            None,
        )


def create_provider(name: str = "simulated", config: dict | None = None) -> AIProvider:
    """Select a provider.

    - ``name == "simulated"`` → always the local simulated provider (honours the
      explicit request; before this it silently went to the env provider).
    - otherwise → env-configurable selection (NARRATIVE_AI_* env vars).
    """
    if name == "simulated":
        return SimulatedAIProvider()
    from packages.infrastructure.openai_compatible_provider import get_provider
    return get_provider()
