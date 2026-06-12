@echo off
REM Script to run the backend server on Windows
cd /d "%~dp0"
uvicorn main:app --reload --port 8080 --host 0.0.0.0
