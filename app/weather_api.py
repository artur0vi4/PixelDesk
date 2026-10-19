"""Погодные данные: несколько источников с автоматическим выбором.

Порядок (источник «Авто»):
  1. Open-Meteo (без ключа);
  2. MET Norway / yr.no (без ключа);
  3. Яндекс Погода (нужен бесплатный ключ — вводится в меню виджета).

Каждый источник возвращает одинаковую структуру, поэтому виджету всё равно,
кто ответил. Определение города по IP тоже с резервами (3 сервиса),
поиск города — 3 геокодера.
"""
from __future__ import annotations

import datetime as dt
import math

import requests

from . import i18n

UA = {"User-Agent": "PixelDesk/1.1 (desktop widgets; github.com/artur0vi4)"}
GEO_TIMEOUT = 8
WX_TIMEOUT = 10

# WMO weather interpretation codes -> (описание RU, описание EN, иконка днём, иконка ночью)
_WMO = {
    0: ("Ясно", "Clear sky", "☀️", "🌙"),
    1: ("Преимущественно ясно", "Mainly clear", "🌤️", "🌙"),
    2: ("Переменная облачность", "Partly cloudy", "⛅", "☁️"),
    3: ("Пасмурно", "Overcast", "☁️", "☁️"),
    45: ("Туман", "Fog", "🌫️", "🌫️"),
    48: ("Изморозь", "Rime fog", "🌫️", "🌫️"),
    51: ("Слабая морось", "Light drizzle", "🌦️", "🌧️"),
    53: ("Морось", "Drizzle", "🌦️", "🌧️"),
    55: ("Сильная морось", "Dense drizzle", "🌧️", "🌧️"),
    56: ("Ледяная морось", "Freezing drizzle", "🌧️", "🌧️"),
    57: ("Ледяная морось", "Freezing drizzle", "🌧️", "🌧️"),
    61: ("Небольшой дождь", "Slight rain", "🌦️", "🌧️"),
    63: ("Дождь", "Rain", "🌧️", "🌧️"),
    65: ("Сильный дождь", "Heavy rain", "🌧️", "🌧️"),
    66: ("Ледяной дождь", "Freezing rain", "🌧️", "🌧️"),
    67: ("Ледяной дождь", "Freezing rain", "🌧️", "🌧️"),
    71: ("Небольшой снег", "Slight snowfall", "🌨️", "🌨️"),
    73: ("Снег", "Snowfall", "🌨️", "🌨️"),
    75: ("Сильный снег", "Heavy snowfall", "❄️", "❄️"),
    77: ("Снежные зёрна", "Snow grains", "🌨️", "🌨️"),
    80: ("Ливень", "Rain showers", "🌧️", "🌧️"),
    81: ("Ливень", "Rain showers", "🌧️", "🌧️"),
    82: ("Сильный ливень", "Violent showers", "⛈️", "⛈️"),
    85: ("Снегопад", "Snow showers", "🌨️", "🌨️"),
    86: ("Сильный снегопад", "Heavy snow showers", "❄️", "❄️"),
    95: ("Гроза", "Thunderstorm", "⛈️", "⛈️"),
    96: ("Гроза с градом", "Thunderstorm with hail", "⛈️", "⛈️"),
    99: ("Гроза с градом", "Thunderstorm with hail", "⛈️", "⛈️"),
}

# Яндекс condition -> код WMO
_YANDEX_WMO = {
    "clear": 0, "partly-cloudy": 1, "cloudy": 2, "overcast": 3,
    "drizzle": 51, "light-rain": 61, "rain": 63, "heavy-rain": 65,
    "continuous-heavy-rain": 65, "showers": 81, "wet-snow": 66,
    "light-snow": 71, "snow": 73, "snow-showers": 85, "hail": 96,
    "thunderstorm": 95, "thunderstorm-with-rain": 95,
    "thunderstorm-with-hail": 96,
}

