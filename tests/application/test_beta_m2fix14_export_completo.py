"""BETA2-FIX-14 (G2-24): el exportador se llevaba el reparto, no la obra.

Un showrunner exportó su biblia de dos temporadas y le salieron 19 fichas de personaje
y utilería: fuera los 18 episodios, las dos temporadas, la cronología, la cadena causal
y las páginas de wiki que acababa de pagar. Las cadenas `causal_milestones`, `eras`,
`project_chronology` y `narrative_memories` no aparecían ni una vez en el fichero.

Estos tests fijan el contenido nuevo del bundle y, sobre todo, sus INVARIANTES:
audiencia/visibilidad/secretos y orden estable entre ejecuciones.
"""

from __future__ import annotations

from packages.application.export_service import ExportService
from packages.application.project_service import ProjectService
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneType
from packages.domain.entity import NarrativeEntity, VisibilityState
from packages.domain.era import Era
from packages.domain.narrative_memory import (
    MemoryCitation,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.result import Ok


def _mundo():
    """Mundo de prueba: 3 entidades, 2 hitos encadenados, 2 eras y 2 páginas de wiki."""
    svc = ProjectService()
    assert isinstance(svc.create(name="Los Pigmentos"), Ok)
    proj = svc.active_project

    rosa = NarrativeEntity(name="Rosa Bermejo", brief_description="La pigmentera")
    rosa.visibility_state = VisibilityState.PUBLICO_MUNDO
    nasr = NarrativeEntity(name="Nasr", brief_description="El noble")
    nasr.visibility_state = VisibilityState.PUBLICO_MUNDO
    oculto = NarrativeEntity(name="El Delator", brief_description="Nadie lo sabe")
    oculto.visibility_state = VisibilityState.PRIVADO_AUTOR
    proj.entities.extend([rosa, nasr, oculto])

    guerra = CausalMilestone(
        title="La Guerra de los Tintes",
        description="Ardieron los talleres.",
        milestone_type=CausalMilestoneType.GUERRA,
        year=1492,
        affected_entity_ids=[rosa.id, oculto.id],
    )
    pacto = CausalMilestone(
        title="El Pacto de los Gremios",
        description="Se repartieron el añil.",
        milestone_type=CausalMilestoneType.PACTO,
        year=1501,
        affected_entity_ids=[nasr.id],
        causal_parent_hito_ids=[guerra.id],
    )
    guerra.causal_child_hito_ids = [pacto.id]
    secreto = CausalMilestone(
        title="La Traición sin contar",
        milestone_type=CausalMilestoneType.TRAICION,
        year=1499,
        visibility_state="privado_autor",
    )
    proj.causal_milestones.extend([guerra, pacto, secreto])

    crono = proj.project_chronology
    crono.calendar_name = "Calendario de los Gremios"
    crono.present_year = 1520
    crono.eras.extend(
        [
            Era(name="Era de los Pigmentos", start_year=1400, end_year=1500, order=0),
            Era(name="Era de la Ceniza", start_year=1501, end_year=None, order=1),
        ]
    )

    pagina_rosa = NarrativeMemory(
        target_kind=MemoryTargetKind.ENTITY,
        target_id=rosa.id,
        resumen_editorial="La pigmentera que sobrevivió al incendio.",
        cuerpo="Rosa aprendió el oficio de su madre y lo perdió en la guerra.",
        wikilinks=[MemoryCitation(ref_kind=MemoryTargetKind.ENTITY, ref_id=nasr.id)],
        tags=["oficio"],
    )
    pagina_oculta = NarrativeMemory(
        target_kind=MemoryTargetKind.ENTITY,
        target_id=oculto.id,
        resumen_editorial="Quien vendió el taller.",
        cuerpo="El Delator cobró en añil.",
    )
    proj.narrative_memories.extend([pagina_rosa, pagina_oculta])
    return svc, {"rosa": rosa, "nasr": nasr, "oculto": oculto, "guerra": guerra}


def test_beta_m2fix14_exporta_los_hitos_con_ano_tipo_y_participantes(tmp_path):
    svc, refs = _mundo()
    resultado = ExportService(project_service=svc).export_markdown_bundle(tmp_path)
    assert isinstance(resultado, Ok), resultado

    hitos = tmp_path / "hitos.md"
    assert hitos.exists(), "el exportador seguía sin escribir un solo hito"
    texto = hitos.read_text(encoding="utf-8")
    assert "La Guerra de los Tintes" in texto
    assert "El Pacto de los Gremios" in texto
    assert "1492" in texto, "sin año un hito no ubica nada"
    assert "Tipo: guerra" in texto
    assert "[[Rosa Bermejo]]" in texto, "los participantes deben viajar como wikilinks"
    # Cadena causal en los dos sentidos.
    assert "Causado por: La Guerra de los Tintes" in texto
    assert "Provoca: El Pacto de los Gremios" in texto
    # La ficha de la entidad enlaza los hitos en los que participa.
    ficha = (tmp_path / "Rosa Bermejo.md").read_text(encoding="utf-8")
    assert "## Hitos" in ficha and "La Guerra de los Tintes" in ficha
    assert resultado.value["hitos"] == 3


def test_beta_m2fix14_exporta_eras_calendario_y_presente(tmp_path):
    svc, _ = _mundo()
    resultado = ExportService(project_service=svc).export_markdown_bundle(tmp_path)
    assert isinstance(resultado, Ok), resultado

    crono = tmp_path / "cronologia.md"
    assert crono.exists(), "sin cronología la obra no es una serie, es un diccionario"
    texto = crono.read_text(encoding="utf-8")
    assert "Era de los Pigmentos" in texto and "Era de la Ceniza" in texto
    assert "Calendario de los Gremios" in texto
    assert "1520" in texto, "el presente del mundo no viajó"
    assert "en curso" in texto, "una era abierta debe decir que sigue abierta"
    assert resultado.value["eras"] == 2
    # El índice hace navegable lo nuevo.
    indice = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert "[[cronologia]]" in indice and "[[hitos]]" in indice


def test_beta_m2fix14_exporta_las_paginas_de_wiki_del_proyecto(tmp_path):
    svc, _ = _mundo()
    resultado = ExportService(project_service=svc).export_markdown_bundle(tmp_path)
    assert isinstance(resultado, Ok), resultado

    wiki = tmp_path / "wiki"
    assert wiki.is_dir(), "las páginas de wiki pagadas a la IA no salían del programa"
    paginas = sorted(p.name for p in wiki.glob("*.md"))
    assert "Rosa Bermejo.md" in paginas
    texto = (wiki / "Rosa Bermejo.md").read_text(encoding="utf-8")
    assert "canon: false" in texto, "una página derivada no puede confundirse con canon"
    assert "derivada: true" in texto
    assert "sobrevivió al incendio" in texto
    assert "[[Nasr]]" in texto, "los wikilinks resolubles deben viajar"
    assert resultado.value["paginas_wiki"] == 2


def test_beta_m2fix14_publico_no_ve_hitos_ni_paginas_no_visibles(tmp_path):
    svc, _ = _mundo()
    resultado = ExportService(project_service=svc).export_markdown_bundle(
        tmp_path, audience="public"
    )
    assert isinstance(resultado, Ok), resultado

    hitos = (tmp_path / "hitos.md").read_text(encoding="utf-8")
    assert "La Guerra de los Tintes" in hitos
    assert "La Traición sin contar" not in hitos, "un hito reservado no se comparte"
    # Un participante NO exportado no puede filtrarse por la puerta de atrás del hito.
    assert "El Delator" not in hitos
    assert not (tmp_path / "El Delator.md").exists()

    paginas = sorted(p.name for p in (tmp_path / "wiki").glob("*.md"))
    assert paginas == ["Rosa Bermejo.md"], (
        "la página hereda la visibilidad de su objetivo; la del oculto no sale"
    )
    assert resultado.value["hitos"] == 2


def test_beta_m2fix14_la_exportacion_sigue_siendo_estable_entre_ejecuciones(tmp_path):
    """Mismo estado ⇒ mismos bytes (espeja test_beta_audit_04_exportacion)."""
    svc, _ = _mundo()
    servicio = ExportService(project_service=svc)
    a, b = tmp_path / "a", tmp_path / "b"
    assert isinstance(servicio.export_markdown_bundle(a), Ok)
    assert isinstance(servicio.export_markdown_bundle(b), Ok)

    ficheros_a = sorted(str(p.relative_to(a)) for p in a.rglob("*.md"))
    ficheros_b = sorted(str(p.relative_to(b)) for p in b.rglob("*.md"))
    assert ficheros_a == ficheros_b
    assert "hitos.md" in ficheros_a and "cronologia.md" in ficheros_a
    for relativo in ficheros_a:
        assert (a / relativo).read_text(encoding="utf-8") == (
            b / relativo
        ).read_text(encoding="utf-8"), f"«{relativo}» no es estable entre ejecuciones"


def test_beta_m2fix14_devuelve_result_ok_con_el_resumen_ampliado(tmp_path):
    svc, _ = _mundo()
    resultado = ExportService(project_service=svc).export_markdown_bundle(tmp_path)
    assert isinstance(resultado, Ok), resultado
    resumen = resultado.value
    # El contrato viejo se conserva palabra por palabra (hay tests y UI que lo leen).
    for clave in ("carpeta", "entidades", "omitidas", "audiencia"):
        assert clave in resumen
    for clave in ("hitos", "eras", "paginas_wiki"):
        assert clave in resumen, f"falta la clave nueva «{clave}» del resumen"
    assert resumen["entidades"] == 3 and resumen["hitos"] == 3 and resumen["eras"] == 2


def test_beta_m2fix14_un_proyecto_vacio_no_ensucia_la_carpeta(tmp_path):
    """Sin hitos, eras ni wiki el bundle es exactamente el de antes (no hay ficheros
    huecos). Es lo que mantiene verde `test_dos_entidades_con_el_mismo_nombre...`."""
    svc = ProjectService()
    assert isinstance(svc.create(name="Vacío"), Ok)
    svc.active_project.entities.append(NarrativeEntity(name="Solo"))
    assert isinstance(ExportService(project_service=svc).export_markdown_bundle(tmp_path), Ok)
    assert sorted(p.name for p in tmp_path.glob("*.md")) == ["Solo.md", "index.md"]
    assert not (tmp_path / "wiki").exists()
