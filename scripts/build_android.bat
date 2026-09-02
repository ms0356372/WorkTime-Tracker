@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

if not exist "release" mkdir "release"

echo ==================================================
echo WorkTime Tracker - Android Build %*
echo ==================================================
echo Project root: %CD%
echo This window will pause after success or failure.
echo.

echo [1/6] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found in PATH.
    echo Install Python 3.11 or newer and enable Add Python to PATH.
    goto :error
)
python --version
if errorlevel 1 goto :error

echo.
echo [2/6] Preparing virtual environment...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto :error
)
set "PYTHON=%CD%\.venv\Scripts\python.exe"
"%PYTHON%" --version
if errorlevel 1 goto :error

echo.
echo [3/6] Installing dependencies...
"%PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error
"%PYTHON%" -m pip install --upgrade "briefcase>=0.3.20,<0.4"
if errorlevel 1 goto :error
"%PYTHON%" -m pip install -e ".[dev]"
if errorlevel 1 goto :error

echo.
echo [4/6] Running tests...
"%PYTHON%" -m pytest -v
if errorlevel 1 goto :error

echo.
echo [5/6] Starting Android build...
set "PYTHONUNBUFFERED=1"
"%PYTHON%" -u build_mobile.py android %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
    echo.
    echo Android build_mobile.py failed.
    echo Exit code: %RESULT%
    goto :error
)

echo.
echo [6/6] Build finished successfully.
echo APK output: release\android
echo Build report: release\build_report.txt
echo Build log: release\build_android.log
echo.
pause
exit /b 0

:error
echo.
echo ==================================================
echo BUILD FAILED
echo ==================================================
echo Review the error above and release\build_android.log.
echo.
pause
exit /b 1
