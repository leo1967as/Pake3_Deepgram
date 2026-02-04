import sys
import os

# Simulate running from src directory logic
# If run from root via scripts/run_pake.bat which probably calls python src/pake_gui.py, 
# then sys.path[0] is src/
# We emulate this by adding src to sys.path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.append(SRC_DIR)

print(f"📂 Added to path: {SRC_DIR}")

try:
    print("1️⃣ Testing ConfigManager import...")
    import config_manager
    print("   ✅ Success")
except Exception as e:
    print(f"   ❌ Failed: {e}")

try:
    print("2️⃣ Testing SettingsDialog import...")
    import gui.settings_dialog
    print("   ✅ Success")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    import traceback
    traceback.print_exc()

try:
    print("3️⃣ Testing TelegramDashboard import...")
    import gui.telegram_dashboard
    print("   ✅ Success")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    import traceback
    traceback.print_exc()

try:
    print("4️⃣ Testing TelegramManager import...")
    import telegram_manager
    print("   ✅ Success")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("🏁 Import Verification Complete.")
