import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from PySide6.QtWidgets import QApplication
from pake_gui import PakeAnalyzerWindow
# from config import ConfigLoader # Not found in src

try:
    # 1. Test Config
    # print("Testing ConfigLoader...")
    # c = ConfigLoader().load()
    # print(f"[PASS] Config loaded successfully")

    # 2. Test GUI Initialization (Headless check)
    print("Testing GUI Initialization...")
    app = QApplication(sys.argv)
    
    # สร้าง Window แต่ไม่ต้องสั่ง app.exec() เพื่อไม่ให้ค้าง
    w = PakeAnalyzerWindow()
    print(f"[PASS] GUI Window initialized successfully")
    
    # ถ้ามาถึงตรงนี้แปลว่าผ่าน
    sys.exit(0) 

except ImportError as e:
    # กรณี import ไม่ได้ อาจเพราะไม่มี PyQt6 หรือ path ผิด
    # ลองใช้ PySide6 แทน (เนื่องจากโปรเจคใช้ PySide6)
    try:
        from PySide6.QtWidgets import QApplication
        from src.pake_gui import PakeAnalyzerWindow
        # config might be different or not exist in src directly based on file structure, 
        # but let's try to mock or load if possible.
        # User snippet used ConfigLoader, but I don't recall seeing it in pake_gui.py imports.
        # In pake_gui.py, it uses load_dotenv directly.
        
        print("[INFO] Fallback to PySide6")
        app = QApplication(sys.argv)
        w = PakeAnalyzerWindow()
        print(f"[PASS] GUI Window initialized successfully (PySide6)")
        sys.exit(0)
    except Exception as e2:
         print(f"[FAIL] Error: {e2}")
         sys.exit(1)

except Exception as e:
    print(f"[FAIL] Error: {e}")
    sys.exit(1)
