
import sys
import unittest
import socket
import json
import time
import threading
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QTcpSocket

# Add src to path
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from pake_gui import PakeAnalyzerWindow

# Mock Config to prevent errors
import config_manager
config_manager.ConfigLoader.load = lambda self: {}

app = QApplication(sys.argv)

class TestDynamicControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Start GUI in a separate thread"""
        cls.window = PakeAnalyzerWindow()
        # We need to process events to let the server start
        for _ in range(10):
            app.processEvents()
            time.sleep(0.01)

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        app.quit()

    def test_tcp_connection(self):
        """Test 1: Can connect to GUI TCP Server"""
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2.0)
        try:
            client.connect(('localhost', 8765))
            self.assertTrue(True, "Connected to GUI TCP Server")
            client.close()
        except Exception as e:
            self.fail(f"Could not connect to GUI TCP Server: {e}")

    def test_send_command_logic(self):
        """Test 2: Verify send_command logic (mocking the socket)"""
        # Mock the client socket in the window
        class MockSocket:
            def __init__(self):
                self.sent_data = b""
            def write(self, data):
                self.sent_data = data
            def flush(self): pass
            
        mock_sock = MockSocket()
        self.window.client_socket = mock_sock
        
        # Test sending START command
        test_url = "https://www.youtube.com/watch?v=test"
        self.window.send_command("START", {"url": test_url})
        
        # Verify JSON
        sent_json = json.loads(mock_sock.sent_data.decode('utf-8'))
        self.assertEqual(sent_json["type"], "START")
        self.assertEqual(sent_json["url"], test_url)
        print(f"\n✅ Verified JSON Command Sent: {sent_json}")

if __name__ == '__main__':
    unittest.main()
