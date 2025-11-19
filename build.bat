@echo off

REM Check if venv exists, if not create it and install requirements
if not exist "venv\" (
    echo Creating virtual environment...
    py -m venv venv
    echo Installing requirements...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    pip install pyinstaller
) else (
    call venv\Scripts\activate.bat
)

echo Building executable...
pyinstaller --onefile --name "BitBus" ^
    --add-data "assets;assets" ^
    --add-data "data;data" ^
    --add-data "src;src" ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=requests ^
    --hidden-import=urllib3 ^
    --hidden-import=idna ^
    --hidden-import=chardet ^
    --collect-all google ^
    src\render_nearby_buses.py

echo.
echo Build complete! Executable is in dist\BusRenderer.exe
pause
