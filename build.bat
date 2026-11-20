@echo off
rem Builds dist\FolderSync.exe locally. Requires: python -m pip install -r requirements.txt -r requirements-dev.txt
setlocal
cd /d "%~dp0"
pyinstaller --noconfirm --clean --onefile --windowed --name FolderSync --icon icon.ico --add-data "icon.ico;." main.py
if errorlevel 1 (echo Build failed.& pause & exit /b 1)
echo.
echo Built dist\FolderSync.exe
endlocal
