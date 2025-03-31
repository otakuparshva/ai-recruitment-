@echo off
REM ==============================================
REM AI Recruitment Partner - Setup Script (Windows)
REM ==============================================

echo Setting up the project...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    echo Download Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Create a virtual environment (if not exists)
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists.
)

REM Activate venv and install dependencies
echo Installing dependencies...
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

echo Setup completed successfully!
pause