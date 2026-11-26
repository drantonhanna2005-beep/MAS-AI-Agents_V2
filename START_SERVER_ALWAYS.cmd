@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8
:loop
echo [%date% %time%] Starting MAS AI Agents server...>> logs\server_watchdog.log
python app.py --no-browser >> logs\server_stdout.log 2>>&1
echo [%date% %time%] Server exited with errorlevel %errorlevel%. Restarting in 3s...>> logs\server_watchdog.log
timeout /t 3 /nobreak >nul
goto loop
