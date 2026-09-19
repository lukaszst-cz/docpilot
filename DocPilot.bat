@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title DocPilot

set "DOC_URL=http://127.0.0.1:8765"
set "HEALTH_URL=http://127.0.0.1:8765/api/health"
set "PY_CMD="

echo.
echo ============================================================
echo  DocPilot
echo  Documents + Deadlines + Actions + Archive
echo ============================================================
echo.

call :FIND_PYTHON

if not defined PY_CMD (
    echo Python 3.11+ is not installed.
    echo.
    where winget >nul 2>&1
    if errorlevel 1 goto :NO_WINGET

    choice /C YN /N /M "Install Python 3.13 automatically? [Y/N]: "
    if errorlevel 2 goto :MANUAL_PYTHON

    echo.
    echo [1/4] Installing Python 3.13...
    winget install --id Python.Python.3.13 -e --source winget --accept-source-agreements --accept-package-agreements
    if errorlevel 1 goto :INSTALL_FAILED

    call :FIND_PYTHON_AFTER_INSTALL
    if not defined PY_CMD (
        echo.
        echo Python was installed but could not be located immediately.
        echo Close this window and run DocPilot.bat once more.
        pause
        exit /b 0
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [2/4] Creating DocPilot private environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto :FAILED
)

set "VENV_PY=%CD%\.venv\Scripts\python.exe"

if not exist ".venv\.docpilot-ready-v051" (
    echo [3/4] Installing/updating DocPilot components...
    "%VENV_PY%" -m pip install --disable-pip-version-check -e ".[full]"
    if errorlevel 1 goto :FAILED
    type nul > ".venv\.docpilot-ready-v051"
) else (
    echo [3/4] DocPilot components are ready.
)

echo [4/4] Starting DocPilot...
echo.
echo Address: %DOC_URL%
echo Keep this window open while using DocPilot.
echo Closing it stops the local server.
echo.

REM A background watcher waits until the application REALLY responds.
REM Only then does it open the browser, preventing ERR_CONNECTION_REFUSED.
start "" powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command ^
  "$health='%HEALTH_URL%'; $app='%DOC_URL%';" ^
  "for($i=0;$i -lt 120;$i++){" ^
  " try { $r=Invoke-WebRequest -UseBasicParsing -Uri $health -TimeoutSec 1; if($r.StatusCode -eq 200){ Start-Process $app; exit 0 } } catch {};" ^
  " Start-Sleep -Milliseconds 500" ^
  "}; exit 1"

REM Run the server directly. This is intentionally NOT wrapped in another
REM PowerShell pipeline, because that caused unreliable startup on some PCs.
"%VENV_PY%" -m docpilot.cli --no-browser

set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
    echo DocPilot stopped.
) else (
    echo ============================================================
    echo  DocPilot stopped unexpectedly. Exit code: %EXIT_CODE%
    echo ============================================================
    echo.
    echo Please send a screenshot of this window if the problem repeats.
)
pause
exit /b %EXIT_CODE%

:FIND_PYTHON
set "PY_CMD="

where py >nul 2>&1
if not errorlevel 1 (
    py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3.13"
)

if not defined PY_CMD (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=py -3.12"
    )
)

if not defined PY_CMD (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=py -3.11"
    )
)

if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=python"
    )
)
exit /b 0

:FIND_PYTHON_AFTER_INSTALL
call :FIND_PYTHON
if defined PY_CMD exit /b 0

REM winget's per-user Python path may not be present in the current process PATH yet.
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) do (
    if exist "%%~P" (
        "%%~P" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PY_CMD="%%~P""
            exit /b 0
        )
    )
)

REM Last-resort discovery under the standard per-user Python directory.
for /f "delims=" %%P in ('dir /b /s "%LOCALAPPDATA%\Programs\Python\python.exe" 2^>nul') do (
    "%%P" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD="%%P""
        exit /b 0
    )
)
exit /b 0

:NO_WINGET
echo.
echo Windows Package Manager (winget) is not available.
goto :MANUAL_PYTHON

:MANUAL_PYTHON
echo.
echo Install Python 3.11 or newer, then run DocPilot.bat again:
echo https://www.python.org/downloads/windows/
echo.
echo During installation select:
echo   Add python.exe to PATH
pause
exit /b 1

:INSTALL_FAILED
echo.
echo Automatic Python installation failed.
goto :MANUAL_PYTHON

:FAILED
echo.
echo ============================================================
echo  DocPilot setup did not complete.
echo ============================================================
echo.
echo Send a screenshot of the messages above.
pause
exit /b 1
