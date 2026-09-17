"""BETA2-FIX-10 (G2-15): la Continuidad corre sobre el canon del AUTOR.

Aitor, showrunner, rompió su propia serie cuatro veces a propósito —como canon
MANUAL, que es como escribe un jefe de continuidad— y no saltó ni un aviso: el
validador determinista de BETA1-J02 solo se ejecutaba al ACEPTAR un candidato de
IA. Aquí se reproducen las cuatro roturas (`beta-testing/2026-08-04/
guionista-serie/sesion_3.py`) sobre un proyecto en memoria y se comprueba que el
servicio las ve TODAS, sin IA, sin red y sin tocar el canon.
"""

from __future__ import annotations

from packages.application.continuity_service import (
    DISMISS_KEY,
    FAMILIA_CALENDARIO,
    FAMILIA_DATACION,
    FAMILIA_HISTORIA,
    ContinuityService,
)
from packages.domain.causal_milestone import (
    CausalMilestone,
    CausalMilestoneStatus,
    CausalMilestoneType,
)
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.era import Era
from packages.domain.project import Project
from packages.domain.project_chronology import ProjectChronology
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok
from packages.domain.temporal_span import TemporalSpan


class _ProveedorProhibido:
    """Si la Continuidad tocara la IA, este doble revienta el test."""

    def provider_unconfigured(self) -> bool:
        return True

    def raw_json_completion(self, system, user):  # pragma: no cover - no debe llamarse
        raise AssertionError("la Continuidad es determinista: no puede llamar a la IA")


class _ProjectService:
    def __init__(self, project: Project | None = None):
        self.active_project = project
        # Un servicio real de la app lleva la IA colgando; aquí es una trampa.
        self.ai_job_service = _ProveedorProhibido()


def _entidad(eid, nombre, tipo, birth=None, death=None):
    e = NarrativeEntity(id=eid, name=nombre, entity_type=tipo)
    e.set_life_span(TemporalSpan.from_years(birth, death))
    return e


def _hito(hid, titulo, year, participantes=(), padres=(), tipo=CausalMilestoneType.OTRO):
    return CausalMilestone(
        id=hid,
        title=titulo,
        year=year,
        milestone_type=tipo,
        status=CausalMilestoneStatus.CANON,
        affected_entity_ids=list(participantes),
        causal_parent_hito_ids=list(padres),
    )


def _orbita_muerta() -> Project:
    """La serie de Aitor, en pequeño y con las cuatro roturas dentro.

    C1 bilocación · C2 sabe+ignora a la vez · C3 muerto que reaparece ·
    C4 payoff antes que su setup.
    """
    proj = Project(id="orbita", name="Órbita Muerta")
    proj.project_chronology = ProjectChronology(
        present_year=16,
        eras=[
            Era(name="Antes del piloto", start_year=-1, end_year=0),
            Era(name="Temporada 1", start_year=1, end_year=8),
            Era(name="Temporada 2", start_year=9, end_year=16),
        ],
    )
    nadia = _entidad("nadia", "Nadia Kerr", EntityType.PERSONAJE, 1)
    teo = _entidad("teo", "Teodor «Teo» Kerr", EntityType.PERSONAJE, 1, 1)
    cubierta = _entidad("cubierta", "Cubierta 9", EntityType.LOCALIZACION, 0)
    estacion = _entidad("estacion", "Estación Cernida", EntityType.LOCALIZACION, 0)
    mentira = _entidad("mentira", "La Tierra es habitable", EntityType.REGLA_DEL_MUNDO, -1)
    proj.entities.extend([nadia, teo, cubierta, estacion, mentira])

    # C2: las dos afirmaciones opuestas, vigentes a la vez.
    proj.relations.append(
        NarrativeRelation(
            id="r-ignora",
            source_id="nadia",
            target_id="mentira",
            relation_type=RelationType.IGNORA,
        )
    )
    proj.relations.append(
        NarrativeRelation(
            id="r-sabe",
            source_id="nadia",
            target_id="mentira",
            relation_type=RelationType.SABE,
        )
    )

    proj.causal_milestones.extend(
        [
            _hito("h1x01", "1x01 — Chatarra", 1, ["nadia", "cubierta"]),
            # C1: Nadia, el mismo año, en un lugar distinto y disjunto.
            _hito("h1x01b", "1x01b — Nadia en la Estación", 1, ["nadia", "estacion"]),
            _hito("h1x03", "1x03 — Caja negra", 3, ["nadia"]),
            # C4: la consecuencia, fechada antes que su causa.
            _hito("h2x03b", "2x03b — El payoff imposible", 2, ["nadia"], ["h1x03"],
                  CausalMilestoneType.CONSECUENCIA),
            # C3: Teo muere en el año 1 y participa en el final de serie.
            _hito("h2x08", "2x08 — Habitable", 16, ["nadia", "teo"], ["h1x03"],
                  CausalMilestoneType.REVELACION),
        ]
    )
    return proj


