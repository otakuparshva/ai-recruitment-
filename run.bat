@echo off
cd /d "%~dp0"
call venv\Scripts\activate
set PYTHONPATH=%CD%
python app\main.py
pause
