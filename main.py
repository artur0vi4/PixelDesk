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

from PySide6.QtCore import QLockFile, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QPen
from PySide6.QtWidgets import (QApplication, QMenu, QMessageBox,
                               QSystemTrayIcon)

from app import autostart, config, i18n, theme
from app.sysinfo import SystemMonitor
from app.widgets import base as widgets_base
from app.widgets.analog import AnalogClockWidget
from app.widgets.base import PixelWidget
from app.widgets.calendar import CalendarWidget
from app.widgets.clock import ClockWidget
from app.widgets.glance import DateWidget
from app.widgets.sysmon import SystemWidget
from app.widgets.weather import WeatherWidget

WIDGET_ORDER = ("clock", "clock_analog", "date", "calendar", "weather", "system")
WIDGET_CLASSES = {
    "clock": ClockWidget,
    "clock_analog": AnalogClockWidget,
    "date": DateWidget,
    "calendar": CalendarWidget,
    "weather": WeatherWidget,
}
WIDGET_TITLES = {
    "clock": "w_clock",
    "clock_analog": "w_clock_analog",
    "date": "w_date",
    "calendar": "w_calendar",
    "weather": "w_weather",
    "system": "w_system",
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


def load_app_fonts() -> str | None:
    """Регистрирует встроенный Google Roboto (Apache 2.0) из
    app/resources/fonts. Работает и из исходников, и внутри
    PyInstaller-onefile (ресурсы распаковываются в _MEIPASS).
    Возвращает имя семейства, если оно доступно."""
    try:
        from PySide6.QtGui import QFontDatabase
        base_dir = getattr(sys, "_MEIPASS", None) \
            or os.path.dirname(os.path.abspath(__file__))
        fdir = os.path.join(base_dir, "app", "resources", "fonts")
        if os.path.isdir(fdir):
            for fn in sorted(os.listdir(fdir)):
                if fn.lower().endswith(".ttf"):
                    QFontDatabase.addApplicationFont(os.path.join(fdir, fn))
        if "Roboto" in QFontDatabase.families():
            return "Roboto"
    except Exception:
        config.log_error("Не удалось загрузить встроенные шрифты\n"
                         + traceback.format_exc())
    return None


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
        # Ссылки на трей обязаны жить всё время работы приложения,
        # иначе Python удалит эти объекты и иконка исчезнет.
        self.tray = None
        self.tray_timer = None

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
#  Старые копии программы (мешают запуску новой версии)
# ---------------------------------------------------------------------- #
STALE_EXE_NAMES = ("pixeldesk.exe", "pixelwidgets.exe")
STALE_PY_MARKERS = ("pixeldesk", "pixelwidgets")


def find_stale_instances() -> list:
    """Живые процессы ДРУГИХ копий PixelDesk / PixelWidgets.

    Свой PID и PID родителя исключаем: у onefile-EXE родитель —
    это загрузчик PyInstaller, он не держит блокировку.
    """
    try:
        import psutil
    except Exception:
        return []
    me, my_parent = os.getpid(), os.getppid()
    found = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = p.info
            if info["pid"] in (me, my_parent):
                continue
            name = (info["name"] or "").lower()
            cmd = " ".join(info["cmdline"] or []).lower()
            is_our_exe = name in STALE_EXE_NAMES
            is_our_py = (name.startswith(("python", "pyw", "py."))
                         and "main.py" in cmd
                         and any(m in cmd for m in STALE_PY_MARKERS))
            if is_our_exe or is_our_py:
                found.append(p)
        except Exception:
            continue
    return found


def terminate_stale(procs: list) -> None:
    """Аккуратно завершает найденные копии: terminate, затем kill."""
    import psutil
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    _, alive = psutil.wait_procs(procs, timeout=3)
    for p in alive:
        try:
            p.kill()
        except Exception:
            pass


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
                                    i18n.t("autostart_win_only"))

    def refresh_weather() -> None:
        w = manager.widgets.get("weather")
        if w is not None:
            w.refresh()

    def show_about() -> None:
        QMessageBox.about(
            None, i18n.t("about_title", name=config.APP_NAME),
            i18n.t("about_body", name=config.APP_NAME,
                   ver=config.APP_VERSION, author=config.APP_AUTHOR,
                   url=config.APP_URL))

    def set_language(val: str) -> None:
        manager.cfg.setdefault("ui", {})["lang"] = val
        config.save(manager.cfg)
        i18n.init(val)
        # заголовки окон + перерисовка (даты, месяцы, подписи)
        for w in manager.widgets.values():
            w.setWindowTitle(i18n.t(w.TITLE))
            w.update()
        wx = manager.widgets.get("weather")
        if wx is not None:
            wx.refresh()   # подписи дней «запечены» в данных

    def rebuild() -> None:
        menu.clear()
        hidden = bool(manager.cfg.get("hidden_all"))
        a_vis = menu.addAction(
            ("✓  " if not hidden else "") +
            i18n.t("show_all" if hidden else "hide_all"))
        a_vis.triggered.connect(lambda: manager.set_all_hidden(not hidden))

        m_w = menu.addMenu(i18n.t("m_widgets"))
        for k in WIDGET_ORDER:
            on = k in manager.widgets
            act = m_w.addAction(("✓  " if on else "     ")
                                + i18n.t(WIDGET_TITLES[k]))
            act.triggered.connect(
                lambda checked, key=k: manager.enable_widget(key, key not in manager.widgets))

        menu.addSeparator()
        m_t = menu.addMenu(i18n.t("m_theme"))
        for pid, pal in theme.PALETTES.items():
            on = manager.cfg["theme"].get("palette") == pid
            act = m_t.addAction(("✓  " if on else "     ")
                                + i18n.t(i18n.PAL_KEYS.get(pid, pid)))
            act.triggered.connect(lambda checked, p=pid: set_palette(p))
        m_t.addSeparator()
        for dark, label in ((True, "th_dark"), (False, "th_light")):
            on = bool(manager.cfg["theme"].get("dark", True)) == dark
            act = m_t.addAction(("✓  " if on else "     ") + i18n.t(label))
            act.triggered.connect(lambda checked, d=dark: set_mode(d))

        a_auto = menu.addAction(
            ("✓  " if autostart.is_enabled() else "     ") + i18n.t("autostart"))
        a_auto.triggered.connect(toggle_autostart)

        a_wx = menu.addAction(i18n.t("refresh_wx"))
        a_wx.triggered.connect(refresh_weather)

        # --- язык интерфейса (RU/EN, авто по системе) ---
        m_l = menu.addMenu("Язык / Language")
        setting = (manager.cfg.get("ui") or {}).get("lang", "auto")
        for val, name in (("auto", i18n.t("lang_auto")),
                          ("ru", "Русский"), ("en", "English")):
            act = m_l.addAction(("✓  " if setting == val else "     ") + name)
            act.triggered.connect(lambda checked, v=val: set_language(v))

        a_about = menu.addAction(i18n.t("about"))
        a_about.triggered.connect(show_about)

        menu.addSeparator()
        a_quit = menu.addAction(i18n.t("quit"))
        a_quit.triggered.connect(app.quit)

    menu.aboutToShow.connect(rebuild)
    tray.setContextMenu(menu)
    tray.menu_ref = menu   # держим ссылку на меню, иначе Python его удалит
    tray.setToolTip(f"{config.APP_NAME} {config.APP_VERSION}")
    tray.activated.connect(
        lambda reason: manager.set_all_hidden(not manager.cfg.get("hidden_all"))
        if reason == QSystemTrayIcon.Trigger else None)
    tray.show()
    return tray


