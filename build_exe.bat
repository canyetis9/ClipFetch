@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================================
echo   CLIPFETCH - ONE-CLICK WINDOWS .EXE BUILDER
echo ==========================================================
echo [1/2] Installing required libraries and PyInstaller...
python -m pip install --upgrade yt-dlp PySide6 pyinstaller
echo [2/2] Compiling ClipFetch.exe...
python -m PyInstaller --noconsole --onefile --name "ClipFetch" main.py
echo.
echo ==========================================================
echo   DONE! You can find your app at dist\ClipFetch.exe
echo ==========================================================
pause
