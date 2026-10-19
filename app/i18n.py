"""Двуязычный интерфейс PixelDesk: русский и английский.

Язык выбирается автоматически по языку системы (настройка ui.lang =
"auto"), либо принудительно в трее: Язык / Language -> Русский/English.

Модуль самостоятельный (без импортов из пакета app), чтобы его можно
было использовать и из weather_api (уровень данных), и из виджетов.
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------- #
#  Тексты
# ---------------------------------------------------------------------- #
STR: dict[str, dict[str, str]] = {
    "ru": {
        # виджеты (заголовки окон и пункты трея)
        "w_clock": "Часы",
        "w_clock_analog": "Аналоговые часы",
        "w_date": "Дата и день недели",
        "w_calendar": "Календарь",
        "w_weather": "Погода",
        "w_system": "Загрузка системы",
        # меню виджета
        "on_top": "Поверх всех окон",
        "opacity": "Прозрачность",
        "zoom": "Масштаб",
        "refresh": "Обновить",
        "hide_widget": "Скрыть виджет",
        # трей
        "hide_all": "Скрыть все виджеты",
        "show_all": "Показать все виджеты",
        "m_widgets": "Виджеты",
        "m_theme": "Тема",
        "th_dark": "Тёмная",
        "th_light": "Светлая",
        "lang_auto": "Авто",
        "autostart": "Автозапуск с Windows",
        "refresh_wx": "Обновить погоду",
        "about": "О программе",
        "quit": "Выход",
        # палитры
        "pal_pixel_blue": "Синий Pixel",
        "pal_sage": "Зелёный Sage",
        "pal_sand": "Песочный",
        "pal_lavender": "Лавандовый",
        "pal_rose": "Розовый",
        "pal_ocean": "Океан",
        # «О программе» и диалоги
        "about_title": "О {name}",
        "about_body": ("<h3>{name} {ver}</h3>"
                       "<p>Виджеты рабочего стола в стиле Material You "
                       "(Google Pixel) для Windows: часы, дата, календарь, "
                       "погода и монитор системы.</p>"
                       "<p>Автор: <b>{author}</b><br>GitHub: {url}</p>"
                       "<p>Лицензия MIT &middot; 2026</p>"),
        "started_msg": ("Виджеты запущены. Меню — правый клик по виджету "
                        "или по иконке в трее."),
        "stale_found": ("Обнаружена запущенная старая копия {name}:\n{names}\n\n"
                        "Завершить её и запустить текущую версию?"),
        "already_running": ("{name} уже запущен (иконка в трее).\n\n"
                            "Если иконки не видно — она в скрытой области трея "
                            "(стрелка ^ возле часов).\n"
                            "Либо завершите старую копию через Диспетчер задач "
                            "({exe} / python.exe)."),
        "autostart_win_only": "Автозапуск доступен только в Windows.",
        # виджет «Дата»
        "greet_morning": "Доброе утро",
        "greet_day": "Добрый день",
        "greet_evening": "Добрый вечер",
        "greet_night": "Доброй ночи",
        # календарь
        "cal_today": "К текущему месяцу",
        # монитор системы
        "lbl_cpu": "Процессор",
        "lbl_ram": "Память",
        "lbl_gpu": "Видеокарта",
        "lbl_net": "Сеть ↓↑",
        "unit_mbit": "Мбит/с",
        # погода: статусы
        "wx_locating": "Определение местоположения…",
        "wx_updating": "Обновление…",
        "wx_loading": "Загрузка…",
        "wx_offline": "Нет сети",
        "wx_updated": "Обновлено в {time} · {src}",
        "wx_data_from": "данные от {time}",
        "wx_default_city": " (город по умолчанию)",
        "wx_city_updating": "Город: {city} — обновление…",
        "wx_city_not_found": "Город «{q}» не найден",
        "wx_searching": "Поиск: {q}…",
        "wx_src_changed": "Источник изменён — обновление…",
        "wx_key_saved": "Ключ сохранён — обновление…",
        "wx_key_removed": "Ключ удалён — обновление…",
        # погода: меню и диалоги
        "wx_change_city": "Сменить город…",
        "wx_change_city_title": "Сменить город",
        "wx_city_prompt": "Название города:",
        "wx_source": "Источник погоды",
        "wx_src_auto": "Авто (с резервами)",
        "wx_src_yandex": "Яндекс Погода",
        "wx_key_menu": "Ключ Яндекс Погоды…",
        "wx_key_title": "Ключ Яндекс Погоды",
        "wx_key_prompt": "Ключ (бесплатный: yandex.ru/dev/weather, 50 зап./день):",
        # погода: подписи
        "lbl_feels": "Ощущается",
        "lbl_wind": "Ветер",
        "lbl_hum": "Влажность",
        "lbl_pres": "Давление",
        "lbl_uv": "УФ-индекс",
        "lbl_cloud": "Облачность",
        "unit_ms": "м/с",
        "unit_mm": "мм",
        "city_moscow": "Москва",
        "wx_yandex_name": "Яндекс Погода",
        "demo": "Демо",
    },
    "en": {
        "w_clock": "Clock",
        "w_clock_analog": "Analog clock",
        "w_date": "Date & weekday",
        "w_calendar": "Calendar",
        "w_weather": "Weather",
        "w_system": "System monitor",
        "on_top": "Always on top",
        "opacity": "Opacity",
        "zoom": "Zoom",
        "refresh": "Refresh",
        "hide_widget": "Hide widget",
        "hide_all": "Hide all widgets",
        "show_all": "Show all widgets",
        "m_widgets": "Widgets",
        "m_theme": "Theme",
        "th_dark": "Dark",
        "th_light": "Light",
        "lang_auto": "Auto",
        "autostart": "Run at Windows startup",
        "refresh_wx": "Refresh weather",
        "about": "About",
        "quit": "Quit",
        "pal_pixel_blue": "Pixel Blue",
        "pal_sage": "Sage",
        "pal_sand": "Sand",
        "pal_lavender": "Lavender",
        "pal_rose": "Rose",
        "pal_ocean": "Ocean",
        "about_title": "About {name}",
        "about_body": ("<h3>{name} {ver}</h3>"
                       "<p>Material You (Google Pixel) style desktop widgets "
                       "for Windows: clock, date, calendar, weather and a "
                       "system monitor.</p>"
                       "<p>Author: <b>{author}</b><br>GitHub: {url}</p>"
                       "<p>MIT license &middot; 2026</p>"),
        "started_msg": ("Widgets are running. Right-click any widget or the "
                        "tray icon for the menu."),
        "stale_found": ("An old copy of {name} is already running:\n{names}\n\n"
                        "Close it and start the current version?"),
        "already_running": ("{name} is already running (tray icon).\n\n"
                            "If you don't see the icon, check the hidden tray "
                            "area (the ^ arrow near the clock).\n"
                            "Or close the old copy in Task Manager "
                            "({exe} / python.exe)."),
        "autostart_win_only": "Autostart is only available on Windows.",
        "greet_morning": "Good morning",
        "greet_day": "Good afternoon",
        "greet_evening": "Good evening",
        "greet_night": "Good night",
        "cal_today": "Back to current month",
        "lbl_cpu": "CPU",
        "lbl_ram": "RAM",
        "lbl_gpu": "GPU",
        "lbl_net": "Network ↓↑",
        "unit_mbit": "Mbit/s",
        "wx_locating": "Detecting location…",
        "wx_updating": "Updating…",
        "wx_loading": "Loading…",
        "wx_offline": "Offline",
        "wx_updated": "Updated at {time} · {src}",
        "wx_data_from": "data from {time}",
        "wx_default_city": " (default city)",
        "wx_city_updating": "City: {city} — updating…",
        "wx_city_not_found": "City \u201c{q}\u201d not found",
        "wx_searching": "Searching: {q}…",
        "wx_src_changed": "Source changed — updating…",
        "wx_key_saved": "Key saved — updating…",
        "wx_key_removed": "Key removed — updating…",
        "wx_change_city": "Change city…",
        "wx_change_city_title": "Change city",
        "wx_city_prompt": "City name:",
        "wx_source": "Weather source",
        "wx_src_auto": "Auto (with fallback)",
        "wx_src_yandex": "Yandex Weather",
        "wx_key_menu": "Yandex Weather key…",
        "wx_key_title": "Yandex Weather key",
        "wx_key_prompt": "Key (free at yandex.ru/dev/weather, 50 req/day):",
        "lbl_feels": "Feels like",
        "lbl_wind": "Wind",
        "lbl_hum": "Humidity",
        "lbl_pres": "Pressure",
        "lbl_uv": "UV index",
        "lbl_cloud": "Cloudiness",
        "unit_ms": "m/s",
        "unit_mm": "mmHg",
        "city_moscow": "Moscow",
        "wx_yandex_name": "Yandex Weather",
        "demo": "Demo",
    },
}

# ---------------------------------------------------------------------- #
#  Таблицы дат (падежи в русском нельзя собрать из шаблона)
# ---------------------------------------------------------------------- #
_WD_FULL = {
    "ru": ("Понедельник", "Вторник", "Среда", "Четверг",
           "Пятница", "Суббота", "Воскресенье"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday",
           "Friday", "Saturday", "Sunday"),
}
_WD_SHORT = {
    "ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}
_MONTH_NOM = {
    "ru": ("Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
           "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"),
    "en": ("January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"),
}
_MONTH_GEN = {
    "ru": ("января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"),
    "en": _MONTH_NOM["en"],
}
_WIND = {
    "ru": ("С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"),
    "en": ("N", "NE", "E", "SE", "S", "SW", "W", "NW"),
}

# id палитры -> ключ перевода
PAL_KEYS = {
    "pixel_blue": "pal_pixel_blue",
    "sage": "pal_sage",
    "sand": "pal_sand",
    "lavender": "pal_lavender",
    "rose": "pal_rose",
    "ocean": "pal_ocean",
}

# ---------------------------------------------------------------------- #
#  Состояние и API
# ---------------------------------------------------------------------- #
_LANG = "ru"   # до init()/set_lang() работаем по-русски (совместимость тестов)


def detect() -> str:
    """Язык системы: 'ru', если системная локаль русская, иначе 'en'."""
    try:
        from PySide6.QtCore import QLocale
        if QLocale.system().language() == QLocale.Language.Russian:
            return "ru"
    except Exception:
        pass
    return "en"


def init(setting: str | None) -> str:
    """Применяет настройку ui.lang: 'auto' | 'ru' | 'en'.
    Переменная окружения PW_LANG (ru/en) имеет приоритет —
    используется в тестах на системах без русской локали."""
    global _LANG
    env = os.environ.get("PW_LANG")
    if env in ("ru", "en"):
        _LANG = env
    else:
        _LANG = setting if setting in ("ru", "en") else detect()
    return _LANG


def set_lang(lang: str) -> str:
    """Принудительная смена языка (тесты, переключатель в трее)."""
    global _LANG
    if lang in ("ru", "en"):
        _LANG = lang
    return _LANG


def current() -> str:
    return _LANG


def t(key: str, **kw) -> str:
    """Перевод по ключу; при отсутствии — русский, затем сам ключ."""
    v = (STR.get(_LANG) or {}).get(key)
    if v is None:
        v = STR["ru"].get(key, key)
    return v.format(**kw) if kw else v


def wd_full(i: int) -> str:
    return _WD_FULL[_LANG][i % 7]


def wd_short(i: int) -> str:
    return _WD_SHORT[_LANG][i % 7]


def month_nom(i: int) -> str:
    """Именительный падеж: «Октябрь» / «October» (заголовок календаря)."""
    return _MONTH_NOM[_LANG][i % 12]


def month_gen(i: int) -> str:
    """Родительный падеж: «октября» / «October» (строка даты)."""
    return _MONTH_GEN[_LANG][i % 12]


def wind_dir_name(i: int) -> str:
    return _WIND[_LANG][i % 8]


def date_line(weekday: int, day: int, month0: int) -> str:
    """Строка 1 виджета «Дата»: ru «Понедельник, 19 октября»,
    en «Monday, October 19». month0 — месяц от 0."""
    if _LANG == "ru":
        return f"{_WD_FULL['ru'][weekday]}, {day} {_MONTH_GEN['ru'][month0]}"
    return f"{_WD_FULL['en'][weekday]}, {_MONTH_NOM['en'][month0]} {day}"
