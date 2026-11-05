@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================================
echo   STARTING CLIPFETCH...
echo ==========================================================
python -m pip install --upgrade yt-dlp PySide6
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application failed to start.
    pause
)
