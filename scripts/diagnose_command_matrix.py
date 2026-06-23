"""Arnés de diagnóstico de la command bar (BETA1-UX4).

Recorre pares Acción×Ámbito de la matriz contra el PROVEEDOR REAL y traza todo el
camino: plan_command_jobs → create_job → execute_job → salida del modelo → staging
de candidatos → aceptación → canon → veredicto de render (contenedor vs hoja).

analizar/explicar/expandir son scope-agnósticas (el ámbito se oculta), así que un
caso por acción cubre toda su fila; editar:hoja == editar:rama (mismo job). Por eso
el set por defecto cubre los 25 pares de la matriz sin llamadas redundantes.

Uso (desde la raíz del repo, con el .venv):
    python scripts/diagnose_command_matrix.py            # set representativo (cubre los 25)
    python scripts/diagnose_command_matrix.py crear:hoja editar:relacion

La API key se lee de .env.local y NUNCA se imprime. Sin proveedor real, aborta.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_env_local() -> None:
    """Carga .env.local en os.environ sin imprimir valores (secretos incluidos)."""
    env_path = REPO_ROOT / ".env.local"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()


_load_env_local()

from packages.application.ai_jobs import (  # noqa: E402
    AIJobService,
    job_type_for_command,
)
from packages.application.candidate_service import CandidateService  # noqa: E402
from packages.application.command_expansion import plan_command_jobs  # noqa: E402
from packages.application.entity_service import EntityService  # noqa: E402
from packages.application.project_service import ProjectService  # noqa: E402
from packages.application.rag_service import RAGService  # noqa: E402
from packages.application.relation_service import RelationService  # noqa: E402
from packages.domain.causal_milestone import CausalMilestone  # noqa: E402
from packages.domain.result import Error  # noqa: E402
from packages.domain.world_layer import WorldLayer  # noqa: E402
from packages.infrastructure.ai_provider import AIProvider, provider_chat  # noqa: E402
from packages.infrastructure.openai_compatible_provider import get_provider  # noqa: E402
from packages.persistence.store import ProjectStore  # noqa: E402

# Criterio EXACTO del render del grafo para dibujar contenedor (graph_canvas.py).
RENDER_CONTAINER_KINDS = {"contenedor"}
# Tipos que la capa de contexto considera RAMA (command_expansion.BRANCH_TYPES).
BRANCH_TYPES = {
    "faccion", "cultura", "sistema_magico", "religion", "institucion", "trama", "contenedor",
}


class _RecordingProvider(AIProvider):
    """Envuelve el proveedor real y registra cada chat() (system, user, respuesta)."""

    def __init__(self, real: AIProvider):
        self._real = real
        self.calls: list[dict] = []

    @property
    def provider_name(self) -> str:
        return getattr(self._real, "provider_name", "real")

    def __getattr__(self, name):
        return getattr(self._real, name)

    def chat(self, system_prompt, user_message, timeout=None, **kwargs):
        text, error = provider_chat(
            self._real, system_prompt, user_message, timeout=timeout, **kwargs
        )
        self.calls.append({"response": text, "error": error})
        return text, error

    def invoke(self, operation):  # pragma: no cover
        return self._real.invoke(operation)


# Cada spec: prompt + cómo construir el context_scope a partir de ids sembrados.
# roles: "ents:N" (N entidades), "rel" (1 relación), "ring" (anillo activo),
# "hito" (1 hito). El set por defecto cubre los 25 pares (ver cabecera).
PAIR_SPECS: dict[tuple[str, str], dict] = {
    ("crear", "hoja"): {"prompt": "Crea un herrero exiliado que oculta su pasado noble.", "roles": []},
    ("crear", "rama"): {"prompt": "Crea una orden de monjes guerreros con su jerarquía interna.", "roles": []},
    ("crear", "relacion"): {"prompt": "Relaciona a estos personajes como rivales de una orden.", "roles": ["ents:2"]},
    ("crear", "anillo"): {"prompt": "Crea un estrato inicial: la era de los primeros reinos.", "roles": ["ring"]},
    ("crear", "hito"): {"prompt": "Crea un hito: la batalla que dividió el continente.", "roles": ["ents:1"]},
    ("editar", "hoja"): {"prompt": "Hazlo más sombrío: dale una cicatriz y una deuda de sangre.", "roles": ["ents:1"]},
    ("editar", "relacion"): {"prompt": "Convierte esta alianza en una rivalidad latente.", "roles": ["rel"]},
    ("editar", "anillo"): {"prompt": "Reescribe este estrato con un clima más árido.", "roles": ["ring"]},
    ("editar", "hito"): {"prompt": "Adelanta este suceso un siglo y suaviza sus consecuencias.", "roles": ["hito"]},
    ("analizar", "hoja"): {"prompt": "Busca incoherencias entre estas entidades.", "roles": ["ents:2"]},
    ("explicar", "hoja"): {"prompt": "Explica el origen de esta entidad y cómo llegó aquí.", "roles": ["ents:1", "ring"]},
    ("expandir", "hoja"): {"prompt": "Amplía el worldbuilding alrededor de esta entidad.", "roles": ["ents:1"]},
}

# Set por defecto: cubre cada AIJobType distinto de los 25 pares.
DEFAULT_PAIRS = [
    ("crear", "hoja"), ("crear", "rama"), ("crear", "relacion"),
    ("crear", "anillo"), ("crear", "hito"),
    ("editar", "hoja"), ("editar", "relacion"), ("editar", "anillo"), ("editar", "hito"),
    ("analizar", "hoja"), ("explicar", "hoja"), ("expandir", "hoja"),
]


def _seed_graph(es: EntityService, rs: RelationService, ps: ProjectService) -> dict:
    """Siembra entidades, una relación, un anillo y un hito para los pares que lo piden."""
    ent_ids = []
    seeds = [
        ("Devian", "Un herrero del puerto, amable y trabajador.",
         "Devian regenta la fragua del muelle. Tiene fama de honrado y de no deber nada a nadie."),
        ("Mara", "Una mercader ambiciosa de la ciudad alta.",
         "Mara controla tres rutas de especias y sueña con un asiento en el consejo."),
        ("Korr", "Un guardia veterano de la muralla norte.",
         "Korr lleva veinte años en la muralla; ha visto demasiados inviernos y pocas recompensas."),
    ]
    for name, brief, extended in seeds:
        res = es.create_entity({"name": name, "entity_type": "personaje",
                                "brief_description": brief, "extended_description": extended})
        if not isinstance(res, Error):
            ent_ids.append(res.value.id)
    rel_id = ""
    if len(ent_ids) >= 2:
        rr = rs.create_relation(source_id=ent_ids[0], target_id=ent_ids[1],
                                relation_type="es_aliado_de", data={})
        if not isinstance(rr, Error):
            rel_id = rr.value.id
    proj = ps.active_project
    ring = WorldLayer(id="layer_seed_1", name="Geografía y Naturaleza",
                      description="Estrato de prueba", order=0, is_visible=True, is_default=False)
    proj.world_layers.append(ring)
    hito_id = ""
    try:
        hito = CausalMilestone.from_dict({"title": "Fundación del Reino", "summary": "Hito de prueba"})
        proj.causal_milestones.append(hito)
        hito_id = hito.id
    except Exception:
        pass
    return {"ents": ent_ids, "rel": rel_id, "ring": ring.id, "hito": hito_id}


def _build_scope(roles: list[str], seed: dict) -> dict:
    scope: dict = {}
    for role in roles:
        if role.startswith("ents:"):
            n = int(role.split(":", 1)[1])
            scope["selected_entity_ids"] = seed["ents"][:n]
        elif role == "rel":
            scope["selected_relation_ids"] = [seed["rel"]] if seed["rel"] else []
        elif role == "ring":
            scope["active_ring_id"] = seed["ring"]
            scope["focused_ring_id"] = seed["ring"]
        elif role == "hito":
            scope["selected_milestone_ids"] = [seed["hito"]] if seed["hito"] else []
    return scope


def _summarize_model_output(response: str | None) -> dict:
    if not response:
        return {"parse": "vacío"}
    try:
        from packages.application.ai_jobs import _extract_json
        payload = _extract_json(response)
    except Exception as exc:  # pragma: no cover
        return {"parse_error": str(exc), "raw_head": response[:200]}
    if not isinstance(payload, dict):
        return {"parse": "no-dict", "raw_head": response[:200]}
    out = {"keys": sorted(payload.keys())}
    for key in ("hojas", "ramas", "entities", "trees", "relations", "rings",
                "milestones", "entity_edits", "relation_edits", "ring_edits",
                "milestone_edits", "issues", "report"):
        val = payload.get(key)
        if isinstance(val, list) and val:
            out[key] = [
                {"name": it.get("name") or it.get("title") or it.get("entity_name"),
                 "entity_type": it.get("entity_type"),
                 "display_type": it.get("display_type")}
                for it in val if isinstance(it, dict)
            ][:5]
    return out


def _accept_and_inspect(c: dict, ps: ProjectService, cands: CandidateService) -> dict:
    info = {"candidate_type": c.get("candidate_type"),
            "proposed_keys": sorted((c.get("proposed_data") or {}).keys())}
    n_ent = len(ps.active_project.entities)
    n_rel = len(ps.active_project.relations)
    n_ring = len(ps.active_project.world_layers)
    n_hito = len(ps.active_project.causal_milestones)
    made = cands.create_candidate(c)
    if isinstance(made, Error):
        info["create_error"] = made.error
        return info
    acc = cands.accept_candidate(made.value.id)
    if isinstance(acc, Error):
        info["accept_error"] = acc.error
        return info
    meta = made.value.metadata or {}
    proj = ps.active_project
    ent_id = meta.get("created_entity_id")  # id de la entidad/contenedor creada
    if ent_id:
        ent = next((e for e in proj.entities if e.id == ent_id), None)
        if ent is not None:
            et = ent.entity_type.value
            kids = [r for r in proj.relations
                    if r.relation_type.value == "contiene" and r.source_id == ent.id]
            info.update({
                "created": "entidad",
                "entity_type": et,
                "custom_metadata_keys": sorted((ent.custom_metadata or {}).keys()),
                "render_as_container": et in RENDER_CONTAINER_KINDS,
                "context_considers_branch": et in BRANCH_TYPES,
                "children_contiene": len(kids),
            })
            return info
    edited = [k for k in meta if k.startswith("edited_") and k.endswith("_id")]
    if edited:
        info["created"] = "editado:" + ",".join(k[len("edited_"):-len("_id")] for k in edited)
    elif meta.get("created_relation_id"):
        info["created"] = "relacion"
    elif meta.get("created_ring_id") or len(proj.world_layers) > n_ring:
        info["created"] = "anillo"
    elif meta.get("created_milestone_id") or len(proj.causal_milestones) > n_hito:
        info["created"] = "hito"
    elif len(proj.entities) > n_ent:
        info["created"] = f"entidad(es) x{len(proj.entities) - n_ent} (sin stamp)"
    else:
        info["created"] = "nada (marcado aceptado)"
        info["stamps"] = sorted(meta.keys())
    return info


def _run_pair(action: str, scope_name: str, ps: ProjectService, ai: AIJobService,
              cands: CandidateService, rec: _RecordingProvider, seed: dict) -> dict:
    spec = PAIR_SPECS.get((action, scope_name), {"prompt": "Haz algo.", "roles": []})
    prompt = spec["prompt"]
    scope_dict = _build_scope(spec.get("roles", []), seed)
    report: dict = {"pair": f"{action}:{scope_name}", "prompt": prompt, "scope": scope_dict}
    try:
        report["job_type"] = job_type_for_command(action, scope_name).value
    except ValueError as exc:
        report["error"] = f"par no soportado: {exc}"
        return report

    plan = plan_command_jobs(
        action, scope_name, prompt,
        selected_entity_ids=scope_dict.get("selected_entity_ids") or [],
        selected_relation_ids=scope_dict.get("selected_relation_ids") or [],
        suggestion_count=2,
        active_ring_id=str(scope_dict.get("active_ring_id") or ""),
    )
    if plan.error:
        report["plan_error"] = plan.error
        return report
    report["jobs"] = []
    for planned in plan.jobs:
        job_rep: dict = {"job_type": planned.job_type.value}
        merged = dict(scope_dict)
        merged.update(planned.context_overrides)
        before = len(rec.calls)
        created = ai.create_job(planned.job_type, planned.prompt, context_scope=merged, explicit=True)
        if isinstance(created, Error):
            job_rep["create_error"] = created.error
            report["jobs"].append(job_rep)
            continue
        executed = ai.execute_job(created.value.id)
        if isinstance(executed, Error):
            job_rep["execute_error"] = executed.error
            report["jobs"].append(job_rep)
            continue
        resp = rec.calls[-1]["response"] if len(rec.calls) > before else None
        job_rep["model_output"] = _summarize_model_output(resp)
        staged = (executed.value.result or {}).get("candidates") or []
        job_rep["n_staged"] = len(staged)
        job_rep["accepted"] = [_accept_and_inspect(c, ps, cands) for c in staged]
        report["jobs"].append(job_rep)
    return report


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    real = get_provider()
    if real.__class__.__name__ == "SimulatedAIProvider":
        print("ABORTADO: no hay proveedor real configurado (.env.local).")
        return 2
    print(f"Proveedor: {real.provider_name} · modelo: {getattr(real, 'model', '?')}")

    rec = _RecordingProvider(real)
    ps = ProjectService(store=ProjectStore())
    ps.create(name="Diagnóstico command bar")
    es = EntityService(project_service=ps)
    rs = RelationService(project_service=ps)
    cands = CandidateService(ps, es, rs)
    rag = RAGService()
    ai = AIJobService(provider=rec, rag_service=rag,
                      project_provider=lambda: ps.active_project, timeout_seconds=120)
    seed = _seed_graph(es, rs, ps)
    try:
        rag.index_project(ps.active_project)  # para que la selección llegue al prompt
    except Exception as exc:
        print(f"(aviso) RAG index falló: {exc}")

    args = sys.argv[1:]
    if args:
        pairs = [(a.partition(":")[0].strip(), a.partition(":")[2].strip()) for a in args]
    else:
        pairs = DEFAULT_PAIRS

    reports = []
    for action, scope_name in pairs:
        print(f"\n=== {action}:{scope_name} ===", flush=True)
        rep = _run_pair(action, scope_name, ps, ai, cands, rec, seed)
        reports.append(rep)
        print(json.dumps(rep, ensure_ascii=False, indent=2), flush=True)

    print("\n=== RESUMEN ===")
    for rep in reports:
        bits = []
        for j in rep.get("jobs", []):
            for a in j.get("accepted", []):
                if "entity_type" in a:
                    bits.append(f"{a['entity_type']}=>{'cont' if a['render_as_container'] else 'hoja'}")
                elif a.get("created"):
                    bits.append(str(a["created"]))
        err = rep.get("plan_error") or rep.get("error") or ""
        print(f"  {rep['pair']}: {rep.get('job_type','?')} | {bits or err or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
