@echo off
cd /d U:\BYSJ\yolov-door\yolov8-door\SmartAccess
call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
