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

GAP = 0.12          # зазор между строками в долях кегля строки 1
LINE2_RATIO = 0.50  # кегль приветствия относительно строки 1


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

        # Кегль считается ТОЧНО по измеренным метрикам активного шрифта.
        # ВАЖНО: метрики можно сравнивать только с фиксированным бюджетом —
        # размером карточки. Прежняя проверка «height() > кегль * 1.24»
        # сравнивала метрику с величиной, растущей вместе со шрифтом:
        # у Segoe UI и Roboto высота строки 1.32–1.33 кегля, условие
        # не выполнялось никогда, и текст схлопывался до минимума
        # независимо от растягивания и масштаба.
        ref = 100.0
        fm_ref = QFontMetrics(self.f(ref, QFont.Bold))
        fm_ref2 = QFontMetrics(self.f(ref, QFont.Normal))
        px_w = fm_ref.horizontalAdvance(line1) / ref          # ширина на 1px
        r1 = fm_ref.height() / ref                            # высота на 1px
        r2 = fm_ref2.height() / ref

        by_width = area.width() * 0.995 / max(px_w, 0.01)
        by_height = area.height() / (r1 + GAP + LINE2_RATIO * r2)
        h1 = max(10.0, min(by_width, by_height))

        # Страховка от округления метрик: бюджет фиксированный (карточка),
        # поэтому цикл всегда сходится на любом шрифте.
        f1 = self.f(h1, QFont.Bold)
        fm1 = QFontMetrics(f1)
        while h1 > 9 and (
                fm1.horizontalAdvance(line1) > area.width()
                or fm1.height() + GAP * h1
                + QFontMetrics(self.f(h1 * LINE2_RATIO, QFont.Normal)).height()
                > area.height()):
            h1 *= 0.96
            f1 = self.f(h1, QFont.Bold)
            fm1 = QFontMetrics(f1)

        self._text(p, QRectF(area.left(), area.top(), area.width(), fm1.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, line1,
                   theme.C("on_surface"), f1)

        f2 = self.f(max(8.0, h1 * LINE2_RATIO), QFont.Normal)
        y2 = area.top() + fm1.height() + GAP * h1
        self._text(p, QRectF(area.left(), y2, area.width(),
                             max(10.0, area.bottom() - y2 + 1)),
                   Qt.AlignLeft | Qt.AlignTop, greeting(now.hour),
                   theme.C("on_surface_variant"), f2)
