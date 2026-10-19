@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title PixelDesk - build exe

echo.
echo ================================================
echo   PixelDesk - building PixelDesk.exe
echo ================================================
echo.

if not exist "main.py" (
    echo ERROR: main.py not found.
    echo Extract the FULL archive first, then run build_exe.bat.
    pause
    exit /b 1
)
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found.
    echo Extract the FULL archive first, then run build_exe.bat.
    pause
    exit /b 1
)
if not exist "pw_check.py" (
    echo ERROR: pw_check.py not found.
    echo Extract the FULL archive first, then run build_exe.bat.
    pause
    exit /b 1
)

rem ==========================================================
rem  Step 1: find a working Python interpreter (very thorough)
rem ==========================================================
set "PY="
set "PYEXE="

py pw_check.py interp >nul 2>nul
if not errorlevel 1 set "PY=py"

if not defined PY (
    py -3 pw_check.py interp >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)

for %%v in (3.15 3.14 3.13 3.12 3.11 3.10) do (
    if not defined PY (
        py -%%v pw_check.py interp >nul 2>nul
        if not errorlevel 1 set "PY=py -%%v"
    )
)

if not defined PY (
    python pw_check.py interp >nul 2>nul
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    python3 pw_check.py interp >nul 2>nul
    if not errorlevel 1 set "PY=python3"
)

rem ---- registry lookup (PEP 514 ExecutablePath) ----
if not defined PY (
    for /f "tokens=2*" %%A in ('reg query "HKCU\Software\Python\PythonCore" /s /v ExecutablePath 2^>nul') do (
        if /i "%%A"=="REG_SZ" if exist "%%B" if not defined PY set "PYEXE=%%B"
    )
)
if not defined PY (
    for /f "tokens=2*" %%A in ('reg query "HKLM\Software\Python\PythonCore" /s /v ExecutablePath 2^>nul') do (
        if /i "%%A"=="REG_SZ" if exist "%%B" if not defined PY set "PYEXE=%%B"
    )
)
rem ---- registry fallback: InstallPath default value ----
if not defined PY (
    for /f "tokens=2*" %%A in ('reg query "HKCU\Software\Python\PythonCore" /s /ve 2^>nul') do (
        if /i "%%A"=="REG_SZ" if exist "%%Bpython.exe" if not defined PY set "PYEXE=%%Bpython.exe"
    )
)
rem ---- last resort: scan common install folders ----
if not defined PY (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%D\python.exe" if not defined PY set "PYEXE=%%D\python.exe"
    )
)
if not defined PY (
    for /d %%D in ("%LOCALAPPDATA%\Python\Python*") do (
        if exist "%%D\python.exe" if not defined PY set "PYEXE=%%D\python.exe"
    )
)
if not defined PY (
    for /d %%D in ("C:\Program Files\Python*") do (
        if exist "%%D\python.exe" if not defined PY set "PYEXE=%%D\python.exe"
    )
)
if not defined PY (
    for /d %%D in ("C:\Program Files (x86)\Python*") do (
        if exist "%%D\python.exe" if not defined PY set "PYEXE=%%D\python.exe"
    )
)

if defined PYEXE set "PY=%PYEXE%"
if not defined PY goto :nopython

if defined PYEXE (set PYQ="%PYEXE%") else set "PYQ=%PY%"

echo Python found:  %PY%
echo.

echo [1/3] Upgrading pip ...
%PYQ% -m pip install --upgrade pip
echo.

echo [2/3] Installing libraries: PySide6, psutil, requests, PyInstaller
echo       (may take a few minutes - DO NOT close this window)
%PYQ% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo.
    echo ERROR: could not install libraries.
    echo Check your internet connection and run this file again.
    pause
    exit /b 1
)
echo.

echo [3/3] Building exe - this takes 2-5 minutes.
echo       The window may look frozen, that is normal. Please wait...
%PYQ% -m PyInstaller --noconfirm --clean --windowed --onefile --name PixelDesk --icon app\resources\app.ico main.py > build_log.txt 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: build failed. Details:
    echo ----------------------------------------------------------------
    type build_log.txt
    echo ----------------------------------------------------------------
    echo (the same text is saved in build_log.txt)
    pause
    exit /b 1
)
del build_log.txt >nul 2>nul

echo.
echo ================================================
echo   DONE!  (Gotovo!)
echo   File:  %~dp0dist\PixelDesk.exe
echo   Copy it anywhere - Python is NOT needed to run it.
echo ================================================
echo.
if exist "dist\PixelDesk.exe" explorer dist
pause
exit /b 0

rem ==========================================================
rem  Diagnostics when no Python was found at all
rem ==========================================================
:nopython
echo ERROR: this script could not find Python.  (Python ne naiden)
echo.
echo TIP: you said "py --version" works. Then Python IS installed,
echo      but this script was started with an old environment.
echo      Do this:
echo        1. Close ALL windows, open cmd again and run:
echo             cd /d "%~dp0"
echo             build_exe.bat
echo        2. If that does not help - RESTART the computer once
echo           after installing Python, then run build_exe.bat again.
echo.
echo ================= diagnostics (screenshot this) =================
echo [1] how py reacts to commands, WITHOUT hiding errors:
echo     ^> py --version
py --version 2>&1
echo     ^> py pw_check.py interp
py pw_check.py interp 2>&1
echo     ^> py -3 pw_check.py interp
py -3 pw_check.py interp 2>&1
echo.
echo [2] runtimes known to the py launcher:
py list 2>&1
py -0p 2>&1
echo.
echo [3] what is on PATH:
where py 2>nul || echo     py: not found on PATH
where python 2>nul || echo     python: not found on PATH
where python3 2>nul || echo     python3: not found on PATH
echo.
echo [4] registry entries:
reg query "HKCU\Software\Python\PythonCore" /s /v ExecutablePath 2>nul
reg query "HKLM\Software\Python\PythonCore" /s /v ExecutablePath 2>nul
echo.
echo [5] common install folders:
dir /b "%LOCALAPPDATA%\Programs\Python" 2>nul
dir /b "%LOCALAPPDATA%\Python" 2>nul
dir /b "C:\Program Files\Python*" 2>nul
echo ================ end diagnostics ================
echo.
pause
exit /b 1
