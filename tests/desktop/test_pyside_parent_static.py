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
    # PA02: baseline regenerado tras mover el wizard a QFrame embebible, el overlay
    # modal, el auto-load y los cambios de la command bar (worldbuilding/tuners).
    "hosts/DesktopHostPySide/main_window.py:174:cw = QWidget()",
    "hosts/DesktopHostPySide/main_window.py:250:bar = QFrame()",
    "hosts/DesktopHostPySide/main_window.py:291:wrapper = QWidget()",
    "hosts/DesktopHostPySide/main_window.py:297:navbar = QFrame()",
    "hosts/DesktopHostPySide/views/corpus_view.py:176:w = QWidget()",
    "hosts/DesktopHostPySide/views/home_view.py:598:content = QWidget()",
    "hosts/DesktopHostPySide/views/home_view.py:707:line = QFrame()",
    "hosts/DesktopHostPySide/views/import_export_view.py:183:self.cards_container = QWidget()",
    "hosts/DesktopHostPySide/views/relation_view.py:222:w = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:455:self.cards = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:515:self.cards = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:628:body = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:861:grid_host = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:889:self._layer_section = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:900:self._layer_chips_container = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:1500:self._chips_widget = QWidget()",
    "hosts/DesktopHostPySide/views/workspaces.py:1906:bar = QFrame()",
    "hosts/DesktopHostPySide/views/workspaces.py:2195:bar = QFrame()",
    "hosts/DesktopHostPySide/widgets/creative_config_panel.py:357:page = QWidget()",
    "hosts/DesktopHostPySide/widgets/design_system.py:439:self.body = QWidget()",
    "hosts/DesktopHostPySide/widgets/left_drawer.py:59:header = QFrame()",
    "hosts/DesktopHostPySide/widgets/milestone_chronology_view.py:208:self.cards_widget = QWidget()",
    "hosts/DesktopHostPySide/widgets/milestone_chronology_view.py:214:self.detail_frame = QFrame()",
    "hosts/DesktopHostPySide/widgets/node_detail_panel.py:292:form_card = QFrame()",
    "hosts/DesktopHostPySide/widgets/node_detail_panel.py:487:ai_card = QFrame()",
    "hosts/DesktopHostPySide/widgets/node_detail_panel.py:533:self.suggestion_frame = QFrame()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:106:block = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:129:row = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:206:content = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:233:rail = QFrame()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:277:head = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:318:foot = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:363:page = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:698:wrap = QWidget()",
    "hosts/DesktopHostPySide/widgets/project_wizard.py:712:line = QFrame()",
    "hosts/DesktopHostPySide/widgets/related_milestones_panel.py:101:self.body = QWidget()",
    "hosts/DesktopHostPySide/widgets/relation_detail_panel.py:313:form_card = QFrame()",
    "hosts/DesktopHostPySide/widgets/relation_detail_panel.py:435:ai_card = QFrame()",
    "hosts/DesktopHostPySide/widgets/relation_detail_panel.py:476:self.suggestion_frame = QFrame()",
    "hosts/DesktopHostPySide/widgets/relation_detail_panel.py:562:_temp_widget = QWidget()",
    "hosts/DesktopHostPySide/widgets/right_drawer.py:66:header = QFrame()",
    "hosts/DesktopHostPySide/widgets/tree_detail_panel.py:75:frame = QFrame()",
    "hosts/DesktopHostPySide/widgets/tree_detail_panel.py:251:id_card = QWidget()",
    "hosts/DesktopHostPySide/widgets/tree_detail_panel.py:580:self.suggestion_frame = QFrame()",
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
