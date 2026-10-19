"""Базовый класс виджета: карточка Material You без рамки.

Возможности:
  - полупрозрачный фон со скруглением (уровень прозрачности настраивается);
  - перетаскивание мышью за любую точку карточки;
  - изменение размера за правый-нижний угол;
  - масштабирование: Ctrl + колесо мыши или пункты меню;
  - контекстное меню: «поверх всех окон», прозрачность, масштаб, скрытие;
  - запоминание позиции/размера/настроек в config.json.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QApplication, QFrame, QMenu

from .. import config, theme

FONT_FAMILY = "Segoe UI" if os.name == "nt" else None

SCALE_MIN, SCALE_MAX = 0.55, 2.4
OPACITY_PRESETS = (100, 90, 80, 70, 60, 50)
SCALE_PRESETS = (70, 85, 100, 120, 140, 170, 200)


class PixelWidget(QFrame):
    """Общий предок всех виджетов."""

    TITLE = "Виджет"
    HAS_REFRESH = False
    disabled = Signal(str)   # ключ виджета — после «Скрыть виджет»

    def __init__(self, app_cfg: dict, key: str):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint)
        self.key = key
        self.app_cfg = app_cfg
        self.cfg = app_cfg["widgets"][key]
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setWindowTitle(self.TITLE)
        self.setMinimumSize(150, 80)
        self._apply_window_flags()
        self.resize(int(self.cfg["w"]), int(self.cfg["h"]))
        self.move(int(self.cfg["x"]), int(self.cfg["y"]))
        self._drag_offset: QPoint | None = None
        self._resize_mode = False
        self._moved = False

    # ------------------------------------------------------------------ #
    #  Геометрия и масштаб
    # ------------------------------------------------------------------ #
    @property
    def s(self) -> float:
        """Масштаб шрифтов и отступов."""
        return float(self.cfg.get("scale", 1.0))

    def pad(self) -> float:
        return 24.0 * self.s

    def radius(self) -> float:
        return 26.0 * self.s

    def f(self, px: float, weight: QFont.Weight = QFont.DemiBold) -> QFont:
        """Шрифт заданного размера. Вызывающий код УЖЕ умножает на
        масштаб (N * s) — второго умножения здесь быть не должно,
        иначе шрифты растут квадратично (s²) и вылезают за карточку."""
        font = QFont(FONT_FAMILY) if FONT_FAMILY else QFont()
        font.setPixelSize(max(7, int(round(px))))
        font.setWeight(weight)
        return font

    def _apply_window_flags(self) -> None:
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(self.cfg.get("on_top", True)))
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)

    def apply_zoom(self, factor: float) -> None:
        """Пропорционально меняет размер окна и шрифтов."""
        new_s = max(SCALE_MIN, min(SCALE_MAX, self.s * factor))
        factor = new_s / self.s
        if abs(factor - 1.0) < 1e-3:
            return
        self.cfg["scale"] = round(new_s, 3)
        self.resize(max(self.minimumWidth(), int(self.width() * factor)),
                    max(self.minimumHeight(), int(self.height() * factor)))
        self.update()
        self.persist()

    def persist(self) -> None:
        self.cfg["x"] = self.x()
        self.cfg["y"] = self.y()
        self.cfg["w"] = self.width()
        self.cfg["h"] = self.height()
        config.save(self.app_cfg)

    def set_on_top(self, on: bool) -> None:
        self.cfg["on_top"] = bool(on)
        self._apply_window_flags()
        if self.isVisible():
            self.show()
        self.persist()
        self.update()

    def hide_me(self) -> None:
        self.cfg["enabled"] = False
        self.persist()
        self.disabled.emit(self.key)
        self.close()

    # ------------------------------------------------------------------ #
    #  Мышь: drag, resize, курсоры
    # ------------------------------------------------------------------ #
    def _grip_rect(self) -> QRect:
        g = int(26 * self.s) + 12
        return QRect(self.width() - g, self.height() - g, g, g)

    def hover_cursor(self, pos: QPoint):
        """Подкласс может вернуть курсор для интерактивных зон."""
        return None

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            pos = e.position().toPoint()
            if self._grip_rect().contains(pos):
                self._resize_mode = True
                self._drag_offset = None
            else:
                self._resize_mode = False
                self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
                if not self.cfg.get("on_top", True):
                    self.raise_()
            self._moved = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        pos = e.position().toPoint()
        buttons = e.buttons()
        if self._resize_mode and (buttons & Qt.LeftButton):
            nw = max(self.minimumWidth(), pos.x() + int(14 * self.s))
            nh = max(self.minimumHeight(), pos.y() + int(14 * self.s))
            self.resize(nw, nh)
            self._moved = True
        elif self._drag_offset is not None and (buttons & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            self._moved = True
        else:
            if self._grip_rect().contains(pos):
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                cur = self.hover_cursor(pos)
                self.setCursor(cur if cur is not None else Qt.ArrowCursor)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if self._moved:
            self.persist()
        self._drag_offset = None
        self._resize_mode = False
        self._moved = False
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e) -> None:
        if e.modifiers() & Qt.ControlModifier:
            step = 1.07 if e.angleDelta().y() > 0 else 1.0 / 1.07
            self.apply_zoom(step)
            e.accept()
        else:
            super().wheelEvent(e)

    def closeEvent(self, e) -> None:
        self.persist()
        super().closeEvent(e)

    # ------------------------------------------------------------------ #
    #  Контекстное меню
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ck(on: bool, text: str) -> str:
        return ("✓  " if on else "     ") + text

    def refresh(self) -> None:  # переопределяется в подклассах
        pass

    def extra_menu(self, menu: QMenu) -> None:  # переопределяется в подклассах
        pass

    def handle_menu_data(self, data) -> bool:
        """Подклассы обрабатывают свои пункты меню. True — пункт обработан."""
        return False

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        a_top = menu.addAction(self._ck(bool(self.cfg.get("on_top", True)), "Поверх всех окон"))
        a_top.setData("top")

        m_op = menu.addMenu("Прозрачность")
        for pct in OPACITY_PRESETS:
            on = abs(float(self.cfg.get("opacity", 0.96)) * 100 - pct) < 3
            act = m_op.addAction(self._ck(on, f"{pct}%"))
            act.setData(("op", pct))

        m_sc = menu.addMenu("Масштаб")
        for pct in SCALE_PRESETS:
            on = abs(self.s * 100 - pct) < 4
            act = m_sc.addAction(self._ck(on, f"{pct}%"))
            act.setData(("sc", pct))

        if self.HAS_REFRESH:
            a_ref = menu.addAction("Обновить")
            a_ref.setData("refresh")

        self.extra_menu(menu)
        menu.addSeparator()
        a_hide = menu.addAction("Скрыть виджет")
        a_hide.setData("hide")

        chosen = menu.exec(e.globalPos())
        if chosen is None:
            return
        data = chosen.data()
        if data == "top":
            self.set_on_top(not self.cfg.get("on_top", True))
        elif data == "refresh":
            self.refresh()
        elif data == "hide":
            self.hide_me()
        elif isinstance(data, tuple):
            kind, val = data
            if kind == "op":
                self.cfg["opacity"] = val / 100.0
                self.update()
                self.persist()
            elif kind == "sc":
                self.apply_zoom((val / 100.0) / self.s)
        else:
            self.handle_menu_data(data)

    # ------------------------------------------------------------------ #
    #  Отрисовка карточки
    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        bg = QColor(theme.C("surface"))
        bg.setAlphaF(max(0.15, min(1.0, float(self.cfg.get("opacity", 0.96)))))
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        p.drawRoundedRect(rect, self.radius(), self.radius())
        self.paint_content(p)

    def paint_content(self, p: QPainter) -> None:
        """Переопределяется в подклассах — рисует содержимое карточки."""
        pass

    # вспомогательная функция отрисовки текста
    def _text(self, p: QPainter, rect: QRectF, flags, text: str,
              color: str, font: QFont) -> None:
        p.setFont(font)
        p.setPen(QColor(color))
        p.drawText(rect, int(flags), text)

    def _elide(self, text: str, font: QFont, width: float) -> str:
        return QFontMetrics(font).elidedText(text, Qt.ElideRight, int(width))
