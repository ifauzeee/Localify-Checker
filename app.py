from __future__ import annotations

import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> int:
    # Allow Ctrl+C to close the application instantly
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("Localify Checker")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()

    # Periodically yield execution to Python to process signals (e.g. SIGINT)
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
