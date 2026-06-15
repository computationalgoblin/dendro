"""Static PySide6 parent guard.

Qt widgets without an explicit parent are a recurring source of subtle Desktop
regressions. The current codebase still has historical parentless widgets, so this
test freezes that baseline and blocks new occurrences until they are fixed or
consciously added to the baseline with justification.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "hosts" / "DesktopHostPySide"
PARENTLESS_WIDGET_RE = re.compile(r"\b(QFrame|QWidget|QGroupBox)\(\)")

EXPECTED_PARENTLESS_WIDGETS = {
    "hosts/DesktopHostPySide/main_window.py:194:cw = QWidget()",
    "hosts/DesktopHostPySide/main_window.py:265:bar = QFrame()",
    "hosts/DesktopHostPySide/main_window.py:306:wrapper = QWidget()",
    "hosts/DesktopHostPySide/main_window.py:312:navbar = QFrame()",
    "hosts/DesktopHostPySide/views/corpus_view.py:176:w = QWidget()",
    "hosts/DesktopHostPySide/views/home_view.py:598:content = QWidget()",
    "hosts/DesktopHostPySide/views/home_view.py:709:line = QFrame()",
    "hosts/DesktopHostPySide/views/import_export_view.py:183:self.cards_container = QWidget()",
    "hosts/DesktopHostPySide/views/live_post_view.py:50:live = QWidget()",
    "hosts/DesktopHostPySide/views/live_post_view.py:87:post = QWidget()",
    "hosts/DesktopHostPySide/views/relation_view.py:189:w = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:429:self.cards = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:489:self.cards = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:602:body = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:835:grid_host = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:863:self._layer_section = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:874:self._layer_chips_container = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:1483:self._chips_widget = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:1890:bar = QFrame()",
    "hosts/DesktopHostPySide/views/workspaces.py:2174:bar = QFrame()",
    "hosts/DesktopHostPySide/views/workspaces.py:3825:self.container = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:3834:header = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:4061:detail = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:4135:header = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:4155:self.container = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:4215:panel = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:4394:header = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:4414:self.container = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:4524:panel = QWidget()",
    "hosts/DesktopHostPySide/widgets/creative_config_panel.py:357:page = QWidget()",
    "hosts/DesktopHostPySide/widgets/design_system.py:439:self.body = QWidget()",
    "hosts/DesktopHostPySide/widgets/left_drawer.py:59:header = QFrame()",
    "hosts/DesktopHostPySide/widgets/milestone_chronology_view.py:208:self.cards_widget = QWidget()",
    "hosts/DesktopHostPySide/widgets/milestone_chronology_view.py:214:self.detail_frame = QFrame()",
    "hosts/DesktopHostPySide/widgets/node_detail_panel.py:292:form_card = QFrame()",
    "hosts/DesktopHostPySide/widgets/node_detail_panel.py:487:ai_card = QFrame()",
    "hosts/DesktopHostPySide/widgets/node_detail_panel.py:533:self.suggestion_frame = QFrame()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:107:block = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:130:row = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:199:content = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:226:rail = QFrame()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:270:head = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:311:foot = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:356:page = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:698:wrap = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:712:line = QFrame()",
    "hosts/DesktopHostPySide/widgets/related_milestones_panel.py:101:self.body = QWidget()",
    "hosts/DesktopHostPySide/widgets/relation_detail_panel.py:304:form_card = QFrame()",
    "hosts/DesktopHostPySide/widgets/relation_detail_panel.py:442:ai_card = QFrame()",
    "hosts/DesktopHostPySide/widgets/relation_detail_panel.py:483:self.suggestion_frame = QFrame()",
    "hosts/DesktopHostPySide/widgets/relation_detail_panel.py:569:_temp_widget = QWidget()",
    "hosts/DesktopHostPySide/widgets/right_drawer.py:66:header = QFrame()",
    "hosts/DesktopHostPySide/widgets/tree_detail_panel.py:75:frame = QFrame()",
    "hosts/DesktopHostPySide/widgets/tree_detail_panel.py:251:id_card = QWidget()",
    "hosts/DesktopHostPySide/widgets/tree_detail_panel.py:584:self.suggestion_frame = QFrame()",
}


def _current_parentless_widgets() -> set[str]:
    rows: set[str] = set()
    for path in sorted(DESKTOP.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if PARENTLESS_WIDGET_RE.search(line):
                rows.add(f"{relative}:{line_number}:{line.strip()}")
    return rows


def test_no_new_parentless_qt_widgets_are_introduced() -> None:
    current = _current_parentless_widgets()
    new_occurrences = sorted(current - EXPECTED_PARENTLESS_WIDGETS)
    removed_occurrences = sorted(EXPECTED_PARENTLESS_WIDGETS - current)

    assert not new_occurrences, "New parentless widgets detected: " + "; ".join(new_occurrences)
    assert not removed_occurrences, (
        "Parentless widget baseline improved; update EXPECTED_PARENTLESS_WIDGETS: "
        + "; ".join(removed_occurrences)
    )
