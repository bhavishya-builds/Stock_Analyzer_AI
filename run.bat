@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Installing/updating requirements...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo Starting StockWise AI at http://127.0.0.1:5000
echo Press CTRL+C to stop.
echo.
".venv\Scripts\python.exe" app.py
pause
