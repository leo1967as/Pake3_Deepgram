import sys
import os
from PySide6.QtWidgets import QApplication

# Setup path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from gui.telegram_dashboard import TelegramDashboard
from telegram_manager import tg_manager

def verify():
    app = QApplication(sys.argv)
    try:
        print("⏳ Initializing TelegramDashboard...")
        # Mock config if needed, but Manager handles defaults
        dlg = TelegramDashboard()
        print("✅ [PASS] TelegramDashboard initialized successfully.")
        return 0
    except Exception as e:
        print(f"❌ [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(verify())
