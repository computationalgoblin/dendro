"""BETA-AUDIT-04: exportar el mundo a una carpeta de Markdown.

`ExportService` existía, estaba testado y NINGÚN fichero de `hosts/` lo importaba: la
única forma de sacar un proyecto de Dendro era copiar el JSON a mano. Además sus
métodos devolvían texto truncado a 120 caracteres y un CONTADOR de relaciones, así que
cablearlos tal cual no resolvía el problema real.

Estos tests fijan el formato: un fichero por entidad, front-matter con id estable,
relaciones como `[[wikilinks]]`, índice, orden estable y respeto de la privacidad.
"""

from __future__ import annotations

from packages.application.export_service import ExportService
from packages.application.project_service import ProjectService
from packages.domain.entity import NarrativeEntity
from packages.domain.relation import NarrativeRelation
from packages.domain.result import Error, Ok


def _proyecto():
    svc = ProjectService()
    assert isinstance(svc.create(name="Mundo exportable"), Ok)
    proj = svc.active_project
    nasr = NarrativeEntity(name="Nasr", brief_description="Noble militar nazarí")
    granada = NarrativeEntity(name="Granada", brief_description="La ciudad condenada")
    proj.entities.extend([nasr, granada])
    proj.relations.append(
        NarrativeRelation(
            source_id=nasr.id, target_id=granada.id, description="La quiere purificar"
        )
    )
    return svc, nasr, granada


def test_escribe_un_fichero_por_entidad_y_un_indice(tmp_path):
    svc, _, _ = _proyecto()
    resultado = ExportService(project_service=svc).export_markdown_bundle(tmp_path)
    assert isinstance(resultado, Ok), resultado
    assert resultado.value["entidades"] == 2
    assert (tmp_path / "index.md").exists()
    assert (tmp_path / "Nasr.md").exists()
    assert (tmp_path / "Granada.md").exists()


def test_el_fichero_lleva_front_matter_con_id_estable(tmp_path):
    svc, nasr, _ = _proyecto()
    assert isinstance(ExportService(project_service=svc).export_markdown_bundle(tmp_path), Ok)
    texto = (tmp_path / "Nasr.md").read_text(encoding="utf-8")
    assert texto.startswith("---\n")
    assert f"id: {nasr.id}" in texto, "sin id estable no se puede reimportar ni cruzar"
    assert "tipo:" in texto and "visibilidad:" in texto
    assert "# Nasr" in texto
    assert "Noble militar nazarí" in texto


def test_las_relaciones_viajan_como_wikilinks(tmp_path):
    svc, _, _ = _proyecto()
    assert isinstance(ExportService(project_service=svc).export_markdown_bundle(tmp_path), Ok)
    nasr = (tmp_path / "Nasr.md").read_text(encoding="utf-8")
    granada = (tmp_path / "Granada.md").read_text(encoding="utf-8")
    assert "[[Granada]]" in nasr, "la relación saliente no aparece en el origen"
    assert "[[Nasr]]" in granada, "la relación entrante no aparece en el destino"
    assert "La quiere purificar" in nasr


def test_la_exportacion_es_estable_entre_ejecuciones(tmp_path):
    """Dos exportaciones del mismo estado deben dar el mismo diff (versionable)."""
    svc, _, _ = _proyecto()
    servicio = ExportService(project_service=svc)
    a = tmp_path / "a"
    b = tmp_path / "b"
    assert isinstance(servicio.export_markdown_bundle(a), Ok)
    assert isinstance(servicio.export_markdown_bundle(b), Ok)
    for fichero in sorted(p.name for p in a.glob("*.md")):
        assert (a / fichero).read_text(encoding="utf-8") == (
            b / fichero
        ).read_text(encoding="utf-8")


def test_no_exporta_fantasmas_ni_secretos_al_publico(tmp_path):
    svc, _, _ = _proyecto()
    proj = svc.active_project
    fantasma = NarrativeEntity(name="Traidor por decidir")
    fantasma.canon_state = type(fantasma.canon_state)("fantasma")
    proj.entities.append(fantasma)

    resultado = ExportService(project_service=svc).export_markdown_bundle(
        tmp_path, audience="public"
    )
    assert isinstance(resultado, Ok)
    assert not (tmp_path / "Traidor por decidir.md").exists(), (
        "un fantasma es borrador interno: exportar es compartir"
    )


def test_sin_proyecto_activo_da_error_claro(tmp_path):
    servicio = ExportService(project_service=ProjectService())
    resultado = servicio.export_markdown_bundle(tmp_path)
    assert isinstance(resultado, Error)
    assert "proyecto" in resultado.error.lower()


def test_dos_entidades_con_el_mismo_nombre_no_se_pisan(tmp_path):
    svc, _, _ = _proyecto()
    svc.active_project.entities.append(NarrativeEntity(name="Nasr"))
    resultado = ExportService(project_service=svc).export_markdown_bundle(tmp_path)
    assert isinstance(resultado, Ok)
    assert resultado.value["entidades"] == 3
    assert len(list(tmp_path.glob("*.md"))) == 4, "un homónimo sobrescribió a otro"
