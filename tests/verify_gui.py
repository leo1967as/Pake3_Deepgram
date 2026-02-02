import sys
from PySide6.QtWidgets import QApplication
from pake_gui import PakeAnalyzerWindow

try:
    print("Testing GUI Initialization...")
    app = QApplication(sys.argv)
    
    # Try to initialize the window (headless check)
    window = PakeAnalyzerWindow()
    print("[PASS] PakeAnalyzerWindow initialized successfully")
    
    # Check if WebSocket server is listening
    if window.server.isListening():
        print(f"[PASS] WebSocket Server listening on port {window.server.serverPort()}")
    else:
        print("[FAIL] WebSocket Server failed to listen")
        sys.exit(1)
        
    print("Verification complete.")
    sys.exit(0)

except Exception as e:
    print(f"[FAIL] Error: {e}")
    sys.exit(1)
