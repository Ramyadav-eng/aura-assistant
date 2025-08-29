@echo off
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
echo Starting AURA Assistant...
set "PYTHON_PATH=%SCRIPT_DIR%.venv\Scripts\python.exe"
set "DAY1_APP=day1:app"
set "TRAY_SCRIPT=%SCRIPT_DIR%aura_tray.py"
echo Starting AI server on port 8080...
start "AURA Server" "%PYTHON_PATH%" -m uvicorn %DAY1_APP% --port 8080
timeout /t 5 >nul
echo Starting system tray icon...
start "AURA Tray" "%PYTHON_PATH%" "%TRAY_SCRIPT%"
timeout /t 2 >nul
:: --- ADD THIS LINE TO OPEN WEB UI ---
echo Opening AURA dashboard in your browser...
start http://localhost:8080
:: -----------------------------------