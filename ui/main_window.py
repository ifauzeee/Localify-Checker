from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.csv_loader import load_local_csv, load_spotify_csv
from core.exporter import export_reports
from core.matcher import match_tracks, summarize_results
from ui.svg_icons import get_svg_icon
from ui.drag_drop_zone import DragDropZone
from ui.circular_progress import CircularProgressRing


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"


class AnalysisWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, local_csv: str, spotify_csv: str) -> None:
        super().__init__()
        self.local_csv = local_csv
        self.spotify_csv = spotify_csv

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit(8, "Reading local CSV")
            local_df = load_local_csv(self.local_csv)

            self.progress.emit(20, "Reading Spotify CSV")
            spotify_df = load_spotify_csv(self.spotify_csv)

            self.progress.emit(30, "Matching songs")

            def progress_callback(value: int, message: str) -> None:
                self.progress.emit(value, message)

            report_df = match_tracks(
                spotify_df,
                local_df,
                progress_callback=progress_callback,
            )
            stats = summarize_results(report_df, local_count=len(local_df))

            self.progress.emit(100, "Analysis complete")
            self.finished.emit({"report": report_df, "stats": stats})
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    status_filters = {
        "Semua": None,
        "Match": "MATCH",
        "Possible": "POSSIBLE MATCH",
        "Missing": "MISSING",
    }

    table_columns = [
        "Spotify Song",
        "Artist",
        "Local Match",
        "Folder",
        "Status",
        "Similarity Score",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Localify Checker")
        self.resize(1280, 800)
        self.setMinimumSize(1040, 680)

        self.report_df = pd.DataFrame(columns=self.table_columns)
        self.worker_thread: QThread | None = None
        self.worker: AnalysisWorker | None = None
        self.stat_labels: dict[str, QLabel] = {}
        self.stat_captions: dict[str, QLabel] = {}

        self._build_ui()
        self._apply_style()
        self._update_stats(self._empty_stats())
        self._apply_filter()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_workspace(), 1)

        self.setCentralWidget(root)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(342)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        # Brand Layout
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(12)
        brand_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        brand_icon = QLabel()
        brand_icon.setPixmap(get_svg_icon("spotify", "#1DB954", 36).pixmap(36, 36))

        brand_text_layout = QVBoxLayout()
        brand_text_layout.setSpacing(0)

        brand_title = QLabel("Localify")
        brand_title.setObjectName("BrandTitle")

        brand_sub = QLabel("CHECKER")
        brand_sub.setObjectName("BrandSub")

        brand_text_layout.addWidget(brand_title)
        brand_text_layout.addWidget(brand_sub)

        brand_layout.addWidget(brand_icon)
        brand_layout.addLayout(brand_text_layout)

        layout.addLayout(brand_layout)

        # Drag Drop Zones
        self.local_drop_zone = DragDropZone("Local Library CSV")
        self.spotify_drop_zone = DragDropZone("Spotify Export CSV")

        layout.addWidget(self.local_drop_zone)
        layout.addWidget(self.spotify_drop_zone)

        layout.addSpacerItem(QSpacerItem(1, 8, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setObjectName("PrimaryButton")
        self.analyze_button.setIcon(get_svg_icon("arrow-right", "#ffffff", 16))
        self.analyze_button.setToolTip("Mulai analisis matching")
        self.analyze_button.clicked.connect(self._start_analysis)
        self.analyze_button.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.analyze_button)

        self.export_button = QPushButton("Export Reports")
        self.export_button.setObjectName("SecondaryButton")
        self.export_button.setIcon(get_svg_icon("export", "#ffffff", 16))
        self.export_button.setToolTip("Export matched, missing, possible match, dan full report")
        self.export_button.clicked.connect(self._export_reports)
        self.export_button.setEnabled(False)
        self.export_button.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.export_button)

        progress_box = QFrame()
        progress_box.setObjectName("ProgressBox")

        progress_shadow = QGraphicsDropShadowEffect(progress_box)
        progress_shadow.setBlurRadius(10)
        progress_shadow.setColor(QColor(0, 0, 0, 60))
        progress_shadow.setOffset(0, 2)
        progress_box.setGraphicsEffect(progress_shadow)

        progress_layout = QVBoxLayout(progress_box)
        progress_layout.setContentsMargins(14, 14, 14, 14)
        progress_layout.setSpacing(10)

        self.progress_label = QLabel("Ready")
        self.progress_label.setObjectName("ProgressLabel")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addWidget(progress_box)

        layout.addStretch(1)

        footer = QLabel("Strict matching mode")
        footer.setObjectName("SidebarFooter")
        layout.addWidget(footer)
        return sidebar

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        workspace.setObjectName("Workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        title = QLabel("Library Reconciliation")
        title.setObjectName("Title")
        subtitle = QLabel("Audit your Spotify export against your local music files.")
        subtitle.setObjectName("Subtitle")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)

        self.completion_card = QFrame()
        self.completion_card.setObjectName("CompletionCard")

        completion_shadow = QGraphicsDropShadowEffect(self.completion_card)
        completion_shadow.setBlurRadius(15)
        completion_shadow.setColor(QColor(0, 0, 0, 80))
        completion_shadow.setOffset(0, 4)
        self.completion_card.setGraphicsEffect(completion_shadow)

        completion_layout = QHBoxLayout(self.completion_card)
        completion_layout.setContentsMargins(20, 14, 20, 14)
        completion_layout.setSpacing(16)

        completion_text_layout = QVBoxLayout()
        completion_text_layout.setSpacing(4)
        completion_text_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        completion_label = QLabel("Library Match Rate")
        completion_label.setObjectName("CompletionLabel")

        completion_desc = QLabel("Persentase lagu Spotify yang berhasil dicocokkan di library musik lokal Anda.")
        completion_desc.setObjectName("CompletionDesc")
        completion_desc.setWordWrap(True)
        completion_desc.setFixedWidth(200)

        completion_text_layout.addWidget(completion_label)
        completion_text_layout.addWidget(completion_desc)

        self.completion_ring = CircularProgressRing()

        completion_layout.addLayout(completion_text_layout, 1)
        completion_layout.addWidget(self.completion_ring)

        header_layout.addLayout(header_text, 1)
        header_layout.addWidget(self.completion_card)
        layout.addLayout(header_layout)

        # 5 statistics cards in a single row layout
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        cards = [
            ("Spotify Songs", "total_spotify", "Imported tracks"),
            ("Local Files", "total_local", "Available files"),
            ("Matched", "match", "Confident matches"),
            ("Possible", "possible_match", "Needs review"),
            ("Missing", "missing", "Not found locally"),
        ]
        for card_title, key, caption in cards:
            stats_layout.addWidget(self._create_stat_card(card_title, key, caption))
        layout.addLayout(stats_layout)

        control_bar = QFrame()
        control_bar.setObjectName("ControlBar")

        control_shadow = QGraphicsDropShadowEffect(control_bar)
        control_shadow.setBlurRadius(10)
        control_shadow.setColor(QColor(0, 0, 0, 50))
        control_shadow.setOffset(0, 2)
        control_bar.setGraphicsEffect(control_shadow)

        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(14, 12, 14, 12)
        control_layout.setSpacing(10)

        # Search icon prefix
        search_icon = QLabel()
        search_icon.setPixmap(get_svg_icon("search", "#b3b3b3", 16).pixmap(16, 16))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search song, artist, folder...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_filter)
        self.search_input.setObjectName("SearchInput")

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(self.status_filters.keys())
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        self.filter_combo.setToolTip("Filter status hasil matching")
        self.filter_combo.setCursor(Qt.PointingHandCursor)

        self.result_count_label = QLabel("0 results")
        self.result_count_label.setObjectName("ResultCount")

        control_layout.addWidget(search_icon)
        control_layout.addWidget(self.search_input, 1)
        control_layout.addWidget(QLabel("Status"))
        control_layout.addWidget(self.filter_combo)
        control_layout.addWidget(self.result_count_label)
        layout.addWidget(control_bar)

        self.content_stack = QStackedWidget()
        self.empty_state = self._build_empty_state()
        self.table = self._build_table()

        stack_shadow = QGraphicsDropShadowEffect(self.content_stack)
        stack_shadow.setBlurRadius(15)
        stack_shadow.setColor(QColor(0, 0, 0, 80))
        stack_shadow.setOffset(0, 4)
        self.content_stack.setGraphicsEffect(stack_shadow)

        self.content_stack.addWidget(self.empty_state)
        self.content_stack.addWidget(self.table)
        layout.addWidget(self.content_stack, 1)

        return workspace

    def _create_stat_card(self, title: str, key: str, caption: str) -> QFrame:
        card = QFrame()
        card.setObjectName(f"StatCard_{key}")
        card.setProperty("class", "StatCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)

        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        label = QLabel(title.upper())
        label.setObjectName("StatTitle")

        value = QLabel("0")
        value.setObjectName("StatValue")

        caption_label = QLabel(caption)
        caption_label.setObjectName("StatCaption")

        text_layout.addWidget(label)
        text_layout.addWidget(value)
        text_layout.addWidget(caption_label)

        icon_name = {
            "total_spotify": "spotify",
            "total_local": "folder",
            "match": "match",
            "possible_match": "possible",
            "missing": "missing",
        }.get(key, "folder")

        icon_color = {
            "total_spotify": "#1DB954",
            "total_local": "#0ea5e9",
            "match": "#1DB954",
            "possible_match": "#FFB636",
            "missing": "#E91429",
        }.get(key, "#ffffff")

        icon_bg_color = {
            "total_spotify": "rgba(29, 185, 84, 0.12)",
            "total_local": "rgba(14, 165, 233, 0.12)",
            "match": "rgba(29, 185, 84, 0.12)",
            "possible_match": "rgba(255, 182, 54, 0.12)",
            "missing": "rgba(233, 20, 41, 0.12)",
        }.get(key, "rgba(255, 255, 255, 0.12)")

        icon_badge = QFrame()
        icon_badge.setFixedSize(42, 42)
        icon_badge.setStyleSheet(f"""
            QFrame {{
                background-color: {icon_bg_color};
                border-radius: 21px;
                border: 1px solid {icon_color}25;
            }}
        """)
        
        badge_layout = QHBoxLayout(icon_badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel()
        icon_label.setPixmap(get_svg_icon(icon_name, icon_color, 20).pixmap(20, 20))
        icon_label.setAlignment(Qt.AlignCenter)
        badge_layout.addWidget(icon_label)

        card_layout.addLayout(text_layout, 1)
        card_layout.addWidget(icon_badge, 0, Qt.AlignVCenter | Qt.AlignRight)

        self.stat_labels[key] = value
        self.stat_captions[key] = caption_label
        return card

    def _build_empty_state(self) -> QFrame:
        empty = QFrame()
        empty.setObjectName("EmptyState")
        layout = QVBoxLayout(empty)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        icon = QLabel()
        icon.setPixmap(get_svg_icon("spotify", "#535353", 48).pixmap(48, 48))
        icon.setAlignment(Qt.AlignCenter)

        title = QLabel("No analysis yet")
        title.setObjectName("EmptyTitle")
        caption = QLabel("Awaiting local and Spotify CSV files.")
        caption.setObjectName("EmptyCaption")

        layout.addWidget(icon)
        layout.addWidget(title, alignment=Qt.AlignCenter)
        layout.addWidget(caption, alignment=Qt.AlignCenter)
        return empty

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, len(self.table_columns))
        table.setHorizontalHeaderLabels(self.table_columns)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(48)
        table.horizontalHeader().setMinimumSectionSize(110)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        return table

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#Root, QWidget#Workspace {
                background-color: #121212;
                color: #ffffff;
                font-family: "Segoe UI", Arial, sans-serif;
            }
            QFrame#Sidebar {
                background-color: #000000;
                border-right: 1px solid #242424;
            }
            QLabel#BrandTitle {
                color: #ffffff;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#BrandSub {
                color: #1DB954;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 2px;
            }
            QLabel#SidebarFooter {
                color: #7f7f7f;
                font-size: 11px;
            }
            QFrame#ProgressBox {
                background-color: #181818;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QLabel#ProgressLabel {
                color: #ffffff;
                font-weight: 700;
                font-size: 12px;
            }
            QProgressBar {
                background-color: #242424;
                border: none;
                border-radius: 4px;
                height: 6px;
                text-visible: false;
            }
            QProgressBar::chunk {
                background-color: #1DB954;
                border-radius: 4px;
            }
            QPushButton#PrimaryButton {
                background-color: #1DB954;
                color: #ffffff;
                border: none;
                border-radius: 20px;
                font-weight: bold;
                font-size: 14px;
                min-height: 40px;
            }
            QPushButton#PrimaryButton:hover {
                background-color: #1ed760;
            }
            QPushButton#PrimaryButton:pressed {
                background-color: #1aa34a;
            }
            QPushButton#PrimaryButton:disabled {
                background-color: #121212;
                color: #535353;
                border: 1px solid #282828;
            }
            QPushButton#SecondaryButton {
                background-color: #181818;
                color: #ffffff;
                border: 1px solid #535353;
                border-radius: 20px;
                font-weight: bold;
                font-size: 13px;
                min-height: 40px;
            }
            QPushButton#SecondaryButton:hover {
                border-color: #ffffff;
                background-color: #282828;
            }
            QPushButton#SecondaryButton:pressed {
                background-color: #121212;
            }
            QPushButton#SecondaryButton:disabled {
                border-color: #282828;
                color: #535353;
                background-color: #121212;
            }
            QLabel#Title {
                color: #ffffff;
                font-size: 26px;
                font-weight: 800;
            }
            QLabel#Subtitle {
                color: #b3b3b3;
                font-size: 13px;
            }
            QFrame#CompletionCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a1a, stop:1 #132516);
                border: 1px solid #243627;
                border-radius: 12px;
            }
            QLabel#CompletionLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }
            QLabel#CompletionDesc {
                color: #b3b3b3;
                font-size: 11px;
            }
            QFrame[class="StatCard"] {
                border-radius: 12px;
            }
            QFrame#StatCard_total_spotify {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a1a, stop:1 #132516);
                border: 1px solid #243627;
            }
            QFrame#StatCard_total_spotify:hover {
                border-color: #1DB954;
            }
            QFrame#StatCard_total_local {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a1a, stop:1 #101f30);
                border: 1px solid #1c2e42;
            }
            QFrame#StatCard_total_local:hover {
                border-color: #0ea5e9;
            }
            QFrame#StatCard_match {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a1a, stop:1 #132516);
                border: 1px solid #243627;
            }
            QFrame#StatCard_match:hover {
                border-color: #1DB954;
            }
            QFrame#StatCard_possible_match {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a1a, stop:1 #2a200b);
                border: 1px solid #3c301c;
            }
            QFrame#StatCard_possible_match:hover {
                border-color: #FFB636;
            }
            QFrame#StatCard_missing {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a1a, stop:1 #2d1315);
                border: 1px solid #421c1f;
            }
            QFrame#StatCard_missing:hover {
                border-color: #E91429;
            }
            QLabel#StatTitle {
                color: #b3b3b3;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 1px;
            }
            QLabel#StatValue {
                color: #ffffff;
                font-size: 28px;
                font-weight: 800;
            }
            QLabel#StatCaption {
                color: #7f7f7f;
                font-size: 11px;
                font-weight: 500;
            }
            QFrame#ControlBar {
                background-color: #181818;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QLineEdit#SearchInput {
                background-color: #282828;
                color: #ffffff;
                border: 1px solid transparent;
                border-radius: 18px;
                padding: 6px 12px 6px 12px;
                min-height: 24px;
            }
            QLineEdit#SearchInput:focus {
                border-color: #535353;
                background-color: #3e3e3e;
            }
            QComboBox {
                background-color: #282828;
                color: #ffffff;
                border: 1px solid transparent;
                border-radius: 18px;
                padding: 6px 20px 6px 12px;
                min-height: 24px;
            }
            QComboBox:focus {
                border-color: #535353;
            }
            QComboBox::drop-down {
                border: none;
            }
            QLabel#ResultCount {
                color: #b3b3b3;
                font-size: 12px;
            }
            QTableWidget {
                background-color: #181818;
                alternate-background-color: #1f1f1f;
                border: 1px solid #282828;
                border-radius: 8px;
                color: #ffffff;
                gridline-color: transparent;
            }
            QTableWidget::item {
                border-bottom: 1px solid #282828;
                padding: 10px;
            }
            QTableWidget::item:selected {
                background-color: #2a2a2a;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #181818;
                color: #b3b3b3;
                border: none;
                border-bottom: 2px solid #282828;
                padding: 10px 8px;
                font-weight: 800;
                font-size: 12px;
            }
            QScrollBar:vertical {
                background: #121212;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #535353;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #b3b3b3;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QFrame#EmptyState {
                background-color: #181818;
                border: 1px solid #282828;
                border-radius: 8px;
            }
            QLabel#EmptyTitle {
                color: #ffffff;
                font-size: 18px;
                font-weight: 800;
            }
            QLabel#EmptyCaption {
                color: #b3b3b3;
                font-size: 13px;
            }
            """
        )

    def _start_analysis(self) -> None:
        local_csv = self.local_drop_zone.file_path.strip()
        spotify_csv = self.spotify_drop_zone.file_path.strip()

        if not local_csv or not spotify_csv:
            QMessageBox.warning(self, "CSV belum lengkap", "Pilih CSV lokal dan CSV Spotify dulu.")
            return

        self._set_busy(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting analysis")
        self.content_stack.setCurrentWidget(self.empty_state)

        self.worker_thread = QThread(self)
        self.worker = AnalysisWorker(local_csv, spotify_csv)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._on_thread_finished)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.start()

    @Slot(int, str)
    def _on_progress(self, value: int, message: str) -> None:
        self.progress_bar.setValue(value)
        self.progress_label.setText(message)

    @Slot(object)
    def _on_analysis_finished(self, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        self.report_df = data.get("report", pd.DataFrame(columns=self.table_columns))
        stats = data.get("stats", self._empty_stats())
        self._update_stats(stats)
        self._apply_filter()
        self.export_button.setEnabled(not self.report_df.empty)
        self.progress_label.setText("Analysis complete")

    @Slot(str)
    def _on_analysis_error(self, message: str) -> None:
        self.progress_label.setText("Error")
        self.progress_bar.setValue(0)
        self.content_stack.setCurrentWidget(self.empty_state)
        QMessageBox.critical(self, "Analysis error", message)

    @Slot()
    def _on_thread_finished(self) -> None:
        self._set_busy(False)
        self.worker_thread = None
        self.worker = None

    def _set_busy(self, busy: bool) -> None:
        self.analyze_button.setEnabled(not busy)
        self.local_drop_zone.setEnabled(not busy)
        self.spotify_drop_zone.setEnabled(not busy)
        self.search_input.setEnabled(not busy)
        self.filter_combo.setEnabled(not busy)
        if busy:
            self.export_button.setEnabled(False)
        else:
            self.export_button.setEnabled(not self.report_df.empty)

    def _update_stats(self, stats: dict[str, object]) -> None:
        values = {
            "total_spotify": str(stats.get("total_spotify", 0)),
            "total_local": str(stats.get("total_local", 0)),
            "match": str(stats.get("match", 0)),
            "possible_match": str(stats.get("possible_match", 0)),
            "missing": str(stats.get("missing", 0)),
        }
        for key, value in values.items():
            if key in self.stat_labels:
                self.stat_labels[key].setText(value)

        completeness = float(stats.get("completeness", 0))
        self.completion_ring.setValue(completeness)

    def _apply_filter(self) -> None:
        if not hasattr(self, "table"):
            return

        filtered = self.report_df
        status = self.status_filters.get(self.filter_combo.currentText())
        query = self.search_input.text().strip().lower()

        if status:
            filtered = filtered[filtered["Status"] == status]

        if query:
            searchable_columns = ["Spotify Song", "Artist", "Local Match", "Folder"]
            mask = pd.Series(False, index=filtered.index)
            for column in searchable_columns:
                mask = mask | filtered[column].astype(str).str.lower().str.contains(query, regex=False)
            filtered = filtered[mask]

        self._populate_table(filtered)
        self.result_count_label.setText(f"{len(filtered)} results")
        self.content_stack.setCurrentWidget(self.table if not self.report_df.empty else self.empty_state)

    def _populate_table(self, data: pd.DataFrame) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for row_index, row in data.reset_index(drop=True).iterrows():
            self.table.insertRow(row_index)
            row_status = str(row.get("Status", ""))
            for column_index, column_name in enumerate(self.table_columns):
                value = row.get(column_name, "")

                if column_name == "Status":
                    badge = QLabel(row_status)
                    badge.setAlignment(Qt.AlignCenter)

                    if row_status == "MATCH":
                        badge.setStyleSheet("color: #1DB954; background-color: rgba(29, 185, 84, 0.15); border: 1px solid rgba(29, 185, 84, 0.3); border-radius: 12px; font-weight: bold; padding: 4px 10px; font-size: 11px;")
                    elif row_status == "POSSIBLE MATCH":
                        badge.setStyleSheet("color: #FFB636; background-color: rgba(255, 182, 54, 0.15); border: 1px solid rgba(255, 182, 54, 0.3); border-radius: 12px; font-weight: bold; padding: 4px 10px; font-size: 11px;")
                    elif row_status == "MISSING":
                        badge.setStyleSheet("color: #E91429; background-color: rgba(233, 20, 41, 0.15); border: 1px solid rgba(233, 20, 41, 0.3); border-radius: 12px; font-weight: bold; padding: 4px 10px; font-size: 11px;")
                    else:
                        badge.setStyleSheet("color: #B3B3B3; background-color: #282828; border-radius: 12px; font-weight: bold; padding: 4px 10px; font-size: 11px;")

                    container = QWidget()
                    container.setStyleSheet("background-color: transparent; border-bottom: 1px solid #282828;")

                    lay = QHBoxLayout(container)
                    lay.addWidget(badge)
                    lay.setContentsMargins(6, 4, 6, 4)
                    lay.setAlignment(Qt.AlignCenter)

                    self.table.setCellWidget(row_index, column_index, container)
                else:
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(str(value))
                    self._style_row_item(item, row_status)

                    if column_name == "Similarity Score":
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        colors = {
                            "MATCH": QColor("#1DB954"),
                            "POSSIBLE MATCH": QColor("#FFB636"),
                            "MISSING": QColor("#E91429"),
                        }
                        item.setForeground(colors.get(row_status, QColor("#ffffff")))

                    self.table.setItem(row_index, column_index, item)

        self.table.setSortingEnabled(True)

    def _style_row_item(self, item: QTableWidgetItem, status: str) -> None:
        item.setForeground(QColor("#ffffff"))

    def _export_reports(self) -> None:
        if self.report_df.empty:
            QMessageBox.information(self, "Belum ada data", "Jalankan analisis dulu sebelum export.")
            return

        DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Pilih folder output",
            str(DEFAULT_OUTPUT_DIR),
        )
        if not selected_dir:
            return

        try:
            files = export_reports(self.report_df, selected_dir)
        except Exception as exc:
            QMessageBox.critical(self, "Export error", str(exc))
            return

        file_list = "\n".join(str(path) for path in files.values())
        QMessageBox.information(self, "Export selesai", f"Laporan dibuat:\n{file_list}")

    @staticmethod
    def _empty_stats() -> dict[str, float | int]:
        return {
            "total_spotify": 0,
            "total_local": 0,
            "match": 0,
            "possible_match": 0,
            "missing": 0,
            "completeness": 0,
        }
