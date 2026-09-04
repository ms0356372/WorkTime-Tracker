@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul || goto :fail_node
where npm >nul 2>nul || goto :fail_npm
if not exist package.json goto :fail_package
if not exist node_modules (
  echo Installing dependencies...
  if exist package-lock.json (call npm ci) else (call npm install)
  if errorlevel 1 goto :fail_install
)
echo Open the Local URL shown by Vite in Chrome.
call npm run dev
if errorlevel 1 goto :fail_dev
exit /b 0
:fail_node
echo FAILED: node command not found
goto :failed
:fail_npm
echo FAILED: npm command not found
goto :failed
:fail_package
echo FAILED: package.json not found
goto :failed
:fail_install
echo FAILED: dependency installation
goto :failed
:fail_dev
echo FAILED: npm run dev
:failed
pause
exit /b 1