# Яндекс wind_dir -> градусы
_YANDEX_DIR = {"n": 0, "ne": 45, "e": 90, "se": 135, "s": 180,
               "sw": 225, "w": 270, "nw": 315, "c": 0}


def wmo(code: int, is_day: bool = True):
    """(текст, эмодзи) по коду WMO; текст на текущем языке."""
    default = ("Облачно", "Cloudy", "☁️", "☁️")
    t = _WMO.get(int(code or 0), default)
    txt = t[0] if i18n.current() == "ru" else t[1]
    return txt, (t[2] if is_day else t[3])


def wind_dir(deg) -> str:
    try:
        i = int(round(float(deg) / 45.0)) % 8
    except Exception:
        return ""
    return i18n.wind_dir_name(i)


def met_symbol_to_wmo(sym: str) -> int:
    """Символ MET Norway (например 'partlycloudy_day') -> код WMO."""
    base = (sym or "").split("_")[0]
    if base == "clearsky":
        c = 0
    elif base == "fair":
        c = 1
    elif base == "partlycloudy":
        c = 2
    elif base == "cloudy":
        c = 3
    elif base == "fog":
        c = 45
    elif base.startswith("lightrain"):
        c = 61
    elif base.startswith("heavyrain"):
        c = 65
    elif base.startswith("rain"):
        c = 63
    elif base.startswith("lightsnow"):
        c = 71
    elif base.startswith("heavysnow"):
        c = 75
    elif base.startswith("snow"):
        c = 73
    elif base.startswith("sleet"):
        c = 66
    else:
        c = 3
    if "thunder" in base:
        c = 95
    return c


# ---------------------------------------------------------------------- #
#  Геолокация
# ---------------------------------------------------------------------- #
def ip_geo():
    """Определение города по IP. -> {'city', 'lat', 'lon'} | None."""
    for url, parse in (
        ("https://ipwho.is/", lambda j: (
            j.get("city") or "—", j.get("latitude"), j.get("longitude"))
            if j.get("success") and j.get("latitude") is not None else None),
        ("http://ip-api.com/json/?fields=status,city,lat,lon&lang=ru",
         lambda j: (j.get("city") or "—", j.get("lat"), j.get("lon"))
            if j.get("status") == "success" else None),
        ("https://freeipapi.com/api/json", lambda j: (
            j.get("cityName") or "—", j.get("latitude"), j.get("longitude"))
            if j.get("latitude") is not None else None),
    ):
        try:
            r = requests.get(url, timeout=GEO_TIMEOUT, headers=UA)
            res = parse(r.json() or {})
            if res and res[1] is not None and res[2] is not None:
                return {"city": res[0],
                        "lat": float(res[1]), "lon": float(res[2])}
        except Exception:
            continue
    return None


def geocode(query: str):
    """Поиск города: Open-Meteo -> Nominatim (OSM) -> Photon."""
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 1, "language": "ru", "format": "json"},
            timeout=GEO_TIMEOUT, headers=UA)
        res = (r.json() or {}).get("results") or []
        if res:
            g = res[0]
            return {"city": g.get("name", query),
                    "lat": float(g["latitude"]), "lon": float(g["longitude"])}
    except Exception:
        pass
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1,
                    "accept-language": "ru"},
            timeout=GEO_TIMEOUT, headers=UA)
        res = r.json() or []
        if res:
            g = res[0]
            name = g.get("name") or (g.get("display_name") or query).split(",")[0]
            return {"city": name, "lat": float(g["lat"]), "lon": float(g["lon"])}
    except Exception:
        pass
    try:
        r = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": query, "limit": 1, "lang": "ru"},
            timeout=GEO_TIMEOUT, headers=UA)
        feats = (r.json() or {}).get("features") or []
        if feats:
            g = feats[0]
            props = g.get("properties") or {}
            coords = (g.get("geometry") or {}).get("coordinates") or []
            if len(coords) == 2:
                city = (props.get("city") or props.get("name")
                        or props.get("state") or query)
                return {"city": city,
                        "lat": float(coords[1]), "lon": float(coords[0])}
    except Exception:
        pass
    return None


