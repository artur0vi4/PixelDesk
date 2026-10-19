"""Виджет «Погода» — подробная: текущая, детали, по часам и на 5 дней."""
from __future__ import annotations

import os
import threading
from datetime import datetime

from PySide6.QtCore import QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QInputDialog

from .base import PixelWidget
from .. import config, theme
from .. import i18n
from .. import weather_api


class _Sig(QObject):
    got = Signal(object)


class WeatherWidget(PixelWidget):
    TITLE = "w_weather"
    HAS_REFRESH = True

    def __init__(self, app_cfg: dict):
        super().__init__(app_cfg, "weather")
        self.setMinimumSize(280, 430)
        self.data: dict | None = None
        self.status = i18n.t("wx_locating")
        self._last_ok: str | None = None   # время последних удачных данных
        self._sig = _Sig()
        self._sig.got.connect(self._on_data)
        mins = max(5, int(self.app_cfg["weather"].get("refresh_min", 15)))
        # У Яндекса бесплатный ключ — всего 50 запросов/день:
        # поднимаем интервал до 30 минут (48 запросов/день)
        if (self.app_cfg["weather"].get("source") or "auto") == "yandex":
            mins = max(mins, 30)
        self._timer = QTimer(self)
        self._timer.setInterval(mins * 60 * 1000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        QTimer.singleShot(400, self.refresh)

    # ------------------------------------------------------------------ #
    #  Загрузка данных в фоновом потоке
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        self.status = i18n.t("wx_updating")
        self.update()
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self) -> None:
        try:
            if os.environ.get("PW_FAKE_WEATHER"):
                data = weather_api.fake_forecast()
                wc = self.app_cfg["weather"]
                data["geo"] = {"city": wc.get("city") or "Тестград",
                               "lat": wc.get("lat") or 55.75,
                               "lon": wc.get("lon") or 37.61}
                self._sig.got.emit({"ok": True, "data": data})
                return
            wc = self.app_cfg["weather"]
            if wc.get("lat") is None or wc.get("lon") is None:
                geo = weather_api.ip_geo()
                if geo is None:
                    geo = {"city": i18n.t("city_moscow"), "lat": 55.7558,
                           "lon": 37.6173, "fallback": True}
            else:
                geo = {"city": wc.get("city") or "—",
                       "lat": wc["lat"], "lon": wc["lon"]}
            data = weather_api.fetch_forecast(
                geo["lat"], geo["lon"],
                source=wc.get("source") or "auto",
                yandex_key=wc.get("yandex_key") or "")
            data["geo"] = geo
            self._sig.got.emit({"ok": True, "data": data})
        except Exception as ex:  # noqa: BLE001
            self._sig.got.emit({"ok": False, "error": str(ex)})

    def _on_data(self, payload: dict) -> None:
        wc = self.app_cfg["weather"]
        if payload.get("manual"):
            geo = payload.get("geo")
            if geo:
                wc.update(city=geo["city"], lat=geo["lat"], lon=geo["lon"],
                          manual=True)
                config.save(self.app_cfg)
                self.status = i18n.t("wx_city_updating", city=geo["city"])
                self.update()
                self.refresh()
            else:
                self.status = i18n.t("wx_city_not_found", q=payload.get("query", ""))
                self.update()
            return
        if payload.get("ok"):
            self.data = payload["data"]
            geo = self.data["geo"]
            if not (wc.get("manual") and wc.get("lat") is not None):
                wc["city"], wc["lat"], wc["lon"] = geo["city"], geo["lat"], geo["lon"]
            note = i18n.t("wx_default_city") if geo.get("fallback") else ""
            src = self.data.get("source")
            self._last_ok = datetime.now().strftime("%H:%M")
            self.status = i18n.t("wx_updated", time=self._last_ok, src=src) + note
        else:
            self.status = i18n.t("wx_offline")
            if self._last_ok:
                self.status += " — " + i18n.t("wx_data_from", time=self._last_ok)
            elif self.data:
                self.status += " — " + i18n.t(
                    "wx_data_from", time=self.data.get("now_local", "?"))
        self.update()
        config.save(self.app_cfg)

    def change_city(self) -> None:
        cur = self.app_cfg["weather"].get("city") or ""
        text, ok = QInputDialog.getText(self, i18n.t("wx_change_city_title"),
                                        i18n.t("wx_city_prompt"), text=cur)
        if not ok:
            return
        q = text.strip()
        if not q:
            return
        self.status = i18n.t("wx_searching", q=q)
        self.update()

        def job():
            geo = weather_api.geocode(q)
            self._sig.got.emit({"ok": True, "data": None,
                                "manual": True, "geo": geo, "query": q})

        threading.Thread(target=job, daemon=True).start()

    def set_yandex_key(self) -> None:
        cur = self.app_cfg["weather"].get("yandex_key") or ""
        text, ok = QInputDialog.getText(
            self, i18n.t("wx_key_title"),
            i18n.t("wx_key_prompt"),
            text=cur)
        if not ok:
            return
        self.app_cfg["weather"]["yandex_key"] = text.strip() or None
        config.save(self.app_cfg)
        self.status = (i18n.t("wx_key_saved")
                       if text.strip() else i18n.t("wx_key_removed"))
        self.update()
        self.refresh()

    # ------------------------------------------------------------------ #
    def extra_menu(self, menu) -> None:
        a_city = menu.addAction(i18n.t("wx_change_city"))
        a_city.setData("city")

        m_src = menu.addMenu(i18n.t("wx_source"))
        cur_src = self.app_cfg["weather"].get("source") or "auto"
        for val, name in (("auto", i18n.t("wx_src_auto")),
                          ("open-meteo", "Open-Meteo"),
                          ("yandex", i18n.t("wx_src_yandex"))):
            act = m_src.addAction(self._ck(cur_src == val, name))
            act.setData(("src", val))

        a_key = menu.addAction(i18n.t("wx_key_menu"))
        a_key.setData("ykey")

    def handle_menu_data(self, data) -> bool:
        if data == "city":
            self.change_city()
            return True
        if data == "ykey":
            self.set_yandex_key()
            return True
        if isinstance(data, tuple) and data and data[0] == "src":
            self.app_cfg["weather"]["source"] = data[1]
            config.save(self.app_cfg)
            self.status = i18n.t("wx_src_changed")
            self.update()
            self.refresh()
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Отрисовка
    # ------------------------------------------------------------------ #
    def paint_content(self, p: QPainter) -> None:
        area = QRectF(self.rect()).adjusted(
            self.pad(), self.pad() * 0.8, -self.pad(), -self.pad() * 0.8)
        s = self.s
        outline = QColor(theme.C("outline"))
        outline.setAlpha(70)

        if not self.data:
            self._text(p, area, Qt.AlignCenter, self.status or i18n.t("wx_loading"),
                       theme.C("on_surface_variant"), self.f(15 * s))
            return

        d = self.data
        cur = d["cur"]
        cond_txt, cond_ico = weather_api.wmo(cur["code"], cur["is_day"])

        # ---- город ----
        city = (self.app_cfg["weather"].get("city")
                or (d.get("geo") or {}).get("city") or "—")
        f_city = self.f(15 * s, QFont.DemiBold)
        self._text(p, QRectF(area.left(), area.top(),
                             area.width() - 30 * s, 20 * s),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   self._elide(city, f_city, area.width() - 30 * s),
                   theme.C("on_surface_variant"), f_city)

        # ---- крупная температура + эмодзи ----
        temp_h = area.height() * 0.265
        temp_txt = f"{cur['temp']}°"
        f_temp = self.f(temp_h * 0.78, QFont.Light)
        while QFontMetrics(f_temp).horizontalAdvance(temp_txt) > area.width() * 0.55 \
                or QFontMetrics(f_temp).height() > temp_h * 1.02:
            if f_temp.pixelSize() <= 8:
                break
            f_temp = QFont(f_temp)
            f_temp.setPixelSize(max(8, int(f_temp.pixelSize() * 0.94)))
        self._text(p, QRectF(area.left(), area.top() + 20 * s,
                             area.width() * 0.6, temp_h),
                   Qt.AlignLeft | Qt.AlignVCenter, temp_txt,
                   theme.C("on_surface"), f_temp)

        f_emoji = self.f(temp_h * 0.62, QFont.Normal)
        self._text(p, QRectF(area.right() - area.width() * 0.35,
                             area.top() + 18 * s, area.width() * 0.35, temp_h),
                   Qt.AlignRight | Qt.AlignVCenter, cond_ico,
                   theme.C("on_surface"), f_emoji)

        # ---- описание погоды ----
        y = area.top() + 20 * s + temp_h
        f_cond = self.f(15 * s, QFont.Normal)
        self._text(p, QRectF(area.left(), y, area.width(), 19 * s),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   self._elide(cond_txt, f_cond, area.width()),
                   theme.C("on_surface_variant"), f_cond)
        y += 24 * s

        # ---- сетка деталей 3 x 2 ----
        details = [
            (i18n.t("lbl_feels"), f"{cur['feels']}°"),
            (i18n.t("lbl_wind"),
             f"{cur['wind']} {i18n.t('unit_ms')} {weather_api.wind_dir(cur['wdir'])}".strip()),
            (i18n.t("lbl_hum"), f"{cur['hum']}%" if cur["hum"] is not None else "—"),
            (i18n.t("lbl_pres"), f"{cur['pres']} {i18n.t('unit_mm')}"),
            (i18n.t("lbl_uv"), str(d["uv"]) if d["uv"] is not None else "—"),
            (i18n.t("lbl_cloud"), f"{cur['cloud']}%" if cur["cloud"] is not None else "—"),
        ]
        col_w = area.width() / 3.0
        row_h = 38 * s
        f_lab = self.f(10.5 * s, QFont.Normal)
        f_val = self.f(14.5 * s, QFont.DemiBold)
        for i, (lab, val) in enumerate(details):
            cx = area.left() + (i % 3) * col_w
            cy = y + (i // 3) * row_h
            self._text(p, QRectF(cx, cy, col_w - 6 * s, 13 * s),
                       Qt.AlignLeft | Qt.AlignVCenter, lab,
                       theme.C("on_surface_variant"), f_lab)
            self._text(p, QRectF(cx, cy + 14 * s, col_w - 6 * s, 18 * s),
                       Qt.AlignLeft | Qt.AlignVCenter,
                       self._elide(val, f_val, col_w - 6 * s),
                       theme.C("on_surface"), f_val)
        y += row_h * 2 + 6 * s

        # ---- восход / закат ----
        f_sun = self.f(13 * s, QFont.Normal)
        self._text(p, QRectF(area.left(), y, area.width(), 17 * s),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   f"↑ {d['sunrise']}    ↓ {d['sunset']}",
                   theme.C("on_surface_variant"), f_sun)
        y += 22 * s

        p.setPen(outline)
        p.drawLine(int(area.left()), int(y), int(area.right()), int(y))
        y += 6 * s

        # ---- по часам ----
        hours = d["hours"][:8]
        n = max(1, len(hours))
        hcol_w = area.width() / n
        block_h = min(84 * s, max(60 * s, (area.bottom() - y) * 0.34))
        f_h1 = self.f(10 * s, QFont.Normal)
        f_h2 = self.f(15 * s, QFont.Normal)
        f_h3 = self.f(11.5 * s, QFont.DemiBold)
        f_h4 = self.f(9 * s, QFont.Normal)
        primary = QColor(theme.C("primary"))
        for i, h in enumerate(hours):
            cx = area.left() + i * hcol_w
            _, ico = weather_api.wmo(h["code"], True)
            self._text(p, QRectF(cx, y, hcol_w, 12 * s),
                       Qt.AlignCenter, h["time"][:2],
                       theme.C("on_surface_variant"), f_h1)
            self._text(p, QRectF(cx, y + 13 * s, hcol_w, 22 * s),
                       Qt.AlignCenter, ico, theme.C("on_surface"), f_h2)
            self._text(p, QRectF(cx, y + 36 * s, hcol_w, 15 * s),
                       Qt.AlignCenter, f"{h['temp']}°",
                       theme.C("on_surface"), f_h3)
            if h["pop"] and h["pop"] >= 5:
                self._text(p, QRectF(cx, y + 52 * s, hcol_w, 11 * s),
                           Qt.AlignCenter, f"{h['pop']}%", primary, f_h4)
        y += block_h

        p.setPen(outline)
        p.drawLine(int(area.left()), int(y), int(area.right()), int(y))
        y += 5 * s

        # ---- на 5 дней ----
        days = d["days"]
        if days:
            row_h = max(17 * s, (area.bottom() - y - 16 * s) / len(days))
            f_d1 = self.f(12 * s, QFont.Normal)
            f_d2 = self.f(13 * s, QFont.Normal)
            f_d3 = self.f(10 * s, QFont.Normal)
            f_d4 = self.f(12 * s, QFont.DemiBold)
            for i, day in enumerate(days):
                ry = y + i * row_h
                if ry + row_h > area.bottom() - 14 * s:
                    break
                _, ico = weather_api.wmo(day["code"], True)
                self._text(p, QRectF(area.left(), ry, area.width() * 0.28, row_h),
                           Qt.AlignLeft | Qt.AlignVCenter, day["label"],
                           theme.C("on_surface"), f_d1)
                self._text(p, QRectF(area.left() + area.width() * 0.28, ry,
                                     area.width() * 0.12, row_h),
                           Qt.AlignCenter, ico, theme.C("on_surface"), f_d2)
                if day["pop"] and day["pop"] >= 5:
                    self._text(p, QRectF(area.right() - 84 * s, ry, 26 * s, row_h),
                               Qt.AlignRight | Qt.AlignVCenter, f"{day['pop']}%",
                               primary, f_d3)
                temps = f"{day['min']}° / {day['max']}°"
                self._text(p, QRectF(area.right() - 56 * s, ry, 56 * s, row_h),
                           Qt.AlignRight | Qt.AlignVCenter, temps,
                           theme.C("on_surface"), f_d4)

        # ---- статус ----
        f_st = self.f(9.5 * s, QFont.Normal)
        st_col = QColor(theme.C("on_surface_variant"))
        st_col.setAlpha(190)
        self._text(p, QRectF(area.left(), area.bottom() - 13 * s, area.width(), 13 * s),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   self._elide(self.status, f_st, area.width()),
                   st_col.name(), f_st)
