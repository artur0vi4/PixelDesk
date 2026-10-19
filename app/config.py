"""Настройки PixelDesk: значения по умолчанию, загрузка и сохранение JSON.

Файл настроек:
  Windows: %APPDATA%\\PixelDesk\\config.json
  Прочие:  ~/.config/PixelDesk/config.json
"""
from __future__ import annotations

import copy
import json
import os
import shutil

APP_NAME = "PixelDesk"
APP_VERSION = "1.1.1"
APP_AUTHOR = "Artur (artur0vi4)"
APP_URL = "https://github.com/artur0vi4/PixelDesk"

# Старое имя программы — для автоматического переноса настроек
_LEGACY_APP_NAME = "PixelWidgets"

CONFIG_DIR = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~/.config"), APP_NAME
)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.join(CONFIG_DIR, "error.log")


def _migrate_legacy() -> None:
    """Разовый перенос настроек из %APPDATA%\\PixelWidgets (старое имя)."""
    try:
        if os.path.exists(CONFIG_PATH):
            return
        base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
        old = os.path.join(base, _LEGACY_APP_NAME, "config.json")
        if os.path.isfile(old):
            os.makedirs(CONFIG_DIR, exist_ok=True)
            shutil.copyfile(old, CONFIG_PATH)
    except Exception:
        pass

DEFAULTS: dict = {
    "theme": {"palette": "pixel_blue", "dark": True},
    "widgets": {
        "clock":    {"enabled": True, "x": None, "y": None, "w": 330, "h": 150,
                     "scale": 1.0, "on_top": True, "opacity": 0.96},
        "date":     {"enabled": True, "x": None, "y": None, "w": 340, "h": 112,
                     "scale": 1.0, "on_top": True, "opacity": 0.96},
        "calendar": {"enabled": True, "x": None, "y": None, "w": 330, "h": 386,
                     "scale": 1.0, "on_top": True, "opacity": 0.96},
        "weather":  {"enabled": True, "x": None, "y": None, "w": 364, "h": 588,
                     "scale": 1.0, "on_top": True, "opacity": 0.96},
        "system":   {"enabled": True, "x": None, "y": None, "w": 344, "h": 334,
                     "scale": 1.0, "on_top": True, "opacity": 0.96},
    },
    "weather": {"city": None, "lat": None, "lon": None, "manual": False,
                "refresh_min": 15, "source": "auto", "yandex_key": None},
    "autostart": False,
    "hidden_all": False,
}


def _merge(base: dict, extra: dict) -> dict:
    """Рекурсивно накладывает extra поверх копии base."""
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    """Загружает настройки, дополняя недостающие значения по умолчанию."""
    _migrate_legacy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    return _merge(DEFAULTS, data)


def save(cfg: dict) -> None:
    """Атомарно сохраняет настройки."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except Exception:
        pass


def log_error(msg: str) -> None:
    """Пишет ошибку в error.log рядом с настройками (для диагностики)."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass
