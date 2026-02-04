
import sys
import os
import py_compile

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    print("Checking syntax of src/pake_gui.py...")
    py_compile.compile('src/pake_gui.py', doraise=True)
    print("[PASS] Syntax is valid.")
    
    # Optional: try simple import to catch runtime-level definition errors
    print("Attempting import...")
    from pake_gui import PakeAnalyzerWindow
    print("[PASS] Import successful.")
    
except Exception as e:
    print(f"[FAIL] Error: {e}")
    sys.exit(1)

sys.exit(0)
