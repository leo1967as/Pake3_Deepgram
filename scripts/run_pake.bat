@echo off
cd /d "%~dp0"
:: Move up to project root (since this script is in /scripts)
cd ..

echo ====================================================
echo   Pake Live Analyzer - Starting from %CD%
echo ====================================================
echo.

echo [1/2] Starting GUI Analyzer...
:: Check if venv exists
if not exist ".venv310\Scripts\python.exe" (
    echo ERROR: Python venv not found at .\.venv310\Scripts\python.exe
    pause
    exit /b
)

start "Pake GUI Analyzer" cmd /k ".\.venv310\Scripts\python.exe src\pake_gui.py"

:: Wait for GUI to start (important!)
timeout /t 3 /nobreak > nul

echo [2/2] Starting Live Transcriber...
start "Pake Live Transcriber" cmd /k ".\.venv310\Scripts\python.exe src\pake_live.py"

echo.
echo ====================================================
echo   Both systems started!
echo   - GUI Window: Shows Transcript and AI Analysis
echo   - Console Window: Shows Deepgram Data Flow
echo ====================================================
echo.
pause
