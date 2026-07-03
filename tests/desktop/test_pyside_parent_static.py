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
    # Baseline regenerado tras la retirada del subsistema de importación (borrado de
    # import_export_view y desplazamiento de líneas en main_window/workspaces).
    'hosts/DesktopHostPySide/main_window.py:176:cw = QWidget()',
    'hosts/DesktopHostPySide/main_window.py:274:bar = QFrame()',
    'hosts/DesktopHostPySide/main_window.py:315:wrapper = QWidget()',
    'hosts/DesktopHostPySide/main_window.py:321:navbar = QFrame()',
    'hosts/DesktopHostPySide/views/corpus_view.py:176:w = QWidget()',
    'hosts/DesktopHostPySide/views/home_view.py:609:content = QWidget()',
    'hosts/DesktopHostPySide/views/home_view.py:718:line = QFrame()',
    'hosts/DesktopHostPySide/views/relation_view.py:222:w = QWidget()',
    'hosts/DesktopHostPySide/views/workspaces.py:1552:self._chips_widget = QWidget()',
    'hosts/DesktopHostPySide/views/workspaces.py:2036:bar = QFrame()',
    'hosts/DesktopHostPySide/views/workspaces.py:3158:bar = QFrame()',
    'hosts/DesktopHostPySide/views/workspaces.py:621:grid_host = QWidget()',
    'hosts/DesktopHostPySide/views/workspaces.py:668:self._layer_section = QWidget()',
    'hosts/DesktopHostPySide/views/workspaces.py:679:self._layer_chips_container = QWidget()',
    'hosts/DesktopHostPySide/widgets/chronology_walk_runner_panel.py:138:self._changes_container = QWidget()',
    'hosts/DesktopHostPySide/widgets/context_preview_panel.py:105:box = QWidget()',
    'hosts/DesktopHostPySide/widgets/context_preview_panel.py:141:box = QWidget()',
    'hosts/DesktopHostPySide/widgets/context_preview_panel.py:72:content = QWidget()',
    'hosts/DesktopHostPySide/widgets/context_preview_panel.py:86:box = QWidget()',
    'hosts/DesktopHostPySide/widgets/creative_config_panel.py:249:page = QWidget()',
    'hosts/DesktopHostPySide/widgets/design_system.py:687:accent = QFrame()',
    'hosts/DesktopHostPySide/widgets/design_system.py:822:self.body = QWidget()',
    'hosts/DesktopHostPySide/widgets/milestone_chronology_view.py:211:self.cards_widget = QWidget()',
    'hosts/DesktopHostPySide/widgets/milestone_chronology_view.py:217:self.detail_frame = QFrame()',
    'hosts/DesktopHostPySide/widgets/milestone_detail_panel.py:103:body = QWidget()',
    'hosts/DesktopHostPySide/widgets/node_detail_panel.py:305:form_card = QFrame()',
    'hosts/DesktopHostPySide/widgets/node_detail_panel.py:497:ai_card = QFrame()',
    'hosts/DesktopHostPySide/widgets/node_detail_panel.py:543:self.suggestion_frame = QFrame()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:175:content = QWidget()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:197:rail = QFrame()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:241:head = QWidget()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:282:foot = QWidget()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:327:page = QWidget()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:449:simple = QWidget()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:89:block = QWidget()',
    'hosts/DesktopHostPySide/widgets/related_milestones_panel.py:101:self.body = QWidget()',
    'hosts/DesktopHostPySide/widgets/relation_detail_panel.py:296:form_card = QFrame()',
    'hosts/DesktopHostPySide/widgets/relation_detail_panel.py:420:ai_card = QFrame()',
    'hosts/DesktopHostPySide/widgets/relation_detail_panel.py:461:self.suggestion_frame = QFrame()',
    'hosts/DesktopHostPySide/widgets/relation_detail_panel.py:547:_temp_widget = QWidget()',
    'hosts/DesktopHostPySide/widgets/repair_review_panel.py:69:holder = QWidget()',
    'hosts/DesktopHostPySide/widgets/repair_review_panel.py:97:frame = QFrame()',
    'hosts/DesktopHostPySide/widgets/tree_detail_panel.py:255:id_card = QWidget()',
    'hosts/DesktopHostPySide/widgets/tree_detail_panel.py:562:self.suggestion_frame = QFrame()',
    'hosts/DesktopHostPySide/widgets/tree_detail_panel.py:79:frame = QFrame()',
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
