"""DesktopHost entry point — PySide6 MVP (B27.1)."""
from __future__ import annotations
import sys
try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 not installed. Run: pip install narrative-architect[desktop]")
    sys.exit(1)
from hosts.DesktopHostPySide.main_window import MainWindow
from hosts.DesktopHostPySide.widgets.tooltip_suppression import install_tooltip_suppression

def main():
    app = QApplication(sys.argv)
    install_tooltip_suppression(app)
    w = MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
