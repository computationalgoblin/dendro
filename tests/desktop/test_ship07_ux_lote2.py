"""BETA2-SHIP-07: fixes del pase de UX (lote 2-3)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.views.home_view import HomeView
from packages.application.ai_prompt_debug import AIPromptDebugTraceStore

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py").read_text(encoding="utf-8")
_STRUCT_PANEL = Path("hosts/DesktopHostPySide/widgets/structure_review_panel.py").read_text(
    encoding="utf-8"
)
_CHRONO_CFG = Path("hosts/DesktopHostPySide/widgets/chronology_config_panel.py").read_text(
    encoding="utf-8"
)


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


# ── El visor de prompts RAG NO salta al navegador en la beta ─────────────────


def test_prompt_trace_store_disabled_by_default():
    assert AIPromptDebugTraceStore.default().enabled is False


def test_open_prompt_trace_gated_on_enabled():
    body = _WORKSPACES.split("def _open_prompt_trace_page(self)")[1].split("\n    def ")[0]
    assert 'getattr(store, "enabled"' in body


# ── El proyecto de ejemplo no lleva basura de test ───────────────────────────


def test_demo_project_has_no_junk_names():
    demo = Path("ejemplos/La Flor de los Almendros/La Flor de Los Almendros.json")
    data = json.loads(demo.read_text(encoding="utf-8"))
    names = [e.get("name", "") for e in data.get("entities", [])]
    names += [wl.get("name", "") for wl in data.get("world_layers", [])]
    junk = [n for n in names if "asdasd" in n.lower()]
    assert not junk, f"el demo aún tiene nombres basura: {junk}"


# ── «Proponer estructura» corre en un hilo (no congela la ventana) ───────────


def test_propose_structure_runs_in_thread():
    assert "class _ProposeWorker(QThread)" in _STRUCT_PANEL
    body = _STRUCT_PANEL.split("def _propose_structure(self)")[1].split("\n    def ")[0]
    assert "_ProposeWorker(" in body
    assert "self._proposing = True" in body
    assert "worker.start()" in body


# ── Textos: pluralización, etiqueta de métrica, tilde ────────────────────────


def test_structural_pill_pluralization():
    assert "1 ajuste estructural" in _WORKSPACES
    assert "ajustes estructurales" in _WORKSPACES
    assert "ajuste(s) estructural(es)" not in _WORKSPACES


def test_suggest_dialog_uses_readable_metric_label():
    body = _WORKSPACES.split("def _on_foco_suggest(self")[1].split("\n    def ")[0]
    assert '"nutrida": "nutrición"' in body
    assert 'f"Sugerir {metric_label}"' in body


def test_chronology_typo_fixed():
    assert "Cronologia no disponible" not in _CHRONO_CFG
    assert "Cronología no disponible" in _CHRONO_CFG


# ── El visor de Memoria es alcanzable desde el Home ──────────────────────────


def test_home_has_memory_button(_app):
    home = HomeView(AppContext())
    assert hasattr(home, "_btn_memory")
    assert "Memoria" in home._btn_memory.text()
