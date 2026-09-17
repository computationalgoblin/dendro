"""Genera un proyecto demo representativo para las capturas visuales.

Construye, vía los servicios de ``packages/application`` (nunca tocando
persistencia desde la UI), un mundo con varios anillos, hojas, ramas,
relaciones y candidatos pendientes, y lo guarda en disco. Devuelve un
manifiesto con la ruta y algunos ids útiles para abrir paneles.

Es presentation-agnostic: no importa nada de ``hosts/`` ni de Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.application.world_layer_service import WorldLayerService
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.era import Era
from packages.domain.result import Ok


@dataclass
class DemoManifest:
    path: Path
    ring_ids: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    relation_ids: list[str] = field(default_factory=list)
    candidate_ids: list[str] = field(default_factory=list)


def _ok(result, what: str):
    if not isinstance(result, Ok):
        raise RuntimeError(f"demo: fallo creando {what}: {getattr(result, 'error', result)!r}")
    return result.value


def build_demo_project(path: str | Path) -> DemoManifest:
    """Crea y guarda un proyecto demo. Devuelve un DemoManifest."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    ps = ProjectService()
    _ok(ps.create(name="Mundo Demo — Dendro"), "proyecto")

    wls = WorldLayerService(ps)
    es = EntityService(ps)
    rs = RelationService(ps)
    cs = CandidateService(ps)

    manifest = DemoManifest(path=path)

    # ── Cronología: present + 3 eras de distinto tramo (para ver la
    # proporcionalidad de la vista cronológica) ──────────────────────
    proj = ps.active_project
    chrono = proj.project_chronology
    chrono.present_year = 400
    chrono.eras = [
        Era(name="Edad Mítica", start_year=0, end_year=80, order=0,
            description="Los orígenes velados."),
        Era(name="Edad de los Reinos", start_year=80, end_year=320, order=1,
            description="Auge de casas y reinos."),
        Era(name="Crónicas Recientes", start_year=320, end_year=None, order=2,
            description="El presente y su memoria."),
    ]

    # ── Anillos (de núcleo a periferia) ──────────────────────────────
    ring_specs = [
        ("Núcleo mítico", "Lo más profundo y causalmente anterior."),
        ("Reinos y casas", "El estrato medio: política, linajes, lugares."),
        ("Crónicas recientes", "Lo más periférico y reciente."),
    ]
    rings: list[str] = []
    for name, desc in ring_specs:
        layer = _ok(wls.create_layer(name, desc), f"anillo {name!r}")
        rings.append(layer.id)
    manifest.ring_ids = rings

    # ── Entidades: hojas (personajes/objetos/lugares) y ramas (contenedores) ──
    # Las fechas (birth/death) pueblan la vista cronológica con líneas de vida.
    def make(
        name: str, kind: str, ring: str, desc: str = "",
        *, birth: int | None = None, death: int | None = None,
    ) -> str:
        data = {
            "name": name,
            "entity_type": kind,
            "brief_description": desc,
            "canon_state": "borrador",
            "layer_ids": [ring] if ring else [],
        }
        if birth is not None:
            data["birth_year"] = birth
        if death is not None:
            data["death_year"] = death
        ent = _ok(es.create_entity(data), f"entidad {name!r}")
        manifest.entity_ids.append(ent.id)
        return ent.id

    # Núcleo (Edad Mítica, 0–80)
    casa = make("Casa de Veladura", "contenedor", rings[0], "Linaje fundacional.", birth=5)
    aurelio = make("Aurelio el Primero", "personaje", rings[0], "Patriarca mítico.", birth=10, death=62)
    reliquia = make("La Simiente", "objeto", rings[0], "Reliquia ancestral.", birth=15)
    # Reinos (80–320)
    valdor = make("Reino de Valdor", "contenedor", rings[1], "Reino central.", birth=95)
    mira = make("Mira de Valdor", "personaje", rings[1], "Heredera.", birth=130, death=300)
    bosque = make("Bosque Umbrío", "lugar", rings[1], "Frontera salvaje.", birth=110)
    # Crónicas (320–presente 400)
    elen = make("Elen la Errante", "personaje", rings[2], "Cronista viajera.", birth=350)
    diario = make("Diario de Elen", "objeto", rings[2], "Registro de viajes.", birth=360)

    # ── Relaciones ───────────────────────────────────────────────────
    def relate(src: str, tgt: str, rtype: str) -> None:
        rel = rs.create_relation(src, tgt, rtype, {})
        if isinstance(rel, Ok):
            manifest.relation_ids.append(rel.value.id)

    relate(casa, aurelio, "contiene")
    relate(casa, reliquia, "contiene")
    relate(valdor, mira, "contiene")
    relate(valdor, bosque, "contiene")
    relate(elen, diario, "contiene")
    # BETA2-FIX-03/12 (cierre de oleada): estos dos usaban
    # `antepasado_de` y `conoce_a`, que NO son valores de `RelationType`. Antes
    # `create_relation` los aplanaba en silencio al default y devolvia Ok; desde
    # FIX-03 devuelve Error, asi que el demo se quedaba en 5 relaciones de 7.
    # Se corrigen a los tipos reales (`es_antepasado_de` lo aporta FIX-12).
    relate(aurelio, mira, "es_antepasado_de")
    relate(mira, elen, "conoce")

    # ── Hitos causales por año (pueblan la vista cronológica) ────────
    proj.causal_milestones.extend([
        CausalMilestone(
            title="Fundación de la Casa", year=22,
            affected_entity_ids=[casa, aurelio],
            metadata={"primary_entity_id": aurelio},
        ),
        CausalMilestone(
            title="Coronación de Mira", year=150,
            affected_entity_ids=[mira, valdor],
            metadata={"primary_entity_id": mira},
        ),
        CausalMilestone(
            title="El viaje de Elen", year=372,
            affected_entity_ids=[elen, diario],
            metadata={"primary_entity_id": elen},
        ),
    ])

    # ── Candidatos pendientes (semillas germinantes) ─────────────────
    # Tolerante a fallos: si el esquema de Candidate cambia, no rompe el demo.
    for title, just in [
        ("Sugerencia: vínculo entre Mira y el Bosque Umbrío", "Coherencia geográfica."),
        ("Sugerencia: nueva hoja «Orden de la Simiente»", "Mencionada en el diario."),
    ]:
        try:
            cand = cs.create_candidate(
                {
                    "title": title,
                    "candidate_type": "sugerencia_ia",
                    "state": "pendiente",
                    "source": "ia",
                    "confidence": 0.6,
                    "justification": just,
                }
            )
            if isinstance(cand, Ok):
                manifest.candidate_ids.append(getattr(cand.value, "id", ""))
        except Exception:  # noqa: BLE001 - el demo nunca debe romper por candidatos
            pass

    saved = ps.save(path)
    _ok(saved, "guardado del proyecto")
    return manifest


if __name__ == "__main__":  # pragma: no cover - utilidad manual
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "demo_dendro.json"
    m = build_demo_project(out)
    print(f"Demo guardado en {m.path}")
    print(
        f"  anillos={len(m.ring_ids)} entidades={len(m.entity_ids)} "
        f"relaciones={len(m.relation_ids)} candidatos={len(m.candidate_ids)}"
    )
