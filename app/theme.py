"""Палитры Material You (6 штук) + тёмная/светлая варианты.

Ключи цвета:
  surface               — фон карточки
  container             — фон меню и диалогов
  primary / on_primary  — акцент и текст поверх акцента
  secondary / tertiary  — дополнительные акценты (графики)
  secondary_container / on_secondary_container — плашки
  on_surface            — основной текст
  on_surface_variant    — второстепенный текст
  outline               — линии, разделители
  error                 — выходные дни, ошибки
"""
from __future__ import annotations

PALETTES: dict = {
    "pixel_blue": {
        "name": "Синий Pixel",
        "dark": {
            "surface": "#17191E", "container": "#22252D",
            "primary": "#A8C7FA", "on_primary": "#062E6F",
            "secondary": "#7FD8BE", "tertiary": "#EFB8C8",
            "secondary_container": "#414960", "on_secondary_container": "#DCE1F9",
            "on_surface": "#E2E2E9", "on_surface_variant": "#C3C6CF",
            "outline": "#8E9099", "error": "#FFB4AB",
        },
        "light": {
            "surface": "#F9F9FE", "container": "#ECEDF4",
            "primary": "#0B57D0", "on_primary": "#FFFFFF",
            "secondary": "#0A6C5E", "tertiary": "#8F3F62",
            "secondary_container": "#D9E2FF", "on_secondary_container": "#0A1D45",
            "on_surface": "#191C20", "on_surface_variant": "#44474E",
            "outline": "#74777F", "error": "#B3261E",
        },
    },
    "sage": {
        "name": "Зелёный Sage",
        "dark": {
            "surface": "#181B18", "container": "#222621",
            "primary": "#AED3A4", "on_primary": "#1C3B20",
            "secondary": "#E7C79B", "tertiary": "#A6C8E8",
            "secondary_container": "#334234", "on_secondary_container": "#D3E8CD",
            "on_surface": "#E0E4DB", "on_surface_variant": "#BFC9BB",
            "outline": "#899388", "error": "#FFB4AB",
        },
        "light": {
            "surface": "#F9FBF3", "container": "#EAEEE3",
            "primary": "#38693C", "on_primary": "#FFFFFF",
            "secondary": "#7A5A10", "tertiary": "#4A6584",
            "secondary_container": "#D5E8CF", "on_secondary_container": "#0E2012",
            "on_surface": "#1A1C19", "on_surface_variant": "#43483F",
            "outline": "#73796F", "error": "#B3261E",
        },
    },
    "sand": {
        "name": "Песочный",
        "dark": {
            "surface": "#1C1917", "container": "#272320",
            "primary": "#E6C38A", "on_primary": "#402D12",
            "secondary": "#A8C7FA", "tertiary": "#EFB8AB",
            "secondary_container": "#4B4034", "on_secondary_container": "#F5DFC6",
            "on_surface": "#ECE0D4", "on_surface_variant": "#D0C5B8",
            "outline": "#998F83", "error": "#FFB4AB",
        },
        "light": {
            "surface": "#FCF8F3", "container": "#F0EBE1",
            "primary": "#755B2A", "on_primary": "#FFFFFF",
            "secondary": "#35609F", "tertiary": "#964B3E",
            "secondary_container": "#F0E0C8", "on_secondary_container": "#251A04",
            "on_surface": "#1E1B16", "on_surface_variant": "#4D4639",
            "outline": "#7F766A", "error": "#B3261E",
        },
    },
    "lavender": {
        "name": "Лавандовый",
        "dark": {
            "surface": "#16161D", "container": "#201F29",
            "primary": "#C9C3FF", "on_primary": "#30296D",
            "secondary": "#9CD8CE", "tertiary": "#F3B9D3",
            "secondary_container": "#3B3659", "on_secondary_container": "#E2DEFF",
            "on_surface": "#E5E1EC", "on_surface_variant": "#C8C4D6",
            "outline": "#928F9F", "error": "#FFB4AB",
        },
        "light": {
            "surface": "#FCF8FF", "container": "#EFECF8",
            "primary": "#544BA7", "on_primary": "#FFFFFF",
            "secondary": "#2C6E64", "tertiary": "#8E446E",
            "secondary_container": "#E4DFFF", "on_secondary_container": "#1C1746",
            "on_surface": "#1B1B21", "on_surface_variant": "#47464F",
            "outline": "#77767F", "error": "#B3261E",
        },
    },
    "rose": {
        "name": "Розовый",
        "dark": {
            "surface": "#1B1517", "container": "#251D20",
            "primary": "#FFB1C1", "on_primary": "#5D1126",
            "secondary": "#B5C7FF", "tertiary": "#E5C49E",
            "secondary_container": "#4C2F3B", "on_secondary_container": "#FFD9E1",
            "on_surface": "#EBDFE2", "on_surface_variant": "#D3C2C7",
            "outline": "#9C8C91", "error": "#FFB4AB",
        },
        "light": {
            "surface": "#FFF8F8", "container": "#F4EDEF",
            "primary": "#A2385A", "on_primary": "#FFFFFF",
            "secondary": "#3F5FA5", "tertiary": "#7C5A34",
            "secondary_container": "#FFD9E1", "on_secondary_container": "#3E001D",
            "on_surface": "#201A1C", "on_surface_variant": "#514347",
            "outline": "#837377", "error": "#B3261E",
        },
    },
    "ocean": {
        "name": "Океан",
        "dark": {
            "surface": "#13181B", "container": "#1D2428",
            "primary": "#87CDFF", "on_primary": "#003257",
            "secondary": "#9FD4C0", "tertiary": "#F2B8CF",
            "secondary_container": "#30414D", "on_secondary_container": "#CDE5FB",
            "on_surface": "#DDE3E8", "on_surface_variant": "#BFC8CE",
            "outline": "#889299", "error": "#FFB4AB",
        },
        "light": {
            "surface": "#F6FAFD", "container": "#E9EFF3",
            "primary": "#0563A8", "on_primary": "#FFFFFF",
            "secondary": "#256B5D", "tertiary": "#8F4068",
            "secondary_container": "#CBE6FF", "on_secondary_container": "#001E33",
            "on_surface": "#181C20", "on_surface_variant": "#41484D",
            "outline": "#71787D", "error": "#B3261E",
        },
    },
}

DEFAULT_PALETTE = "pixel_blue"


class _Theme:
    """Текущая активная палитра. Виджеты читают цвета через C(key)."""

    def __init__(self) -> None:
        self.palette_id: str = DEFAULT_PALETTE
        self.dark: bool = True
        self._colors: dict = PALETTES[DEFAULT_PALETTE]["dark"]

    def apply(self, palette_id: str | None, dark: bool | None) -> None:
        pid = palette_id if palette_id in PALETTES else DEFAULT_PALETTE
        self.palette_id = pid
        self.dark = bool(dark)
        self._colors = PALETTES[pid]["dark" if self.dark else "light"]

    def c(self, key: str) -> str:
        return self._colors.get(key, "#FF00FF")


THEME = _Theme()


def apply(palette_id: str | None, dark: bool | None) -> None:
    THEME.apply(palette_id, dark)


def C(key: str) -> str:
    """Цвет активной темы по имени ключа."""
    return THEME.c(key)
