"""UX5 — revisión legible de ediciones/análisis, Reparar canon y germinación.

Cubre los arreglos pedidos por el usuario:
- El candidato de EDICIÓN muestra el texto propuesto en la caja grande, editable,
  y al aceptar lo escrito se guarda en `edit_proposed_value` (lo que se aplica a canon).
- El candidato de ANÁLISIS muestra el informe completo de forma legible (solo lectura).
- «Reparar canon» delega en el host (UX8: lanza el job IA de reparación concreta).
- Las entidades en edición germinan mientras corre el job; al aceptar, florecen.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace
from packages.application.ai_jobs import AIJobType
from hosts.DesktopHostPySide.widgets.candidate_review_panel import (
    CandidateReviewPanel,
    analysis_report_text,
    candidate_body_text,
    is_analysis_candidate,
    is_edit_candidate,
)
from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView
from hosts.DesktopHostPySide.widgets.seed_audio import ZenBell
from hosts.DesktopHostPySide.widgets.seed_notifications import SeedNotificationLayer
from packages.domain.result import Ok


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class _FakeController:
    def __init__(self, entities=None):
        self.created: list[dict] = []
        self.accepted: list[str] = []
        self.rejected: list[str] = []
        self._seq = 0
        self._cands: dict[str, SimpleNamespace] = {}
        self.ps = SimpleNamespace(
            active_project=SimpleNamespace(entities=list(entities or []))
        )

    def create(self, data):
        self._seq += 1
        cid = f"new-{self._seq}"
        cand = SimpleNamespace(
            id=cid, title=data.get("title", "x"),
            state=SimpleNamespace(value="pendiente"),
        )
        self._cands[cid] = cand
        self.created.append(dict(data))
        return Ok(cand)

    def accept(self, cid):
        self.accepted.append(cid)
        cand = self._cands.get(cid)
        if cand is not None:
            cand.state = SimpleNamespace(value="aceptado")
        return Ok(SimpleNamespace(id=cid))

    def reject(self, cid):
        self.rejected.append(cid)
        return Ok(SimpleNamespace(id=cid))

    def list_all(self):
        return [c for c in self._cands.values() if c.state.value == "pendiente"]


def _entity(eid, name):
    return SimpleNamespace(id=eid, name=name)


# ── Helpers puros ─────────────────────────────────────────────────────────


def test_edit_vs_analysis_classification():
    assert is_edit_candidate({"edit_proposed_value": "x"}) is True
    assert is_edit_candidate({"report": "x"}) is False
    assert is_analysis_candidate({"report": "informe"}) is True
    assert is_analysis_candidate({"proposals": [{"title": "p"}]}) is True
    # una edición NO se clasifica como análisis aunque traiga report.
    assert is_analysis_candidate({"edit_proposed_value": "x", "report": "y"}) is False
    assert is_analysis_candidate({"name": "Hoja"}) is False


def test_candidate_body_text_prefers_edit_value():
    assert candidate_body_text({"edit_proposed_value": "nuevo"}) == "nuevo"
    assert candidate_body_text({"extended_description": "largo"}) == "largo"
    assert candidate_body_text({}) == ""


def test_analysis_report_text_composes_sections():
    text = analysis_report_text({
        "report": "Hay una contradicción central.",
        "issues": [{"title": "Choque", "description": "X vs Y", "severity": "alta"}],
        "proposals": [{"title": "Aclarar", "description": "Reescribir motivación"}],
        "open_questions": ["¿Y Z?"],
    })
    assert "contradicción central" in text
    assert "Choque" in text and "alta" in text
    assert "Aclarar" in text
    assert "¿Y Z?" in text


# ── Panel: candidato de EDICIÓN ────────────────────────────────────────────


def test_edit_candidate_shows_proposed_text_editable(qapp):
    controller = _FakeController()
    candidate = SimpleNamespace(
        id="e1", title="Editar body de Eldrin",
        candidate_type=SimpleNamespace(value="sugerencia_ia"),
        proposed_data={
            "report": "Propuesta…",
            "edit_target_name": "Eldrin",
            "edit_field": "body",
            "edit_proposed_value": "Texto propuesto original",
        },
        metadata={},
    )
    panel = CandidateReviewPanel(candidate, controller)
    assert panel._mode == "edit"
    assert panel._body_edit.toPlainText() == "Texto propuesto original"
    assert panel._body_edit.isReadOnly() is False
    assert panel._target_edit is not None
    assert panel._target_edit.text() == "Eldrin"


def test_edit_candidate_accept_writes_edited_value_to_canon_field(qapp):
    controller = _FakeController()
    candidate = SimpleNamespace(
        id="e1", title="Editar body de Eldrin",
        candidate_type=SimpleNamespace(value="sugerencia_ia"),
        proposed_data={
            "edit_target_name": "Eldrin",
            "edit_field": "body",
            "edit_proposed_value": "Texto propuesto original",
        },
        metadata={},
    )
    panel = CandidateReviewPanel(candidate, controller)
    panel._body_edit.setPlainText("Texto editado por el usuario")
    panel._target_edit.setText("Eldrin el Viejo")
    panel._accept()

    assert candidate.proposed_data["edit_proposed_value"] == "Texto editado por el usuario"
    assert candidate.proposed_data["edit_target_name"] == "Eldrin el Viejo"
    assert controller.accepted == ["e1"]


def test_relation_edit_panel_shows_type_and_content_in_one_seed(qapp):
    # UX5e: editar una relación = UNA semilla con dos campos (tipo + contenido).
    controller = _FakeController()
    candidate = SimpleNamespace(
        id="r1", title="Editar relación: A → B",
        candidate_type=SimpleNamespace(value="sugerencia_ia"),
        proposed_data={
            "edit_kind": "relation_edits",
            "edit_target_name": "A → B",
            "edit_field": "description",
            "edit_proposed_value": "Una alianza tensa.",
            "edit_relation_type": "es_aliado_de",
        },
        metadata={},
    )
    panel = CandidateReviewPanel(candidate, controller)
    assert panel._mode == "edit"
    assert panel._rel_type_edit is not None
    assert panel._rel_type_edit.text() == "es_aliado_de"
    assert panel._body_edit.toPlainText() == "Una alianza tensa."
    # El usuario ajusta ambos campos; al aceptar viajan juntos en la misma semilla.
    panel._rel_type_edit.setText("es_enemigo_de")
    panel._body_edit.setPlainText("Ahora rivalidad abierta.")
    panel._accept()
    assert candidate.proposed_data["edit_relation_type"] == "es_enemigo_de"
    assert candidate.proposed_data["edit_proposed_value"] == "Ahora rivalidad abierta."
    assert controller.accepted == ["r1"]


def test_type_only_relation_edit_is_edit_candidate(qapp):
    # Edición solo de tipo (sin contenido): sigue siendo edición y abre modo edit.
    pd = {"edit_kind": "relation_edits", "edit_relation_type": "es_enemigo_de",
          "edit_proposed_value": ""}
    assert is_edit_candidate(pd) is True
    controller = _FakeController()
    candidate = SimpleNamespace(
        id="r2", title="Editar relación: A → B",
        candidate_type=SimpleNamespace(value="sugerencia_ia"),
        proposed_data=dict(pd), metadata={},
    )
    panel = CandidateReviewPanel(candidate, controller)
    assert panel._mode == "edit"
    assert panel._rel_type_edit.text() == "es_enemigo_de"


# ── Panel: candidato de ENTIDAD (nombre + cuerpo) ──────────────────────────


def _entity_candidate():
    return SimpleNamespace(
        id="h1", title="Hoja candidata: Eldrin",
        candidate_type=SimpleNamespace(value="entidad"),
        proposed_data={
            "name": "Eldrin",
            "entity_type": "personaje",
            "brief_description": "breve",
            "extended_description": "Un mago anciano.",
        },
        metadata={},
    )


def test_entity_candidate_field_shows_clean_name_not_title(qapp):
    controller = _FakeController()
    panel = CandidateReviewPanel(_entity_candidate(), controller)
    # El campo editable muestra el NOMBRE real, no "Hoja candidata: …".
    assert panel._title_edit.text() == "Eldrin"
    assert panel._body_edit.toPlainText() == "Un mago anciano."


def test_entity_candidate_accept_writes_clean_name_and_body(qapp):
    controller = _FakeController()
    cand = _entity_candidate()
    panel = CandidateReviewPanel(cand, controller)
    panel._title_edit.setText("Eldrin el Sabio")
    panel._body_edit.setPlainText("Un mago muy anciano y sabio.")
    panel._accept()
    assert cand.proposed_data["name"] == "Eldrin el Sabio"  # sin prefijo
    assert cand.proposed_data["extended_description"] == "Un mago muy anciano y sabio."
    assert controller.accepted == ["h1"]


def test_entity_candidate_accept_unedited_keeps_clean_name(qapp):
    # Aceptar sin tocar nada NO debe canonizar "Hoja candidata: …" como nombre.
    controller = _FakeController()
    cand = _entity_candidate()
    panel = CandidateReviewPanel(cand, controller)
    panel._accept()
    assert cand.proposed_data["name"] == "Eldrin"


# ── Panel: candidato de ANÁLISIS + Reparar canon ───────────────────────────


def _analysis_candidate():
    return SimpleNamespace(
        id="a1", title="Informe de coherencia",
        candidate_type=SimpleNamespace(value="sugerencia_ia"),
        proposed_data={
            "report": "Hay una contradicción central.",
            "issues": [{"title": "Choque", "description": "X vs Y", "severity": "alta"}],
            "proposals": [
                {"title": "Aclarar motivación",
                 "description": "Reescribir la motivación de Eldrin"},
            ],
            "open_questions": ["¿Y Z?"],
        },
        metadata={"context_scope": {"selected_entity_ids": ["ent-1", "ent-2"]}},
    )


def test_analysis_candidate_renders_report_readonly(qapp):
    controller = _FakeController()
    panel = CandidateReviewPanel(_analysis_candidate(), controller)
    assert panel._mode == "analysis"
    text = panel._body_edit.toPlainText()
    assert "contradicción central" in text
    assert "Choque" in text
    assert "Aclarar motivación" in text
    assert "¿Y Z?" in text
    assert panel._body_edit.isReadOnly() is True


def test_repair_button_delegates_to_host_with_candidate_id(qapp):
    # UX8: «Reparar canon» ya no genera candidatos literales en el panel; delega en
    # el host (que lanza el job IA de reparación) pasando solo el id del informe.
    controller = _FakeController(entities=[_entity("ent-1", "Eldrin")])
    captured: list = []
    panel = CandidateReviewPanel(
        _analysis_candidate(), controller,
        on_repair=lambda cid: captured.append(cid),
    )
    panel._repair()
    assert captured == ["a1"]


# ── Vista: _repair_canon_from_analysis lanza el job IA de reparación ──────────


def test_repair_canon_from_analysis_launches_repair_job(qapp, monkeypatch):
    import hosts.DesktopHostPySide.views.workspaces as ws
    monkeypatch.setattr(ws, "pulse_feedback", lambda *a, **k: None)
    captured: dict = {}
    candidate = SimpleNamespace(
        id="a1",
        proposed_data={"report": "Informe", "proposals": [{"title": "X", "description": "Y"}]},
        metadata={"context_scope": {"selected_entity_ids": ["ent-1"]}},
    )
    job = SimpleNamespace(id="job-1")

    def fake_create_job(jt, prompt, context_scope=None, explicit=False):
        captured.update(job_type=jt, prompt=prompt, scope=context_scope)
        return Ok(job)

    stub = SimpleNamespace(
        _find_candidate=lambda cid: candidate if cid == "a1" else None,
        ai_job_service=SimpleNamespace(create_job=fake_create_job),
        _close_candidate_review=lambda: None,
        _job_status_label=SimpleNamespace(setText=lambda t: None),
        _sync_jobs_indicator=lambda: None,
        _start_ai_job_worker=lambda jid: captured.__setitem__("started", jid),
        ctx=SimpleNamespace(log=lambda *a, **k: None),
    )
    CreationWorkspace._repair_canon_from_analysis(stub, "a1")

    assert captured["job_type"] == AIJobType.REPAIR_COHERENCE
    assert "Repara las incoherencias" in captured["prompt"]
    assert captured["scope"]["selected_entity_ids"] == ["ent-1"]
    assert captured["started"] == "job-1"
    assert stub._repair_source_cid["job-1"] == "a1"


def test_apply_repair_changes_applies_and_consumes_report(qapp):
    # UX8: aplicar cambios concretos edita canon vía servicios y consume el informe.
    from packages.application.entity_service import EntityService
    from packages.application.project_service import ProjectService
    from packages.application.relation_service import RelationService
    from packages.application.candidate_service import CandidateService
    from packages.persistence.store import ProjectStore
    from packages.application import coherence_repair as cr

    ps = ProjectService(store=ProjectStore())
    ps.create(name="UX8")
    es = EntityService(project_service=ps)
    es.create_entity({"name": "Casa Vex", "entity_type": "contenedor",
                      "extended_description": "viejo"})
    cs = SimpleNamespace(entity_service=es, relation_service=RelationService(project_service=ps))
    controller = SimpleNamespace(cs=cs, ps=ps, accepted=[],
                                 accept=lambda cid: controller.accepted.append(cid))

    host = __import__("PySide6.QtWidgets", fromlist=["QWidget"]).QWidget()
    layer = SeedNotificationLayer(host)
    layer.add("a1", "Informe")
    bell = ZenBell(); bell.set_enabled(False)
    stub = SimpleNamespace(
        # BETA2-UX-02: la Creación usa candidate_controller directo (antes candidate_view.cc).
        candidate_controller=controller,
        _get_active_project=lambda: ps.active_project,
        _seed_notifications=layer, _zen_bell=bell,
        ctx=SimpleNamespace(log=lambda *a, **k: None),
        _save_project_from_canvas=lambda: None,
        _close_candidate_review=lambda: None,
        _on_suggestion_changed=lambda: None,
        _rehydrate_seed_notifications=lambda: None,
    )
    changes = cr.resolve_repair_changes(
        cr.normalize_repair_changes([
            {"change_type": "edit_entity", "entity_name": "Casa Vex", "field": "body",
             "proposed_value": "Casa en declive."},
        ]), ps.active_project)
    CreationWorkspace._apply_repair_changes(stub, changes, "a1")

    ent = next(e for e in ps.active_project.entities if e.name == "Casa Vex")
    assert ent.extended_description == "Casa en declive."  # canon reparado
    assert controller.accepted == ["a1"]  # informe consumido
    assert not layer.has("a1")
    host._keep = layer


def test_apply_repair_changes_uses_real_workspace_methods(qapp):
    # Guarda contra el bug de llamar a métodos inexistentes (el stub los enmascara):
    # los colaboradores reales que usa _apply_repair_changes deben existir en la clase.
    for name in ("_save_project_from_canvas", "_on_suggestion_changed",
                 "_rehydrate_seed_notifications", "_close_candidate_review"):
        assert callable(getattr(CreationWorkspace, name, None)), f"falta {name}"


# ── Germinación por entidad durante el job de edición ───────────────────────


class _FakeNode:
    def __init__(self):
        self.phase = 0.0

    def set_bloom_phase(self, phase):
        self.phase = phase


def test_node_germination_start_tick_stop(qapp):
    canvas = GraphCanvasView()  # GraphCanvasView es el canvas interno (QGraphicsView)
    fakes = {"a": _FakeNode(), "b": _FakeNode()}
    canvas._bloom_target = lambda k: fakes.get(k)  # type: ignore[method-assign]

    started = canvas.start_node_germination(["a", "b", "missing"])
    assert started is True
    assert canvas._germinating == {"a", "b"}  # «missing» no tiene nodo
    assert canvas._germ_timer.isActive()

    canvas._germ_tick()
    assert fakes["a"].phase > 0.0 and fakes["b"].phase > 0.0  # latido aplicado

    canvas.stop_node_germination(["a"])
    assert canvas._germinating == {"b"}
    assert fakes["a"].phase == 0.0  # glow apagado al parar

    canvas.stop_node_germination()  # todos
    assert canvas._germinating == set()
    assert not canvas._germ_timer.isActive()


def test_start_node_germination_no_targets_is_noop(qapp):
    canvas = GraphCanvasView()
    canvas._bloom_target = lambda k: None  # type: ignore[method-assign]
    assert canvas.start_node_germination(["x"]) is False
    assert not canvas._germ_timer.isActive()


def test_widget_facade_delegates_germination(qapp):
    # La vista usa self.graph = GraphCanvasWidget → sus passthroughs delegan en .canvas.
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget

    calls = {"start": [], "stop": []}
    fake = SimpleNamespace(
        canvas=SimpleNamespace(
            start_node_germination=lambda ids: calls["start"].append(list(ids)),
            stop_node_germination=lambda ids=None: calls["stop"].append(ids),
        )
    )
    GraphCanvasWidget.start_node_germination(fake, ["e1"])
    GraphCanvasWidget.stop_node_germination(fake, ["e1"])
    assert calls["start"] == [["e1"]]
    assert calls["stop"] == [["e1"]]


def test_stop_edit_germination_clears_job(qapp):
    calls: list = []
    stub = SimpleNamespace(
        graph=SimpleNamespace(stop_node_germination=lambda ids: calls.append(list(ids))),
        _edit_germ_jobs={"j1": ["e1", "e2"]},
    )
    CreationWorkspace._stop_edit_germination(stub, "j1")
    assert calls == [["e1", "e2"]]
    assert "j1" not in stub._edit_germ_jobs
    # job desconocido → no-op (sin excepción)
    CreationWorkspace._stop_edit_germination(stub, "jX")
    assert calls == [["e1", "e2"]]


# ── Bloom al aceptar una EDICIÓN ────────────────────────────────────────────


def _germinate_stub():
    calls = {"node": [], "relation": [], "ring": [], "milestone": []}
    stub = SimpleNamespace(
        graph=SimpleNamespace(
            bloom_node=lambda i: calls["node"].append(i),
            bloom_relation=lambda i: calls["relation"].append(i),
            bloom_ring=lambda i: calls["ring"].append(i),
        ),
        chrono=SimpleNamespace(bloom_milestone=lambda i: calls["milestone"].append(i)),
    )
    return stub, calls


def test_germinate_blooms_edited_entity(qapp):
    stub, calls = _germinate_stub()
    CreationWorkspace._germinate(stub, {"edited_entity_id": "ent-7"})
    assert calls["node"] == ["ent-7"]


def test_germinate_blooms_edited_relation_ring_milestone(qapp):
    stub, calls = _germinate_stub()
    CreationWorkspace._germinate(stub, {"edited_relation_id": "rel-1"})
    CreationWorkspace._germinate(stub, {"edited_ring_id": "ring-1"})
    CreationWorkspace._germinate(stub, {"edited_milestone_id": "hito-1"})
    assert calls["relation"] == ["rel-1"]
    assert calls["ring"] == ["ring-1"]
    assert calls["milestone"] == ["hito-1"]
    assert calls["node"] == []
