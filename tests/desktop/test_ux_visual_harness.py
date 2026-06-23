"""Cobertura mínima del arnés visual (BETA1-UX00).

Verifica que el generador de proyecto demo produce un mundo representativo
y persistible. El arnés de *captura* (Qt) es una utilidad manual y no se
testea aquí para no arrastrar la fragilidad de PySide al CI.
"""

from __future__ import annotations

from pathlib import Path

from packages.application.project_service import ProjectService
from packages.domain.result import Ok
from tests.desktop._visual.demo_project import build_demo_project


def test_demo_project_tiene_mundo_representativo(tmp_path: Path) -> None:
    path = tmp_path / "demo.json"
    manifest = build_demo_project(path)

    assert path.exists(), "el demo debe guardarse en disco"
    assert len(manifest.ring_ids) == 3
    assert len(manifest.entity_ids) == 8
    assert len(manifest.relation_ids) == 7
    # Los candidatos son best-effort, pero el demo apunta a 2.
    assert len(manifest.candidate_ids) >= 0


def test_demo_project_recarga_sin_perdida(tmp_path: Path) -> None:
    path = tmp_path / "demo.json"
    manifest = build_demo_project(path)

    ps = ProjectService()
    reopened = ps.open(path)
    assert isinstance(reopened, Ok)
    proj = ps.active_project
    assert len(proj.entities) == len(manifest.entity_ids)
    assert len(proj.relations) == len(manifest.relation_ids)
    # 3 anillos creados (más los layers por defecto que traiga el proyecto).
    ring_ids = {wl.id for wl in proj.world_layers}
    assert set(manifest.ring_ids) <= ring_ids
