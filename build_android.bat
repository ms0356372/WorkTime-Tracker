@echo off
setlocal
cd /d "%~dp0"

if not exist "scripts\build_android.bat" (
    echo.
    echo ERROR: scripts\build_android.bat not found.
    echo.
    pause
    exit /b 1
)

call "%~dp0scripts\build_android.bat"
set "BUILD_EXIT_CODE=%ERRORLEVEL%"

if not "%BUILD_EXIT_CODE%"=="0" (
    echo.
    echo Android build failed.
    echo Exit code: %BUILD_EXIT_CODE%
    echo.
    pause
    exit /b %BUILD_EXIT_CODE%
)

exit /b 0
