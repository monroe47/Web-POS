@echo off
REM ===============================================
REM Django Portable Launcher
REM -----------------------------------------------
REM Starts Django dev server hidden (no visible window),
REM waits until reachable, then opens browser automatically.
REM Works from any drive/folder on any Windows machine.
REM ===============================================

REM Change to script’s directory (where manage.py is expected)
cd /d "%~dp0"

REM ---- Detect Python executable ----
set "PY_EXE="

REM Prefer virtual environments first
if exist "%CD%\.venv\Scripts\python.exe" set "PY_EXE=%CD%\.venv\Scripts\python.exe"
if exist "%CD%\venv\Scripts\python.exe" set "PY_EXE=%CD%\venv\Scripts\python.exe"

REM Fallback to system Python if no venv found
if not defined PY_EXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        set "PY_EXE=%%P"
        goto :found_python
    )
)
:found_python

if not defined PY_EXE (
    echo ERROR: Could not find Python executable. Ensure Python is installed or a virtualenv exists.
    pause
    exit /b 1
)

REM ---- Start Django dev server detached (hidden) ----
powershell -NoProfile -WindowStyle Hidden -Command ^
    "Start-Process -FilePath '%PY_EXE%' -ArgumentList 'manage.py','runserver','127.0.0.1:8000' -WorkingDirectory '%CD%' -WindowStyle Hidden"

REM ---- Wait until server is available ----
echo Waiting for Django server to start on http://127.0.0.1:8000 ...
powershell -NoProfile -Command ^
    "$max=30; $i=0; while ($i -lt $max) {try {Invoke-WebRequest -Uri 'http://127.0.0.1:8000' -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop; exit 0} catch {Start-Sleep -Seconds 1; $i++}}; exit 1"

if errorlevel 1 (
    echo WARNING: Server did not respond in time. Opening browser anyway...
) else (
    echo Server is up!
)

REM ---- Open default browser ----
start "" "http://127.0.0.1:8000/"

REM ---- Exit silently ----
exit /b 0
