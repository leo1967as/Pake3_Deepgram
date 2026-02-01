"""
Pake Live Analyzer GUI v3
=========================
3-Column Layout - Translation happens with Batch (not per segment)
"""

import sys
import json
import os
import datetime
import socket
import threading
import httpx
from dotenv import load_dotenv
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLabel, QSplitter, QProgressBar, QFrame, QPushButton
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QTextCursor

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_KEY", "")

# ============================================================================
# STYLES
# ============================================================================
DARK_STYLE = """
QMainWindow { background-color: #0f0f14; }
QWidget { font-family: 'Segoe UI', Arial, sans-serif; color: #e0e0e0; }
QSplitter::handle { background-color: #1a1a24; width: 2px; }
QTextEdit { 
    background-color: #14141c; 
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    padding: 12px;
    color: #e0e0e0;
    font-size: 13px;
}
QProgressBar {
    border: none;
    background-color: #1a1a24;
    height: 2px;
}
QProgressBar::chunk { background-color: #6366f1; }
QLabel { color: #808090; }
QPushButton {
    background-color: #2a2a3a;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    color: #e0e0e0;
    font-size: 11px;
}
QPushButton:hover { background-color: #3a3a4a; }
QPushButton:checked { background-color: #6366f1; color: white; }
"""

# ============================================================================
# SOCKET SERVER
# ============================================================================
class SocketServerThread(QThread):
    message_received = Signal(dict)
    client_connected = Signal()
    client_disconnected = Signal()
    
    def __init__(self, port=8765):
        super().__init__()
        self.port = port
        self.running = True
        
    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.settimeout(1.0)
        
        try:
            server.bind(('localhost', self.port))
            server.listen(1)
            print(f"✅ GUI Server on port {self.port}")
            
            while self.running:
                try:
                    client, _ = server.accept()
                    self.client_connected.emit()
                    threading.Thread(target=self._handle, args=(client,), daemon=True).start()
                except socket.timeout:
                    continue
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            server.close()
            
    def _handle(self, client):
        buffer = ""
        try:
            while self.running:
                data = client.recv(4096).decode('utf-8')
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            self.message_received.emit(json.loads(line))
                        except:
                            pass
        except:
            pass
        finally:
            client.close()
            self.client_disconnected.emit()
            
    def stop(self):
        self.running = False

