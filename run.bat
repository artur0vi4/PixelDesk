@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title PixelDesk

echo.
echo ================================================
echo   PixelDesk - starting desktop widgets
echo ================================================
echo.

if not exist "main.py" (
    echo ERROR: main.py not found.
    echo Extract the FULL archive first, then run run.bat.
    pause
    exit /b 1
)
if not exist "pw_check.py" (
    echo ERROR: pw_check.py not found.
    echo Extract the FULL archive first, then run run.bat.
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

if not defined PY (
    pythonw pw_check.py interp >nul 2>nul
    if not errorlevel 1 set "PY=pythonw"
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

rem ==========================================================
rem  Step 2: check and install libraries
rem ==========================================================
echo [1/2] Checking libraries: PySide6, psutil, requests ...
%PYQ% pw_check.py >nul 2>nul
if not errorlevel 1 goto :libs_ok

echo       Libraries are not installed yet.
echo       Internet is needed ONCE, download is about 100-200 MB.
echo.
set "ANS=y"
set /p "ANS=      Install them now? [Y/n]: "
if /i "%ANS%"=="n" (
    echo.
    echo Cancelled. Tip: build_exe.bat makes a standalone exe instead.
    pause
    exit /b 1
)
echo.
echo       Installing, please wait 2-5 minutes ...
echo       --------------------------------------------------
%PYQ% -m pip install -r requirements.txt
if errorlevel 1 (
    echo       --------------------------------------------------
    echo.
    echo ERROR: installation failed. Check your internet
    echo connection and run run.bat again.
    echo If pip itself is missing, first run:
    echo     %PYQ% -m ensurepip --upgrade
    pause
    exit /b 1
)
echo       --------------------------------------------------
echo       Verifying ...
%PYQ% pw_check.py
if errorlevel 1 (
    echo.
    echo ERROR: libraries are still missing - see the text above.
    pause
    exit /b 1
)

:libs_ok
echo       OK - all libraries are in place.
echo.

rem ==========================================================
rem  Step 3: launch widgets
rem ==========================================================
echo [2/2] Starting widgets ...

set "PYWEXE="
if defined PYEXE set "PYWEXE=%PYEXE:python.exe=pythonw.exe%"

if defined PYEXE if exist "%PYWEXE%" (
    start "" "%PYWEXE%" main.py
    goto :started
)

set "PYW="
if /i "%PY:~0,2%"=="py" if not "%PY:~2,1%"=="" set "PYW=pyw %PY:~2%"
if /i "%PY%"=="py" set "PYW=pyw"
if /i "%PY%"=="python" set "PYW=pythonw"
if /i "%PY%"=="python3" set "PYW=pythonw"

if defined PYW (
    %PYW% pw_check.py interp >nul 2>nul
    if not errorlevel 1 (
        start "" %PYW% main.py
        goto :started
    )
)

start "PixelDesk console" /min cmd /c "%PYQ% main.py & echo. & echo Widgets stopped. & pause"

:started
echo.
echo ================================================
echo   DONE - widgets are starting!
echo ================================================
echo   * Look at your DESKTOP - cards appear in a few seconds.
echo   * A tray icon appears near the clock (it may be hidden
echo     under the "^" arrow in the tray corner).
echo   * Right-click a widget for its menu, drag to move it,
echo     pull the bottom-right corner to resize.
echo.
echo   If NOTHING appeared within a minute, open the file
echo   %APPDATA%\PixelDesk\error.log
echo   and send its contents to the developer.
echo.
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
echo             run.bat
echo        2. If that does not help - RESTART the computer once
echo           after installing Python, then run run.bat again.
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
