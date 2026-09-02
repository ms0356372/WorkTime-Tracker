@echo off
rem Double-click launcher kept at the repository root for beginners.
call "%~dp0scripts\build_android.bat"
exit /b %ERRORLEVEL%