def setup_tray(app: QApplication, manager: WidgetManager) -> None:
    """Создаёт иконку трея и СОХРАНЯЕТ ссылку на неё в manager (иначе
    Python удаляет объект — иконка мгновенно исчезает, а меню умирает
    вместе с ней). Если системный трей ещё не готов (например, автозапуск
    сработал раньше Проводника) — повторяет попытки по таймеру до минуты.
    При успехе показывает уведомление — видимое подтверждение запуска.
    """
    state = {"tray": None, "tries": 0}

    def create() -> bool:
        """True — повторять больше не нужно (создан или создан не будет)."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        try:
            tray = build_tray(app, manager)
        except Exception:
            config.log_error("Трей недоступен\n" + traceback.format_exc())
            return True
        state["tray"] = tray
        manager.tray = tray
        tray.showMessage(
            f"{config.APP_NAME} {config.APP_VERSION}",
            i18n.t("started_msg"),
            QSystemTrayIcon.Information, 5000)
        return True

    def retry() -> None:
        state["tries"] += 1
        if create() or state["tries"] >= 40:
            if state["tray"] is None:
                config.log_error(
                    "Системный трей так и не стал доступен за 60 секунд.")
            timer.stop()

    if create():
        return
    timer = QTimer(app)
    timer.setInterval(1500)
    timer.timeout.connect(retry)
    timer.start()
    manager.tray_timer = timer   # держим ссылку, иначе таймер умрёт


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
    # язык интерфейса: из настроек или по языку Windows
    i18n.init((cfg.get("ui") or {}).get("lang", "auto"))
    app.setStyleSheet(app_stylesheet())

    # Google Roboto везде: виджеты, меню, диалоги. Если файлы не нашлись
    # (например, ресурсы не попали в сборку) — системный шрифт по умолчанию.
    fam = load_app_fonts()
    if fam:
        widgets_base.FONT_FAMILY = fam
        app.setFont(QFont(fam))

    os.makedirs(config.CONFIG_DIR, exist_ok=True)
    lock = QLockFile(os.path.join(config.CONFIG_DIR, "app.lock"))
    lock.setStaleLockTime(0)

    locked = lock.tryLock(200)
    if not locked:
        # Блокировка занята: либо живёт другая копия, либо остался
        # устаревший lock-файл после сбоя.
        stale = find_stale_instances()
        if stale:
            names = ", ".join(f"{p.info['name']} (PID {p.info['pid']})"
                              for p in stale)
            answer = QMessageBox.question(
                None, config.APP_NAME,
                i18n.t("stale_found", name=config.APP_NAME, names=names),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if answer == QMessageBox.Yes:
                terminate_stale(stale)
                locked = lock.tryLock(500)
        else:
            lock.removeStaleLockFile()
            locked = lock.tryLock(200)
    if not locked:
        QMessageBox.warning(
            None, config.APP_NAME,
            i18n.t("already_running", name=config.APP_NAME,
                   exe=f"{config.APP_NAME}.exe"))
        return app, None

    manager = WidgetManager(cfg)
    manager.build_all()
    setup_tray(app, manager)

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
