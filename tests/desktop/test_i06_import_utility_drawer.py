from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")

if HAS_QT:
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget

    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace
    from hosts.DesktopHostPySide.widgets.right_drawer import RightDrawer


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


class FakeDrawer:
    def __init__(self):
        self.content = None
        self.title = None
        self.opened = False

    def set_content(self, widget, title: str = ""):
        self.content = widget
        self.title = title

    def open(self):
        self.opened = True


class DeletedQtWrapperLike:
    @property
    def windowTitle(self):
        raise RuntimeError("Internal C++ object already deleted")


def test_i06_open_utility_survives_deleted_qt_title_wrapper():
    drawer = FakeDrawer()
    workspace = CreationWorkspace.__new__(CreationWorkspace)
    workspace.ctx = SimpleNamespace(drawer=drawer)
    view = DeletedQtWrapperLike()

    workspace._open_utility(view)

    assert drawer.content is view
    assert drawer.title == "Herramienta"
    assert drawer.opened is True


def test_i06_right_drawer_reopen_cancels_pending_close(qapp):
    parent = QWidget()
    parent.resize(1180, 760)
    parent.show()
    QTest.qWait(30)

    drawer = RightDrawer(parent)
    first = QWidget()
    first.setObjectName("project-panel")
    second = QWidget()
    second.setObjectName("import-panel")

    drawer.set_content(first, title="Proyecto")
    drawer.open()
    QTest.qWait(360)
    assert drawer.isVisible()
    assert drawer._content is first

    drawer.close()
    drawer.set_content(second, title="Importacion documental")
    drawer.open()
    QTest.qWait(360)

    assert drawer.isVisible()
    assert drawer.maximumWidth() > 0
    assert drawer._content is second
    assert drawer._title.text() == "Importacion documental"

    parent.close()


def test_i06_open_utility_accepts_explicit_title_without_touching_window_title():
    drawer = FakeDrawer()
    workspace = CreationWorkspace.__new__(CreationWorkspace)
    workspace.ctx = SimpleNamespace(drawer=drawer)
    view = DeletedQtWrapperLike()

    workspace._open_utility(view, title="Importación documental")

    assert drawer.title == "Importación documental"