def _servicio(project=None):
    return ContinuityService(_ProjectService(project if project is not None else _orbita_muerta()))


# ── Las cuatro roturas ────────────────────────────────────────────────────


def test_beta_m2fix10_las_cuatro_roturas_de_aitor_saltan():
    svc = _servicio()
    res = svc.analyze()
    assert isinstance(res, Ok)
    codigos = sorted(i.code for i in res.value)
    assert codigos == [
        "T07_MILESTONE_BEFORE_PARENT",  # C4 payoff antes del setup
        "T10_BILOCATION",  # C1 bilocación
        "T11_PARTICIPANT_OUTSIDE_LIFE",  # C3 muerto que reaparece
        "T12_KNOWS_AND_IGNORES",  # C2 sabe e ignora a la vez
    ]


def test_beta_m2fix10_count_cuadra_con_lo_que_lista():
    """Lección de BETA-FIX-05 (ronda 1): la píldora y las tarjetas
    se descuadraron por contar cosas distintas."""
    svc = _servicio()
    assert svc.count() == len(svc.analyze().value) == 4
    assert sum(g.count for g in svc.grouped().value) == svc.count()


def test_beta_m2fix10_sin_roturas_no_hay_ruido():
    """Silencio honesto: el mismo mundo, sin las roturas, no dice nada."""
    proj = _orbita_muerta()
    proj.relations = [r for r in proj.relations if r.id != "r-sabe"]  # C2 fuera
    proj.causal_milestones = [
        h for h in proj.causal_milestones if h.id not in ("h1x01b", "h2x03b")  # C1 y C4 fuera
    ]
    hito = next(h for h in proj.causal_milestones if h.id == "h2x08")
    hito.affected_entity_ids = ["nadia"]  # C3 fuera
    assert ContinuityService(_ProjectService(proj)).analyze().value == []


def test_beta_m2fix10_la_ia_apagada_da_el_mismo_resultado():
    """Coste IA cero: el doble de proveedor revienta si alguien lo llama."""
    svc = _servicio()
    assert svc.count() == 4
    assert not hasattr(svc, "ai_job_service")


def test_beta_m2fix10_sin_proyecto_devuelve_error_no_excepcion():
    svc = ContinuityService(_ProjectService(None))
    assert isinstance(svc.analyze(), Error)
    assert isinstance(svc.grouped(), Error)
    assert isinstance(svc.loose_threads(), Error)
    assert isinstance(svc.dismiss("cont:entity:x:T01:"), Error)
    assert svc.count() == 0


# ── Agrupación (el ruido es el enemigo del producto) ──────────────────────


def test_beta_m2fix10_agrupa_por_codigo_y_separa_familias():
    svc = _servicio()
    grupos = svc.grouped().value
    assert {g.code for g in grupos} == {
        "T07_MILESTONE_BEFORE_PARENT",
        "T10_BILOCATION",
        "T11_PARTICIPANT_OUTSIDE_LIFE",
        "T12_KNOWS_AND_IGNORES",
    }
    assert all(g.family == FAMILIA_HISTORIA for g in grupos)
    assert all(g.title and g.title != g.code for g in grupos)


def test_beta_m2fix10_calendario_y_datacion_no_pesan_como_contradicciones():
    """El mundo entregado da 19 avisos de calendario cuya CAUSA es una datación
    desincronizada (§5 del hallazgo). Se agrupan y se separan: «tu calendario no
    cubre estas fechas» no es «tu serie se contradice»."""
    proj = _orbita_muerta()
    for entidad in proj.entities:
        entidad.life_span.start.year = -7300  # escala vieja, como el mundo de Aitor
    svc = ContinuityService(_ProjectService(proj))
    por_familia = {}
    for grupo in svc.grouped().value:
        por_familia.setdefault(grupo.family, {})[grupo.code] = grupo.count
    assert por_familia[FAMILIA_CALENDARIO]["T02_OUTSIDE_ERAS"] == 5
    assert por_familia[FAMILIA_DATACION]["T14_DATING_DESYNC"] == 5
    # Y las contradicciones de la historia siguen ahí, sin diluirse.
    assert "T10_BILOCATION" in por_familia[FAMILIA_HISTORIA]


