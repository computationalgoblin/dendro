"""BETA2-FIX-12 (G2-16 / G2-29) — lo que el usuario VE y TOCA.

Tres pantallas, tres ausencias que expulsaban perfiles enteros:

1. la caja de tipo de relación ofrecía 17 valores y ninguno era «madre»;
2. la ficha de entidad no tenía dónde escribir un año (el único editor de fecha
   era un arrastre sobre una ventana de 0 a 10 años), y el mundo entregado en el
   beta llegó con sus nueve fichas sin datar;
3. el editor de calendario definía las eras por duración encadenada desde el año
   0: no había forma de decir «empieza en 1900».
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402
from packages.domain.relation import (  # noqa: E402
    KINSHIP_RELATION_TYPES,
    NarrativeRelation,
    RelationType,
)
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
    ps.create("La casa de Santa María")
    return ps


def _node_panel(ps, ctx, entity_id, variant="normal"):
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

    return NodeDetailPanel(ctx, EntityController(ps), entity_id, variant=variant)


# ── 1 · la caja OFRECE el parentesco ────────────────────────────────────────


def test_beta_m2fix12_el_combo_de_relacion_ofrece_parentesco(qapp):
    """No basta con el enum: la caja se puebla con `OFFERED_RELATION_TYPES`."""
    ps = _setup()
    a = NarrativeEntity(name="Remedios")
    b = NarrativeEntity(name="Manuel")
    ps.active_project.entities.extend([a, b])
    rel = NarrativeRelation(
        source_id=a.id, target_id=b.id, relation_type=RelationType.ESTA_RELACIONADO_CON
    )
    ps.active_project.relations.append(rel)

    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
    from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel

    panel = RelationDetailPanel(_ctx(ps), RelationController(ps), rel.id)
    combo = panel.type_combo
    textos = [combo.itemText(i) for i in range(combo.count())]
    datos = [combo.itemData(i) for i in range(combo.count())]

    # Por TEXTO VISIBLE (lo que el usuario lee al desplegar).
    assert any("madre" in t.lower() for t in textos), textos
    assert any("hijo" in t.lower() for t in textos), textos
    assert any("casado" in t.lower() for t in textos), textos
    assert any("hermano" in t.lower() for t in textos), textos
    # Y la familia entera está ofrecida.
    faltan = {t.value for t in KINSHIP_RELATION_TYPES} - set(datos)
    assert not faltan, f"parentescos que la caja no ofrece: {sorted(faltan)}"


def test_beta_m2fix12_elegir_madre_guarda_madre(qapp):
    ps = _setup()
    a = NarrativeEntity(name="Remedios")
    b = NarrativeEntity(name="Manuel")
    ps.active_project.entities.extend([a, b])
    rel = NarrativeRelation(
        source_id=a.id, target_id=b.id, relation_type=RelationType.ESTA_RELACIONADO_CON
    )
    ps.active_project.relations.append(rel)

    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
    from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel

    panel = RelationDetailPanel(_ctx(ps), RelationController(ps), rel.id)
    idx = panel.type_combo.findData(RelationType.ES_MADRE_DE.value)
    assert idx >= 0
    panel.type_combo.setCurrentIndex(idx)
    panel.save()

    guardada = ps.active_project.relation_by_id(rel.id)
    assert guardada.relation_type is RelationType.ES_MADRE_DE
    # …y la lista del Foco lo dice con palabras, no con «Está relacionado con».
    from hosts.DesktopHostPySide.widgets.foco.relations_panel import relation_entries_for

    entradas = relation_entries_for(ps.active_project, b.id)
    assert entradas and "madre" in entradas[0][1].lower()
    assert "relacionado" not in entradas[0][1].lower()


def test_beta_m2fix12_la_etiqueta_libre_viaja_al_foco(qapp):
    """Pregunta abierta nº4: la escotilla de texto libre deja de ser un callejón.

    `custom_metadata["custom_relation_label"]` tenía cinco apariciones en el repo
    y las cinco en el panel que la escribía: aunque el autor escribiera «Madre» a
    mano, la lista del Foco seguía diciendo «Está relacionado con».
    """
    from hosts.DesktopHostPySide.widgets.foco.relations_panel import relation_entries_for

    ps = _setup()
    a = NarrativeEntity(name="Remedios")
    b = NarrativeEntity(name="Manuel")
    ps.active_project.entities.extend([a, b])
    rel = NarrativeRelation(
        source_id=a.id,
        target_id=b.id,
        relation_type=RelationType.ESTA_RELACIONADO_CON,
        custom_metadata={"custom_relation_label": "Comadre de crianza"},
    )
    ps.active_project.relations.append(rel)

    entradas = relation_entries_for(ps.active_project, b.id)
    assert entradas and "Comadre de crianza" in entradas[0][1]
    assert "Está relacionado con" not in entradas[0][1]


# ── 2 · «Nació» y «Murió» en la ficha ───────────────────────────────────────


@pytest.mark.parametrize("variant", ["normal", "foco"])
def test_beta_m2fix12_la_ficha_tiene_nacio_y_murio(qapp, variant):
    ps = _setup()
    entidad = NarrativeEntity(name="Remedios")
    ps.active_project.entities.append(entidad)
    panel = _node_panel(ps, _ctx(ps), entidad.id, variant=variant)
    assert panel.birth_year_label.text() == "Nació"
    assert panel.death_year_label.text() == "Murió"
    assert panel.birth_year_edit.isEnabled()
    assert panel.death_year_edit.isEnabled()


def test_beta_m2fix12_teclear_1901_llega_al_controller_no_a_persistencia(qapp):
    """La UI nunca escribe persistencia: pasa por `EntityController.update`."""
    ps = _setup()
    entidad = NarrativeEntity(name="Remedios")
    ps.active_project.entities.append(entidad)

    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

    controller = EntityController(ps)
    visto: list[dict] = []
    original = controller.update

    def _espia(entity_id, payload):
        visto.append(dict(payload))
        return original(entity_id, payload)

    controller.update = _espia
    panel = NodeDetailPanel(_ctx(ps), controller, entidad.id)
    panel.birth_year_edit.setText("1901")
    panel.death_year_edit.setText("1985")
    panel.save()

    assert visto, "el panel no llamó al controller"
    assert visto[-1]["birth_year"] == 1901
    assert visto[-1]["death_year"] == 1985
    guardada = ps.active_project.entity_by_id(entidad.id)
    assert guardada.birth_year == 1901
    assert guardada.death_year == 1985


def test_beta_m2fix12_los_anos_sobreviven_a_reabrir_la_ficha(qapp):
    ps = _setup()
    entidad = NarrativeEntity(name="Remedios")
    ps.active_project.entities.append(entidad)
    panel = _node_panel(ps, _ctx(ps), entidad.id)
    panel.birth_year_edit.setText("1901")
    panel.death_year_edit.setText("1985")
    panel.save()

    otro = _node_panel(ps, _ctx(ps), entidad.id)
    assert otro.birth_year_edit.text() == "1901"
    assert otro.death_year_edit.text() == "1985"

    # Vaciar la casilla vuelve a dejarla sin datar (no se inventa un año).
    otro.birth_year_edit.setText("")
    otro.save()
    assert ps.active_project.entity_by_id(entidad.id).birth_year is None


def test_beta_m2fix12_un_ano_ilegible_no_borra_el_ano_guardado(qapp):
    """Borrar un año es una decisión (casilla vacía), no un descuido de teclado."""
    ps = _setup()
    entidad = NarrativeEntity(name="Remedios", birth_year=1901)
    ps.active_project.entities.append(entidad)
    panel = _node_panel(ps, _ctx(ps), entidad.id)
    # El validador impide teclearlo; se fuerza para probar el cinturón.
    panel.birth_year_edit.setValidator(None)
    panel.birth_year_edit.setText("mil novecientos uno")
    panel.save()
    assert ps.active_project.entity_by_id(entidad.id).birth_year == 1901


def test_beta_m2fix12_editar_el_ano_no_borra_la_datacion_rica(qapp):
    """Contrato BETA2-SHIP-07: solo se mueve el EJE ENTERO."""
    ps = _setup()
    entidad = NarrativeEntity(name="María de Padilla", birth_year=1334)
    ps.active_project.entities.append(entidad)
    panel = _node_panel(ps, _ctx(ps), entidad.id)
    panel.rigor.set_expanded(True)
    panel.rigor._set_combo(panel.rigor.precision_combo, TemporalPrecision.APPROXIMATE.value)
    panel.rigor.world_date_edit.setText("h. 1334")
    panel.rigor.notes_edit.setText("Fecha discutida: Ayala no la data.")
    panel.rigor.period_edit.setText("reinado de Alfonso XI")
    panel.save()

    otro = _node_panel(ps, _ctx(ps), entidad.id)
    otro.birth_year_edit.setText("1335")
    otro.save()

    guardada = ps.active_project.entity_by_id(entidad.id)
    assert guardada.birth_year == 1335
    span = guardada.life_span
    assert span.start.year == 1335
    assert span.start.precision == TemporalPrecision.APPROXIMATE  # NO se degrada a exacta
    assert span.start.world_date == "h. 1334"
    assert span.start.period == "reinado de Alfonso XI"
    assert span.start.notes.startswith("Fecha discutida")


def test_beta_m2fix12_datar_retira_la_marca_de_pendiente(qapp):
    """Las nueve fichas del beta traían `notes = 'sin datar (pendiente)'`."""
    from packages.application.temporal_dating import PENDING_NOTE, normalize_entity_dating

    ps = _setup()
    entidad = NarrativeEntity(name="Remedios")
    normalize_entity_dating(entidad)
    ps.active_project.entities.append(entidad)
    assert entidad.life_span.start.notes == PENDING_NOTE

    panel = _node_panel(ps, _ctx(ps), entidad.id)
    panel.birth_year_edit.setText("1901")
    panel.save()

    guardada = ps.active_project.entity_by_id(entidad.id)
    assert guardada.birth_year == 1901
    assert PENDING_NOTE not in (guardada.life_span.start.notes or "")
    assert guardada.life_span.start.precision == TemporalPrecision.EXACT


# ── 3 · el ancla en el editor de calendario ─────────────────────────────────


def test_beta_m2fix12_el_editor_expone_el_ano_de_inicio(qapp):
    from hosts.DesktopHostPySide.widgets.calendar_editor import CalendarEditor

    editor = CalendarEditor()
    assert editor.value()["start_year"] == 0  # por defecto, como siempre

    editor.start_year_spin.setValue(1900)
    valor = editor.value()
    assert valor["start_year"] == 1900
    assert editor.start_year() == 1900


def test_beta_m2fix12_el_editor_reabre_con_el_ancla_guardada(qapp):
    from hosts.DesktopHostPySide.widgets.calendar_editor import CalendarEditor

    editor = CalendarEditor()
    editor.set_value({
        "start_year": 1900,
        "eras": [{"name": "Siglo XX", "duration": 100}],
        "present": {"era_index": 0, "year_within": 86},
    })
    assert editor.start_year_spin.value() == 1900
    assert editor.value()["start_year"] == 1900
    assert editor.value()["eras"][0]["duration"] == 100


def test_beta_m2fix12_el_payload_del_editor_ancla_las_eras_de_verdad(qapp):
    """De punta a punta: editor → `CalendarService.configure` → eras canónicas."""
    from hosts.DesktopHostPySide.widgets.calendar_editor import CalendarEditor
    from packages.application.calendar_service import CalendarService

    ps = _setup()
    editor = CalendarEditor()
    editor.set_value({
        "start_year": 1900,
        "eras": [{"name": "Siglo XX", "duration": 100}],
        "present": {"era_index": 0, "year_within": 86},
    })
    result = CalendarService(ps).configure(editor.value())
    assert not hasattr(result, "error") or result.value is not None
    eras = ps.active_project.project_chronology.sorted_eras()
    assert eras[0].start_year == 1900
    assert eras[-1].end_year is None
    assert ps.active_project.project_chronology.present_year == 1985
