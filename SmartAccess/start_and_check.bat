@echo off
echo ========================================
echo SmartAccess - Starting Application
echo ========================================
echo.

cd /d "%~dp0"

echo [1] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [2] Checking Python version...
python --version

echo [3] Checking installed packages...
pip list

echo [4] Checking missing dependencies...
pip check

echo [5] Starting FastAPI server...
echo Server will start at: http://localhost:8000
echo API Docs at: http://localhost:8000/docs
echo.
python app\main.py
