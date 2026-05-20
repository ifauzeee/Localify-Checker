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
    QGridLayout,
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
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.csv_loader import load_local_csv, load_spotify_csv
from core.exporter import export_reports
from core.matcher import match_tracks, summarize_results


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
        self._update_path_badges()
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

        brand = QLabel("Localify")
        brand.setObjectName("Brand")
        brand_caption = QLabel("Checker")
        brand_caption.setObjectName("BrandCaption")

        layout.addWidget(brand)
        layout.addWidget(brand_caption)

        self.local_path_input = self._create_path_input("Local CSV")
        self.spotify_path_input = self._create_path_input("Spotify CSV")

        layout.addWidget(self._create_file_picker(
            "Local Library",
            self.local_path_input,
            "Pilih Lokal",
            self._select_local_csv,
        ))
        layout.addWidget(self._create_file_picker(
            "Spotify Export",
            self.spotify_path_input,
            "Pilih Spotify",
            self._select_spotify_csv,
        ))

        self.local_badge = QLabel("Local CSV: kosong")
        self.local_badge.setObjectName("PathBadge")
        self.spotify_badge = QLabel("Spotify CSV: kosong")
        self.spotify_badge.setObjectName("PathBadge")
        layout.addWidget(self.local_badge)
        layout.addWidget(self.spotify_badge)

        layout.addSpacerItem(QSpacerItem(1, 8, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setObjectName("PrimaryButton")
        self.analyze_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.analyze_button.setToolTip("Mulai analisis matching")
        self.analyze_button.clicked.connect(self._start_analysis)
        layout.addWidget(self.analyze_button)

        self.export_button = QPushButton("Export Reports")
        self.export_button.setObjectName("SecondaryButton")
        self.export_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.export_button.setToolTip("Export matched, missing, possible match, dan full report")
        self.export_button.clicked.connect(self._export_reports)
        self.export_button.setEnabled(False)
        layout.addWidget(self.export_button)

        progress_box = QFrame()
        progress_box.setObjectName("ProgressBox")
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
        completion_layout = QVBoxLayout(self.completion_card)
        completion_layout.setContentsMargins(18, 14, 18, 14)
        completion_layout.setSpacing(6)
        completion_label = QLabel("Completion")
        completion_label.setObjectName("CompletionLabel")
        self.completion_value = QLabel("0.00%")
        self.completion_value.setObjectName("CompletionValue")
        self.completion_bar = QProgressBar()
        self.completion_bar.setRange(0, 100)
        self.completion_bar.setValue(0)
        self.completion_bar.setTextVisible(False)
        completion_layout.addWidget(completion_label)
        completion_layout.addWidget(self.completion_value)
        completion_layout.addWidget(self.completion_bar)

        header_layout.addLayout(header_text, 1)
        header_layout.addWidget(self.completion_card)
        layout.addLayout(header_layout)

        stats_layout = QGridLayout()
        stats_layout.setHorizontalSpacing(12)
        stats_layout.setVerticalSpacing(12)
        cards = [
            ("Spotify Songs", "total_spotify", "Imported tracks"),
            ("Local Files", "total_local", "Available files"),
            ("Matched", "match", "Confident matches"),
            ("Possible", "possible_match", "Needs review"),
            ("Missing", "missing", "Not found locally"),
        ]
        for index, (title, key, caption) in enumerate(cards):
            stats_layout.addWidget(self._create_stat_card(title, key, caption), index // 3, index % 3)
        layout.addLayout(stats_layout)

        control_bar = QFrame()
        control_bar.setObjectName("ControlBar")
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(14, 12, 14, 12)
        control_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search song, artist, folder")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_filter)
        self.search_input.setObjectName("SearchInput")

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(self.status_filters.keys())
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        self.filter_combo.setToolTip("Filter status hasil matching")

        self.result_count_label = QLabel("0 results")
        self.result_count_label.setObjectName("ResultCount")

        control_layout.addWidget(self.search_input, 1)
        control_layout.addWidget(QLabel("Status"))
        control_layout.addWidget(self.filter_combo)
        control_layout.addWidget(self.result_count_label)
        layout.addWidget(control_bar)

        self.content_stack = QStackedWidget()
        self.empty_state = self._build_empty_state()
        self.table = self._build_table()
        self.content_stack.addWidget(self.empty_state)
        self.content_stack.addWidget(self.table)
        layout.addWidget(self.content_stack, 1)

        return workspace

    def _create_path_input(self, placeholder: str) -> QLineEdit:
        path_input = QLineEdit()
        path_input.setPlaceholderText(placeholder)
        path_input.setReadOnly(True)
        path_input.setClearButtonEnabled(False)
        path_input.textChanged.connect(self._update_path_badges)
        return path_input

    def _create_file_picker(
        self,
        title: str,
        path_input: QLineEdit,
        button_text: str,
        callback: object,
    ) -> QFrame:
        box = QFrame()
        box.setObjectName("InputGroup")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        label = QLabel(title)
        label.setObjectName("InputTitle")
        button = QPushButton(button_text)
        button.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        button.clicked.connect(callback)  # type: ignore[arg-type]

        if button_text == "Pilih Lokal":
            self.local_button = button
        else:
            self.spotify_button = button

        layout.addWidget(label)
        layout.addWidget(path_input)
        layout.addWidget(button)
        return box

    def _create_stat_card(self, title: str, key: str, caption: str) -> QFrame:
        card = QFrame()
        card.setObjectName(f"StatCard_{key}")
        card.setProperty("class", "StatCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        label = QLabel(title)
        label.setObjectName("StatTitle")
        value = QLabel("0")
        value.setObjectName("StatValue")
        caption_label = QLabel(caption)
        caption_label.setObjectName("StatCaption")

        layout.addWidget(label)
        layout.addWidget(value)
        layout.addWidget(caption_label)
        self.stat_labels[key] = value
        self.stat_captions[key] = caption_label
        return card

    def _build_empty_state(self) -> QFrame:
        empty = QFrame()
        empty.setObjectName("EmptyState")
        layout = QVBoxLayout(empty)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        title = QLabel("No analysis yet")
        title.setObjectName("EmptyTitle")
        caption = QLabel("Awaiting local and Spotify CSV files.")
        caption.setObjectName("EmptyCaption")
        layout.addWidget(title, alignment=Qt.AlignCenter)
        layout.addWidget(caption, alignment=Qt.AlignCenter)
        return empty

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, len(self.table_columns))
        table.setHorizontalHeaderLabels(self.table_columns)
        table.setAlternatingRowColors(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(42)
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
                background: #f4f6f8;
                color: #17202a;
                font-family: Segoe UI, Arial, sans-serif;
                font-size: 13px;
            }
            QFrame#Sidebar {
                background: #101820;
                border: none;
            }
            QLabel#Brand {
                color: #ffffff;
                font-size: 30px;
                font-weight: 800;
            }
            QLabel#BrandCaption {
                color: #7dd3fc;
                font-size: 14px;
                font-weight: 700;
                margin-bottom: 8px;
            }
            QLabel#SidebarFooter, QLabel#PathBadge {
                color: #9fb2c4;
                font-size: 12px;
            }
            QLabel#PathBadge {
                background: #172431;
                border: 1px solid #243647;
                border-radius: 8px;
                padding: 8px 10px;
            }
            QFrame#InputGroup, QFrame#ProgressBox {
                background: #152230;
                border: 1px solid #243647;
                border-radius: 8px;
            }
            QLabel#InputTitle, QLabel#ProgressLabel {
                color: #d9e5f0;
                font-weight: 700;
            }
            QLabel#Title {
                color: #111827;
                font-size: 28px;
                font-weight: 800;
            }
            QLabel#Subtitle {
                color: #64748b;
                font-size: 13px;
            }
            QFrame#CompletionCard, QFrame#ControlBar, QFrame#EmptyState {
                background: #ffffff;
                border: 1px solid #dce3ea;
                border-radius: 8px;
            }
            QFrame[class="StatCard"] {
                background: #ffffff;
                border: 1px solid #dce3ea;
                border-radius: 8px;
            }
            QFrame#StatCard_match {
                border-top: 3px solid #16a34a;
            }
            QFrame#StatCard_possible_match {
                border-top: 3px solid #d97706;
            }
            QFrame#StatCard_missing {
                border-top: 3px solid #dc2626;
            }
            QLabel#StatTitle, QLabel#CompletionLabel {
                color: #64748b;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#StatValue {
                color: #111827;
                font-size: 26px;
                font-weight: 800;
            }
            QLabel#StatCaption, QLabel#ResultCount {
                color: #64748b;
                font-size: 12px;
            }
            QLabel#CompletionValue {
                color: #111827;
                font-size: 28px;
                font-weight: 800;
            }
            QLabel#EmptyTitle {
                color: #111827;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#EmptyCaption {
                color: #64748b;
            }
            QLineEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 10px;
                min-height: 24px;
                color: #17202a;
            }
            QFrame#Sidebar QLineEdit {
                background: #0e1721;
                color: #d9e5f0;
                border: 1px solid #243647;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0ea5e9;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 9px 12px;
                min-height: 26px;
                font-weight: 700;
                color: #17202a;
            }
            QPushButton:hover {
                background: #f1f5f9;
            }
            QPushButton:disabled {
                color: #8a9aab;
                background: #e9eef4;
            }
            QFrame#Sidebar QPushButton {
                background: #1c2d3c;
                border: 1px solid #2c455c;
                color: #e8f1f8;
            }
            QFrame#Sidebar QPushButton:hover {
                background: #24394d;
            }
            QPushButton#PrimaryButton {
                background: #0ea5e9;
                border: 1px solid #0ea5e9;
                color: #ffffff;
                min-height: 34px;
            }
            QPushButton#PrimaryButton:hover {
                background: #0284c7;
            }
            QPushButton#SecondaryButton {
                background: #172431;
                border: 1px solid #355168;
                color: #e8f1f8;
                min-height: 32px;
            }
            QProgressBar {
                background: #e2e8f0;
                border: none;
                border-radius: 5px;
                min-height: 10px;
            }
            QFrame#Sidebar QProgressBar {
                background: #0e1721;
            }
            QProgressBar::chunk {
                background: #16a34a;
                border-radius: 5px;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #dce3ea;
                border-radius: 8px;
                selection-background-color: #dbeafe;
                selection-color: #0f172a;
                color: #17202a;
            }
            QTableWidget::item {
                border-bottom: 1px solid #edf2f7;
                padding: 6px;
            }
            QHeaderView::section {
                background: #f8fafc;
                color: #475569;
                border: none;
                border-bottom: 1px solid #dce3ea;
                padding: 10px 8px;
                font-weight: 800;
            }
            """
        )

    def _select_local_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih CSV musik lokal",
            str(Path.home()),
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            self.local_path_input.setText(path)

    def _select_spotify_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih CSV Spotify",
            str(Path.home()),
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            self.spotify_path_input.setText(path)

    def _start_analysis(self) -> None:
        local_csv = self.local_path_input.text().strip()
        spotify_csv = self.spotify_path_input.text().strip()

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
        self.local_button.setEnabled(not busy)
        self.spotify_button.setEnabled(not busy)
        self.local_path_input.setEnabled(not busy)
        self.spotify_path_input.setEnabled(not busy)
        self.search_input.setEnabled(not busy)
        self.filter_combo.setEnabled(not busy)
        if busy:
            self.export_button.setEnabled(False)
        else:
            self.export_button.setEnabled(not self.report_df.empty)

    def _update_path_badges(self) -> None:
        if not hasattr(self, "local_badge"):
            return

        local_name = Path(self.local_path_input.text()).name if self.local_path_input.text() else "kosong"
        spotify_name = Path(self.spotify_path_input.text()).name if self.spotify_path_input.text() else "kosong"
        self.local_badge.setText(f"Local CSV: {local_name}")
        self.spotify_badge.setText(f"Spotify CSV: {spotify_name}")

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
        self.completion_value.setText(f"{completeness:.2f}%")
        self.completion_bar.setValue(max(0, min(100, int(round(completeness)))))

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
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self._style_row_item(item, row_status)

                if column_name == "Similarity Score":
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif column_name == "Status":
                    item.setTextAlignment(Qt.AlignCenter)
                    self._style_status_item(item, row_status)

                self.table.setItem(row_index, column_index, item)

        self.table.setSortingEnabled(True)

    def _style_row_item(self, item: QTableWidgetItem, status: str) -> None:
        backgrounds = {
            "MATCH": QColor("#fbfffd"),
            "POSSIBLE MATCH": QColor("#fffdf5"),
            "MISSING": QColor("#fffafa"),
        }
        item.setBackground(backgrounds.get(status, QColor("#ffffff")))

    def _style_status_item(self, item: QTableWidgetItem, status: str) -> None:
        colors = {
            "MATCH": (QColor("#166534"), QColor("#dcfce7")),
            "POSSIBLE MATCH": (QColor("#92400e"), QColor("#fef3c7")),
            "MISSING": (QColor("#991b1b"), QColor("#fee2e2")),
        }
        foreground, background = colors.get(status, (QColor("#334155"), QColor("#f1f5f9")))
        item.setForeground(foreground)
        item.setBackground(background)

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