def _hhmm(iso: str) -> str:
    try:
        s = iso.replace("Z", "+00:00")
        d = dt.datetime.fromisoformat(s)
        if d.tzinfo is not None:
            d = d.astimezone()
        return d.strftime("%H:%M")
    except Exception:
        return "—"


def _is_day_solar(lat: float, lon: float, when_utc: dt.datetime) -> bool:
    """День или ночь: высота солнца по упрощённой формуле NOAA (> -3°)."""
    try:
        day = when_utc.timetuple().tm_yday
        hour = (when_utc.hour + when_utc.minute / 60.0
                + when_utc.second / 3600.0)
        g = 2 * math.pi / 365.0 * (day - 1 + (hour - 12) / 24.0)
        eq = 229.18 * (0.000075 + 0.001868 * math.cos(g)
                       - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                       - 0.040849 * math.sin(2 * g))
        decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
                - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
                - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
        tst = hour * 60.0 + eq + 4.0 * lon
        ha = math.radians(tst / 4.0 - 180.0)
        la = math.radians(lat)
        cos_z = (math.sin(la) * math.sin(decl)
                 + math.cos(la) * math.cos(decl) * math.cos(ha))
        alt = math.asin(max(-1.0, min(1.0, cos_z)))
        return alt > math.radians(-3.0)
    except Exception:
        return 6 <= (when_utc.astimezone().hour) < 22


# ---------------------------------------------------------------------- #
#  Источник 1: Open-Meteo
# ---------------------------------------------------------------------- #
def _fetch_open_meteo(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 6,
        "current": ("temperature_2m,relative_humidity_2m,apparent_temperature,"
                    "is_day,weather_code,wind_speed_10m,wind_direction_10m,"
                    "pressure_msl,cloud_cover"),
        "hourly": "temperature_2m,weather_code,precipitation_probability",
        "daily": ("weather_code,temperature_2m_max,temperature_2m_min,"
                  "sunrise,sunset,uv_index_max,precipitation_probability_max"),
    }
    r = requests.get("https://api.open-meteo.com/v1/forecast",
                     params=params, timeout=WX_TIMEOUT, headers=UA)
    r.raise_for_status()
    j = r.json()

    cur = j["current"]
    is_day = bool(cur.get("is_day", 1))
    try:
        now_local = dt.datetime.fromisoformat(cur["time"])
    except Exception:
        now_local = dt.datetime.now()

    hourly = j["hourly"]
    times = [dt.datetime.fromisoformat(t) for t in hourly["time"]]
    target = now_local.replace(minute=0, second=0, microsecond=0)
    idx = min(range(len(times)),
              key=lambda i: abs((times[i] - target).total_seconds()))
    pops_h = hourly.get("precipitation_probability") or [0] * len(times)
    hours = []
    for i in range(idx, min(idx + 10, len(times))):
        hours.append({
            "time": times[i].strftime("%H:00"),
            "temp": round(hourly["temperature_2m"][i]),
            "code": int(hourly["weather_code"][i] or 0),
            "pop": pops_h[i] if pops_h[i] is not None else 0,
        })

    daily = j["daily"]
    pops_d = daily.get("precipitation_probability_max") or [0] * len(daily["time"])
    days = []
    for i in range(min(5, len(daily["time"]))):
        d = dt.date.fromisoformat(daily["time"][i])
        days.append({
            "label": f"{i18n.wd_short(d.weekday())} {d.day:02d}",
            "code": int(daily["weather_code"][i] or 0),
            "min": round(daily["temperature_2m_min"][i]),
            "max": round(daily["temperature_2m_max"][i]),
            "pop": pops_d[i] if pops_d[i] is not None else 0,
        })

    uv_list = daily.get("uv_index_max") or []
    uv = round(uv_list[0], 1) if uv_list and uv_list[0] is not None else None

    return {
        "cur": {
            "temp": round(cur["temperature_2m"]),
            "feels": round(cur["apparent_temperature"]),
            "hum": cur.get("relative_humidity_2m"),
            "code": int(cur.get("weather_code", 0) or 0),
            "is_day": is_day,
            "wind": round(float(cur.get("wind_speed_10m", 0) or 0) / 3.6, 1),
            "wdir": cur.get("wind_direction_10m") or 0,
            "pres": round(float(cur.get("pressure_msl", 1013) or 1013) * 0.750062),
            "cloud": cur.get("cloud_cover"),
        },
        "hours": hours,
        "days": days,
        "sunrise": _hhmm(daily["sunrise"][0]),
        "sunset": _hhmm(daily["sunset"][0]),
        "uv": uv,
        "now_local": now_local.strftime("%H:%M"),
    }


