#!/usr/bin/env python3
"""PixelDesk — виджеты Material You (Google Pixel) для рабочего стола Windows.

Автор: Artur (artur0vi4) — https://github.com/artur0vi4

Запуск:  python main.py        (или через run.bat)
Сборка:  build_exe.bat          (получится dist\\PixelDesk.exe)
"""
from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtCore import QLockFile, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPen
from PySide6.QtWidgets import (QApplication, QMenu, QMessageBox,
                               QSystemTrayIcon)

from app import autostart, config, theme
from app.sysinfo import SystemMonitor
from app.widgets.base import PixelWidget
from app.widgets.calendar import CalendarWidget
from app.widgets.clock import ClockWidget
from app.widgets.glance import DateWidget
from app.widgets.sysmon import SystemWidget
from app.widgets.weather import WeatherWidget

WIDGET_ORDER = ("clock", "date", "calendar", "weather", "system")
WIDGET_CLASSES = {
    "clock": ClockWidget,
    "date": DateWidget,
    "calendar": CalendarWidget,
    "weather": WeatherWidget,
}
WIDGET_TITLES = {
    "clock": "Часы",
    "date": "Дата и день недели",
    "calendar": "Календарь",
    "weather": "Погода",
    "system": "Загрузка системы",
}


def _excepthook(tp, val, tb) -> None:
    msg = "".join(traceback.format_exception(tp, val, tb))
    config.log_error(msg)
    sys.stderr.write(msg)


def make_app_icon() -> QIcon:
    """Иконка: скруглённый квадрат с циферблатом (рисуется кодом)."""
    pm = QPixmap(256, 256)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(theme.C("primary")))
    p.drawRoundedRect(16, 16, 224, 224, 60, 60)
    p.setBrush(QColor(theme.C("surface")))
    p.drawEllipse(64, 64, 128, 128)
    pen = QPen(QColor(theme.C("on_primary")))
    pen.setWidth(13)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(128, 128, 128, 86)     # минутная
    p.drawLine(128, 128, 156, 140)    # часовая
    p.end()
    return QIcon(pm)


def app_stylesheet() -> str:
    c = theme.C
    return f"""
    QMenu {{
        background-color: {c("container")}; color: {c("on_surface")};
        border: 1px solid {c("outline")}; border-radius: 10px; padding: 6px;
    }}
    QMenu::item {{
        padding: 7px 26px 7px 12px; border-radius: 7px; margin: 1px 4px;
        background: transparent;
    }}
    QMenu::item:selected {{
        background-color: {c("secondary_container")};
        color: {c("on_secondary_container")};
    }}
    QMenu::separator {{ height: 1px; background: {c("outline")}; margin: 5px 10px; }}
    QMenu::indicator {{ width: 0px; }}
    QMenu::right-arrow {{ width: 0px; }}
    QDialog {{ background-color: {c("container")}; }}
    QDialog QLabel {{ color: {c("on_surface")}; background: transparent; }}
    QLineEdit {{
        background: {c("surface")}; color: {c("on_surface")};
        border: 1px solid {c("outline")}; border-radius: 8px; padding: 6px 8px;
        selection-background-color: {c("primary")};
    }}
    QPushButton {{
        background: {c("secondary_container")}; color: {c("on_secondary_container")};
        border: none; border-radius: 8px; padding: 7px 16px;
    }}
    QPushButton:hover {{ background: {c("primary")}; color: {c("on_primary")}; }}
    """


