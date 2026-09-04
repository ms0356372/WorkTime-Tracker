@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul || goto :fail_node
where npm >nul 2>nul || goto :fail_npm
if not exist package.json goto :fail_package
if exist package-lock.json (call npm ci) else (call npm install)
if errorlevel 1 goto :fail_install
call npm run build
if errorlevel 1 goto :fail_build
if not exist dist\index.html goto :fail_output
echo Production build PASSED: %CD%\dist
pause
exit /b 0
:fail_node
set STEP=node command not found
goto :failed
:fail_npm
set STEP=npm command not found
goto :failed
:fail_package
set STEP=package.json not found
goto :failed
:fail_install
set STEP=dependency installation
goto :failed
:fail_build
set STEP=npm run build
goto :failed
:fail_output
set STEP=dist\index.html not found
:failed
echo FAILED: %STEP%
pause
exit /b 1
