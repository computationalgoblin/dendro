"""B40 wizard save regressions.

The initial wizard must create the JSON at the path selected by the user and the
saved project must be loadable afterwards. This covers the Windows report where
a wizard-created project did not appear again after saving.
"""

from pathlib import Path

from hosts.DesktopHostPySide.controllers.project_controller import ProjectController
from packages.domain.result import Ok
from packages.persistence.store import ProjectStore


def test_project_controller_create_with_path_saves_loadable_json(tmp_path: Path):
    path = tmp_path / "wizard_project.json"
    controller = ProjectController(store=ProjectStore())

    created = controller.create("Proyecto Wizard", str(path))
    assert isinstance(created, Ok)
    assert controller.current_path == str(path)

    project = controller.ps.active_project
    assert project is not None
    project.primary_language = "es"
    project.worldbuilding_active = True
    project.creative_config.core_premise = "Premisa creada desde wizard"

    saved = controller.save()
    assert isinstance(saved, Ok)
    assert path.exists()
    assert not path.with_suffix(path.suffix + ".tmp").exists()

    reopened = ProjectController(store=ProjectStore())
    reopened.open(str(path))
    loaded = reopened.ps.active_project
    assert loaded is not None
    assert loaded.name == "Proyecto Wizard"
    assert loaded.worldbuilding_active is True
    assert loaded.creative_config.core_premise == "Premisa creada desde wizard"
    assert len(loaded.entities) == 0
    assert len(loaded.relations) == 0
    assert len(loaded.candidates) == 0
    assert loaded.world_layers == []


def test_main_window_new_project_uses_selected_save_path_contract():
    source = Path("hosts/DesktopHostPySide/main_window.py").read_text(encoding="utf-8")
    assert "self.controller.create(name, path)" in source
    assert "save_result = self.controller.save()" in source
    assert "Error guardando proyecto" in source
