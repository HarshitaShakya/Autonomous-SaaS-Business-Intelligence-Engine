@echo off
echo ========================================================
echo  Autonomous SaaS BI Engine - Development Server Launcher
echo ========================================================
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" start_dev.py
) else (
    python start_dev.py
)

pause
