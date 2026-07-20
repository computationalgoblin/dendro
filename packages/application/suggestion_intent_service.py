"""SuggestionIntentService — análisis de intención previo a las Sugerencias creativas.

BETA2-WIKI-13: para las métricas **arraigo** e **iluminada**, una Sugerencia puede
requerir crear entidades, ramas, relaciones o hitos, o editar existentes. En vez de fijar
el tipo por la métrica (como hacen *nutrida*/*calidad*), un job de análisis LIGERO lee la
petición del usuario + el contexto de la entidad + la wiki navegada y decide un **plan**:
qué tipos de output producirá el siguiente job (la generación compuesta).

El plan se usa como *feedback* (se muestra en vivo) y para construir el prompt del job
compuesto. Es una decisión, no canon: la generación posterior sigue produciendo Semillas
revisables que el usuario acepta o descarta. La IA nunca escribe canon.

Capa de aplicación, ``Result``-based. Usa ``AIJobService.raw_json_completion`` (borde IA
autorizado) para NO importar infraestructura — mismo patrón que ``WikiNavigator``. Sin
proveedor real, devuelve un **plan por defecto** determinista por métrica: el flujo sigue.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from packages.domain.result import Error, Ok, Result


class IntentActionKind(str, Enum):
    """Tipos de output que el plan puede pedir a la generación."""

    CREAR_HOJA = "crear_hoja"
    CREAR_RAMA = "crear_rama"
    CREAR_RELACION = "crear_relacion"
    CREAR_HITO = "crear_hito"
    EDITAR = "editar"


# Etiqueta corta legible para el feedback ("Plan: 1 rama, 2 hojas…").
_KIND_NOUN: dict[IntentActionKind, str] = {
    IntentActionKind.CREAR_HOJA: "hoja",
    IntentActionKind.CREAR_RAMA: "rama",
    IntentActionKind.CREAR_RELACION: "relación",
    IntentActionKind.CREAR_HITO: "hito",
    IntentActionKind.EDITAR: "edición",
}
# Claves JSON que la generación compuesta debe rellenar por tipo (las lee stage_results).
_KIND_OUTPUT_KEY: dict[IntentActionKind, str] = {
    IntentActionKind.CREAR_HOJA: "hojas",
    IntentActionKind.CREAR_RAMA: "ramas",
    IntentActionKind.CREAR_RELACION: "relations",
    IntentActionKind.CREAR_HITO: "hitos",
    IntentActionKind.EDITAR: "entity_edits",
}

# Plan por defecto (sin IA o ante fallo) por métrica: el mínimo coherente con la métrica.
_FALLBACK_KIND: dict[str, IntentActionKind] = {
    "arraigo": IntentActionKind.CREAR_RELACION,
    "iluminada": IntentActionKind.CREAR_HOJA,
}

_METRIC_BIAS: dict[str, str] = {
    "arraigo": (
        "La métrica es ARRAIGO (raíces): la entidad necesita más sostén — causas, contextos "
        "superiores, vínculos con hitos/ramas o relaciones que la hagan verosímil. Prioriza "
        "crear_relacion, crear_hito o crear_rama que la enraícen; edita si el hueco es interno."
    ),
    "iluminada": (
        "La métrica es ILUMINADA (brotes): la entidad necesita proyectar consecuencias — "
        "derivaciones, entidades o hitos que nazcan de ella e irradien su influencia. Prioriza "
        "crear_hoja, crear_hito o crear_relacion hacia lo que la entidad hace posible."
    ),
}

_VALID_KINDS = frozenset(k.value for k in IntentActionKind)

_SYSTEM_INTENT = (
    "Eres un planificador editorial de un proyecto narrativo. Recibes una ENTIDAD en foco, "
    "una MÉTRICA del jardín a reforzar, una PETICIÓN opcional del usuario y CONTEXTO de la "
    "wiki. Tu única tarea es decidir el PLAN MÍNIMO de piezas a proponer para atender la "
    "petición y reforzar la métrica: qué tipos de output y cuántos. NO escribes el contenido "
    "todavía (eso lo hace otro paso); NO tocas el canon; NO inventes ids.\n"
    "Tipos permitidos: crear_hoja (entidad/personaje/objeto), crear_rama (contenedor que "
    "agrupa hojas), crear_relacion (vínculo entre entidades), crear_hito (evento causal), "
    "editar (mejorar un elemento existente).\n"
    "Si la petición pide algo explícito (p. ej. «crea una rama», «relaciona con X»), el plan "
    "DEBE reflejarlo. Sé austero: solo lo necesario, sin inflar.\n"
    "Responde SIEMPRE y SOLO con un objeto JSON con esta forma exacta:\n"
    '{"acciones": [{"tipo": "crear_hoja|crear_rama|crear_relacion|crear_hito|editar", '
    '"descripcion": "qué proponer, en una frase", "objetivo": "nombre del elemento afectado '
    'o \\"\\""}], "resumen": "una línea de lo que se hará"}\n'
    "No añadas texto fuera del JSON."
)


@dataclass
class IntentAction:
    kind: IntentActionKind
    descripcion: str = ""
    objetivo: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"tipo": self.kind.value, "descripcion": self.descripcion, "objetivo": self.objetivo}


@dataclass
class IntentPlan:
    """El plan decidido por el análisis de intención (no canon)."""

    acciones: list[IntentAction] = field(default_factory=list)
    resumen: str = ""
    truncated: bool = False
    from_fallback: bool = False

    def is_empty(self) -> bool:
        return not self.acciones

    def output_keys(self) -> list[str]:
        """Claves JSON (para stage_results) que la generación debe poder rellenar."""
        seen: list[str] = []
        for a in self.acciones:
            key = _KIND_OUTPUT_KEY.get(a.kind)
            if key and key not in seen:
                seen.append(key)
        return seen

    def summary_line(self) -> str:
        """Feedback legible: «Plan: 1 rama, 2 hojas, 1 relación»."""
        if not self.acciones:
            return "Plan: (sin acciones)"
        counts: dict[str, int] = {}
        order: list[str] = []
        for a in self.acciones:
            noun = _KIND_NOUN.get(a.kind, a.kind.value)
            if noun not in counts:
                counts[noun] = 0
                order.append(noun)
            counts[noun] += 1
        # 'relación'→'relaciones', 'edición'→'ediciones' tienen plural irregular.
        parts: list[str] = []
        for n in order:
            c = counts[n]
            plural = n
            if c != 1:
                plural = {"relación": "relaciones", "edición": "ediciones"}.get(n, n + "s")
            parts.append(f"{c} {plural}")
        return "Plan: " + ", ".join(parts)

    def to_generation_directives(self) -> str:
        """Bloque de texto que encabeza el prompt de la generación compuesta."""
        lines = [
            "PLAN DE GENERACIÓN (decidido por el análisis de intención). Produce SOLO los "
            "tipos que el plan pide; nada más:"
        ]
        for a in self.acciones:
            objetivo = f" [objetivo: {a.objetivo}]" if a.objetivo else ""
            desc = a.descripcion or "(sin detalle)"
            lines.append(f"- {a.kind.value}: {desc}{objetivo}")
        keys = ", ".join(self.output_keys()) or "(ninguna)"
        lines.append(f"Claves JSON a rellenar: {keys}. Deja vacías las claves de tipos no pedidos.")
        return "\n".join(lines)


@dataclass
class SuggestionIntentService:
    project_service: Any
    ai_job_service: Any = None
    max_actions: int = 6

    def _proj(self):
        return getattr(self.project_service, "active_project", None)

    def plan(
        self,
        entity_id: str,
        metric: str,
        peticion: str = "",
        *,
        wiki_context: dict | None = None,
    ) -> Result[IntentPlan, str]:
        """Decide el plan de generación para una Sugerencia de arraigo/iluminada."""
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        metric_key = str(metric or "").strip().lower()
        entity = proj.entity_by_id(entity_id) if hasattr(proj, "entity_by_id") else None
        if entity is None:
            return Error(f"Entidad no encontrada: {entity_id}")

        # Sin proveedor real: plan determinista mínimo (el flujo nunca se rompe).
        if self.ai_job_service is None or self.ai_job_service.provider_unconfigured():
            return Ok(self._fallback_plan(metric_key))

        user_message = self._build_message(
            proj, entity, metric_key, str(peticion or "").strip(), wiki_context
        )
        try:
            text, err = self.ai_job_service.raw_json_completion(_SYSTEM_INTENT, user_message)
        except Exception as exc:  # noqa: BLE001 — el análisis nunca rompe la sugerencia
            text, err = None, str(exc)
        if err or not text:
            return Ok(self._fallback_plan(metric_key))
        parsed = self._parse(text)
        if parsed is None or parsed.is_empty():
            return Ok(self._fallback_plan(metric_key))
        return Ok(parsed)

    # ── construcción del mensaje ────────────────────────────────────────

    def _build_message(
        self, proj, entity, metric_key: str, peticion: str, wiki_context: dict | None
    ) -> str:
        payload: dict[str, Any] = {
            "entidad": {
                "nombre": getattr(entity, "name", ""),
                "tipo": getattr(getattr(entity, "entity_type", None), "value", ""),
                "breve": getattr(entity, "brief_description", ""),
            },
            "metrica": metric_key,
            "sesgo_metrica": _METRIC_BIAS.get(metric_key, ""),
            "peticion": peticion,
            "max_acciones": self.max_actions,
        }
        if hasattr(proj, "relations_for"):
            rels = proj.relations_for(entity.id)
            payload["entidad"]["n_relaciones"] = len(rels)
        if wiki_context:
            payload["contexto_wiki"] = wiki_context
        return json.dumps(payload, ensure_ascii=False)

    # ── parseo + fallback ───────────────────────────────────────────────

    def _parse(self, text: str) -> IntentPlan | None:
        obj = _loads_object(text)
        if obj is None:
            return None
        raw_actions = obj.get("acciones")
        if not isinstance(raw_actions, list):
            return None
        actions: list[IntentAction] = []
        for item in raw_actions:
            if not isinstance(item, dict):
                continue
            tipo = str(item.get("tipo", "")).strip().lower()
            if tipo not in _VALID_KINDS:
                continue
            actions.append(
                IntentAction(
                    kind=IntentActionKind(tipo),
                    descripcion=str(item.get("descripcion", "")).strip(),
                    objetivo=str(item.get("objetivo", "")).strip(),
                )
            )
            if len(actions) >= max(1, self.max_actions):
                break
        if not actions:
            return None
        truncated = len(actions) < len([a for a in raw_actions if isinstance(a, dict)])
        return IntentPlan(
            acciones=actions,
            resumen=str(obj.get("resumen", "")).strip(),
            truncated=truncated,
        )

    def _fallback_plan(self, metric_key: str) -> IntentPlan:
        kind = _FALLBACK_KIND.get(metric_key, IntentActionKind.CREAR_HOJA)
        noun = _KIND_NOUN.get(kind, kind.value)
        return IntentPlan(
            acciones=[
                IntentAction(kind=kind, descripcion=f"Propuesta de {noun} guiada por la métrica")
            ],
            resumen=f"Plan por defecto: 1 {noun}",
            from_fallback=True,
        )


def _loads_object(text: str) -> dict | None:
    text = (text or "").strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (ValueError, TypeError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except (ValueError, TypeError):
            return None
    return None


__all__ = ["IntentAction", "IntentActionKind", "IntentPlan", "SuggestionIntentService"]
