"""Автозапуск с Windows: раздел реестра HKCU\\...\\Run (без прав администратора)."""
from __future__ import annotations

import os
import sys

_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE = "PixelDesk"
# запись от версии, когда программа называлась PixelWidgets — чистим за собой
_LEGACY_VALUES = ("PixelWidgets",)


def _command() -> str:
    if getattr(sys, "frozen", False):          # запуск из exe
        return f'"{sys.executable}"'
    script = os.path.abspath(sys.argv[0])      # запуск из исходников
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    return f'"{exe}" "{script}"'


def is_enabled() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY) as k:
            for name in (_VALUE, *_LEGACY_VALUES):
                try:
                    winreg.QueryValueEx(k, name)
                    return True
                except OSError:
                    continue
        return False
    except Exception:
        return False


def set_enabled(on: bool) -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _KEY, 0,
                                winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, _VALUE, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(k, _VALUE)
                except FileNotFoundError:
                    pass
            # убрать запись под старым именем, если она осталась
            for legacy in _LEGACY_VALUES:
                try:
                    winreg.DeleteValue(k, legacy)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False
