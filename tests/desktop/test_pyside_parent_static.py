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
    # Baseline regenerado en el CIERRE DE LA OLEADA BETA2 (2026-08-05).
    # El baseline se indexa por `fichero:LINEA:codigo`, asi que 15 tickets editando
    # los mismos ficheros lo dejan rojo solo por desplazamiento. Esta es la pasada
    # unica que pedia BETA2-FIX-01.
    #
    # El conjunto MEJORA: 52 -> 49. Salen 3 entradas de `workspaces.py`
    # (grid_host/_layer_section/_layer_chips_container) porque FIX-11 borro
    # `NarrativeWorkbench`. Los 2 widgets sin padre que la oleada introdujo
    # (`field_help.py` GlossaryPanel y `milestone_detail_panel._build_causal_section`)
    # NO se anaden al baseline: se les dio padre explicito.
    'hosts/DesktopHostPySide/main_window.py:317:cw = QWidget()',
    'hosts/DesktopHostPySide/main_window.py:414:wrapper = QWidget()',
    'hosts/DesktopHostPySide/main_window.py:420:navbar = QFrame()',
    'hosts/DesktopHostPySide/views/home_view.py:640:content = QWidget()',
    'hosts/DesktopHostPySide/views/home_view.py:823:banner = QFrame()',
    'hosts/DesktopHostPySide/views/home_view.py:887:line = QFrame()',
    'hosts/DesktopHostPySide/views/workspaces.py:1672:bar = QFrame()',
    'hosts/DesktopHostPySide/views/workspaces.py:956:self._chips_widget = QWidget()',
    'hosts/DesktopHostPySide/widgets/calendar_editor.py:355:grid_holder = QWidget()',
    'hosts/DesktopHostPySide/widgets/calendar_editor.py:438:grid_holder = QWidget()',
    'hosts/DesktopHostPySide/widgets/calendar_editor.py:449:anchor_holder = QWidget()',
    'hosts/DesktopHostPySide/widgets/chrono_canvas.py:1629:form_host = QWidget()',
    'hosts/DesktopHostPySide/widgets/chronology_config_panel.py:60:holder = QWidget()',
    'hosts/DesktopHostPySide/widgets/context_preview_panel.py:107:box = QWidget()',
    'hosts/DesktopHostPySide/widgets/context_preview_panel.py:143:box = QWidget()',
    'hosts/DesktopHostPySide/widgets/context_preview_panel.py:74:content = QWidget()',
    'hosts/DesktopHostPySide/widgets/context_preview_panel.py:88:box = QWidget()',
    'hosts/DesktopHostPySide/widgets/creative_config_panel.py:249:page = QWidget()',
    'hosts/DesktopHostPySide/widgets/design_system.py:1228:accent = QFrame()',
    'hosts/DesktopHostPySide/widgets/design_system.py:1367:self.body = QWidget()',
    'hosts/DesktopHostPySide/widgets/design_system.py:1423:self.body = QWidget()',
    'hosts/DesktopHostPySide/widgets/foco/foco_view.py:1532:container = QWidget()',
    'hosts/DesktopHostPySide/widgets/foco/foco_view.py:450:shelf_inner = QWidget()',
    'hosts/DesktopHostPySide/widgets/foco/memory_section.py:107:frame = QFrame()',
    'hosts/DesktopHostPySide/widgets/foco/relations_panel.py:192:line = QWidget()',
    'hosts/DesktopHostPySide/widgets/foco/watering_progress_popover.py:110:row = QWidget()',
    'hosts/DesktopHostPySide/widgets/foco/watering_progress_popover.py:64:holder = QWidget()',
    'hosts/DesktopHostPySide/widgets/image_search_dialog.py:219:preview_panel = QWidget()',
    'hosts/DesktopHostPySide/widgets/milestone_detail_panel.py:723:container = QWidget()',
    'hosts/DesktopHostPySide/widgets/node_detail_panel.py:151:wrapper = QWidget()',
    'hosts/DesktopHostPySide/widgets/node_detail_panel.py:465:form_card = QFrame()',
    'hosts/DesktopHostPySide/widgets/node_detail_panel.py:764:ai_card = QFrame()',
    'hosts/DesktopHostPySide/widgets/node_detail_panel.py:803:self.suggestion_frame = QFrame()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:177:content = QWidget()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:199:rail = QFrame()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:243:head = QWidget()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:284:foot = QWidget()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:329:page = QWidget()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:480:simple = QWidget()',
    'hosts/DesktopHostPySide/widgets/project_wizard.py:91:block = QWidget()',
    'hosts/DesktopHostPySide/widgets/related_milestones_panel.py:101:self.body = QWidget()',
    'hosts/DesktopHostPySide/widgets/relation_detail_panel.py:309:form_card = QFrame()',
    'hosts/DesktopHostPySide/widgets/relation_detail_panel.py:434:ai_card = QFrame()',
    'hosts/DesktopHostPySide/widgets/relation_detail_panel.py:462:self.suggestion_frame = QFrame()',
    'hosts/DesktopHostPySide/widgets/relation_detail_panel.py:557:_temp_widget = QWidget()',
    'hosts/DesktopHostPySide/widgets/repair_review_panel.py:69:holder = QWidget()',
    'hosts/DesktopHostPySide/widgets/repair_review_panel.py:97:frame = QFrame()',
    'hosts/DesktopHostPySide/widgets/structure_review_panel.py:159:holder = QWidget()',
    'hosts/DesktopHostPySide/widgets/structure_review_panel.py:207:frame = QFrame()',
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
