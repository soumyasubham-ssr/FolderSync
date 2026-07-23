@echo off
setlocal
cd /d "%~dp0"
python -c "import PySide6, watchdog" >nul 2>nul
if errorlevel 1 (
    echo.
    echo Folder Sync cannot start because required Python packages are missing.
    echo Install them once with:
    echo   python -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
python main.py
if errorlevel 1 pause
endlocal
