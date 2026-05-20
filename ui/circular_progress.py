from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QFont, QPaintEvent, QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QSizePolicy


class CircularProgressRing(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._animated_value = 0.0

        # Colors compatible with Spotify Dark theme
        self.track_color = QColor("#242424")
        self.progress_color = QColor("#1DB954")
        self.text_color = QColor("#ffffff")
        self.subtext_color = QColor("#b3b3b3")
        
        self.track_width = 8
        self.progress_width = 8

        self.animation = QVariantAnimation(self)
        self.animation.setDuration(1000)
        self.animation.valueChanged.connect(self._on_animation_value_changed)

        self.setMinimumSize(130, 130)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def _on_animation_value_changed(self, val: float) -> None:
        self._animated_value = val
        self.update()

    def setValue(self, val: float) -> None:
        self.animation.stop()
        self.animation.setStartValue(self._animated_value)
        self.animation.setEndValue(float(val))
        self.animation.start()
        self._value = float(val)

    def value(self) -> float:
        return self._value

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        margin = max(self.track_width, self.progress_width) + 4
        size = min(width, height) - margin

        rect = QRectF(
            (width - size) / 2,
            (height - size) / 2,
            size,
            size
        )

        # Draw background track
        track_pen = QPen(self.track_color)
        track_pen.setWidth(self.track_width)
        track_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(track_pen)
        painter.drawEllipse(rect)

        # Draw active progress path (clockwise from 12 o'clock)
        start_angle = 90 * 16
        span_angle = int(-self._animated_value / 100.0 * 360.0 * 16)

        if span_angle != 0:
            progress_pen = QPen(self.progress_color)
            progress_pen.setWidth(self.progress_width)
            progress_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(progress_pen)
            painter.drawArc(rect, start_angle, span_angle)

        # Draw percentage text in center
        painter.setPen(self.text_color)
        font_pct = QFont("Segoe UI", 16, QFont.Bold)
        painter.setFont(font_pct)
        
        pct_text = f"{self._animated_value:.1f}%"
        # We want to draw percentage text slightly offset upward to accommodate "Kelengkapan" or "Complete" subtitle
        text_rect = self.rect()
        text_rect.setBottom(text_rect.bottom() - 10)
        painter.drawText(text_rect, Qt.AlignCenter, pct_text)

        # Draw small status subtitle
        painter.setPen(self.subtext_color)
        font_sub = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font_sub)
        sub_rect = self.rect()
        sub_rect.setTop(sub_rect.top() + 42)
        painter.drawText(sub_rect, Qt.AlignCenter, "MATCHED")