# ============================================================================
# AI + TRANSLATION WORKER (Combined)
# ============================================================================
class AIWorker(QObject):
    finished = Signal(dict)
    
    def __init__(self, text: str, batch_num: int):
        super().__init__()
        self.text = text
        self.batch_num = batch_num
        
    def run(self):
        if not OPENROUTER_API_KEY:
            self.finished.emit({"error": "No API Key", "batch_num": self.batch_num})
            return
            
        prompt = f"""คุณเป็นนักวิเคราะห์การเงิน วิเคราะห์ transcript นี้:

เนื้อหา: {self.text}

ตอบเป็น JSON เท่านั้น (ห้ามมี markdown):
{{
    "translation": "แปลเนื้อหาข้างบนเป็นภาษาไทยทั้งหมด",
    "summary": "สรุปประเด็นสำคัญ 2-3 ข้อ",
    "prediction": "คาดการณ์หัวข้อถัดไป",
    "sentiment": "HAWKISH หรือ DOVISH หรือ NEUTRAL",
    "gold": "ผลต่อทองคำ: ขึ้น/ลง/ทรงตัว + เหตุผลสั้นๆ",
    "forex": "ผลต่อ USD: แข็ง/อ่อน/ทรงตัว + เหตุผลสั้นๆ",
    "stock": "ผลต่อหุ้น: ขึ้น/ลง/ทรงตัว + หมวดที่ได้รับผลกระทบ"
}}"""

        try:
            with httpx.Client(timeout=45) as client:
                resp = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                    json={
                        "model": "google/gemini-2.0-flash-001",
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"}
                    }
                )
                result = resp.json()
                content = result["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                parsed["batch_num"] = self.batch_num
                self.finished.emit(parsed)
        except Exception as e:
            self.finished.emit({"error": str(e), "batch_num": self.batch_num})

# ============================================================================
# MAIN WINDOW
# ============================================================================
class PakeAnalyzerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📺 Pake Live Analyzer")
        self.resize(1600, 900)
        self.setStyleSheet(DARK_STYLE)
        
        self.show_thai = True
        self.ai_thread = None
        self.ai_worker = None
        
        self._build_ui()
        self._start_server()
        
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- HEADER ---
        header = QFrame()
        header.setFixedHeight(36)
        header.setStyleSheet("background-color: #0a0a0f; border-bottom: 1px solid #1a1a24;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        
        title = QLabel("PAKE LIVE ANALYZER")
        title.setStyleSheet("font-size: 12px; font-weight: bold; color: #6366f1; letter-spacing: 2px;")
        
        # Toggle Thai
        self.toggle_btn = QPushButton("🇹🇭 Thai ON")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.clicked.connect(self._toggle_thai)
        
        self.status = QLabel("● WAITING")
        self.status.setStyleSheet("font-size: 11px; color: #606070;")
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.toggle_btn)
        header_layout.addSpacing(20)
        header_layout.addWidget(self.status)
        layout.addWidget(header)
        
        # --- PROGRESS ---
        self.progress = QProgressBar()
        self.progress.setFixedHeight(2)
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)
        
        # --- 3-COLUMN LAYOUT ---
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Column 1: Original Transcript
        col1 = QWidget()
        col1_layout = QVBoxLayout(col1)
        col1_layout.setContentsMargins(12, 10, 6, 12)
        
        lbl1 = QLabel("📝 TRANSCRIPT (EN)")
        lbl1.setStyleSheet("font-size: 10px; font-weight: bold; margin-bottom: 6px;")
        col1_layout.addWidget(lbl1)
        
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        col1_layout.addWidget(self.transcript)
        
        # Column 2: Thai Translation (Batched)
        self.col2 = QWidget()
        col2_layout = QVBoxLayout(self.col2)
        col2_layout.setContentsMargins(6, 10, 6, 12)
        
        lbl2 = QLabel("🇹🇭 TRANSLATION (TH) - Batched")
        lbl2.setStyleSheet("font-size: 10px; font-weight: bold; margin-bottom: 6px;")
        col2_layout.addWidget(lbl2)
        
        self.thai_view = QTextEdit()
        self.thai_view.setReadOnly(True)
        col2_layout.addWidget(self.thai_view)
        
        # Column 3: AI Intelligence
        col3 = QWidget()
        col3_layout = QVBoxLayout(col3)
        col3_layout.setContentsMargins(6, 10, 12, 12)
        
        lbl3 = QLabel("🧠 INTELLIGENCE")
        lbl3.setStyleSheet("font-size: 10px; font-weight: bold; margin-bottom: 6px;")
        col3_layout.addWidget(lbl3)
        
        self.ai_feed = QTextEdit()
        self.ai_feed.setReadOnly(True)
        col3_layout.addWidget(self.ai_feed)
        
        self.splitter.addWidget(col1)
        self.splitter.addWidget(self.col2)
        self.splitter.addWidget(col3)
        self.splitter.setSizes([450, 450, 700])
        layout.addWidget(self.splitter)
        
    def _toggle_thai(self):
        self.show_thai = self.toggle_btn.isChecked()
        if self.show_thai:
            self.toggle_btn.setText("🇹🇭 Thai ON")
            self.col2.show()
            self.splitter.setSizes([450, 450, 700])
        else:
            self.toggle_btn.setText("🇹🇭 Thai OFF")
            self.col2.hide()
            self.splitter.setSizes([600, 0, 800])
        
    def _start_server(self):
        self.server = SocketServerThread(8765)
        self.server.message_received.connect(self._on_message)
        self.server.client_connected.connect(lambda: self._set_status("● LIVE", "#22c55e"))
        self.server.client_disconnected.connect(lambda: self._set_status("● OFFLINE", "#ef4444"))
        self.server.start()
        
    def _set_status(self, text: str, color: str):
        self.status.setText(text)
        self.status.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: bold;")
        
    def _on_message(self, payload: dict):
        msg_type = payload.get("type")
        data = payload.get("data", {})
        
        if msg_type == "segment":
            self._add_segment(data)
        elif msg_type == "batch":
            self._process_batch(data)
            
    def _add_segment(self, seg: dict):
        speaker = seg.get("speaker", "?")
        text = seg.get("text", "")
        start = seg.get("start", 0)
        
        # Color per speaker
        colors = ["#6366f1", "#a855f7", "#22c55e", "#ef4444", "#f59e0b"]
        try:
            idx = int(''.join(filter(str.isdigit, speaker)) or 0)
        except:
            idx = 0
        color = colors[idx % len(colors)]
        
        time_str = f"{int(start // 60)}:{int(start % 60):02d}"
        
        html = f'''
        <div style="margin-bottom: 10px;">
            <div style="font-size: 10px; color: #606070; margin-bottom: 2px;">
                <b style="color: {color};">{speaker}</b> • {time_str}
            </div>
            <div style="font-size: 13px; color: #e0e0e0; line-height: 1.4; padding-left: 8px; border-left: 2px solid {color};">{text}</div>
        </div>
        '''
        
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        self.transcript.ensureCursorVisible()
        
    def _process_batch(self, batch: dict):
        self.progress.show()
        
        text = batch.get("current_batch", {}).get("text", "")
        batch_num = batch.get("batch_number", 0)
        
        # Create new thread safely
        self.ai_thread = QThread()
        self.ai_worker = AIWorker(text, batch_num)
        self.ai_worker.moveToThread(self.ai_thread)
        
        self.ai_thread.started.connect(self.ai_worker.run)
        self.ai_worker.finished.connect(self._update_results)
        self.ai_worker.finished.connect(self.ai_thread.quit)
        self.ai_worker.finished.connect(self.ai_worker.deleteLater)
        self.ai_thread.finished.connect(self.ai_thread.deleteLater)
        
        self.ai_thread.start()
        
    def _update_results(self, result: dict):
        self.progress.hide()
        
        if "error" in result:
            print(f"AI Error: {result['error']}")
            return
            
        batch_num = result.get("batch_num", 0)
        translation = result.get("translation", "")
        summary = result.get("summary", "-")
        prediction = result.get("prediction", "-")
        sentiment = result.get("sentiment", "NEUTRAL").upper()
        gold = result.get("gold", "-")
        forex = result.get("forex", "-")
        stock = result.get("stock", "-")
        
        now = datetime.datetime.now().strftime("%H:%M:%S")
        
        # --- Add Translation ---
        if translation and self.show_thai:
            thai_html = f'''
            <div style="margin-bottom: 12px; padding: 10px; background: #1a1a24; border-radius: 6px; border-left: 3px solid #22c55e;">
                <div style="font-size: 10px; color: #606070; margin-bottom: 4px;">BATCH #{batch_num} • {now}</div>
                <div style="font-size: 13px; color: #e0e0e0; line-height: 1.5;">{translation}</div>
            </div>
            '''
            cursor = self.thai_view.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertHtml(thai_html)
            self.thai_view.ensureCursorVisible()
        
        # --- Add AI Analysis ---
        s_color = "#606070"
        s_bg = "#1a1a24"
        if "HAWK" in sentiment:
            s_color = "#ef4444"
            s_bg = "#2a1a1a"
        elif "DOVE" in sentiment:
            s_color = "#22c55e"
            s_bg = "#1a2a1a"
        
        ai_html = f'''
        <div style="margin-bottom: 14px; padding: 12px; background: #1a1a24; border-radius: 8px; border: 1px solid #2a2a3a;">
            <div style="margin-bottom: 8px; font-size: 10px; color: #606070;">
                BATCH #{batch_num} • {now}
                <span style="float: right; color: {s_color}; font-weight: bold; background: {s_bg}; padding: 2px 8px; border-radius: 4px;">{sentiment}</span>
            </div>
            
            <div style="margin-bottom: 10px;">
                <div style="font-size: 10px; color: #6366f1; font-weight: bold; margin-bottom: 3px;">📝 SUMMARY</div>
                <div style="font-size: 12px; color: #e0e0e0;">{summary}</div>
            </div>
            
            <div style="margin-bottom: 10px;">
                <div style="font-size: 10px; color: #a855f7; font-weight: bold; margin-bottom: 3px;">🔮 PREDICTION</div>
                <div style="font-size: 11px; color: #a0a0b0;">{prediction}</div>
            </div>
            
            <div style="background: #0f0f14; padding: 10px; border-radius: 6px;">
                <div style="font-size: 10px; color: #22c55e; font-weight: bold; margin-bottom: 6px;">📊 MARKET IMPACT</div>
                <div style="font-size: 11px; color: #f59e0b; margin-bottom: 4px;">🥇 Gold: <span style="color: #e0e0e0;">{gold}</span></div>
                <div style="font-size: 11px; color: #3b82f6; margin-bottom: 4px;">💱 Forex: <span style="color: #e0e0e0;">{forex}</span></div>
                <div style="font-size: 11px; color: #ec4899;">📈 Stock: <span style="color: #e0e0e0;">{stock}</span></div>
            </div>
        </div>
        '''
        
        cursor = self.ai_feed.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.insertHtml(ai_html)
        
    def closeEvent(self, event):
        self.server.stop()
        self.server.wait(1000)
        event.accept()

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    
    window = PakeAnalyzerWindow()
    window.show()
    
    sys.exit(app.exec())
