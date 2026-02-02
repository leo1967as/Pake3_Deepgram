import sys
import os

# Add src to path so we can import pake_gui
sys.path.append(os.path.join(os.getcwd(), "src"))

from PySide6.QtWidgets import QApplication
from pake_gui import PakeAnalyzerWindow

def verify_gui():
    print("🚀 Starting GUI Verification...")
    try:
        app = QApplication(sys.argv)
        
        print("⏳ Initializing PakeAnalyzerWindow...")
        window = PakeAnalyzerWindow()
        
        # Check if news dock exists
        if hasattr(window, "news_dock"):
             print("✅ News Dock found initialized.")
        else:
             print("❌ News Dock NOT found.")
             sys.exit(1)
             
        # Check if news button exists
        if hasattr(window, "btn_news"):
             print("✅ News Button found initialized.")
        else:
             print("❌ News Button NOT found.")
             sys.exit(1)

        print("✅ GUI Components initialized successfully.")
        
        # Don't run exec(), just exit with success
        sys.exit(0)

    except Exception as e:
        print(f"❌ GUI Verification Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    verify_gui()
