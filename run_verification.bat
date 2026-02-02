@echo off
echo 🔧 Activating .venv310 Environment...
if exist ".venv310\Scripts\activate.bat" (
    call .venv310\Scripts\activate
) else (
    echo ❌ .venv310 not found! Please check your environment.
    pause
    exit /b 1
)

echo 📦 Installing required packages (requests, pytz)...
pip install requests pytz

echo 🚀 Running Verification Script...
python test/verify_news.py

echo.
echo ✅ Done.
pause
