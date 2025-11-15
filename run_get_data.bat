@echo off

REM Check if venv exists, if not create it and install requirements
if not exist "venv\" (
    echo Creating virtual environment...
    py -m venv venv
    echo Installing requirements...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

py -m src.fetch_static_data
pause
