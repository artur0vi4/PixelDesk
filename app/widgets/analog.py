"""Виджет «Аналоговые часы» — круглый циферблат в стиле Material You.

Круглая карточка (вместо прямоугольной), классические цифры 1–12,
тонкая минутная шкала, часовая/минутная/секундная стрелки. Всё рисуется
от меньшей стороны окна — растягивается и масштабируется вместе с
виджетом.
"""
from __future__ import annotations

import math
from datetime import datetime

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen

from .base import PixelWidget
from .. import theme


class AnalogClockWidget(PixelWidget):
    TITLE = "w_clock_analog"

    def __init__(self, app_cfg: dict):
        super().__init__(app_cfg, "clock_analog")
        self.setMinimumSize(120, 120)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:
        """Круглая карточка вместо прямоугольной + циферблат."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        side = min(self.width(), self.height())
        r = side / 2.0 - 1.0
        c = QPointF(self.width() / 2.0, self.height() / 2.0)

        bg = QColor(theme.C("surface"))
        bg.setAlphaF(max(0.15, min(1.0, float(self.cfg.get("opacity", 0.96)))))
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawEllipse(c, r, r)

        now = datetime.now()
        self._face(p, c, r)
        self._hands(p, c, r, now)

    def _face(self, p: QPainter, c: QPointF, r: float) -> None:
        """Минутная шкала (60 меток) + классические цифры 1–12.
        Четверные (12-3-6-9) — крупнее, ярче и полужирные."""
        # --- минутная шкала по краю ------------------------------------- #
        for i in range(60):
            a = math.radians(i * 6.0)
            quarter = (i % 15 == 0)
            sa, ca = math.sin(a), math.cos(a)
            r1 = 0.875 * r if quarter else 0.888 * r
            r2 = 0.935 * r if quarter else 0.928 * r
            col = QColor(theme.C("on_surface" if quarter else "on_surface_variant"))
            col.setAlphaF(0.60 if quarter else 0.38)
            pen = QPen(col)
            pen.setWidthF(max(1.0, (0.014 if quarter else 0.008) * r))
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(c.x() + r1 * sa, c.y() - r1 * ca),
                       QPointF(c.x() + r2 * sa, c.y() - r2 * ca))

        # --- цифры ------------------------------------------------------- #
        for i in range(12):
            n = 12 if i == 0 else i
            quarter = (i % 3 == 0)
            a = math.radians(i * 30.0)
            pos = QPointF(c.x() + 0.72 * r * math.sin(a),
                          c.y() - 0.72 * r * math.cos(a))
            font = self.f((0.165 if quarter else 0.148) * r,
                          QFont.Weight.DemiBold if quarter
                          else QFont.Weight.Medium)
            p.setFont(font)
            p.setPen(QColor(theme.C("on_surface" if quarter
                                    else "on_surface_variant")))
            # центр глифа точно в точке pos (учёт реальных метрик цифры)
            br = QFontMetrics(font).tightBoundingRect(str(n))
            p.drawText(QPointF(pos.x() - br.center().x(),
                               pos.y() - br.center().y()), str(n))

    def _hands(self, p: QPainter, c: QPointF, r: float, now: datetime) -> None:
        sec = now.second
        minute = now.minute + sec / 60.0
        hour = (now.hour % 12) + minute / 60.0

        def hand(angle_deg: float, length: float, width: float,
                 color: str, tail: float = 0.0) -> None:
            a = math.radians(angle_deg)
            pen = QPen(QColor(color))
            pen.setWidthF(max(2.0, width * r))
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(c.x() + tail * r * math.sin(a),
                               c.y() - tail * r * math.cos(a)),
                       QPointF(c.x() + length * r * math.sin(a),
                               c.y() - length * r * math.cos(a)))

        hand(hour * 30.0, 0.44, 0.052, theme.C("on_surface"))
        hand(minute * 6.0, 0.65, 0.040, theme.C("on_surface"))
        hand(sec * 6.0, 0.90, 0.016, theme.C("primary"), tail=0.17)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.C("primary")))
        p.drawEllipse(c, 0.042 * r, 0.042 * r)
        p.setBrush(QColor(theme.C("on_primary")))
        p.drawEllipse(c, 0.016 * r, 0.016 * r)
