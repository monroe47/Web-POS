@echo off
REM ===============================================
REM Django Portable Server Stopper
REM -----------------------------------------------
REM Gracefully stops the Django development server
REM started by django_portable_launcher.bat
REM ===============================================

setlocal enabledelayedexpansion

REM ---- Default host:port ----
set "HOSTPORT=127.0.0.1:8000"

REM ---- Allow override from command-line argument ----
if not "%~1"=="" set "HOSTPORT=%~1"

echo.
echo ===============================================
echo   Django Server Stop Utility
echo ===============================================
echo Target: %HOSTPORT%
echo.

REM ---- Extract port number (assumes format HOST:PORT) ----
for /f "tokens=2 delims=:" %%A in ("%HOSTPORT%") do set "PORT=%%A"

if not defined PORT (
    echo [ERROR] Invalid host:port format. Expected something like 127.0.0.1:8000
    echo.
    pause
    exit /b 1
)

REM ---- Find PID listening on that port ----
set "PID="
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    set "PID=%%P"
    goto :found
)

:found
if not defined PID (
    echo [INFO] No Django server found running on %HOSTPORT%.
    echo.
    pause
    exit /b 0
)

REM ---- Attempt graceful termination ----
echo [INFO] Found Django server process (PID: !PID!).
echo [ACTION] Attempting to stop it gracefully...

taskkill /PID !PID! >nul 2>&1

REM ---- Verify if process is gone ----
timeout /t 1 >nul
set "STILL_RUNNING="
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    if "%%P"=="!PID!" set "STILL_RUNNING=1"
)

if defined STILL_RUNNING (
    echo [WARNING] Process did not exit gracefully. Forcing termination...
    taskkill /F /PID !PID! >nul 2>&1
    echo [DONE] Django server on %HOSTPORT% was forcefully stopped.
) else (
    echo [DONE] Django server on %HOSTPORT% stopped successfully.
)

echo.
pause
exit /b 0
