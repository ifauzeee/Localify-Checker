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
        "Possible Match": "POSSIBLE MATCH",
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
        self.resize(1180, 760)

        self.report_df = pd.DataFrame(columns=self.table_columns)
        self.worker_thread: QThread | None = None
        self.worker: AnalysisWorker | None = None
        self.stat_labels: dict[str, QLabel] = {}

        self._build_ui()
        self._apply_style()
        self._update_stats(
            {
                "total_spotify": 0,
                "total_local": 0,
                "match": 0,
                "possible_match": 0,
                "missing": 0,
                "completeness": 0,
            }
        )

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(22, 22, 22, 22)
        root_layout.setSpacing(16)

        title = QLabel("Localify Checker")
        title.setObjectName("Title")
        subtitle = QLabel("Check whether every Spotify track already exists in your local music folder CSV.")
        subtitle.setObjectName("Subtitle")

        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        input_panel = QFrame()
        input_panel.setObjectName("Panel")
        input_layout = QGridLayout(input_panel)
        input_layout.setContentsMargins(18, 18, 18, 18)
        input_layout.setHorizontalSpacing(12)
        input_layout.setVerticalSpacing(12)

        self.local_path_input = QLineEdit()
        self.local_path_input.setPlaceholderText("CSV musik lokal: folder, filename")
        self.local_path_input.setClearButtonEnabled(True)

        self.spotify_path_input = QLineEdit()
        self.spotify_path_input.setPlaceholderText("CSV Spotify: track_name / Track name, artist, album")
        self.spotify_path_input.setClearButtonEnabled(True)

        self.local_button = QPushButton("Pilih Lokal")
        self.local_button.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.local_button.setToolTip("Import CSV musik lokal")
        self.local_button.clicked.connect(self._select_local_csv)

        self.spotify_button = QPushButton("Pilih Spotify")
        self.spotify_button.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.spotify_button.setToolTip("Import CSV Spotify")
        self.spotify_button.clicked.connect(self._select_spotify_csv)

        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.analyze_button.setToolTip("Mulai analisis matching")
        self.analyze_button.clicked.connect(self._start_analysis)
        self.analyze_button.setObjectName("PrimaryButton")

        self.export_button = QPushButton("Export")
        self.export_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.export_button.setToolTip("Export matched, missing, possible match, dan full report")
        self.export_button.clicked.connect(self._export_reports)
        self.export_button.setEnabled(False)

        input_layout.addWidget(QLabel("Local CSV"), 0, 0)
        input_layout.addWidget(self.local_path_input, 0, 1)
        input_layout.addWidget(self.local_button, 0, 2)
        input_layout.addWidget(QLabel("Spotify CSV"), 1, 0)
        input_layout.addWidget(self.spotify_path_input, 1, 1)
        input_layout.addWidget(self.spotify_button, 1, 2)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.analyze_button)
        action_layout.addWidget(self.export_button)
        action_layout.addStretch(1)
        input_layout.addLayout(action_layout, 2, 1, 1, 2)

        input_layout.setColumnStretch(1, 1)
        root_layout.addWidget(input_panel)

        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_label = QLabel("Ready")
        self.progress_label.setObjectName("Muted")
        progress_layout.addWidget(self.progress_bar, 1)
        progress_layout.addWidget(self.progress_label)
        root_layout.addLayout(progress_layout)

        stats_layout = QGridLayout()
        stats_layout.setHorizontalSpacing(12)
        stats_layout.setVerticalSpacing(12)
        cards = [
            ("Total Spotify", "total_spotify"),
            ("Total Local", "total_local"),
            ("Match", "match"),
            ("Possible", "possible_match"),
            ("Missing", "missing"),
            ("Complete", "completeness"),
        ]
        for column, (title, key) in enumerate(cards):
            stats_layout.addWidget(self._create_stat_card(title, key), 0, column)
        root_layout.addLayout(stats_layout)

        table_header_layout = QHBoxLayout()
        result_title = QLabel("Hasil Matching")
        result_title.setObjectName("SectionTitle")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(self.status_filters.keys())
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        self.filter_combo.setToolTip("Filter status hasil matching")
        table_header_layout.addWidget(result_title)
        table_header_layout.addStretch(1)
        table_header_layout.addWidget(QLabel("Filter"))
        table_header_layout.addWidget(self.filter_combo)
        root_layout.addLayout(table_header_layout)

        self.table = QTableWidget(0, len(self.table_columns))
        self.table.setHorizontalHeaderLabels(self.table_columns)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        root_layout.addWidget(self.table, 1)

        self.setCentralWidget(root)

    def _create_stat_card(self, title: str, key: str) -> QFrame:
        card = QFrame()
        card.setObjectName("StatCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)

        label = QLabel(title)
        label.setObjectName("StatTitle")
        value = QLabel("0")
        value.setObjectName("StatValue")

        layout.addWidget(label)
        layout.addWidget(value)
        self.stat_labels[key] = value
        return card

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6f7f9;
                color: #18202a;
                font-family: Segoe UI, Arial, sans-serif;
                font-size: 13px;
            }
            QLabel#Title {
                font-size: 28px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#Subtitle, QLabel#Muted {
                color: #64748b;
            }
            QLabel#SectionTitle {
                font-size: 17px;
                font-weight: 650;
                color: #111827;
            }
            QFrame#Panel, QFrame#StatCard {
                background: #ffffff;
                border: 1px solid #dde3ea;
                border-radius: 8px;
            }
            QLabel#StatTitle {
                color: #64748b;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#StatValue {
                color: #111827;
                font-size: 24px;
                font-weight: 700;
            }
            QLineEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 10px;
                min-height: 22px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #2563eb;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
                min-height: 24px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #f1f5f9;
            }
            QPushButton:disabled {
                color: #94a3b8;
                background: #eef2f7;
            }
            QPushButton#PrimaryButton {
                color: #ffffff;
                background: #2563eb;
                border: 1px solid #2563eb;
            }
            QPushButton#PrimaryButton:hover {
                background: #1d4ed8;
            }
            QProgressBar {
                background: #e2e8f0;
                border: none;
                border-radius: 5px;
                min-height: 10px;
            }
            QProgressBar::chunk {
                background: #22c55e;
                border-radius: 5px;
            }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #dde3ea;
                border-radius: 8px;
                gridline-color: #e2e8f0;
                selection-background-color: #dbeafe;
                selection-color: #0f172a;
            }
            QHeaderView::section {
                background: #eef2f7;
                color: #334155;
                border: none;
                border-bottom: 1px solid #cbd5e1;
                padding: 8px;
                font-weight: 700;
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
        stats = data.get("stats", {})
        self._update_stats(stats)
        self._apply_filter()
        self.export_button.setEnabled(not self.report_df.empty)
        self.progress_label.setText("Done")

    @Slot(str)
    def _on_analysis_error(self, message: str) -> None:
        self.progress_label.setText("Error")
        self.progress_bar.setValue(0)
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
            "completeness": f"{float(stats.get('completeness', 0)):.2f}%",
        }
        for key, value in values.items():
            if key in self.stat_labels:
                self.stat_labels[key].setText(value)

    def _apply_filter(self) -> None:
        selected = self.filter_combo.currentText()
        status = self.status_filters.get(selected)
        if status:
            filtered = self.report_df[self.report_df["Status"] == status]
        else:
            filtered = self.report_df
        self._populate_table(filtered)

    def _populate_table(self, data: pd.DataFrame) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for row_index, row in data.reset_index(drop=True).iterrows():
            self.table.insertRow(row_index)
            for column_index, column_name in enumerate(self.table_columns):
                value = row.get(column_name, "")
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))

                if column_name == "Similarity Score":
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif column_name == "Status":
                    item.setTextAlignment(Qt.AlignCenter)
                    self._style_status_item(item, str(value))

                self.table.setItem(row_index, column_index, item)

        self.table.setSortingEnabled(True)

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
