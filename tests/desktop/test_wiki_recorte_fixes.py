"""BETA2-WIKI (post-smoke): regresiones del recorte de IA.

Cubre tres arreglos del recorte de IA (guard ``_LEGACY_AI_UI=False``):

- A1: el panel de relación ya NO muestra su barra de IA cuando ``ai_controller`` es
  None (validación por instanciación real — el panel se construye barato).
- A2: ``_position_floats`` ya no sale temprano si no hay command bar, así la píldora
  Guardar/💧 y la leyenda del jardín no saltan a (0,0).
- A3: el indicador de estado de IA (``_job_status_label`` + ``_busy_indicator``) existe
  SIEMPRE en un floater propio, independiente de la command bar retirada; sin él las
  Sugerencias reventaban al referenciarlo (sin feedback).

CreationWorkspace no se instancia sin AppContext completo (patrón de la casa, ver
``test_foco_band_pills_icons``): A2/A3 se validan por comprobación de FUENTE.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel
from packages.application.project_service import ProjectService
from packages.domain.result import Ok

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")
_REMOVED_NO_AI_LABEL = "IA contextual no disponible en esta sesión."


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


def _ctx_project():
    ps = ProjectService()
    assert isinstance(ps.create("WIKI-RECORTE"), Ok)
    ctx = AppContext()
    ctx.set_advanced_mode(False)
    ctx.project_controller = SimpleNamespace(ps=ps)
    return ctx, EntityController(ps), RelationController(ps)


def _entity(ec, name):
    r = ec.create(
        {
            "name": name,
            "entity_type": "personaje",
            "brief_description": "",
            "canon_state": "borrador",
        }
    )
    assert isinstance(r, Ok)
    return r.value


# ── A1: barra de IA del panel de relación retirada ──────────────────────────


def test_relation_panel_hides_ai_bar_without_controller(_app):
    ctx, ec, rc = _ctx_project()
    a, b = _entity(ec, "A"), _entity(ec, "B")
    rel = rc.create(a.id, b.id, "es_aliado_de")
    rel_id = rel.value.id if isinstance(rel, Ok) else rel.id

    panel = RelationDetailPanel(ctx, rc, rel_id, on_saved=lambda: None)  # ai_controller=None
    assert panel.ai_controller is None

    # La etiqueta muerta "IA contextual no disponible…" se eliminó por completo.
    texts = [w.text() for w in panel.findChildren(QLabel)]
    assert _REMOVED_NO_AI_LABEL not in texts

    # El card de IA no se monta: existe como huérfano oculto, nunca visible en el panel.
    ai_card = panel.findChild(QFrame, "aiCard")
    assert ai_card is None or not ai_card.isVisibleTo(panel)


def test_relation_panel_mounts_ai_bar_with_controller(_app):
    """Contraprueba: con ai_controller presente, el card SÍ se monta (no rompimos el legacy)."""
    ctx, ec, rc = _ctx_project()
    a, b = _entity(ec, "A"), _entity(ec, "B")
    rel = rc.create(a.id, b.id, "es_aliado_de")
    rel_id = rel.value.id if isinstance(rel, Ok) else rel.id

    fake_ai = SimpleNamespace(relation_text_suggestion=lambda *a, **k: ("", ""))
    panel = RelationDetailPanel(ctx, rc, rel_id, on_saved=lambda: None, ai_controller=fake_ai)
    ai_card = panel.findChild(QFrame, "aiCard")
    assert ai_card is not None and ai_card.isVisibleTo(panel)


# ── A2: _position_floats ya no sale temprano sin command bar ─────────────────


def test_position_floats_no_early_return_without_command_bar():
    src = _WORKSPACES.read_text(encoding="utf-8")
    # Aíslo el cuerpo de _position_floats (hay otros `if bar is None: return` legítimos).
    body = src.split("def _position_floats(self)")[1].split("\n    def ")[0]
    # El early-return que dejaba las píldoras en (0,0) desapareció de ESTA función…
    assert "if bar is None:\n            return" not in body
    # …y hay un fallback de anclaje abajo-derecha cuando no hay command bar.
    assert "max(58, self.height() - 62)" in body


# ── A3: indicador de estado de IA SIEMPRE presente (floater propio) ──────────


def test_status_floater_always_built_without_command_bar():
    src = _WORKSPACES.read_text(encoding="utf-8")
    assert "class _StatusLabel(QLabel)" in src
    assert "def _build_status_floater(self)" in src
    # Se crea SIEMPRE que no haya command bar (que es el caso con el recorte).
    assert "if self._command_bar is None:" in src
    assert "self._float_status = self._build_status_floater()" in src
    # El floater define ambos atributos que los llamantes referencian sin guard.
    floater = src.split("def _build_status_floater(self)")[1].split("\n    def ")[0]
    assert "self._busy_indicator = BusyIndicator(" in floater
    assert "self._job_status_label = _StatusLabel(" in floater


# ── Part B: análisis de intención + generación compuesta (wiring desktop) ────


def test_suggestion_prep_worker_runs_compose_generation():
    src = _WORKSPACES.read_text(encoding="utf-8")
    assert "class _SuggestionPrepWorker(QThread)" in src
    run = src.split("class _SuggestionPrepWorker(QThread)")[1].split("\nclass ")[0]
    # El worker delega en WateringService.compose_generation (nav + intención, off-thread).
    assert "self.svc.compose_generation(" in run


def test_intent_service_wired_into_watering():
    src = _WORKSPACES.read_text(encoding="utf-8")
    assert "SuggestionIntentService(_foco_ps" in src
    assert "intent_service=self.suggestion_intent_service" in src


def test_launch_suggestion_surfaces_plan_summary():
    src = _WORKSPACES.read_text(encoding="utf-8")
    body = src.split("def _launch_suggestion(self")[1].split("\n    def ")[0]
    assert "_SuggestionPrepWorker(" in body
    assert "plan_summary" in body  # el plan viaja como feedback al status
