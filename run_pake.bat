@echo off
cd /d "%~dp0"

echo ====================================================
echo   Pake Live Analyzer - Starting...
echo ====================================================
echo.

echo [1/2] Starting GUI Analyzer...
start "Pake GUI Analyzer" cmd /k ".\.venv310\Scripts\python.exe pake_gui.py"

:: Wait for GUI to start (important!)
timeout /t 3 /nobreak > nul

echo [2/2] Starting Live Transcriber...
start "Pake Live Transcriber" cmd /k ".\.venv310\Scripts\python.exe pake_live.py"

echo.
echo ====================================================
echo   Both systems started!
echo   - GUI Window: Shows Transcript and AI Analysis
echo   - Console Window: Shows Deepgram Data Flow
echo ====================================================
echo.
pause
