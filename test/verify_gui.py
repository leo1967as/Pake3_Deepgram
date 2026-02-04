import sys
import os

# 1. Setup Path to include 'src' so imports inside pake_gui work
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

print(f"📂 Added src to path: {SRC_DIR}")

from PySide6.QtWidgets import QApplication

def verify():
    app = QApplication(sys.argv)
    try:
        print("⏳ Importing pake_gui...")
        from pake_gui import PakeAnalyzerWindow
        
        print("🏗️ Initializing Window...")
        window = PakeAnalyzerWindow()
        
        print("✅ [PASS] GUI Window initialized successfully.")
        return 0
    except Exception as e:
        print(f"❌ [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(verify())