class WidgetManager:
    """Создаёт/прячет виджеты, хранит общий монитор системы."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.monitor = SystemMonitor()
        self.widgets: dict[str, PixelWidget] = {}

    # ------------------------------------------------------------------ #
    def _ensure_position(self, key: str) -> None:
        wc = self.cfg["widgets"][key]
        if wc.get("x") is not None and wc.get("y") is not None:
            return
        scr = QApplication.primaryScreen().availableGeometry()
        idx = WIDGET_ORDER.index(key)
        wc["x"] = max(scr.left() + 8, scr.right() - wc["w"] - 56 - idx * 26)
        wc["y"] = max(scr.top() + 8, scr.top() + 34 + idx * 34)

    def create_widget(self, key: str) -> PixelWidget:
        if key in self.widgets:
            return self.widgets[key]
        if key == "system":
            w: PixelWidget = SystemWidget(self.cfg, self.monitor)
        else:
            w = WIDGET_CLASSES[key](self.cfg)
        w.disabled.connect(self._on_disabled)
        self.widgets[key] = w
        if not self.cfg.get("hidden_all"):
            w.show()
        return w

    def _on_disabled(self, key: str) -> None:
        self.widgets.pop(key, None)
        self.cfg["widgets"][key]["enabled"] = False
        config.save(self.cfg)

    def build_all(self) -> None:
        for k in WIDGET_ORDER:
            self._ensure_position(k)
        for k in WIDGET_ORDER:
            if self.cfg["widgets"][k].get("enabled", True):
                self.create_widget(k)
        config.save(self.cfg)
        self.monitor.start()

    def set_all_hidden(self, hidden: bool) -> None:
        self.cfg["hidden_all"] = bool(hidden)
        for w in self.widgets.values():
            if hidden:
                w.hide()
            else:
                w.show()
        config.save(self.cfg)

    def enable_widget(self, key: str, on: bool) -> None:
        self.cfg["widgets"][key]["enabled"] = bool(on)
        if on:
            self._ensure_position(key)
            self.create_widget(key)
        else:
            w = self.widgets.pop(key, None)
            if w is not None:
                w.blockSignals(True)
                w.close()
                w.blockSignals(False)
        config.save(self.cfg)

    def apply_theme(self) -> None:
        t = self.cfg["theme"]
        theme.apply(t.get("palette"), t.get("dark", True))
        QApplication.instance().setStyleSheet(app_stylesheet())
        for w in self.widgets.values():
            w.update()

    def shutdown(self) -> None:
        for w in self.widgets.values():
            try:
                w.persist()
            except Exception:
                pass
        self.monitor.stop()
        config.save(self.cfg)


# ---------------------------------------------------------------------- #
#  Трей
# ---------------------------------------------------------------------- #
def build_tray(app: QApplication, manager: WidgetManager) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(make_app_icon())
    menu = QMenu()

    def set_palette(pid: str) -> None:
        manager.cfg["theme"]["palette"] = pid
        config.save(manager.cfg)
        manager.apply_theme()

    def set_mode(dark: bool) -> None:
        manager.cfg["theme"]["dark"] = bool(dark)
        config.save(manager.cfg)
        manager.apply_theme()

    def toggle_autostart() -> None:
        on = not autostart.is_enabled()
        ok = autostart.set_enabled(on)
        if ok:
            manager.cfg["autostart"] = on
            config.save(manager.cfg)
        else:
            QMessageBox.information(None, config.APP_NAME,
                                    "Автозапуск доступен только в Windows.")

    def refresh_weather() -> None:
        w = manager.widgets.get("weather")
        if w is not None:
            w.refresh()

    def show_about() -> None:
        QMessageBox.about(
            None, f"О {config.APP_NAME}",
            f"<h3>{config.APP_NAME} {config.APP_VERSION}</h3>"
            "<p>Виджеты рабочего стола в стиле Material You (Google Pixel) "
            "для Windows: часы, дата, календарь, погода и монитор системы.</p>"
            f"<p>Автор: <b>{config.APP_AUTHOR}</b><br>"
            f"GitHub: {config.APP_URL}</p>"
            "<p>Лицензия MIT &middot; 2026</p>")

    def rebuild() -> None:
        menu.clear()
        hidden = bool(manager.cfg.get("hidden_all"))
        a_vis = menu.addAction(
            ("✓  " if not hidden else "") +
            ("Скрыть все виджеты" if not hidden else "Показать все виджеты"))
        a_vis.triggered.connect(lambda: manager.set_all_hidden(not hidden))

        m_w = menu.addMenu("Виджеты")
        for k in WIDGET_ORDER:
            on = k in manager.widgets
            act = m_w.addAction(("✓  " if on else "     ") + WIDGET_TITLES[k])
            act.triggered.connect(
                lambda checked, key=k: manager.enable_widget(key, key not in manager.widgets))

        menu.addSeparator()
        m_t = menu.addMenu("Тема")
        for pid, pal in theme.PALETTES.items():
            on = manager.cfg["theme"].get("palette") == pid
            act = m_t.addAction(("✓  " if on else "     ") + pal["name"])
            act.triggered.connect(lambda checked, p=pid: set_palette(p))
        m_t.addSeparator()
        for dark, label in ((True, "Тёмная"), (False, "Светлая")):
            on = bool(manager.cfg["theme"].get("dark", True)) == dark
            act = m_t.addAction(("✓  " if on else "     ") + label)
            act.triggered.connect(lambda checked, d=dark: set_mode(d))

        a_auto = menu.addAction(
            ("✓  " if autostart.is_enabled() else "     ") + "Автозапуск с Windows")
        a_auto.triggered.connect(toggle_autostart)

        a_wx = menu.addAction("Обновить погоду")
        a_wx.triggered.connect(refresh_weather)

        a_about = menu.addAction("О программе")
        a_about.triggered.connect(show_about)

        menu.addSeparator()
        a_quit = menu.addAction("Выход")
        a_quit.triggered.connect(app.quit)

    menu.aboutToShow.connect(rebuild)
    tray.setContextMenu(menu)
    tray.setToolTip(f"{config.APP_NAME} {config.APP_VERSION}")
    tray.activated.connect(
        lambda reason: manager.set_all_hidden(not manager.cfg.get("hidden_all"))
        if reason == QSystemTrayIcon.Trigger else None)
    tray.show()
    return tray


# ---------------------------------------------------------------------- #
#  Точка входа
# ---------------------------------------------------------------------- #
def build_app(argv=None):
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.APP_VERSION)
    app.setApplicationDisplayName(config.APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    sys.excepthook = _excepthook

    cfg = config.load()
    t = cfg.get("theme", {})
    theme.apply(t.get("palette"), t.get("dark", True))
    app.setStyleSheet(app_stylesheet())

    os.makedirs(config.CONFIG_DIR, exist_ok=True)
    lock = QLockFile(os.path.join(config.CONFIG_DIR, "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.warning(None, config.APP_NAME,
                            f"{config.APP_NAME} уже запущен (иконка в трее).")
        return app, None

    manager = WidgetManager(cfg)
    manager.build_all()
    try:
        tray = build_tray(app, manager)
    except Exception:
        tray = None
        config.log_error("Трей недоступен\n" + traceback.format_exc())

    def on_quit() -> None:
        manager.shutdown()

    app.aboutToQuit.connect(on_quit)
    return app, manager


def main() -> None:
    app, manager = build_app()
    if manager is None:
        return
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
