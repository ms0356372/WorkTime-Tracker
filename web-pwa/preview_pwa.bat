@echo off
setlocal
cd /d "%~dp0"
echo Current directory: %CD%
where node >nul 2>nul || goto :fail_node
where npm >nul 2>nul || goto :fail_npm
if not exist package.json goto :fail_package
if not exist dist\index.html goto :fail_dist
echo Open the Local URL shown by Vite in Chrome.
call npm run preview
if errorlevel 1 goto :fail_preview
exit /b 0
:fail_node
echo FAILED: node command not found.
exit /b 1
:fail_npm
echo FAILED: npm command not found.
exit /b 1
:fail_package
echo FAILED: package.json not found.
exit /b 1
:fail_dist
echo FAILED: dist\index.html not found. Run verify_pwa.bat first.
exit /b 1
:fail_preview
echo FAILED: npm run preview.
exit /b 1