# ---------------------------------------------------------------------- #
#  Источник 2: MET Norway / yr.no (без ключа)
# ---------------------------------------------------------------------- #
def _fetch_met(lat: float, lon: float) -> dict:
    r = requests.get(
        "https://api.met.no/weatherapi/locationforecast/2.0/compact",
        params={"lat": f"{lat:.4f}", "lon": f"{lon:.4f}"},
        timeout=WX_TIMEOUT, headers=UA)
    r.raise_for_status()
    j = r.json()
    series = j["properties"]["timeseries"]

    now_utc = dt.datetime.now(dt.timezone.utc)
    now_local = now_utc.astimezone()
    entries = []
    for e in series:
        when = dt.datetime.fromisoformat(e["time"].replace("Z", "+00:00"))
        entries.append((when, e))
    entries.sort(key=lambda x: x[0])

    def details(e):
        return (e["data"].get("instant") or {}).get("details") or {}

    def symbol(e):
        n1 = e["data"].get("next_1_hours") or {}
        return (n1.get("summary") or {}).get("symbol_code") or ""

    # --- текущие условия: ближайший по времени прогноз ---
    _, ce = min(entries, key=lambda x: abs((x[0] - now_utc).total_seconds()))
    det = details(ce)
    temp = det.get("air_temperature")
    cur_code_sym = symbol(ce)
    if not cur_code_sym:
        for _, e in entries:
            if e is ce:
                continue
            if symbol(e):
                cur_code_sym = symbol(e)
                break
    cur_code = met_symbol_to_wmo(cur_code_sym)
    wind = det.get("wind_speed")
    wdir = det.get("wind_from_direction") or 0
    hum = det.get("relative_humidity")
    pres_hpa = det.get("air_pressure_at_sea_level")
    cloud = det.get("cloud_area_fraction")
    feels = temp
    if temp is not None:
        feels = round(temp - max(0.0, (wind or 0.0) - 1.5) * 0.6)

    # --- по часам: 10 записей от текущего часа ---
    hours = []
    for when, e in entries:
        local = when.astimezone()
        if local < now_local.replace(minute=0, second=0, microsecond=0):
            continue
        if len(hours) >= 10:
            break
        d = details(e)
        t = d.get("air_temperature")
        if t is None:
            continue
        hours.append({
            "time": local.strftime("%H:00"),
            "temp": round(t),
            "code": met_symbol_to_wmo(symbol(e)),
            "pop": 0,
        })

    # --- по дням: 5 дней, мин/макс по часам, символ дня ~ 13:00 ---
    by_day: dict = {}
    for when, e in entries:
        local = when.astimezone()
        d = details(e)
        t = d.get("air_temperature")
        if t is None:
            continue
        by_day.setdefault(local.date(), []).append(
            (local.hour, t, symbol(e)))
    days = []
    today = now_local.date()
    for i in range(5):
        day = today + dt.timedelta(days=i)
        rows = by_day.get(day) or []
        if not rows:
            break
        temps = [t for _, t, _ in rows]
        mid = min(rows, key=lambda r: abs(r[0] - 13))
        code = met_symbol_to_wmo(mid[2] if mid[2] else rows[len(rows) // 2][2])
        days.append({
            "label": f"{i18n.wd_short(day.weekday())} {day.day:02d}",
            "code": code,
            "min": round(min(temps)),
            "max": round(max(temps)),
            "pop": 0,
        })

    # --- восход/закат (отдельный запрос, при ошибке — «—») ---
    sunrise = sunset = "—"
    try:
        r2 = requests.get(
            "https://api.met.no/weatherapi/sunrise/3.0/sun",
            params={"lat": f"{lat:.4f}", "lon": f"{lon:.4f}",
                    "date": today.isoformat()},
            timeout=GEO_TIMEOUT, headers=UA)
        props = (r2.json() or {}).get("properties") or {}
        sunrise = _hhmm((props.get("sunrise") or {}).get("time") or "—")
        sunset = _hhmm((props.get("sunset") or {}).get("time") or "—")
    except Exception:
        pass

    return {
        "cur": {
            "temp": round(temp) if temp is not None else 0,
            "feels": round(feels) if feels is not None else 0,
            "hum": round(hum) if hum is not None else None,
            "code": cur_code,
            "is_day": _is_day_solar(lat, lon, now_utc),
            "wind": round(float(wind or 0), 1),
            "wdir": wdir,
            "pres": round(float(pres_hpa or 1013) * 0.750062),
            "cloud": round(cloud) if cloud is not None else None,
        },
        "hours": hours,
        "days": days,
        "sunrise": sunrise,
        "sunset": sunset,
        "uv": None,
        "now_local": now_local.strftime("%H:%M"),
    }


# ---------------------------------------------------------------------- #
#  Источник 3: Яндекс Погода (нужен ключ)
# ---------------------------------------------------------------------- #
def _fetch_yandex(lat: float, lon: float, key: str) -> dict:
    if not key:
        raise RuntimeError("Yandex key is not set")
    r = requests.get(
        "https://api.weather.yandex.ru/v2/forecast",
        params={"lat": f"{lat:.4f}", "lon": f"{lon:.4f}", "lang": "ru_RU",
                "limit": "7", "hours": "true"},
        headers={"X-Yandex-Weather-Key": key, "X-Yandex-API-Key": key, **UA},
        timeout=WX_TIMEOUT)
    r.raise_for_status()
    j = r.json()

    fact = j.get("fact") or {}
    fc = j.get("forecasts") or []
    now_local = dt.datetime.now()
    is_day = fact.get("daytime") != "n"
    code = _YANDEX_WMO.get(fact.get("condition"), 3)
    cloud = fact.get("cloudness")
    uv = fact.get("uvi")

    hours = []
    if fc:
        for h in (fc[0].get("hours") or []):
            try:
                if int(h.get("hour", 0)) < now_local.hour:
                    continue
            except Exception:
                pass
            hours.append(h)
        k = 1
        while len(hours) < 10 and k < len(fc):
            hours += (fc[k].get("hours") or [])
            k += 1
    hours = [{
        "time": f"{int(h.get('hour', 0)):02d}:00",
        "temp": round(float(h.get("temp") or 0)),
        "code": _YANDEX_WMO.get(h.get("condition"), 3),
        "pop": int(h.get("prec_prob") or 0),
    } for h in hours[:10]]

    days = []
    for f in fc[:5]:
        parts = f.get("parts") or {}
        ds = parts.get("day_short") or {}
        ns = parts.get("night_short") or {}
        if not ds:
            continue
        day = dt.date.fromisoformat(f.get("date") or now_local.date().isoformat())
        pop = (parts.get("day") or {}).get("prec_prob") or ds.get("prec_prob") or 0
        days.append({
            "label": f"{i18n.wd_short(day.weekday())} {day.day:02d}",
            "code": _YANDEX_WMO.get(ds.get("condition"), 3),
            "min": round(float(ns.get("temp", ds.get("temp", 0)))),
            "max": round(float(ds.get("temp", 0))),
            "pop": int(pop or 0),
        })

    return {
        "cur": {
            "temp": round(float(fact.get("temp") or 0)),
            "feels": round(float(fact.get("feels_like") or 0)),
            "hum": fact.get("humidity"),
            "code": code,
            "is_day": is_day,
            "wind": round(float(fact.get("wind_speed") or 0), 1),
            "wdir": _YANDEX_DIR.get(fact.get("wind_dir"), 0),
            "pres": round(float(fact.get("pressure_mm") or 746)),
            "cloud": round(cloud * 100) if cloud is not None else None,
        },
        "hours": hours,
        "days": days,
        "sunrise": fc[0].get("sunrise", "—") if fc else "—",
        "sunset": fc[0].get("sunset", "—") if fc else "—",
        "uv": round(float(uv), 1) if uv is not None else None,
        "now_local": now_local.strftime("%H:%M"),
    }


# ---------------------------------------------------------------------- #
#  Диспетчер: выбирает источник с резервами
# ---------------------------------------------------------------------- #
def fetch_forecast(lat: float, lon: float,
                   source: str = "auto", yandex_key: str | None = None) -> dict:
    """Прогноз с любого доступного источника. RuntimeError если сеть недоступна."""
    key = (yandex_key or "").strip()
    if source == "yandex" and key:
        chain = ("yandex", "met", "open-meteo")
    elif source == "yandex":
        chain = ("met", "open-meteo")
    elif source == "open-meteo":
        chain = ("open-meteo", "met", "yandex") if key else ("open-meteo", "met")
    else:
        chain = ("open-meteo", "met", "yandex") if key else ("open-meteo", "met")

    names = {"open-meteo": "Open-Meteo", "met": "MET Norway (yr.no)",
             "yandex": i18n.t("wx_yandex_name")}
    last_err: Exception | None = None
    for name in chain:
        try:
            if name == "open-meteo":
                data = _fetch_open_meteo(lat, lon)
            elif name == "met":
                data = _fetch_met(lat, lon)
            else:
                data = _fetch_yandex(lat, lon, key)
            data["source"] = names[name]
            return data
        except Exception as ex:  # noqa: BLE001
            last_err = ex
    raise last_err or RuntimeError("all weather sources failed")


def fake_forecast() -> dict:
    """Демо-данные без сети (отладка: переменная окружения PW_FAKE_WEATHER=1)."""
    now = dt.datetime.now()
    codes = [2, 3, 2, 61, 3, 2, 1, 0, 1, 2]
    pops = [0, 10, 20, 70, 45, 10, 0, 5, 10, 15]
    hours = []
    for i in range(10):
        hh = (now.hour + i) % 24
        t = 9 + ((i * 3) % 7) - 2
        hours.append({"time": f"{hh:02d}:00", "temp": t,
                      "code": codes[i], "pop": pops[i]})
    codes_d = [3, 61, 0, 2, 71]
    pops_d = [30, 80, 0, 10, 60]
    days = []
    for i in range(5):
        d = dt.date.today() + dt.timedelta(days=i)
        days.append({"label": f"{i18n.wd_short(d.weekday())} {d.day:02d}",
                     "code": codes_d[i], "min": 2 + i % 3,
                     "max": 8 + (i * 3) % 7, "pop": pops_d[i]})
    return {
        "cur": {"temp": 7, "feels": 4, "hum": 82, "code": 61, "is_day": True,
                "wind": 4.6, "wdir": 225, "pres": 742, "cloud": 90},
        "hours": hours, "days": days,
        "sunrise": "07:42", "sunset": "16:58", "uv": 1.4,
        "now_local": now.strftime("%H:%M"),
        "source": i18n.t("demo"),
    }
