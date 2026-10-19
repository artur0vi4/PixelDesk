"""Виджет «Дата» — день недели, число и месяц + приветствие (At a Glance)."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics, QPainter

from .base import PixelWidget
from .. import theme

WEEKDAYS = ("Понедельник", "Вторник", "Среда", "Четверг",
            "Пятница", "Суббота", "Воскресенье")
MONTHS_GEN = ("января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря")


def greeting(hour: int) -> str:
    if 5 <= hour < 12:
        return "Доброе утро"
    if 12 <= hour < 18:
        return "Добрый день"
    if 18 <= hour < 23:
        return "Добрый вечер"
    return "Доброй ночи"


class DateWidget(PixelWidget):
    TITLE = "Дата"

    def __init__(self, app_cfg: dict):
        super().__init__(app_cfg, "date")
        self.setMinimumSize(230, 92)
        self._timer = QTimer(self)
        self._timer.setInterval(20000)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def paint_content(self, p: QPainter) -> None:
        now = datetime.now()
        area = QRectF(self.rect()).adjusted(
            self.pad(), self.pad(), -self.pad(), -self.pad())

        line1 = f"{WEEKDAYS[now.weekday()]}, {now.day} {MONTHS_GEN[now.month - 1]}"

        # Шрифт занимает максимум места в карточке и растёт при любом
        # увеличении: и при растягивании мышью, и при смене масштаба.
        # Ограничители — высота карточки (до 50 %) и ширина строки.
        h1 = max(10.0, area.height() * 0.50)
        f1 = self.f(h1, QFont.Bold)
        while h1 > 9 and (
                QFontMetrics(f1).horizontalAdvance(line1) > area.width()
                or QFontMetrics(f1).height() > h1 * 1.24):
            h1 *= 0.94
            f1 = self.f(h1, QFont.Bold)

        self._text(p, QRectF(area.left(), area.top(), area.width(), h1 * 1.24),
                   Qt.AlignLeft | Qt.AlignVCenter, line1,
                   theme.C("on_surface"), f1)

        y2 = area.top() + h1 * 1.30
        f2 = self.f(max(8.0, h1 * 0.50), QFont.Normal)
        self._text(p, QRectF(area.left(), y2, area.width(),
                             max(10.0, area.bottom() - y2 + 1)),
                   Qt.AlignLeft | Qt.AlignVCenter, greeting(now.hour),
                   theme.C("on_surface_variant"), f2)
