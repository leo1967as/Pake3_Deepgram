@echo off
echo Running GUI Verification...
if exist ".venv310\Scripts\activate.bat" (
    call .venv310\Scripts\activate
) else (
    echo Virtual environment not found, trying system python...
)
python test/verify_gui.py
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] GUI Verification Passed!
) else (
    echo.
    echo [FAIL] GUI Verification Failed!
)
pause
