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
from PySide6.QtWidgets import (QApplication, QInputDialog, QMenu, QMessageBox,
                               QSystemTrayIcon)

from app import autostart, config, i18n, layout, theme
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
    #  Экраны и координаты
    # ------------------------------------------------------------------ #
    @staticmethod
    def _area() -> tuple:
        """Доступная область основного экрана — (x, y, w, h)."""
        scr = QApplication.primaryScreen()
        if scr is None:
            return (0, 0, 1920, 1080)
        g = scr.availableGeometry()
        return (g.x(), g.y(), g.width(), g.height())

    @staticmethod
    def _areas() -> list:
        """Доступные области всех мониторов."""
        out = []
        for scr in QApplication.screens():
            g = scr.availableGeometry()
            out.append((g.x(), g.y(), g.width(), g.height()))
        return out or [(0, 0, 1920, 1080)]

    def _rect_from_cfg(self, key: str) -> tuple | None:
        """Прямоугольник карточки из настроек; None — координат ещё нет."""
        wc = self.cfg["widgets"][key]
        if wc.get("x") is None or wc.get("y") is None:
            return None
        return (int(wc["x"]), int(wc["y"]), int(wc["w"]), int(wc["h"]))

    # ------------------------------------------------------------------ #
    #  Позиции: значения по умолчанию и страховка от потери
    # ------------------------------------------------------------------ #
    def ensure_positions(self) -> None:
        """Гарантирует, что у каждой карточки есть позиция и её видно.

        1. Виджетам без координат выдаётся место: при первом запуске (или
           после сброса) — колонками у правого края, одиночному — свободное.
        2. Карточку, улетевшую за пределы всех мониторов (утащили мышью или
           отключили второй экран), возвращает на основной экран.
        """
        items = self.cfg["widgets"]
        area = self._area()
        missing = [k for k in WIDGET_ORDER
                   if items[k].get("x") is None or items[k].get("y") is None]
        if missing:
            if len(missing) == len(WIDGET_ORDER):
                # Первый запуск / сброс — цельная раскладка, а не каша.
                enabled = [k for k in WIDGET_ORDER if items[k].get("enabled", True)]
                sizes = {k: (int(items[k]["w"]), int(items[k]["h"])) for k in enabled}
                for k, (x, y) in layout.default_positions(enabled, sizes, area).items():
                    items[k]["x"], items[k]["y"] = int(x), int(y)
            else:
                # Включили один виджет — ставим его на свободное место.
                occupied = [r for r in (self._rect_from_cfg(k) for k in WIDGET_ORDER)
                            if r is not None]
                for k in missing:
                    w, h = int(items[k]["w"]), int(items[k]["h"])
                    x, y = layout.find_free_spot(w, h, occupied, area)
                    items[k]["x"], items[k]["y"] = int(x), int(y)
                    occupied.append((int(x), int(y), w, h))

        areas = self._areas()
        for k in WIDGET_ORDER:
            rect = self._rect_from_cfg(k)
            if rect is None:
                continue
            nx, ny, _, _ = layout.ensure_reachable(rect, areas, area)
            if (nx, ny) != (rect[0], rect[1]):
                items[k]["x"], items[k]["y"] = int(nx), int(ny)
                config.log_error(f"Виджет {k} возвращён на экран: "
                                 f"{rect[0]},{rect[1]} -> {nx},{ny}")

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
        self.ensure_positions()
        for k in WIDGET_ORDER:
            if self.cfg["widgets"][k].get("enabled", True):
                self.create_widget(k)
        config.save(self.cfg)
        self.monitor.start()

    # ------------------------------------------------------------------ #
    #  Расстановка: профили, выравнивание, сброс
    # ------------------------------------------------------------------ #
    def capture_layout(self) -> dict:
        """Снимок текущей расстановки: позиции, размеры, масштаб, вкл/выкл."""
        for key, w in self.widgets.items():
            wc = self.cfg["widgets"].get(key)
            if wc is None:
                continue
            wc["x"], wc["y"] = w.x(), w.y()
            wc["w"], wc["h"] = w.width(), w.height()
        return {"widgets": layout.capture(self.cfg["widgets"]),
                "saved": layout.stamp()}

    def _push_undo(self) -> None:
        """Запоминает расстановку до изменения — для «Вернуть как было»."""
        self.cfg["layout_undo"] = self.capture_layout()

    def apply_geometry(self) -> None:
        """Переносит геометрию из настроек в живые окна.

        Заодно приводит состав виджетов к настройкам: недостающие создаёт,
        выключенные закрывает.
        """
        for key in WIDGET_ORDER:
            wc = self.cfg["widgets"][key]
            enabled = bool(wc.get("enabled", True))
            widget = self.widgets.get(key)
            if not enabled:
                if widget is not None:
                    self.widgets.pop(key, None)
                    widget.blockSignals(True)
                    widget.close()
                    widget.blockSignals(False)
                continue
            if widget is None or wc.get("x") is None or wc.get("y") is None:
                self.create_widget(key)
                continue
            widget.resize(int(wc["w"]), int(wc["h"]))
            widget.move(int(wc["x"]), int(wc["y"]))
            widget.update()
            if not self.cfg.get("hidden_all") and not widget.isVisible():
                widget.show()
        config.save(self.cfg)

    def apply_layout_snapshot(self, snapshot: dict) -> None:
        """Возвращает расстановку из снимка (профиль или «как было»)."""
        if not isinstance(snapshot, dict):
            return
        layout.restore(self.cfg["widgets"], snapshot.get("widgets") or {})
        self.ensure_positions()   # снимок мог быть сделан на другом мониторе
        self.apply_geometry()

    def save_layout(self, name: str) -> str | None:
        """Сохраняет текущую расстановку под именем. Возвращает имя."""
        name = layout.clean_name(name)
        if not name:
            return None
        if not isinstance(self.cfg.get("layouts"), dict):
            self.cfg["layouts"] = {}   # config.json мог быть испорчен вручную
        self.cfg["layouts"][name] = self.capture_layout()
        config.save(self.cfg)
        return name

    def apply_named_layout(self, name: str) -> bool:
        """Применяет сохранённый профиль. True — профиль найден."""
        layouts = self.cfg.get("layouts")
        snapshot = layouts.get(name) if isinstance(layouts, dict) else None
        if not snapshot:
            return False
        self._push_undo()
        self.apply_layout_snapshot(snapshot)
        return True

    def delete_layout(self, name: str) -> bool:
        """Удаляет профиль расстановки."""
        layouts = self.cfg.get("layouts")
        if not isinstance(layouts, dict) or name not in layouts:
            return False
        layouts.pop(name, None)
        config.save(self.cfg)
        return True

    def undo_layout(self) -> bool:
        """Возвращает расстановку, которая была до последнего изменения."""
        snapshot = self.cfg.get("layout_undo")
        if not isinstance(snapshot, dict) or not snapshot:
            return False
        self.cfg["layout_undo"] = None   # действие одноразовое
        self.apply_layout_snapshot(snapshot)
        return True

    def arrange_default(self) -> None:
        """Выравнивает включённые карточки колонками у правого края экрана.

        Размеры и масштаб не меняются — это «верни всё на место», а не
        «сбрось мои настройки».
        """
        self._push_undo()
        items = self.cfg["widgets"]
        area = self._area()
        enabled = [k for k in WIDGET_ORDER if items[k].get("enabled", True)]
        sizes = {k: (int(items[k]["w"]), int(items[k]["h"])) for k in enabled}
        for k, (x, y) in layout.default_positions(enabled, sizes, area).items():
            items[k]["x"], items[k]["y"] = int(x), int(y)
        self.ensure_positions()   # экран меньше раскладки — подтянуть крайние
        self.apply_geometry()

    def reset_layout(self) -> None:
        """Сбрасывает расстановку к заводской: размеры, масштаб, позиции.

        Все виджеты снова включаются и возвращаются на экран — тот самый
        «вытащить календарь из-за края» одним пунктом меню.
        """
        self._push_undo()
        self.cfg["hidden_all"] = False
        for key in WIDGET_ORDER:
            defaults = config.DEFAULTS["widgets"][key]
            wc = self.cfg["widgets"][key]
            wc["w"], wc["h"] = defaults["w"], defaults["h"]
            wc["scale"] = defaults["scale"]
            wc["enabled"] = True
            wc["x"] = wc["y"] = None
        self.ensure_positions()
        self.apply_geometry()

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
            self.ensure_positions()
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

    def notify(text: str) -> None:
        """Короткое сообщение в трее — подтверждение действия."""
        if manager.tray is not None:
            manager.tray.showMessage(config.APP_NAME, text,
                                     QSystemTrayIcon.Information, 3000)

    # --- расстановка: сохранение/применение профилей, сброс ---
    def ask_yes(title: str, text: str) -> bool:
        return QMessageBox.question(
            None, title, text,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def save_layout() -> None:
        layouts = manager.cfg.get("layouts")
        names = list(layouts) if isinstance(layouts, dict) else []
        name, ok = QInputDialog.getText(
            None, i18n.t("lay_save_title"), i18n.t("lay_name_prompt"),
            text=names[-1] if names else i18n.t("lay_default_name"))
        if not ok:
            return
        name = layout.clean_name(name)
        if not name:
            return
        if name in names and not ask_yes(config.APP_NAME,
                                         i18n.t("lay_exists", name=name)):
            return
        manager.save_layout(name)
        notify(i18n.t("lay_saved", name=name))

    def apply_preset(name: str) -> None:
        if manager.apply_named_layout(name):
            notify(i18n.t("lay_applied", name=name))

    def delete_preset(name: str) -> None:
        if not ask_yes(config.APP_NAME, i18n.t("lay_delete_confirm", name=name)):
            return
        if manager.delete_layout(name):
            notify(i18n.t("lay_deleted", name=name))

    def undo_layout() -> None:
        if manager.undo_layout():
            notify(i18n.t("lay_undo_done"))

    def arrange() -> None:
        manager.arrange_default()
        notify(i18n.t("lay_arranged"))

    def reset_layout() -> None:
        if not ask_yes(i18n.t("lay_reset_title"), i18n.t("lay_reset_confirm")):
            return
        manager.reset_layout()
        notify(i18n.t("lay_reset_done"))

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

        # --- расстановка: профили, выравнивание, сброс ---
        presets = manager.cfg.get("layouts")
        presets = list(presets) if isinstance(presets, dict) else []
        m_lay = menu.addMenu(i18n.t("m_layout"))
        a_save = m_lay.addAction(i18n.t("lay_save"))
        a_save.triggered.connect(save_layout)
        if presets:
            m_lay.addSeparator()
            for name in presets:
                act = m_lay.addAction(name)
                act.triggered.connect(
                    lambda checked=False, n=name: apply_preset(n))
        m_lay.addSeparator()
        a_undo = m_lay.addAction(i18n.t("lay_undo"))
        a_undo.setEnabled(isinstance(manager.cfg.get("layout_undo"), dict))
        a_undo.triggered.connect(undo_layout)
        a_arr = m_lay.addAction(i18n.t("lay_arrange"))
        a_arr.triggered.connect(arrange)
        a_rst = m_lay.addAction(i18n.t("lay_reset"))
        a_rst.triggered.connect(reset_layout)
        if presets:
            m_lay.addSeparator()
            m_del = m_lay.addMenu(i18n.t("lay_delete"))
            for name in presets:
                act = m_del.addAction(name)
                act.triggered.connect(
                    lambda checked=False, n=name: delete_preset(n))

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
