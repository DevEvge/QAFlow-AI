@echo off
echo Starting QAFlow-AI Web Server...
".\.venv\Scripts\python.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
