"""B40 ProjectPanel regressions.

Covers the configuration menu crash reported on Windows after replacing the
old campaign/novela cards with the B40 tabbed creative config panel.
"""

from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.widgets.settings_panels import ProjectPanel
from packages.domain.project import Project


def test_project_panel_opens_after_b40_tabbed_config_replaced_legacy_cards():
    app = QApplication.instance() or QApplication([])
    project = Project(name="Smoke B40 config")
    ctx = SimpleNamespace(
        project_controller=SimpleNamespace(
            ps=SimpleNamespace(active_project=project)
        )
    )
    callbacks = {
        "new_project": lambda *args, **kwargs: None,
        "open_project": lambda *args, **kwargs: None,
        "save_project": lambda *args, **kwargs: None,
        "close_project": lambda *args, **kwargs: None,
    }

    panel = ProjectPanel(ctx=ctx, callbacks=callbacks, on_preview=lambda *_: None)

    assert panel.project is project
    assert hasattr(panel, "creative_tabs")
    panel._update_type_visibility()
    panel._save_all()
