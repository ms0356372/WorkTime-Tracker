@echo off
setlocal
cd /d "%~dp0"
echo Current directory: %CD%
echo [1/4] Checking environment...
where node >nul 2>nul || goto :fail_node
where npm >nul 2>nul || goto :fail_npm
if not exist package.json goto :fail_package
for /f "delims=" %%v in ('node -v') do set NODE_VERSION=%%v
for /f "delims=" %%v in ('npm -v') do set NPM_VERSION=%%v
echo Node: %NODE_VERSION%
echo npm: %NPM_VERSION%
echo [2/4] Installing dependencies...
if exist package-lock.json (call npm ci) else (call npm install)
if errorlevel 1 goto :fail_install
echo [3/4] Running tests...
call npm test
if errorlevel 1 goto :fail_test
echo [4/4] Building production...
call npm run build
if errorlevel 1 goto :fail_build
if not exist dist\index.html goto :fail_output
echo ================================================
echo  WorkTime Tracker PWA Verification PASSED
echo ================================================
echo Node:
echo %NODE_VERSION%
echo npm:
echo %NPM_VERSION%
echo Tests:
echo PASSED
echo Build:
echo PASSED
echo Output:
echo web-pwa\dist
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
:fail_test
set STEP=npm test
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
