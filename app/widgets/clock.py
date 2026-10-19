"""Виджет «Часы» — крупные цифры 24-часового формата, как на Pixel."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter

from .base import PixelWidget
from .. import theme


class ClockWidget(PixelWidget):
    TITLE = "Часы"

    def __init__(self, app_cfg: dict):
        super().__init__(app_cfg, "clock")
        self.setMinimumSize(170, 96)
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def paint_content(self, p: QPainter) -> None:
        now = datetime.now()
        text = f"{now.hour:02d}:{now.minute:02d}"
        area = QRectF(self.rect()).adjusted(
            self.pad() * 0.9, self.pad() * 0.6, -self.pad() * 0.9, -self.pad() * 0.6)
        # реальное отношение высоты строки к кеглю у активного шрифта
        # (Segoe UI/Roboto ~1.32-1.33, DejaVu 1.17 — различие заметное)
        ratio = QFontMetrics(self.f(100.0, QFont.Black)).height() / 100.0
        size = area.height() * 0.90 / max(1.0, ratio)
        font = self.f(size, QFont.Black)
        # страховка: бюджет фиксированный (карточка) — цикл сходится
        while size > 10 and (
                QFontMetrics(font).horizontalAdvance(text) > area.width()
                or QFontMetrics(font).height() > area.height()):
            size *= 0.95
            font = self.f(size, QFont.Black)
        self._text(p, area, Qt.AlignLeft | Qt.AlignVCenter, text,
                   theme.C("on_surface"), font)
