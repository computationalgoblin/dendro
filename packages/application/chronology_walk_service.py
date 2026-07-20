"""Servicio de aplicación del Modo Creación Cronológica (CRON).

Orquesta un recorrido guiado hito por hito: análisis editorial por paso (por el
MISMO pipeline IA que analyze_coherence), memoria de sesión persistente y
reanudable, parada ante problemas duros, e informe final.

Política de capa: muta el proyecto activo SOLO en memoria; la persistencia es
explícita vía ProjectService.save(). No importa persistencia ni UI. La IA nunca
muta canon: stagea candidatos/diffs que el host revisa.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.application.ai_jobs import AIJobType
from packages.application.candidate_service import CandidateService
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.domain.chronology_walk import (
    ChronologyWalkReport,
    ChronologyWalkSession,
    WalkAggressiveness,
    WalkDepth,
    WalkDirection,
    WalkMode,
    WalkStatus,
)
from packages.domain.result import Error, Ok, Result

# Tipos de problema que DETIENEN el recorrido (problema duro del hito).
HARD_KINDS: frozenset[str] = frozenset(
    {
        "contradiction",
        "causal_gap",
        "motivation_incompatibility",
        "impossible_temporal_order",
        "higher_ring_contradiction",
        "missing_required_element",
    }
)

# Tipos de problema clasificados como contradicción vs hueco en el informe.
_CONTRADICTION_KINDS: frozenset[str] = frozenset(
    {
        "contradiction",
        "impossible_temporal_order",
        "higher_ring_contradiction",
        "motivation_incompatibility",
    }
)
_GAP_KINDS: frozenset[str] = frozenset({"causal_gap", "missing_required_element"})

_SUMMARY_MAX_CHARS = 1200


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _temperature_for_mode(mode: WalkMode) -> float:
    if mode is WalkMode.CONSISTENCIA:
        return 0.15
    if mode is WalkMode.CREATIVO:
        return 0.6
    return 0.3  # MIXTO


def _num_suggestions_for_depth(depth: WalkDepth) -> int:
    if depth is WalkDepth.LIGERA:
        return 1
    if depth is WalkDepth.PROFUNDA:
        return 5
    return 3  # NORMAL


def _sort_key(hito: Any) -> tuple[int, float, float, str]:
    """Clave de orden cronológico (año primero), espejo de milestone_sort_value.

    No se importa el widget desktop (límite de capas); se reimplementa la
    semántica: hitos con año entero van antes y ordenados por año, con
    ``metadata.sort_index`` como desempate; los no datados van después.
    """
    meta = getattr(hito, "metadata", None) or {}
    try:
        tiebreak = float(meta.get("sort_index", 0) or 0)
    except (TypeError, ValueError):
        tiebreak = 0.0
    title = str(getattr(hito, "title", ""))
    year = getattr(hito, "year", None)
    if isinstance(year, int) and not isinstance(year, bool):
        return (0, float(year), tiebreak, title)
    return (1, 0.0, tiebreak, title)


@dataclass
class ChronologyWalkService:
    """Casos de uso del recorrido cronológico.

    Devuelve siempre ``Result[T, str]``. Reusa ``AIJobService.run_focused_job``
    para el análisis IA y ``CandidateService`` indirectamente (la UI stagea).
    """

    project_service: Any
    ai_job_service: Any
    candidate_service: CandidateService | None = None
    milestone_service: CausalMilestoneService | None = None
    history_service: Any = None
    navigator: Any = None  # BETA2-WIKI-09: el paso del walk navega la wiki para su contexto

    # ── helpers de proyecto/hito ──────────────────────────────────────────
    def _proj(self) -> Result[Any, str]:
        project = getattr(self.project_service, "active_project", None)
        if project is None:
            return Error("No active project")
        return Ok(project)

    def _get_session(self, session_id: str) -> Result[ChronologyWalkSession, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        for session in proj.value.chronology_walk_sessions:
            if session.id == session_id:
                return Ok(session)
        return Error(f"Recorrido '{session_id[:8]}' no encontrado")

    def _ordered_milestones(self, proj: Any) -> list[Any]:
        return sorted(list(proj.causal_milestones), key=_sort_key)

    def _milestone_by_id(self, proj: Any, mid: str) -> Any | None:
        for hito in proj.causal_milestones:
            if hito.id == mid:
                return hito
        return None

    def _index_of(self, ordered: list[Any], mid: str) -> int:
        for i, hito in enumerate(ordered):
            if hito.id == mid:
                return i
        return -1

    # ── contexto estratificado ────────────────────────────────────────────
    def _neighbors(self, ordered: list[Any], idx: int, window: int = 1) -> list[dict[str, Any]]:
        lo = max(0, idx - window)
        hi = min(len(ordered), idx + window + 1)
        return [self._hito_brief(h) for i, h in enumerate(ordered[lo:hi], start=lo) if i != idx]

    def _arc(
        self, ordered: list[Any], start_idx: int, current_idx: int, direction: WalkDirection
    ) -> list[dict[str, Any]]:
        if start_idx < 0 or current_idx < 0:
            return []
        lo, hi = sorted((start_idx, current_idx))
        arc = [self._hito_brief(h) for h in ordered[lo : hi + 1]]
        if direction is WalkDirection.PAST:
            arc.reverse()
        return arc

    def _rings_context(self, proj: Any, hito: Any) -> dict[str, Any]:
        ctx: dict[str, Any] = {
            "layer_ids": list(getattr(hito, "layer_ids", []) or []),
            "affected_layer_ids": list(getattr(hito, "affected_layer_ids", []) or []),
            "causal_parent_hito_ids": list(getattr(hito, "causal_parent_hito_ids", []) or []),
            "causal_child_hito_ids": list(getattr(hito, "causal_child_hito_ids", []) or []),
        }
        if self.milestone_service is not None:
            chain = self.milestone_service.list_causal_chain(hito.id)
            if isinstance(chain, Ok):
                ctx["causal_chain"] = [self._hito_brief(h) for h in chain.value]
        return ctx

    @staticmethod
    def _hito_brief(hito: Any) -> dict[str, Any]:
        return {
            "id": hito.id,
            "title": getattr(hito, "title", ""),
            "year": getattr(hito, "year", None),
            "description": getattr(hito, "description", ""),
            "affected_entity_ids": list(getattr(hito, "affected_entity_ids", []) or []),
        }

    def _build_step_context(
        self,
        session: ChronologyWalkSession,
        proj: Any,
        hito: Any,
        ordered: list[Any],
        idx: int,
    ) -> dict[str, Any]:
        start_idx = self._index_of(ordered, session.start_milestone_id)
        return {
            "selected_entity_ids": list(getattr(hito, "affected_entity_ids", []) or []),
            "model_temperature": _temperature_for_mode(session.mode),
            "directivas": {
                "parametros": {
                    "agresividad": session.aggressiveness.value,
                    "numero_sugerencias": _num_suggestions_for_depth(session.depth),
                    "modo_recorrido": session.mode.value,
                    "profundidad": session.depth.value,
                }
            },
            "chrono_walk": {
                "mode": session.mode.value,
                "depth": session.depth.value,
                "aggressiveness": session.aggressiveness.value,
                "direction": session.direction.value,
                "current": self._hito_brief(hito),
                "neighbors": self._neighbors(ordered, idx),
                "arc": self._arc(ordered, start_idx, idx, session.direction),
                "rings": self._rings_context(proj, hito),
                "session_state": {
                    "accumulated_summary": session.accumulated_summary,
                    "open_problems": [
                        dict(p) for p in session.open_problems if not p.get("resolved")
                    ],
                    "decisions": [dict(d) for d in session.decisions],
                    "last_narrative_state": dict(session.last_narrative_state),
                    "visited_count": len(session.visited_milestone_ids),
                },
            },
        }

    # ── ciclo de vida del recorrido ───────────────────────────────────────
    def start_walk(
        self,
        start_milestone_id: str,
        direction: WalkDirection | str = WalkDirection.FUTURE,
        mode: WalkMode | str = WalkMode.MIXTO,
        depth: WalkDepth | str = WalkDepth.NORMAL,
        aggressiveness: WalkAggressiveness | str = WalkAggressiveness.REPARAR,
    ) -> Result[ChronologyWalkSession, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        if self._milestone_by_id(proj.value, start_milestone_id) is None:
            return Error(f"Hito de inicio '{start_milestone_id[:8]}' no encontrado")
        # Si ya hay un recorrido activo, se devuelve (no se solapan recorridos).
        existing = self.get_active_session()
        if isinstance(existing, Ok):
            return existing
        session = ChronologyWalkSession(
            direction=_as_enum(WalkDirection, direction, WalkDirection.FUTURE),
            mode=_as_enum(WalkMode, mode, WalkMode.MIXTO),
            depth=_as_enum(WalkDepth, depth, WalkDepth.NORMAL),
            aggressiveness=_as_enum(WalkAggressiveness, aggressiveness, WalkAggressiveness.REPARAR),
            start_milestone_id=start_milestone_id,
            current_milestone_id=start_milestone_id,
            status=WalkStatus.ACTIVE,
        )
        proj.value.chronology_walk_sessions.append(session)
        _touch_project(proj.value)
        return Ok(session)

    def get_active_session(self) -> Result[ChronologyWalkSession, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        for session in proj.value.chronology_walk_sessions:
            if session.status in (WalkStatus.ACTIVE, WalkStatus.PAUSED):
                return Ok(session)
        return Error("No hay recorrido cronológico activo")

    def resume(self, session_id: str) -> Result[ChronologyWalkSession, str]:
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        session = found.value
        if session.status in (WalkStatus.STOPPED, WalkStatus.COMPLETED):
            return Error("El recorrido ya ha terminado; no puede reanudarse")
        if session.status is WalkStatus.PAUSED:
            session.status = WalkStatus.ACTIVE
            session.touch()
        return Ok(session)

    def analyze_step(self, session_id: str) -> Result[dict[str, Any], str]:
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        session = found.value
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        hito = self._milestone_by_id(proj.value, session.current_milestone_id)
        if hito is None:
            return Error("El hito actual del recorrido no existe")
        run = self._run_step_analysis(session, proj.value, hito)
        if isinstance(run, Error):
            return run
        return Ok(self._fold_step(session, proj.value, hito, run.value))

    def analyze_step_at(self, session_id: str, milestone_id: str) -> Result[dict[str, Any], str]:
        """Analiza un hito SIN mutar la sesión (prefetch y desvíos causales).

        Devuelve el mismo dict de resultado que ``analyze_step`` pero sin la
        sección ``walk``: la memoria se pliega después con ``commit_step``,
        cuando el usuario LLEGA de verdad a la escena.
        """
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        session = found.value
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        hito = self._milestone_by_id(proj.value, str(milestone_id))
        if hito is None:
            return Error("El hito indicado no existe")
        return self._run_step_analysis(session, proj.value, hito)

    def commit_step(
        self, session_id: str, milestone_id: str, result: dict[str, Any]
    ) -> Result[dict[str, Any], str]:
        """Pliega en la sesión un análisis obtenido con ``analyze_step_at``.

        Solo se pliega el hito ACTUAL del recorrido: el resumen acumulado debe
        crecer en el orden cronológico real, no en el orden del prefetch.
        """
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        session = found.value
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        if str(milestone_id) != session.current_milestone_id:
            return Error("El hito no es el actual del recorrido; no se puede plegar su análisis")
        hito = self._milestone_by_id(proj.value, session.current_milestone_id)
        if hito is None:
            return Error("El hito actual del recorrido no existe")
        return Ok(self._fold_step(session, proj.value, hito, dict(result or {})))

    def step_scene(
        self, session_id: str, milestone_id: str | None = None
    ) -> Result[dict[str, Any], str]:
        """Datos deterministas de la escena de un hito (sin IA, sin mutación).

        Sin ``milestone_id`` describe el hito actual del recorrido; con él,
        cualquier hito (desvíos causales en modo «visita»).
        """
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        session = found.value
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        mid = str(milestone_id) if milestone_id else session.current_milestone_id
        hito = self._milestone_by_id(proj.value, mid)
        if hito is None:
            return Error("El hito indicado no existe")
        ordered = self._ordered_milestones(proj.value)
        idx = self._index_of(ordered, mid)
        nxt = idx + 1 if session.direction is WalkDirection.FUTURE else idx - 1
        next_id = ordered[nxt].id if 0 <= nxt < len(ordered) else None
        year = getattr(hito, "year", None)
        era_name = ""
        chron = getattr(proj.value, "project_chronology", None)
        if chron is not None and isinstance(year, int) and not isinstance(year, bool):
            era = chron.era_for_year(year)
            if era is not None:
                era_name = str(getattr(era, "name", "") or "")
        return Ok(
            {
                "session_id": session.id,
                "status": session.status.value,
                "direction": session.direction.value,
                "hito": self._hito_brief(hito),
                "era_name": era_name,
                "position": idx + 1,
                "total": len(ordered),
                "next_milestone_id": next_id,
                "causes": self._briefs_for_ids(
                    proj.value, getattr(hito, "causal_parent_hito_ids", []) or []
                ),
                "consequences": self._briefs_for_ids(
                    proj.value, getattr(hito, "causal_child_hito_ids", []) or []
                ),
                "open_problems": [
                    dict(p) for p in session.open_problems if p.get("milestone_id") == mid
                ],
                "is_visited": mid in session.visited_milestone_ids,
                "is_current": mid == session.current_milestone_id,
            }
        )

    def _briefs_for_ids(self, proj: Any, ids: list[str]) -> list[dict[str, Any]]:
        briefs: list[dict[str, Any]] = []
        for mid in ids:
            hito = self._milestone_by_id(proj, str(mid))
            if hito is not None:
                briefs.append(self._hito_brief(hito))
        return briefs

    def _run_step_analysis(
        self, session: ChronologyWalkSession, proj: Any, hito: Any
    ) -> Result[dict[str, Any], str]:
        """Lanza el job de análisis de un hito. NO muta sesión ni proyecto."""
        ordered = self._ordered_milestones(proj)
        idx = self._index_of(ordered, hito.id)
        context = self._build_step_context(session, proj, hito, ordered, idx)
        # BETA2-WIKI-09: navega la wiki para traer contexto coherente del paso (sin
        # prompt de usuario; corre en el worker del walk, no bloquea la UI).
        self._attach_wiki_context(context, hito)
        sentido = "el futuro" if session.direction is WalkDirection.FUTURE else "el pasado"
        prompt = (
            f"Analiza el hito «{getattr(hito, 'title', '')}» dentro del recorrido cronológico "
            f"hacia {sentido}. Da una lectura editorial, un diagnóstico y, según la "
            "agresividad, candidatos o cambios."
        )
        run = self.ai_job_service.run_focused_job(
            AIJobType.CHRONOLOGY_WALK_STEP, prompt, context_scope=context
        )
        if isinstance(run, Error):
            return run
        job = run.value
        result = dict(getattr(job, "result", None) or {})
        result["job_id"] = job.id
        return Ok(result)

    def _attach_wiki_context(self, context: dict[str, Any], hito: Any) -> None:
        """WIKI-09: adjunta ``contexto_wiki`` navegando la wiki (best-effort)."""
        if self.navigator is None:
            return
        try:
            from packages.application.wiki_navigator import NavigationRequest

            res = self.navigator.assemble_context(
                NavigationRequest(
                    intent=AIJobType.CHRONOLOGY_WALK_STEP.value,
                    focus_ids=[hito.id],
                    focus_kind="milestone",
                )
            )
            bundle = res.value if isinstance(res, Ok) else None
            if bundle is not None and not bundle.is_empty():
                context["contexto_wiki"] = bundle.as_context_dict()
        except Exception:  # noqa: BLE001 — la navegación nunca rompe el paso del walk
            pass

    def _fold_step(
        self, session: ChronologyWalkSession, proj: Any, hito: Any, result: dict[str, Any]
    ) -> dict[str, Any]:
        """Pliega un análisis en la memoria de sesión y arma la sección ``walk``."""
        payload = dict(result.get("model_payload") or {})
        if hito.id not in session.visited_milestone_ids:
            session.visited_milestone_ids.append(hito.id)
        self._fold_issues(session, hito.id, payload.get("issues"))
        narrative_state = payload.get("narrative_state")
        if isinstance(narrative_state, dict):
            session.last_narrative_state = dict(narrative_state)
        self._update_summary(session, hito, payload)

        stopped = self._should_stop(payload)
        if stopped:
            session.status = WalkStatus.PAUSED
        # BETA2-PLAY: registra la observación del paso en el historial de cada
        # entidad afectada del hito (lectura + issues, tengan o no edición). Se
        # pliega SOLO aquí (analyze/commit), no en el prefetch → sin duplicados.
        self._record_observation(session, hito, payload)
        session.touch()
        _touch_project(proj)

        ordered = self._ordered_milestones(proj)
        idx = self._index_of(ordered, hito.id)
        result["walk"] = {
            "session_id": session.id,
            "milestone_id": hito.id,
            "milestone_title": str(getattr(hito, "title", "")),
            "milestone_year": getattr(hito, "year", None),
            "position": idx + 1,
            "total": len(ordered),
            "stopped": stopped,
            "stop_reason": str(payload.get("stop_reason") or "") if stopped else "",
            "open_problems": [dict(p) for p in session.open_problems if not p.get("resolved")],
            "accumulated_summary": session.accumulated_summary,
            "status": session.status.value,
            "job_id": str(result.get("job_id") or ""),
        }
        return result

    def record_decision(
        self, session_id: str, decision: str, note: str = ""
    ) -> Result[ChronologyWalkSession, str]:
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        session = found.value
        session.decisions.append(
            {
                "milestone_id": session.current_milestone_id,
                "decision": str(decision),
                "note": str(note),
                "at": _now_iso(),
            }
        )
        # Una decisión sobre el hito actual resuelve sus problemas abiertos.
        for problem in session.open_problems:
            if problem.get("milestone_id") == session.current_milestone_id:
                problem["resolved"] = True
        if session.status is WalkStatus.PAUSED:
            session.status = WalkStatus.ACTIVE
        session.touch()
        _touch_project(self.project_service.active_project)
        return Ok(session)

    def defer_problems(self, session_id: str, note: str = "") -> Result[ChronologyWalkSession, str]:
        """Aplaza los problemas abiertos del hito actual SIN fingir resolución.

        El problema queda marcado ``deferred`` (sigue sin ``resolved``): deja de
        bloquear el avance pero permanece vivo y reaparece en el informe final.
        Resolver (decisión, reparación aplicada) sigue ganando a aplazar.
        """
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        session = found.value
        deferred = 0
        for problem in session.open_problems:
            if problem.get("milestone_id") == session.current_milestone_id and not problem.get(
                "resolved"
            ):
                problem["deferred"] = True
                deferred += 1
        if not deferred:
            return Error("No hay problemas abiertos que aplazar en este hito")
        session.decisions.append(
            {
                "milestone_id": session.current_milestone_id,
                "decision": "aplazado",
                "note": str(note),
                "at": _now_iso(),
            }
        )
        if session.status is WalkStatus.PAUSED:
            session.status = WalkStatus.ACTIVE
        session.touch()
        _touch_project(self.project_service.active_project)
        return Ok(session)

    def advance(self, session_id: str) -> Result[ChronologyWalkSession, str]:
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        session = found.value
        if session.status in (WalkStatus.STOPPED, WalkStatus.COMPLETED):
            return Error("El recorrido ya ha terminado")
        if self._has_unresolved_for(session, session.current_milestone_id):
            return Error(
                "Hay un problema sin resolver en este hito; registra una decisión antes de avanzar"
            )
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        ordered = self._ordered_milestones(proj.value)
        idx = self._index_of(ordered, session.current_milestone_id)
        if idx < 0:
            return Error("El hito actual del recorrido no existe")
        nxt = idx + 1 if session.direction is WalkDirection.FUTURE else idx - 1
        if nxt < 0 or nxt >= len(ordered):
            # No quedan más hitos en esta dirección → cierre del recorrido.
            self._finalize(session, proj.value)
            session.status = WalkStatus.COMPLETED
            session.touch()
            _touch_project(proj.value)
            return Ok(session)
        session.current_milestone_id = ordered[nxt].id
        session.status = WalkStatus.ACTIVE
        session.touch()
        _touch_project(proj.value)
        return Ok(session)

    def stop(self, session_id: str) -> Result[ChronologyWalkSession, str]:
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        session = found.value
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._finalize(session, proj.value)
        session.status = WalkStatus.STOPPED
        session.touch()
        _touch_project(proj.value)
        return Ok(session)

    def finalize_report(self, session_id: str) -> Result[ChronologyWalkReport, str]:
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        report = self._finalize(found.value, proj.value)
        _touch_project(proj.value)
        return Ok(report)

    def attach_generated_candidates(
        self, session_id: str, candidate_ids: list[str]
    ) -> Result[ChronologyWalkSession, str]:
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        session = found.value
        for cid in candidate_ids:
            cid = str(cid)
            if cid and cid not in session.generated_candidate_ids:
                session.generated_candidate_ids.append(cid)
        session.touch()
        _touch_project(self.project_service.active_project)
        return Ok(session)

    def apply_step(
        self, session_id: str, items: list[dict[str, Any]]
    ) -> Result[dict[str, Any], str]:
        """Aplica los cambios aceptados de un paso como BLOQUE ATÓMICO por ID.

        ``items``: lista de ``{"candidate_id": str, "edited_data": dict | None}``.
        Resuelve referencias por ID y aplica en orden de dependencias
        (creaciones → hitos → relaciones → ediciones/renombrados), de modo que
        un renombrado no deje una relación apuntando a un nombre antiguo.
        Todo pasa por ``CandidateService`` (canon, traza, historial).
        """
        if self.candidate_service is None:
            return Error("CandidateService no disponible")
        found = self._get_session(session_id)
        if isinstance(found, Error):
            return found
        proj = self._proj()
        if isinstance(proj, Error):
            return proj

        # 1) Resolver candidatos pedidos y aplicar las ediciones del usuario.
        selected: list[Any] = []
        for item in items or []:
            cid = str((item or {}).get("candidate_id") or "")
            if not cid:
                continue
            cand = self._candidate_by_id(proj.value, cid)
            if cand is None:
                continue
            edited = (item or {}).get("edited_data")
            if isinstance(edited, dict) and edited:
                cand.proposed_data = {**(cand.proposed_data or {}), **edited}
            selected.append(cand)

        # 2) Clasificar por dependencia.
        buckets: dict[str, list[Any]] = {
            "entity": [],
            "milestone": [],
            "relation": [],
            "edit": [],
        }
        for cand in selected:
            kind = self._change_kind(cand)
            if kind in buckets:
                buckets[kind].append(cand)

        applied: list[str] = []
        failed: list[dict[str, str]] = []

        # 3) Creaciones primero (entidades, luego hitos).
        for cand in buckets["entity"] + buckets["milestone"]:
            self._accept_one(cand, applied, failed)

        # 4) Relaciones: pre-resolver extremos por ID contra el canon ACTUAL
        #    (ya con las entidades nuevas creadas) antes de cualquier renombrado.
        name_to_id = {
            str(getattr(e, "name", "")).strip().lower(): e.id
            for e in proj.value.entities
            if str(getattr(e, "name", "")).strip()
        }
        for cand in buckets["relation"]:
            pd = dict(cand.proposed_data or {})
            if not pd.get("source_id"):
                sid = name_to_id.get(str(pd.get("source_name") or "").strip().lower())
                if sid:
                    pd["source_id"] = sid
            if not pd.get("target_id"):
                tid = name_to_id.get(str(pd.get("target_name") or "").strip().lower())
                if tid:
                    pd["target_id"] = tid
            cand.proposed_data = pd
            self._accept_one(cand, applied, failed)

        # 5) Ediciones / renombrados al final (las relaciones ya tienen ID fijo).
        for cand in buckets["edit"]:
            self._accept_one(cand, applied, failed)

        # 6) Aplicar una reparación RESUELVE los problemas abiertos del hito actual
        #    y reanuda el recorrido (si estaba en pausa por una parada dura), para
        #    que «Avanzar» funcione sin exigir además una decisión manual.
        session = found.value
        if applied:
            for problem in session.open_problems:
                if problem.get("milestone_id") == session.current_milestone_id:
                    problem["resolved"] = True
            if session.status is WalkStatus.PAUSED:
                session.status = WalkStatus.ACTIVE
            session.decisions.append(
                {
                    "milestone_id": session.current_milestone_id,
                    "decision": "reparado",
                    "note": f"{len(applied)} cambio(s) aplicado(s)",
                    "at": _now_iso(),
                }
            )
            session.touch()

        _touch_project(proj.value)
        return Ok({"applied": applied, "failed": failed})

    def _accept_one(self, cand: Any, applied: list[str], failed: list[dict[str, str]]) -> None:
        res = self.candidate_service.accept_candidate(cand.id)
        if isinstance(res, Error):
            failed.append({"candidate_id": cand.id, "error": res.error})
        else:
            applied.append(cand.id)

    @staticmethod
    def _candidate_by_id(proj: Any, cid: str) -> Any | None:
        for cand in getattr(proj, "candidates", []) or []:
            if cand.id == cid:
                return cand
        return None

    @staticmethod
    def _change_kind(cand: Any) -> str:
        ctype = getattr(getattr(cand, "candidate_type", None), "value", "") or ""
        pd = getattr(cand, "proposed_data", None) or {}
        if ctype == "entidad":
            return "entity"
        if ctype == "relacion":
            return "relation"
        if pd.get("kind") == "causal_milestone":
            return "milestone"
        if pd.get("edit_proposed_value"):
            return "edit"
        # PLAY-15: patch multi-campo — mismo bucket de aplicación que las ediciones.
        if isinstance(pd.get("edit_fields"), dict) and pd.get("edit_fields"):
            return "edit"
        return "report"

    def _record_observation(
        self, session: ChronologyWalkSession, hito: Any, payload: dict[str, Any]
    ) -> None:
        """BETA2-PLAY: deja la lectura del paso en el historial de las entidades
        afectadas (traza, no canon). No-op sin ``history_service`` inyectado."""
        if self.history_service is None:
            return
        record = getattr(self.history_service, "record", None)
        if not callable(record):
            return
        lectura = str(payload.get("summary") or payload.get("report") or "").strip()
        issues = payload.get("issues")
        obs_lines: list[str] = []
        if isinstance(issues, list):
            for issue in issues:
                if isinstance(issue, dict):
                    title = str(issue.get("title") or issue.get("kind") or "").strip()
                    desc = str(issue.get("description") or "").strip()
                    if title or desc:
                        obs_lines.append(f"• {title}: {desc}".strip(": "))
        description = lectura
        if obs_lines:
            description = (description + "\n" + "\n".join(obs_lines)).strip()
        if not description:
            return
        from packages.domain.source_history import HistoryEventType

        for entity_id in getattr(hito, "affected_entity_ids", []) or []:
            try:
                record(
                    HistoryEventType.OBSERVACION_RECORRIDO,
                    description=description,
                    affected_entity_ids=[str(entity_id)],
                    change_origin="recorrido_cronologico",
                    metadata={
                        "session_id": session.id,
                        "milestone_id": str(getattr(hito, "id", "")),
                        "object_type": "chronology_walk",
                    },
                )
            except Exception:  # noqa: BLE001 — la traza nunca rompe el recorrido
                pass

    # ── lógica interna ────────────────────────────────────────────────────
    def _fold_issues(self, session: ChronologyWalkSession, milestone_id: str, issues: Any) -> None:
        if not isinstance(issues, list):
            return
        existing = len(session.open_problems)
        for i, issue in enumerate(issues):
            if not isinstance(issue, dict):
                continue
            kind = str(issue.get("kind") or "")
            severity = str(issue.get("severity") or "media")
            # Oportunidades menores NO bloquean: van a bandeja como candidatos, no a problemas.
            if kind == "opportunity" or (severity == "baja" and kind not in HARD_KINDS):
                continue
            session.open_problems.append(
                {
                    "id": f"{milestone_id}:{existing + i}",
                    "milestone_id": milestone_id,
                    "kind": kind,
                    "severity": severity,
                    "title": str(issue.get("title") or ""),
                    "description": str(issue.get("description") or ""),
                    "resolved": False,
                }
            )

    def _update_summary(
        self, session: ChronologyWalkSession, hito: Any, payload: dict[str, Any]
    ) -> None:
        step_summary = str(payload.get("summary") or payload.get("report") or "").strip()
        if not step_summary:
            return
        title = str(getattr(hito, "title", "")).strip()
        line = f"- {title}: {step_summary}" if title else f"- {step_summary}"
        combined = (
            (session.accumulated_summary + "\n" + line).strip()
            if session.accumulated_summary
            else line
        )
        # Acotado: se conserva la cola (lo más reciente) bajo el límite.
        if len(combined) > _SUMMARY_MAX_CHARS:
            combined = combined[-_SUMMARY_MAX_CHARS:]
        session.accumulated_summary = combined

    @staticmethod
    def _should_stop(payload: dict[str, Any]) -> bool:
        if bool(payload.get("stop_required")):
            return True
        issues = payload.get("issues")
        if isinstance(issues, list):
            for issue in issues:
                if not isinstance(issue, dict):
                    continue
                if str(issue.get("severity")) == "alta":
                    return True
                if str(issue.get("kind")) in HARD_KINDS:
                    return True
        return False

    @staticmethod
    def _has_unresolved_for(session: ChronologyWalkSession, milestone_id: str) -> bool:
        # Un problema aplazado (deferred) NO bloquea: sigue vivo pero el usuario
        # decidió explícitamente seguir; reaparece en el informe final.
        return any(
            p.get("milestone_id") == milestone_id
            and not p.get("resolved")
            and not p.get("deferred")
            for p in session.open_problems
        )

    def _finalize(self, session: ChronologyWalkSession, proj: Any) -> ChronologyWalkReport:
        unresolved = [p for p in session.open_problems if not p.get("resolved")]
        if any(p.get("severity") == "alta" or p.get("kind") in HARD_KINDS for p in unresolved):
            verdict = "Incoherente: requiere atención antes de continuar"
        elif unresolved:
            verdict = "Parcialmente coherente"
        else:
            verdict = "Coherente hasta el hito revisado"
        report = ChronologyWalkReport(
            session_id=session.id,
            direction=session.direction,
            mode=session.mode,
            range_start_milestone_id=session.start_milestone_id,
            range_end_milestone_id=session.current_milestone_id,
            milestones_analyzed=list(session.visited_milestone_ids),
            verdict=verdict,
            critical_gaps=[dict(p) for p in session.open_problems if p.get("kind") in _GAP_KINDS],
            contradictions=[
                dict(p) for p in session.open_problems if p.get("kind") in _CONTRADICTION_KINDS
            ],
            candidates_created=list(session.generated_candidate_ids),
            decisions=[dict(d) for d in session.decisions],
            timeline_reviewed_up_to_milestone_id=session.current_milestone_id,
            recommended_next_steps=[
                str(p.get("title") or p.get("description") or "") for p in unresolved
            ],
        )
        deferred = [dict(p) for p in unresolved if p.get("deferred")]
        if deferred:
            report.metadata["deferred_problems"] = deferred
        proj.chronology_walk_reports.append(report)
        session.report_id = report.id
        return report


def _as_enum(enum_cls, value, default):
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    return default


def _touch_project(proj: Any) -> None:
    touch = getattr(proj, "touch", None)
    if callable(touch):
        try:
            touch()
        except Exception:
            pass


__all__ = ["ChronologyWalkService", "HARD_KINDS"]
