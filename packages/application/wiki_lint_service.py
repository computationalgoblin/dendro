"""WikiLintService — salud de la wiki (BETA2-WIKI-07).

Pasada de 'lint' bajo demanda, análoga al mantenimiento periódico del método
Karpathy: detecta incoherencias de la wiki SIN tocar canon. La parte principal es
**determinista** (sin IA); opcionalmente una única llamada IA (sin bucle) busca
contradicciones cruzadas entre páginas. Todo se reporta como incidencias
revisables; nada se convierte en canon (contrato ``wiki_memoria.md`` §5.2).

Categorías deterministas:
- **huérfanas**: páginas cuyo elemento (target) ya no existe en el canon,
- **enlaces rotos**: wikilinks/citas/dependencias que apuntan a ids ausentes,
- **stale**: páginas ``FALTA_REGAR``/``SECADA`` (afirmaciones potencialmente obsoletas),
- **contradicciones**: incidencias ``CONTRADICCION`` ya ancladas en las páginas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from packages.domain.narrative_memory import MemoryFreshness, MemoryIssueKind, MemoryTargetKind
from packages.domain.result import Error, Ok, Result

_STALE = frozenset({MemoryFreshness.FALTA_REGAR, MemoryFreshness.SECADA})

_AI_SYSTEM = (
    "Eres un revisor de coherencia de una wiki narrativa. Recibirás varias PÁGINAS "
    "(síntesis editoriales derivadas, NO canon). Señala solo CONTRADICCIONES claras entre "
    "páginas distintas. No inventes; si no hay contradicciones evidentes, devuelve lista vacía. "
    'Responde SOLO JSON: {"contradicciones": [{"texto": "...", "paginas": ["<id>", "<id>"]}]}'
)


@dataclass(frozen=True)
class WikiLintIssue:
    kind: str  # orphan | broken_link | stale | contradiction
    target_kind: str
    target_id: str
    context: str
    detail: str


@dataclass
class WikiLintReport:
    orphans: list[WikiLintIssue] = field(default_factory=list)
    broken_links: list[WikiLintIssue] = field(default_factory=list)
    stale: list[WikiLintIssue] = field(default_factory=list)
    contradictions: list[WikiLintIssue] = field(default_factory=list)

    def all_issues(self) -> list[WikiLintIssue]:
        return [*self.orphans, *self.broken_links, *self.stale, *self.contradictions]

    def is_clean(self) -> bool:
        return not self.all_issues()


@dataclass
class WikiLintService:
    project_service: Any
    ai_job_service: Any = None

    def _proj(self):
        return getattr(self.project_service, "active_project", None)

    # ── lint determinista ───────────────────────────────────────────────

    def lint(self, project: Any = None) -> Result[WikiLintReport, str]:
        proj = project if project is not None else self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        report = WikiLintReport()
        for block in getattr(proj, "narrative_memories", []) or []:
            tk = block.target_kind.value
            # Huérfana: el elemento al que pertenece la página ya no existe.
            if block.target_id and not self._exists(proj, tk, block.target_id):
                report.orphans.append(
                    WikiLintIssue("orphan", tk, block.target_id, block.context,
                                  "la página apunta a un elemento inexistente")
                )
            # Enlaces rotos: wikilinks/citas/dependencias a ids ausentes.
            for group in (block.wikilinks, block.citations, block.dependencias):
                for ref in group or []:
                    if not self._exists(proj, ref.ref_kind.value, ref.ref_id):
                        report.broken_links.append(
                            WikiLintIssue("broken_link", tk, block.target_id, block.context,
                                          f"enlace roto → {ref.ref_kind.value}:{ref.ref_id}")
                        )
            # Stale: página obsoleta (Falta regar / Secada).
            if block.freshness in _STALE:
                report.stale.append(
                    WikiLintIssue("stale", tk, block.target_id, block.context,
                                  f"página {block.freshness.value}: puede estar obsoleta")
                )
            # Contradicciones ya ancladas en la página.
            for issue in block.issues:
                if issue.kind == MemoryIssueKind.CONTRADICCION and issue.texto:
                    report.contradictions.append(
                        WikiLintIssue("contradiction", tk, block.target_id, block.context,
                                      issue.texto)
                    )
        return Ok(report)

    # ── contradicciones cruzadas por IA (una sola llamada, sin bucle) ────

    def detect_ai_contradictions(self, project: Any = None) -> Result[list[WikiLintIssue], str]:
        """Una única llamada IA para contradicciones cruzadas entre páginas.

        No escribe nada: devuelve incidencias propuestas (para que el caller las
        ancle como ``MemoryIssue`` si el usuario acepta). Sin proveedor, error claro.
        """
        proj = project if project is not None else self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        if self.ai_job_service is None or self.ai_job_service.provider_unconfigured():
            return Error("No hay proveedor de IA configurado para el lint IA")

        pages = [
            {"id": b.target_id, "kind": b.target_kind.value, "resumen": b.resumen_editorial,
             "cuerpo": b.cuerpo}
            for b in (getattr(proj, "narrative_memories", []) or [])
            if b.resumen_editorial.strip() or b.cuerpo.strip()
        ]
        if len(pages) < 2:
            return Ok([])  # con menos de dos páginas no hay contradicción cruzada
        try:
            text, err = self.ai_job_service.raw_json_completion(
                _AI_SYSTEM, json.dumps({"paginas": pages}, ensure_ascii=False)
            )
        except Exception as exc:  # noqa: BLE001 — el lint nunca rompe el flujo
            return Error(str(exc))
        if err or not text:
            return Error(err or "sin respuesta del proveedor")
        parsed = self._parse(text)
        out: list[WikiLintIssue] = []
        for item in (parsed.get("contradicciones") or []) if parsed else []:
            if not isinstance(item, dict):
                continue
            texto = str(item.get("texto", "")).strip()
            if not texto:
                continue
            paginas = [str(p) for p in (item.get("paginas") or [])]
            anchor = paginas[0] if paginas else ""
            out.append(
                WikiLintIssue("contradiction", MemoryTargetKind.ENTITY.value, anchor, "",
                              f"{texto} (páginas: {', '.join(paginas)})")
            )
        return Ok(out)

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _exists(proj: Any, kind: str, target_id: str) -> bool:
        if kind == MemoryTargetKind.PROJECT.value:
            return True
        if kind in (MemoryTargetKind.ENTITY.value, MemoryTargetKind.BRANCH.value):
            return hasattr(proj, "entity_by_id") and proj.entity_by_id(target_id) is not None
        if kind == MemoryTargetKind.RELATION.value:
            return hasattr(proj, "relation_by_id") and proj.relation_by_id(target_id) is not None
        if kind == MemoryTargetKind.MILESTONE.value:
            return any(h.id == target_id for h in getattr(proj, "causal_milestones", []) or [])
        if kind == MemoryTargetKind.RING.value:
            return any(lay.id == target_id for lay in getattr(proj, "world_layers", []) or [])
        return True  # kind desconocido: no lo marcamos roto

    @staticmethod
    def _parse(text: str) -> dict | None:
        text = (text or "").strip()
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else None
        except (ValueError, TypeError):
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                try:
                    obj = json.loads(text[start : end + 1])
                    return obj if isinstance(obj, dict) else None
                except (ValueError, TypeError):
                    return None
        return None


__all__ = ["WikiLintIssue", "WikiLintReport", "WikiLintService"]
