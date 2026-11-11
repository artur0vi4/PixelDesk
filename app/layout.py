"""Расстановка виджетов: раскладка по умолчанию, подгонка под экран, профили.

Модуль намеренно НЕ импортирует Qt: вся геометрия считается над обычными
числами (x, y, w, h в пикселях рабочего стола), поэтому раскладку и проверку
«улетел ли виджет за экран» можно тестировать без графической среды.
main.py переводит результат в QRect/QPoint.

Термины:
  area      — доступная область экрана (availableGeometry);
  rect      — прямоугольник карточки (x, y, w, h);
  reachable — карточку видно настолько, что за неё можно схватиться мышью.
"""
from __future__ import annotations

import time

# Отступы раскладки по умолчанию (пиксели рабочего стола).
MARGIN = 18        # от края экрана до карточек
GAP = 14           # между карточками в колонке
COL_GAP = 24       # между колонками
MIN_VISIBLE = 96   # минимум видимой ширины карточки
MIN_TITLE = 40     # минимум видимой полосы сверху (за неё тащат мышью)

# Поля профиля расстановки: их и только их запоминаем/восстанавливаем.
FIELDS = ("x", "y", "w", "h", "scale", "enabled")

Rect = tuple  # (x, y, w, h) — числа в пикселях рабочего стола


# ---------------------------------------------------------------------- #
#  Видимость карточки на экране
# ---------------------------------------------------------------------- #
def _intersection(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def is_reachable(rect: Rect, area: Rect,
                 min_w: float = MIN_VISIBLE, min_h: float = MIN_TITLE) -> bool:
    """True, если карточку можно увидеть и схватить мышью.

    Достаточно, чтобы на экране остались min_w по ширине и верхняя полоса
    min_h — именно за неё виджет перетаскивают, поэтому «торчащий» снизу
    угол бесполезен.
    """
    x, y, w, h = rect
    ax, ay, aw, ah = area
    if w <= 0 or h <= 0:
        return False
    ix = _intersection(x, x + w, ax, ax + aw)
    strip = _intersection(y, y + min(h, min_h), ay, ay + ah)
    return ix >= min(min_w, w) and strip >= min(min_h, h)


def clamp_rect(rect: Rect, area: Rect, margin: int = MARGIN) -> Rect:
    """Сдвигает прямоугольник внутрь area, сохраняя размер.

    Если карточка больше экрана, прижимаем её к левому-верхнему углу —
    дальше она вылезет вправо-вниз, но верхний левый угол останется
    доступным.
    """
    x, y, w, h = rect
    ax, ay, aw, ah = area
    left = ax + margin
    top = ay + margin
    nx = min(max(x, left), max(left, ax + aw - margin - w))
    ny = min(max(y, top), max(top, ay + ah - margin - h))
    return nx, ny, w, h


def ensure_reachable(rect: Rect, areas: list, fallback: Rect) -> Rect:
    """Возвращает rect, если он виден хотя бы на одном экране.

    Иначе — переносит карточку на fallback-экран (обычно основной), чтобы
    после смены монитора или неудачного перетаскивания она не пропала.
    """
    if any(is_reachable(rect, a) for a in areas):
        return tuple(rect)
    return clamp_rect(rect, fallback)


# ---------------------------------------------------------------------- #
#  Раскладка по умолчанию
# ---------------------------------------------------------------------- #
def default_positions(order, sizes: dict, area: Rect,
                      gap: int = GAP, margin: int = MARGIN,
                      col_gap: int = COL_GAP) -> dict:
    """Расставляет карточки колонками у правого края экрана.

    order — порядок виджетов, sizes — {ключ: (ширина, высота)}.
    Колонки набираются сверху вниз, пока влезают по высоте; следующая
    колонка уходит влево. Внутри колонки карточки прижаты к её правому краю,
    поэтому ряд выглядит ровно при разной ширине виджетов.

    Если на маленьком экране (1366×768) колонки не влезают по ширине —
    пробуем тесные отступы: лучше плотнее, чем карточка за краем.
    """
    keys = [k for k in order if k in sizes]
    if not keys:
        return {}
    out: dict = {}
    for g, mg, cg in ((gap, margin, col_gap), (8, 8, 8)):
        out = _pack(keys, sizes, area, g, mg, cg)
        if min(x for x, _ in out.values()) >= area[0] + mg:
            break
    return out


def _pack(keys: list, sizes: dict, area: Rect,
          gap: int, margin: int, col_gap: int) -> dict:
    """Раскладка колонками с заданными отступами (один шаг подбора)."""
    ax, ay, aw, ah = area
    inner_h = max(1, ah - 2 * margin)

    # 1. Разбиение на колонки «первым подходящим» способом.
    columns: list[list[str]] = []
    current: list[str] = []
    used = 0
    for key in keys:
        h = sizes[key][1]
        add = h if not current else gap + h
        if current and used + add > inner_h:
            columns.append(current)
            current, used = [key], h
        else:
            current.append(key)
            used += add
    if current:
        columns.append(current)

    # 2. Координаты: справа налево, каждая колонка — по своей ширине.
    out: dict = {}
    right = ax + aw - margin
    for col in reversed(columns):
        col_w = max(sizes[k][0] for k in col)
        y = ay + margin
        for key in col:
            w, h = sizes[key]
            ny = min(y, ay + ah - margin - h)
            out[key] = (right - w, max(ay + margin, ny))
            y += h + gap
        right -= col_w + col_gap
    return out


def find_free_spot(w: int, h: int, occupied: list, area: Rect,
                   gap: int = GAP, margin: int = MARGIN,
                   step: int = 24, columns: int = 4) -> tuple:
    """Свободное место для одной новой карточки (включили виджет в трее).

    Идём колонками справа налево и сверху вниз с шагом step, пока карточка
    не перестанет пересекаться с уже стоящими. Если места нет совсем —
    ставим в правый верхний угол (пусть лучше перекроет, чем пропадёт).
    """
    ax, ay, aw, ah = area
    for col in range(max(1, columns)):
        x = ax + aw - margin - w - col * (w + gap)
        if x < ax + margin:
            break
        y = ay + margin
        while y + h <= ay + ah - margin:
            r = (x, y, w, h)
            if not any(_overlaps(r, o) for o in occupied):
                return x, y
            y += step
    return ax + aw - margin - w, ay + margin


def _overlaps(a: Rect, b: Rect) -> bool:
    """Пересекаются ли прямоугольники (касание не считается)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah)


# ---------------------------------------------------------------------- #
#  Профили расстановки («Сохранить расстановку»)
# ---------------------------------------------------------------------- #
def capture(widgets_cfg: dict) -> dict:
    """Снимок геометрии всех виджетов для config.json."""
    return {
        key: {f: wc.get(f) for f in FIELDS}
        for key, wc in (widgets_cfg or {}).items()
    }


def restore(widgets_cfg: dict, snapshot: dict) -> None:
    """Накладывает снимок на настройки виджетов (лишние ключи игнорируются)."""
    for key, data in (snapshot or {}).items():
        wc = (widgets_cfg or {}).get(key)
        if wc is None or not isinstance(data, dict):
            continue
        for f in FIELDS:
            if data.get(f) is not None:
                wc[f] = data[f]


def stamp() -> str:
    """Дата снимка — только для чтения человеком, логика её не использует."""
    return time.strftime("%Y-%m-%d %H:%M")


def clean_name(name: str, limit: int = 40) -> str:
    """Имя профиля: без ведущих/хвостовых пробелов, не длиннее limit."""
    return " ".join((name or "").split())[:limit]
