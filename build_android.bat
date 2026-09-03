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

if not "%~1"=="" (
    set "BUILD_ARGS=%*"
    goto :run
)

echo WorkTime Tracker Android Debug Build
echo.
echo [1] Build APK
echo [2] Build + Install
echo [3] Clean Install
echo.
choice /C 123 /N /M "Select mode [1-3]: "
if errorlevel 3 goto :confirm_clean
if errorlevel 2 set "BUILD_ARGS=--debug --install"
if errorlevel 2 goto :run
set "BUILD_ARGS=--debug"
goto :run

:confirm_clean
echo.
echo WARNING: Clean Install will delete all app data.
choice /C YN /N /M "Continue [Y/N]? "
if errorlevel 2 exit /b 0
choice /C YN /N /M "Confirm again - permanently delete app data [Y/N]? "
if errorlevel 2 exit /b 0
set "BUILD_ARGS=--debug --clean-install"

:run
call "%~dp0scripts\build_android.bat" %BUILD_ARGS%
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