# ── Caché derive-on-read ──────────────────────────────────────────────────


def test_beta_m2fix10_no_recomputa_sin_cambios_y_si_tras_touch():
    svc = _servicio()
    svc.analyze()
    assert svc.computes == 1
    svc.analyze()
    assert svc.computes == 1  # misma revisión de índice: no se recalcula
    svc.project_service.active_project.touch()
    svc.analyze()
    assert svc.computes == 2


# ── Descartes ─────────────────────────────────────────────────────────────


def test_beta_m2fix10_descartar_saca_el_aviso_y_no_toca_el_canon():
    svc = _servicio()
    proj = svc.project_service.active_project
    antes_entidades = [e.id for e in proj.entities]
    aviso = next(i for i in svc.analyze().value if i.code == "T10_BILOCATION")
    huella = svc.fingerprint(aviso)

    assert isinstance(svc.dismiss(huella), Ok)

    codigos = [i.code for i in svc.analyze().value]
    assert "T10_BILOCATION" not in codigos
    assert svc.count() == len(codigos) == 3
    # El descarte es una DECISIÓN, no canon: ni candidatos ni elementos nuevos.
    assert proj.candidates == []
    assert [e.id for e in proj.entities] == antes_entidades
    assert len(proj.causal_milestones) == 5
    # Y vive en el elemento afectado, append-safe (patrón `_struct_dismissed`).
    hito = next(h for h in proj.causal_milestones if h.id == aviso.subject_id)
    assert hito.metadata[DISMISS_KEY] == [huella]
    assert svc.dismissed_count() == 1


def test_beta_m2fix10_descartar_es_idempotente_y_persiste_en_metadata():
    svc = _servicio()
    aviso = next(i for i in svc.analyze().value if i.code == "T12_KNOWS_AND_IGNORES")
    huella = svc.fingerprint(aviso)
    svc.dismiss(huella)
    svc.dismiss(huella)
    relacion = next(
        r for r in svc.project_service.active_project.relations if r.id == aviso.subject_id
    )
    assert relacion.custom_metadata[DISMISS_KEY] == [huella]
    assert svc.count() == 3


def test_beta_m2fix10_el_descarte_sobrevive_a_guardar_y_reabrir(tmp_path):
    """Criterio 10: sin forma nueva en disco. El marcador viaja en el
    ``metadata`` que ya se serializa, así que no hay migración vN+1."""
    from packages.application.project_service import ProjectService
    from packages.persistence.store import ProjectStore

    ps = ProjectService(ProjectStore())
    ps.active_project = _orbita_muerta()
    svc = ContinuityService(ps)
    aviso = next(i for i in svc.analyze().value if i.code == "T10_BILOCATION")
    svc.dismiss(svc.fingerprint(aviso))
    destino = tmp_path / "orbita.json"
    assert isinstance(ps.save(destino), Ok)

    otro = ProjectService(ProjectStore())
    assert isinstance(otro.open(destino), Ok)
    codigos = sorted(i.code for i in ContinuityService(otro).analyze().value)
    assert codigos == [
        "T07_MILESTONE_BEFORE_PARENT",
        "T11_PARTICIPANT_OUTSIDE_LIFE",
        "T12_KNOWS_AND_IGNORES",
    ]


def test_beta_m2fix10_huella_estable_entre_lecturas():
    svc = _servicio()
    primera = {svc.fingerprint(i) for i in svc.analyze().value}
    svc.project_service.active_project.touch()
    assert {svc.fingerprint(i) for i in svc.analyze().value} == primera


def test_beta_m2fix10_descartar_una_huella_desconocida_no_revienta():
    svc = _servicio()
    assert isinstance(svc.dismiss("cont:entity:no-existe:T01_END_BEFORE_START:"), Error)
    assert isinstance(svc.dismiss("basura"), Error)


# ── «Plantado sin recoger» (consume FIX-09) ───────────────────────────────


def test_beta_m2fix10_hilos_sueltos_son_los_hitos_que_nadie_recoge():
    svc = _servicio()
    titulos = [h.title for h in svc.loose_threads().value]
    # 1x03 lo recogen el payoff y el 2x08; los demás son puntas sueltas.
    assert "1x03 — Caja negra" not in titulos
    assert "2x08 — Habitable" in titulos
