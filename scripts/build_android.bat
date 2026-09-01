@echo off
setlocal
cd /d "%~dp0\.."
echo [1/4] 檢查 Python
python --version || goto :error
if not exist .venv (echo [2/4] 建立虛擬環境 & python -m venv .venv || goto :error)
call .venv\Scripts\activate.bat
python -m pip install -e ".[dev]" briefcase || goto :error
echo [3/4] 測試與 Android 打包
python build_mobile.py android || goto :error
echo [4/4] 完成。請查看 release\android 與 release\build_report.txt
pause
exit /b 0
:error
echo 建置失敗，請閱讀上方錯誤訊息。
pause
exit /b 1
