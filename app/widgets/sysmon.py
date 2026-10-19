"""Виджет «Загрузка системы»: CPU, RAM, GPU, сеть — с живыми графиками."""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from .base import PixelWidget
from .. import theme

HIST = 60  # точек на графике (секунд)


class SystemWidget(PixelWidget):
    TITLE = "Загрузка системы"
    disabled = Signal(str)

    def __init__(self, app_cfg: dict, monitor):
        super().__init__(app_cfg, "system")
        self.setMinimumSize(280, 250)
        self.monitor = monitor
        self.cpu = deque([0.0] * HIST, maxlen=HIST)
        self.ram = deque([0.0] * HIST, maxlen=HIST)
        self.gpu_hist = deque([0.0] * HIST, maxlen=HIST)
        self.down = deque([0.0] * HIST, maxlen=HIST)
        self.up = deque([0.0] * HIST, maxlen=HIST)
        self._last = {"cpu": 0.0, "ram": 0.0, "down": 0.0, "up": 0.0}
        self.gpu_val: dict | None = None
        self._gpu_missing = False
        monitor.tick.connect(self._on_tick)
        monitor.gpu.connect(self._on_gpu)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    # ------------------------------------------------------------------ #
    def _on_tick(self, d: dict) -> None:
        self._last = d
        self.cpu.append(d["cpu"])
        self.ram.append(d["ram"])
        self.down.append(d["down"])
        self.up.append(d["up"])

    def _on_gpu(self, g) -> None:
        if g is None:
            self._gpu_missing = True
            self.gpu_hist.append(0.0)
        else:
            self._gpu_missing = False
            self.gpu_val = g
            self.gpu_hist.append(float(g.get("util") or 0.0))

    # ------------------------------------------------------------------ #
    @staticmethod
    def _fmt_speed(v: float) -> str:
        return f"{v:.1f}" if v < 10 else f"{v:.0f}"

    def _spark(self, p: QPainter, rect: QRectF, hist, color: str,
               vmax: float = 100.0, fill: bool = True) -> None:
        if rect.width() < 4 or rect.height() < 3:
            return
        n = len(hist)
        pts = []
        for i, v in enumerate(hist):
            x = rect.left() + rect.width() * (i / (n - 1))
            y = rect.bottom() - rect.height() * (max(0.0, min(float(v), vmax)) / vmax)
            pts.append(QPointF(x, y))
        path = QPainterPath(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        if fill:
            fpath = QPainterPath(path)
            fpath.lineTo(rect.right(), rect.bottom())
            fpath.lineTo(rect.left(), rect.bottom())
            fpath.closeSubpath()
            fc = QColor(color)
            fc.setAlpha(42)
            p.fillPath(fpath, fc)
        pen = QPen(QColor(color))
        pen.setWidthF(max(1.2, 1.7 * self.s))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

    def paint_content(self, p: QPainter) -> None:
        area = QRectF(self.rect()).adjusted(
            self.pad() * 0.9, self.pad() * 0.75, -self.pad() * 0.9, -self.pad() * 0.85)
        s = self.s
        outline = QColor(theme.C("outline"))
        outline.setAlpha(60)

        down = self._last["down"]
        up = self._last["up"]

        hw = self.gpu_val or {}
        cpu_txt = f"{self._last['cpu']:.0f}%"
        ct = hw.get("cpu_temp")
        if ct is not None:
            cpu_txt += f" · {ct:.0f}°C"

        gpu_segs = []
        if hw.get("util") is not None:
            gpu_segs.append(f"{hw['util']:.0f}%")
        if hw.get("temp") is not None:
            gpu_segs.append(f"{hw['temp']:.0f}°C")
        gpu_txt = " · ".join(gpu_segs) if gpu_segs else "—"

        net_vmax = 5.0
        for v in list(self.down) + list(self.up):
            if v > net_vmax:
                net_vmax = v
        net_vmax *= 1.25

        rows = [
            ("Процессор", cpu_txt, self.cpu,
             theme.C("primary"), 100.0, False),
            ("Память", f"{self._last['ram']:.0f}%", self.ram,
             theme.C("tertiary"), 100.0, False),
            ("Видеокарта", gpu_txt, self.gpu_hist,
             theme.C("secondary"), 100.0, False),
            ("Сеть ↓↑", f"{self._fmt_speed(down)} · {self._fmt_speed(up)} Мбит/с",
             self.down, theme.C("primary"), net_vmax, True),
        ]

        n = len(rows)
        row_h = area.height() / n
        f_lab = self.f(12 * s, QFont.Normal)
        f_val = self.f(14 * s, QFont.DemiBold)
        for i, (lab, val, hist, color, vmax, dual) in enumerate(rows):
            ry = area.top() + i * row_h
            self._text(p, QRectF(area.left(), ry, area.width() * 0.5, 17 * s),
                       Qt.AlignLeft | Qt.AlignVCenter, lab,
                       theme.C("on_surface_variant"), f_lab)
            self._text(p, QRectF(area.left(), ry, area.width() - 2, 17 * s),
                       Qt.AlignRight | Qt.AlignVCenter, val,
                       theme.C("on_surface"), f_val)
            grect = QRectF(area.left(), ry + 20 * s, area.width(),
                           max(6.0, row_h - 26 * s))
            if dual:
                self._spark(p, grect, self.up, theme.C("tertiary"),
                            vmax=vmax, fill=False)
                self._spark(p, grect, hist, color, vmax=vmax, fill=True)
            else:
                self._spark(p, grect, hist, color, vmax=vmax, fill=True)
            if i < n - 1:
                p.setPen(outline)
                y = ry + row_h
                p.drawLine(int(area.left()), int(y), int(area.right()), int(y))
