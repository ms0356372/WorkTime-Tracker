@echo off
setlocal EnableExtensions
chcp 65001 >nul
title WorkTime Tracker - Android Build
cd /d "%~dp0\.."

if not exist release mkdir release
cls
echo ========================================================
echo   工時管家 Android 自動建置
echo ========================================================
echo 專案目錄：%CD%
echo 此視窗在成功或失敗後都不會自動關閉。
echo 首次建置需要下載 Briefcase、Android SDK 與 Gradle，可能需 10-30 分鐘。
echo.

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD goto :no_python

call :step 1 6 "檢查 Python"
%PYTHON_CMD% --version || goto :error

call :step 2 6 "建立虛擬環境"
if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv || goto :error
) else (
    echo 已存在 .venv，繼續使用。
)
set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

call :step 3 6 "更新打包工具"
"%VENV_PYTHON%" -m pip install --upgrade pip || goto :error

call :step 4 6 "安裝專案、測試與 Briefcase"
"%VENV_PYTHON%" -m pip install -e ".[dev]" briefcase || goto :error

call :step 5 6 "執行測試、建立 Android 專案並打包"
echo 建置期間若一段時間沒有新文字，通常是 Gradle 正在下載或編譯，請勿關閉視窗。
"%VENV_PYTHON%" build_mobile.py android
if errorlevel 1 goto :error

call :step 6 6 "完成"
echo Android 安裝／發布檔案：release\android\
echo 完整紀錄：release\android_build.log
echo 建置報告：release\build_report.txt
echo.
goto :success

:step
echo.
echo [%~1/%~2] %~3
echo --------------------------------------------------------
exit /b 0

:no_python
echo [錯誤] 找不到 Python。
echo 請安裝 Python 3.11 或更新版本，安裝時勾選 Add Python to PATH。
goto :error_pause

:error
echo.
echo [錯誤] Android 建置失敗，錯誤碼：%ERRORLEVEL%
echo 請查看上方最後一段訊息以及 release\android_build.log。
:error_pause
echo.
echo 按任意鍵關閉此視窗...
pause >nul
exit /b 1

:success
echo 按任意鍵關閉此視窗...
pause >nul
exit /b 0
