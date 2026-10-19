"""Виджет «Календарь» — месяц с навигацией, подсветкой сегодняшнего дня."""
from __future__ import annotations

import calendar as calendar_mod
from datetime import date

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen

from .base import PixelWidget
from .. import theme

WD_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
MONTHS_NOM = ("Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
              "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь")


def _add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


class CalendarWidget(PixelWidget):
    TITLE = "Календарь"

    def __init__(self, app_cfg: dict):
        super().__init__(app_cfg, "calendar")
        self.setMinimumSize(250, 320)
        self._month = date.today().replace(day=1)
        self._prev_rect = QRect()
        self._next_rect = QRect()

    # ------------------------------------------------------------------ #
    def _arrow_zone(self) -> float:
        return 30.0 * self.s

    def _chevron(self, p: QPainter, rect: QRect, right: bool) -> None:
        pen = QPen(QColor(theme.C("on_surface_variant")))
        pen.setWidthF(max(1.6, 2.1 * self.s))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        cx, cy = rect.center().x(), rect.center().y()
        r = rect.width() * 0.20
        if right:
            pts = [QPointF(cx - r, cy - r * 1.6), QPointF(cx + r, cy),
                   QPointF(cx - r, cy + r * 1.6)]
        else:
            pts = [QPointF(cx + r, cy - r * 1.6), QPointF(cx - r, cy),
                   QPointF(cx + r, cy + r * 1.6)]
        p.drawPolyline(pts)

    def paint_content(self, p: QPainter) -> None:
        area = QRectF(self.rect()).adjusted(
            self.pad(), self.pad(), -self.pad(), -self.pad())
        zone = self._arrow_zone()
        title_h = 30.0 * self.s

        # --- заголовок «Октябрь 2026» + стрелки ---
        title = f"{MONTHS_NOM[self._month.month - 1]} {self._month.year}"
        title_w = area.width() - 2.4 * zone
        f_title = self.f(title_h * 0.96, QFont.Bold)
        while f_title.pixelSize() > 9 and (
                QFontMetrics(f_title).horizontalAdvance(title) > title_w
                or QFontMetrics(f_title).height() > title_h):
            f_title = QFont(f_title)
            f_title.setPixelSize(f_title.pixelSize() - 1)
        self._text(p, QRectF(area.left(), area.top(), title_w, title_h),
                   Qt.AlignLeft | Qt.AlignVCenter, title,
                   theme.C("on_surface"), f_title)

        cy = area.top() + title_h / 2
        self._prev_rect = QRect(int(area.right() - 2 * zone - 6 * self.s),
                                int(cy - zone / 2), int(zone), int(zone))
        self._next_rect = QRect(int(area.right() - zone),
                                int(cy - zone / 2), int(zone), int(zone))
        self._chevron(p, self._prev_rect, right=False)
        self._chevron(p, self._next_rect, right=True)

        # --- шапка дней недели ---
        wy = area.top() + title_h + 6 * self.s
        header_h = 20.0 * self.s
        cell_w = area.width() / 7.0
        f_head = self.f(11 * self.s, QFont.DemiBold)
        for i, wd in enumerate(WD_SHORT):
            color = theme.C("error") if i >= 5 else theme.C("on_surface_variant")
            self._text(p, QRectF(area.left() + i * cell_w, wy, cell_w, header_h),
                       Qt.AlignCenter, wd, color, f_head)

        # --- сетка дней ---
        gy = wy + header_h + 4 * self.s
        rows = 6
        row_h = (area.height() - (gy - area.top())) / rows
        first_off = self._month.weekday()          # Пн = 0
        days_in = calendar_mod.monthrange(self._month.year, self._month.month)[1]
        prev_m = _add_months(self._month, -1)
        days_prev = calendar_mod.monthrange(prev_m.year, prev_m.month)[1]
        today = date.today()

        f_day_px = max(9.0, min(13.0 * self.s, row_h * 0.44))
        f_day = self.f(f_day_px, QFont.Normal)
        f_day_b = self.f(f_day_px, QFont.Bold)
        dim = QColor(theme.C("outline"))
        dim.setAlpha(120)

        for row in range(rows):
            for col in range(7):
                idx = row * 7 + col
                dnum = idx - first_off + 1
                cell = QRectF(area.left() + col * cell_w,
                              gy + row * row_h, cell_w, row_h)
                if 1 <= dnum <= days_in:
                    d = date(self._month.year, self._month.month, dnum)
                    if d == today:
                        r = min(cell.width(), cell.height()) * 0.38
                        c = cell.center()
                        p.setBrush(QColor(theme.C("primary")))
                        p.setPen(Qt.NoPen)
                        p.drawEllipse(QPointF(c.x(), c.y()), r, r)
                        p.setFont(f_day_b)
                        p.setPen(QColor(theme.C("on_primary")))
                    else:
                        p.setBrush(Qt.NoBrush)
                        p.setFont(f_day)
                        if col >= 5:
                            p.setPen(QColor(theme.C("error")))
                        else:
                            p.setPen(QColor(theme.C("on_surface")))
                    p.drawText(cell, int(Qt.AlignCenter), str(dnum))
                else:
                    n = days_prev + dnum if dnum < 1 else dnum - days_in
                    p.setFont(f_day)
                    p.setPen(dim)
                    p.drawText(cell, int(Qt.AlignCenter), str(n))

    # ------------------------------------------------------------------ #
    def mousePressEvent(self, e) -> None:
        pos = e.position().toPoint()
        if e.button() == Qt.LeftButton:
            if self._next_rect.contains(pos):
                self._month = _add_months(self._month, 1)
                self.update()
                return
            if self._prev_rect.contains(pos):
                self._month = _add_months(self._month, -1)
                self.update()
                return
        super().mousePressEvent(e)

    def hover_cursor(self, pos):
        if self._next_rect.contains(pos) or self._prev_rect.contains(pos):
            return Qt.PointingHandCursor
        return None

    def extra_menu(self, menu) -> None:
        act = menu.addAction("К текущему месяцу")
        act.setData("today")

    def handle_menu_data(self, data) -> bool:
        if data == "today":
            self._month = date.today().replace(day=1)
            self.update()
            return True
        return False
