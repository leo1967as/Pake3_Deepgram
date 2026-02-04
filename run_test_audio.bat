@echo off
echo Testing Audio Pipeline...
if exist ".venv310\Scripts\activate.bat" (
    call .venv310\Scripts\activate
) else (
    echo Virtual environment not found, trying system python...
)
python test/test_audio_pipeline.py
pause
