
import sys
import os

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(os.path.dirname(current_dir), 'src')
sys.path.insert(0, src_dir)

from PySide6.QtWidgets import QApplication
from pake_gui import PakeAnalyzerWindow

def verify():
    try:
        print("Checking imports...")
        # Just importing checks static imports
        
        # Test GUI Initialization (Headless check)
        app = QApplication(sys.argv)
        
        print("Initializing PakeAnalyzerWindow...")
        w = PakeAnalyzerWindow()
        
        print(f"[PASS] GUI Window initialized successfully.")
        
        # Verify Attributes
        if hasattr(w, 'btn_start'):
            print("[PASS] found 'btn_start'")
        else:
            print("[FAIL] 'btn_start' missing!")
            sys.exit(1)
            
        if hasattr(w, 'url_input'):
            print("[WARN] 'url_input' still exists? (Should be removed/unused)")
        else:
            print("[PASS] 'url_input' correctly absent")

        if hasattr(w, 'start_btn'):
            print("[WARN] 'start_btn' still exists? (Should be renamed to btn_start)")
            
        # Check methods
        if hasattr(w, 'toggle_processing'):
             print("[PASS] found 'toggle_processing'")
             
        if hasattr(w, 'toggle_start_stop'):
             print("[FAIL] 'toggle_start_stop' should be removed/renamed!")
             sys.exit(1)

        print("[SUCCESS] All checks passed.")
        sys.exit(0) 

    except NameError as e:
        print(f"[FAIL] NameError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify()
