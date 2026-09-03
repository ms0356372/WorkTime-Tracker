@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo WorkTime Tracker - Signed Android Release Build
echo ==================================================
echo This build requires ANDROID_KEYSTORE, ANDROID_KEY_ALIAS,
echo ANDROID_KEYSTORE_PASSWORD, and ANDROID_KEY_PASSWORD.
echo Credentials must be set in the environment and never committed to Git.
echo.

if not exist "scripts\build_android.bat" (
    echo ERROR: scripts\build_android.bat not found.
    pause
    exit /b 1
)

call "%~dp0scripts\build_android.bat" --release --require-release-signing
set "BUILD_EXIT_CODE=%ERRORLEVEL%"
if not "%BUILD_EXIT_CODE%"=="0" (
    echo Signed Android release build failed.
    pause
    exit /b %BUILD_EXIT_CODE%
)

exit /b 0
