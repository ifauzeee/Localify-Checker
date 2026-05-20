from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from ui.svg_icons import get_svg_icon


class DragDropZone(QFrame):
    fileSelected = Signal(str)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.file_path = ""

        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("DragDropZone")
        self.setProperty("active", "false")
        self.setProperty("filled", "false")

        self._init_ui()
        self._apply_style()

    def _init_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(6)
        self.main_layout.setAlignment(Qt.AlignCenter)

        # Title of the zone
        self.title_label = QLabel(self.title)
        self.title_label.setObjectName("ZoneTitle")
        self.title_label.setAlignment(Qt.AlignCenter)

        # Icon
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setPixmap(get_svg_icon("folder", "#8a9aab", 28).pixmap(28, 28))

        # Subtitle instructions
        self.instructions = QLabel("Drag & drop CSV or click to browse")
        self.instructions.setObjectName("ZoneInstructions")
        self.instructions.setAlignment(Qt.AlignCenter)
        self.instructions.setWordWrap(True)

        self.main_layout.addWidget(self.title_label)
        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addWidget(self.instructions)

        # File info widget (hidden initially)
        self.file_widget = QFrame()
        self.file_widget.setObjectName("FileInfoWidget")
        self.file_widget.setVisible(False)

        file_layout = QHBoxLayout(self.file_widget)
        file_layout.setContentsMargins(4, 4, 4, 4)
        file_layout.setSpacing(8)

        self.file_icon = QLabel()
        self.file_icon.setPixmap(get_svg_icon("match", "#1DB954", 18).pixmap(18, 18))

        self.file_name_label = QLabel()
        self.file_name_label.setObjectName("FileNameLabel")
        self.file_name_label.setWordWrap(True)

        self.clear_button = QPushButton()
        self.clear_button.setObjectName("ClearZoneButton")
        self.clear_button.setIcon(get_svg_icon("clear", "#E91429", 14))
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear)
        self.clear_button.setToolTip("Hapus file")

        file_layout.addWidget(self.file_icon)
        file_layout.addWidget(self.file_name_label, 1)
        file_layout.addWidget(self.clear_button)

        self.main_layout.addWidget(self.file_widget)

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QFrame#DragDropZone {
                background: #181818;
                border: 2px dashed #292929;
                border-radius: 10px;
                min-height: 100px;
            }
            QFrame#DragDropZone:hover {
                border-color: #3e3e3e;
                background: #202020;
            }
            QFrame#DragDropZone[active="true"] {
                border-color: #1DB954;
                background: #142a19;
            }
            QFrame#DragDropZone[filled="true"] {
                border-style: solid;
                border-color: #292929;
                background: #1e1e1e;
            }
            QFrame#DragDropZone[filled="true"]:hover {
                background: #252525;
            }
            QLabel#ZoneTitle {
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
            }
            QLabel#ZoneInstructions {
                color: #b3b3b3;
                font-size: 11px;
            }
            QLabel#FileNameLabel {
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton#ClearZoneButton {
                background: transparent;
                border: none;
                padding: 4px;
                min-height: 20px;
                min-width: 20px;
            }
            QPushButton#ClearZoneButton:hover {
                background: #333333;
                border-radius: 4px;
            }
        """)

    def mousePressEvent(self, event) -> None:
        # Check if the click happened on the clear button to avoid triggering dialog
        child = self.childAt(event.position().toPoint())
        if child == self.clear_button or (child and child.parent() == self.file_widget and isinstance(child, QPushButton)):
            super().mousePressEvent(event)
            return

        if not self.file_path:
            self._browse_file()
        else:
            super().mousePressEvent(event)

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Pilih {self.title}",
            str(Path.home()),
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            self.setFilePath(path)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith('.csv') for url in urls):
                self.setProperty("active", "true")
                self.style().polish(self)
                event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("active", "false")
        self.style().polish(self)
        event.accept()

    def dropEvent(self, event) -> None:
        self.setProperty("active", "false")
        self.style().polish(self)
        urls = event.mimeData().urls()
        csv_urls = [url.toLocalFile() for url in urls if url.toLocalFile().lower().endswith('.csv')]
        if csv_urls:
            self.setFilePath(csv_urls[0])
            event.acceptProposedAction()

    def setFilePath(self, file_path: str) -> None:
        self.file_path = file_path
        if file_path:
            p = Path(file_path)
            self.title_label.setVisible(False)
            self.icon_label.setVisible(False)
            self.instructions.setVisible(False)

            try:
                size_bytes = p.stat().st_size
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            except Exception:
                size_str = ""

            self.file_name_label.setText(f"{p.name}\n{size_str}")
            self.file_widget.setVisible(True)
            self.setProperty("filled", "true")
            self.style().polish(self)
            self.fileSelected.emit(file_path)
        else:
            self.clear()

    def clear(self) -> None:
        self.file_path = ""
        self.title_label.setVisible(True)
        self.icon_label.setVisible(True)
        self.instructions.setVisible(True)
        self.file_widget.setVisible(False)
        self.setProperty("filled", "false")
        self.style().polish(self)
        self.fileSelected.emit("")
