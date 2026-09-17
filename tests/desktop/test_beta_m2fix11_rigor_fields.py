"""BETA2-FIX-11 (fase B): el aparato de rigor tiene formulario.

`certainty_level` tenía CERO apariciones en `hosts/`, `precision` solo aparecía
como texto de lectura en la revisión de semillas, y el campo «Fecha / posición»
del hito guardaba una cadena libre en `metadata["chronology_key"]` sin tocar
`temporality`. Es decir: «h. 1334» era indistinguible de un 1334 documentado
(HIS-04) y no había forma de decir «esto lo dice López de Ayala y esto me lo
inventé yo» (HIS-05).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.causal_milestone import CausalMilestone  # noqa: E402
from packages.domain.entity import CertaintyLevel, NarrativeEntity  # noqa: E402
from packages.domain.relation import NarrativeRelation, RelationType  # noqa: E402
from packages.domain.temporal_models import TemporalPrecision  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ctx(project_service, advanced=False):
    return SimpleNamespace(
        advanced_mode=advanced,
        log=lambda *a, **k: None,
        notify=lambda *a, **k: None,
        animation_duration=lambda default=220: 0,
        request_save_silent=lambda: None,
        selected_entity_id=None,
        selected_relation_id=None,
        drawer=None,
        project_controller=SimpleNamespace(ps=project_service),
    )


def _setup():
    ps = ProjectService()
    ps.create("Castilla s. XIV")
    return ps


# ── B1/B2 · Ficha de entidad ────────────────────────────────────────────


def _node_panel(ps, ctx, entity_id):
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

    return NodeDetailPanel(ctx, EntityController(ps), entity_id)


def test_beta_m2fix11_ficha_manda_certeza_y_datacion_rica(qapp):
    ps = _setup()
    entidad = NarrativeEntity(name="María de Padilla", birth_year=1334)
    ps.active_project.entities.append(entidad)
    ctx = _ctx(ps)
    panel = _node_panel(ps, ctx, entidad.id)

    panel.rigor.set_expanded(True)
    panel.rigor._set_combo(panel.rigor.certeza_combo, CertaintyLevel.PROBABLE.value)
    panel.rigor._set_combo(panel.rigor.precision_combo, TemporalPrecision.APPROXIMATE.value)
    panel.rigor.world_date_edit.setText("h. 1334")
    panel.rigor.notes_edit.setText("Fecha discutida: Ayala no la data.")
    panel.rigor.period_edit.setText("reinado de Alfonso XI")
    panel.rigor.sources_edit.setText("Crónica de Ayala; Zúñiga")
    panel.save()

    guardada = ps.active_project.entity_by_id(entidad.id)
    assert guardada.certainty_level == CertaintyLevel.PROBABLE
    span = guardada.life_span
    assert span.start.precision == TemporalPrecision.APPROXIMATE
    assert span.start.world_date == "h. 1334"
    assert span.start.period == "reinado de Alfonso XI"
    assert span.start.notes.startswith("Fecha discutida")
    assert span.start.contradictory_sources == ["Crónica de Ayala", "Zúñiga"]
    # El año entero sigue mandando: la cronología no se mueve de sitio.
    assert guardada.birth_year == 1334
    assert span.start.year == 1334


def test_beta_m2fix11_ficha_lee_lo_guardado(qapp):
    ps = _setup()
    entidad = NarrativeEntity(name="Pedro I", birth_year=1334)
    ps.active_project.entities.append(entidad)
    ctx = _ctx(ps)
    panel = _node_panel(ps, ctx, entidad.id)
    panel.rigor.world_date_edit.setText("h. 1334")
    panel.rigor._set_combo(panel.rigor.precision_combo, TemporalPrecision.APPROXIMATE.value)
    panel.save()

    # Un panel nuevo sobre la misma entidad tiene que PINTAR lo guardado.
    otro = _node_panel(ps, ctx, entidad.id)
    assert otro.rigor.world_date_edit.text() == "h. 1334"
    assert otro.rigor.precision() == TemporalPrecision.APPROXIMATE.value


def test_beta_m2fix11_rigor_plegado_para_el_perfil_no_tecnico(qapp):
    ps = _setup()
    entidad = NarrativeEntity(name="Carmen")
    ps.active_project.entities.append(entidad)
    panel = _node_panel(ps, _ctx(ps, advanced=False), entidad.id)
    assert not panel.rigor.is_expanded()  # la Ficha no crece cinco campos
    assert panel.rigor.body.isHidden()

    avanzado = _node_panel(ps, _ctx(ps, advanced=True), entidad.id)
    assert avanzado.rigor.is_expanded()


def test_beta_m2fix11_etiquetas_en_espanol_llano(qapp):
    ps = _setup()
    entidad = NarrativeEntity(name="Carmen")
    ps.active_project.entities.append(entidad)
    panel = _node_panel(ps, _ctx(ps), entidad.id)
    combo = panel.rigor.certeza_combo
    textos = [combo.itemText(i) for i in range(combo.count())]
    assert "Confirmada (documentada)" in textos
    assert not any("certainty" in t.lower() for t in textos)
    assert "certainty" not in panel.rigor.toggle.text().lower()


# ── B3 · fuentes en la Ficha ────────────────────────────────────────────


def test_beta_m2fix11_ficha_crea_y_enlaza_fuente(qapp):
    ps = _setup()
    entidad = NarrativeEntity(name="Pedro I")
    ps.active_project.entities.append(entidad)
    panel = _node_panel(ps, _ctx(ps), entidad.id)

    assert panel.sources_label.text() == "Sin fuentes enlazadas"
    assert panel.add_source(
        "López de Ayala — Crónica del rey don Pedro",
        "BNE MSS/1234, f. 12r",
        "«E el rey don Pedro…»",
    )
    # Se ve en la ficha...
    assert "López de Ayala" in panel.sources_label.text()
    assert "BNE MSS/1234" in panel.sources_label.text()
    # ...y el enlace está en la FUENTE (no hay entity.source_ids).
    fuente = ps.active_project.sources[0]
    assert fuente.derived_entity_ids == [entidad.id]
    assert fuente.fragment.startswith("«E el rey")


def test_beta_m2fix11_ficha_pinta_las_fuentes_ya_enlazadas(qapp):
    ps = _setup()
    entidad = NarrativeEntity(name="Pedro I")
    ps.active_project.entities.append(entidad)
    primero = _node_panel(ps, _ctx(ps), entidad.id)
    primero.add_source("Zúñiga", "Anales")

    otro = _node_panel(ps, _ctx(ps), entidad.id)
    assert "Zúñiga" in otro.sources_label.text()


def test_beta_m2fix11_fuente_sin_nombre_no_se_crea(qapp):
    ps = _setup()
    entidad = NarrativeEntity(name="Pedro I")
    ps.active_project.entities.append(entidad)
    panel = _node_panel(ps, _ctx(ps), entidad.id)
    assert not panel.add_source("   ")
    assert ps.active_project.sources == []


# ── B1 · panel de relación ──────────────────────────────────────────────


def test_beta_m2fix11_panel_de_relacion_guarda_certeza(qapp):
    ps = _setup()
    a = NarrativeEntity(name="Pedro I")
    b = NarrativeEntity(name="María de Padilla")
    ps.active_project.entities.extend([a, b])
    rel = NarrativeRelation(
        source_id=a.id, target_id=b.id, relation_type=RelationType.ESTA_RELACIONADO_CON
    )
    ps.active_project.relations.append(rel)

    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
    from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel

    ctx = _ctx(ps)
    panel = RelationDetailPanel(ctx, RelationController(ps), rel.id)
    panel.rigor._set_combo(panel.rigor.certeza_combo, CertaintyLevel.DUDOSO.value)
    panel.save()

    guardada = ps.active_project.relation_by_id(rel.id)
    assert guardada.certainty_level == CertaintyLevel.DUDOSO


# ── B2 · panel de hito ──────────────────────────────────────────────────


def test_beta_m2fix11_hito_escribe_temporality_no_chronology_key(qapp):
    ps = _setup()
    hito = CausalMilestone(title="Matrimonio con Juana de Castro", year=1354)
    ps.active_project.causal_milestones.append(hito)

    from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
        CausalMilestoneController,
    )
    from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel

    ctx = _ctx(ps)
    panel = MilestoneDetailPanel(ctx, CausalMilestoneController(ps), hito.id)
    panel.rigor.set_expanded(True)
    panel.rigor._set_combo(panel.rigor.precision_combo, TemporalPrecision.APPROXIMATE.value)
    panel.rigor.world_date_edit.setText("h. 1354")
    panel.rigor.notes_edit.setText("Ayala lo data un año después.")
    panel._do_save(reload_after=False)

    guardado = next(h for h in ps.active_project.causal_milestones if h.id == hito.id)
    assert guardado.temporality.precision == TemporalPrecision.APPROXIMATE
    assert guardado.temporality.world_date == "h. 1354"
    assert guardado.temporality.notes.startswith("Ayala lo data")
    assert guardado.year == 1354  # el año entero se conserva
    assert guardado.temporality.year == 1354


def test_beta_m2fix11_hito_hereda_la_clave_improvisada_sin_perderla(qapp):
    """No se pierde lo que los usuarios ya escribieron en `chronology_key`."""
    ps = _setup()
    hito = CausalMilestone(title="La tala", year=1300)
    hito.metadata["chronology_key"] = "Era del Cuervo, tercer invierno"
    ps.active_project.causal_milestones.append(hito)

    from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
        CausalMilestoneController,
    )
    from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel

    panel = MilestoneDetailPanel(ctx := _ctx(ps), CausalMilestoneController(ps), hito.id)
    assert ctx is not None
    assert panel.rigor.world_date_edit.text() == "Era del Cuervo, tercer invierno"
    panel._do_save(reload_after=False)

    guardado = next(h for h in ps.active_project.causal_milestones if h.id == hito.id)
    # Ahora vive en el modelo de verdad, y la clave vieja sigue donde estaba.
    assert guardado.temporality.world_date == "Era del Cuervo, tercer invierno"
    assert guardado.metadata.get("chronology_key") == "Era del Cuervo, tercer invierno"
