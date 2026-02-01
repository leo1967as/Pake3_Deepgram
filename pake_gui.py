"""
Pake Live Analyzer GUI v4
=========================
3-Column Layout - Separate API calls for Translation and Analysis
"""

import sys
import json
import os
import datetime
import socket
import threading
import time
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
        self.client_thread = None
        
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
                    client, addr = server.accept()
                    print(f"🔗 Client connected from {addr}")
                    self.client_connected.emit()
                    # Start handler in background thread
                    self.client_thread = threading.Thread(
                        target=self._handle_client, 
                        args=(client,), 
                        daemon=True
                    )
                    self.client_thread.start()
                except socket.timeout:
                    continue
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            server.close()
            
    def _handle_client(self, client):
        buffer = ""
        try:
            while self.running:
                data = client.recv(4096).decode('utf-8')
                if not data:
                    print("❌ Client disconnected (no data)")
                    break
                buffer += data
                
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            print(f"📩 Received: {msg.get('type', '?')}")
                            self.message_received.emit(msg)
                        except json.JSONDecodeError as e:
                            print(f"⚠️ JSON error: {e}")
        except Exception as e:
            print(f"⚠️ Handle error: {e}")
        finally:
            client.close()
            self.client_disconnected.emit()
            print("🔌 Client handler ended")
            
    def stop(self):
        self.running = False

# ============================================================================
# TRANSLATION WORKER (Separate API)
# ============================================================================
class TranslateWorker(QObject):
    finished = Signal(int, list)  # batch_num, list of translated segments
    
    def __init__(self, segments: list, batch_num: int):
        super().__init__()
        self.segments = segments  # List of {"speaker": ..., "text": ..., "start": ...}
        self.batch_num = batch_num
        
    def run(self):
        if not OPENROUTER_API_KEY or not self.segments:
            self.finished.emit(self.batch_num, [])
            return
        
        # Format segments for translation with speaker labels
        lines = []
        for i, seg in enumerate(self.segments):
            speaker = seg.get("speaker", "?")
            text = seg.get("text", "")
            lines.append(f"{i+1}. [{speaker}]: {text}")
        
        formatted_text = "\n".join(lines)
        
        prompt = f"""แปลบทสนทนาต่อไปนี้เป็นภาษาไทย เก็บรูปแบบเดิม (หมายเลข และ [Speaker X]) ไว้ทุกบรรทัด:

{formatted_text}

ตอบในรูปแบบเดิม:
1. [Speaker X]: คำแปล
2. [Speaker Y]: คำแปล
..."""

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                        json={
                            "model": "google/gemini-2.0-flash-001",
                            "messages": [{"role": "user", "content": prompt}]
                        }
                    )
                    result = resp.json()
                    translated_text = result["choices"][0]["message"]["content"]
                    
                    # Parse translated lines back into segments
                    translated_segments = []
                    for line in translated_text.strip().split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        # Try to parse "1. [Speaker X]: translated text"
                        if "]:" in line:
                            parts = line.split("]:", 1)
                            if len(parts) == 2:
                                speaker_part = parts[0]
                                text_part = parts[1].strip()
                                # Extract speaker name
                                if "[" in speaker_part:
                                    speaker = speaker_part.split("[", 1)[1]
                                else:
                                    speaker = "?"
                                translated_segments.append({
                                    "speaker": speaker,
                                    "text": text_part
                                })
                    
                    # If parsing failed, fall back to original segments with translated text
                    if len(translated_segments) == 0:
                        translated_segments.append({
                            "speaker": "Translation",
                            "text": translated_text
                        })
                    
                    print(f"✅ Translation #{self.batch_num} OK ({len(translated_segments)} segments)")
                    self.finished.emit(self.batch_num, translated_segments)
                    return # Success
                    
            except Exception as e:
                if attempt == max_retries:
                    print(f"Translate Error (Final): {e}")
                    self.finished.emit(self.batch_num, [])
                else:
                    print(f"⚠️ Translate Error (Attempt {attempt+1}): {e} - Retrying...")
                    time.sleep(2 ** attempt)

# ============================================================================
# AI ANALYSIS WORKER (Separate API)
# ============================================================================
class AnalysisWorker(QObject):
    finished = Signal(dict)
    
    def __init__(self, text: str, batch_num: int, previous_context: str = "", memory: dict = None):
        super().__init__()
        self.text = text
        self.batch_num = batch_num
        self.previous_context = previous_context
        self.memory = memory or {"summaries": [], "markets": [], "trend": {"hawkish": 0, "dovish": 0, "neutral": 0}}
        
    def run(self):
        if not OPENROUTER_API_KEY:
            self.finished.emit({"error": "No API Key", "batch_num": self.batch_num})
            return
        
        # Build comprehensive memory context
        context_section = ""
        summaries = self.memory.get("summaries", [])
        markets = self.memory.get("markets", [])
        trend = self.memory.get("trend", {})
        
        # Overall trend status
        total = trend.get("hawkish", 0) + trend.get("dovish", 0) + trend.get("neutral", 0)
        if total > 0:
            dominant = max(trend, key=trend.get)
            trend_pct = int(trend[dominant] / total * 100)
            context_section += f"\n📊 แนวโน้มรวม: {dominant.upper()} ({trend_pct}%) จาก {total} batches\n"
        
        # Previous summaries with sentiment
        if summaries:
            summaries_text = "\n".join([f"  B{s['batch']}: [{s['sentiment']}] {s['summary']}" for s in summaries[-5:]])
            context_section += f"\n📖 สรุปย้อนหลัง:\n{summaries_text}\n"
        
        # Previous market predictions for consistency
        if markets:
            last_market = markets[-1]
            context_section += f"\n💹 ทิศทางตลาดล่าสุด (B{last_market['batch']}):\n"
            context_section += f"  Gold: {last_market.get('gold', '-')[:30]}\n"
            context_section += f"  Forex: {last_market.get('forex', '-')[:30]}\n"
            context_section += f"  Stock: {last_market.get('stock', '-')[:30]}\n"
        
        if self.previous_context:
            context_section += f"\n⚡ ข้อความก่อนหน้า:\n{self.previous_context[:400]}\n"
            
        prompt = f"""คุณคือนักวิเคราะห์การเงินมืออาชีพ มีหน้าที่วิเคราะห์แบบ REAL-TIME และต้องรักษา CONSISTENCY
{context_section}
🎯 บทสนทนาปัจจุบัน (Batch #{self.batch_num}):
{self.text}

⚠️ กฎ CONSISTENCY (สำคัญมาก):
1. ดูแนวโน้มรวมและทิศทางตลาดล่าสุด → ถ้าจะเปลี่ยนทิศต้องมีเหตุผลชัดเจนมาก
2. ห้ามกลับทิศทางตลาด (เช่น Gold ขึ้น→ลง) ถ้าผู้พูดยังพูดเรื่องเดิม
3. ถ้าเป็นการขยายความหรือตอบคำถามเรื่องเดิม → ทิศทางควรคงเดิมหรือแรงขึ้น
4. เปลี่ยนทิศทางได้เมื่อ: ผู้พูดเปลี่ยนจุดยืน, มีข้อมูลใหม่ที่ขัดแย้ง, เปลี่ยนหัวข้อ

📏 กฎการวิเคราะห์:
1. signal_strength: HIGH=ประกาศนโยบายใหม่/ตัวเลขใหม่, MEDIUM=ขยายความ, LOW=ตอบคำถามทั่วไป
2. sentiment: HAWKISH (กังวลเงินเฟ้อ/เข้มงวด), DOVISH (กังวลเศรษฐกิจ/ผ่อนคลาย), NEUTRAL (ไม่มีสัญญาณชัด)
3. ถ้า signal_strength=LOW → ทิศทางตลาดควรคงเดิมตาม batch ก่อนหน้า

ตอบเป็น JSON เท่านั้น (ภาษาไทย):
{{
    "summary": "สรุป 1-2 ประโยค (เชื่อมโยงบริบทย้อนหลัง)",
    "prediction": "คาดการณ์สิ่งที่ผู้พูดจะพูดต่อไป",
    "sentiment": "HAWKISH|DOVISH|NEUTRAL",
    "signal_strength": "HIGH|MEDIUM|LOW",
    "consistency_note": "อธิบายสั้นๆ ว่าทำไมทิศทางเปลี่ยน/ไม่เปลี่ยนจาก batch ก่อน",
    "gold": "ขึ้น/ลง/ทรงตัว: เหตุผลสั้น",
    "forex": "แข็ง/อ่อน/ทรงตัว: เหตุผลสั้น",
    "stock": "ขึ้น/ลง/ทรงตัว: กลุ่ม + เหตุผล"
}}"""

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=45) as client:
                    resp = client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                        json={
                            "model": "google/gemini-2.5-flash",
                            "messages": [{"role": "user", "content": prompt}],
                            "response_format": {"type": "json_object"},
                            "provider": {"order": ["google-vertex/global"]}
                        }
                    )
                    result = resp.json()
                    
                    # Debug: print raw response keys
                    # print(f"🔍 API Response keys: {list(result.keys())}")
                    
                    # Check for API error
                    if "error" in result:
                        raise Exception(f"API Error: {result['error']}")
                    
                    # Safely extract content
                    choices = result.get("choices")
                    if choices is None:
                        raise Exception(f"No 'choices' in response: {result}")
                    
                    first_choice = choices[0]
                    message = first_choice.get("message", {})
                    content = message.get("content", "")
                    
                    if not content:
                        raise Exception("Empty content")
                    
                    # Try to parse JSON, handling markdown code blocks
                    content = content.strip()
                    if content.startswith("```"):
                        lines = content.split("\n")
                        content = "\n".join(lines[1:-1])
                    
                    parsed = json.loads(content)
                    
                    # Handle case where AI returns a list instead of dict
                    if isinstance(parsed, list):
                        print(f"⚠️ AI returned list, taking first item")
                        if len(parsed) > 0 and isinstance(parsed[0], dict):
                            parsed = parsed[0]
                        else:
                            parsed = {}
                    
                    if not isinstance(parsed, dict):
                        raise Exception(f"Parsed content is not dict: {type(parsed)}")
                    
                    parsed["batch_num"] = self.batch_num
                    print(f"✅ Analysis #{self.batch_num} OK")
                    self.finished.emit(parsed)
                    return # Success
                    
            except Exception as e:
                if attempt == max_retries:
                    import traceback
                    print(f"Analysis Error (Final): {e}")
                    traceback.print_exc()
                    self.finished.emit({"error": str(e), "batch_num": self.batch_num})
                else:
                    print(f"⚠️ Analysis Error (Attempt {attempt+1}): {e} - Retrying...")
                    time.sleep(2 ** attempt)

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
        
        # Keep references to prevent garbage collection
        self.translate_thread = None
        self.translate_worker = None
        self.analysis_thread = None
        self.analysis_worker = None
        
        # Enhanced Memory System
        self.memory = {
            "summaries": [],      # [{batch, summary, sentiment}, ...]
            "markets": [],        # [{batch, gold, forex, stock}, ...]
            "trend": {"hawkish": 0, "dovish": 0, "neutral": 0}
        }
        self.last_context = ""
        
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
        
        # Overall Trend Indicator
        self.trend_label = QLabel("📊 TREND: -")
        self.trend_label.setStyleSheet("font-size: 11px; color: #606070; padding: 4px 10px; background: #1a1a24; border-radius: 4px;")
        
        self.toggle_btn = QPushButton("🇹🇭 Thai ON")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.clicked.connect(self._toggle_thai)
        
        self.status = QLabel("● WAITING")
        self.status.setStyleSheet("font-size: 11px; color: #606070;")
        
        header_layout.addWidget(title)
        header_layout.addSpacing(20)
        header_layout.addWidget(self.trend_label)
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
        
        # Column 2: Thai Translation
        self.col2 = QWidget()
        col2_layout = QVBoxLayout(self.col2)
        col2_layout.setContentsMargins(6, 10, 6, 12)
        
        lbl2 = QLabel("🇹🇭 TRANSLATION (TH)")
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
        
        colors = ["#6366f1", "#a855f7", "#22c55e", "#ef4444", "#f59e0b"]
        try:
            idx = int(''.join(filter(str.isdigit, speaker)) or 0)
        except:
            idx = 0
        color = colors[idx % len(colors)]
        
        time_str = f"{int(start // 60)}:{int(start % 60):02d}"
        
        html = f'''<table style="width:100%; margin-bottom:8px; border-collapse:collapse;">
<tr>
<td style="width:100px; vertical-align:top; padding-right:8px;">
<span style="font-size:10px; color:{color}; font-weight:bold;">{speaker}</span><br/>
<span style="font-size:9px; color:#606070;">{time_str}</span>
</td>
<td style="vertical-align:top; border-left:2px solid {color}; padding-left:10px;">
<span style="font-size:13px; color:#e0e0e0;">{text}</span>
</td>
</tr>
</table>'''
        
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        self.transcript.ensureCursorVisible()
        
    def _process_batch(self, batch: dict):
        self.progress.show()
        
        current_batch = batch.get("current_batch", {})
        text = current_batch.get("text", "")
        segments = current_batch.get("segments", [])
        batch_num = batch.get("batch_number", 0)
        
        # ดึง previous_context จาก batch (ถ้ามี)
        previous_context = batch.get("previous_context", "")
        self.last_context = previous_context  # เก็บไว้ใช้ต่อ
        
        # --- Start Translation Thread ---
        if self.show_thai:
            self.translate_thread = QThread()
            self.translate_worker = TranslateWorker(segments, batch_num)
            self.translate_worker.moveToThread(self.translate_thread)
            
            self.translate_thread.started.connect(self.translate_worker.run)
            self.translate_worker.finished.connect(self._update_translation)
            self.translate_worker.finished.connect(self.translate_thread.quit)
            self.translate_worker.finished.connect(self.translate_worker.deleteLater)
            self.translate_thread.finished.connect(self.translate_thread.deleteLater)
            
            self.translate_thread.start()
        
        # --- Start Analysis Thread (with full memory) ---
        self.analysis_thread = QThread()
        self.analysis_worker = AnalysisWorker(
            text, batch_num, 
            previous_context=previous_context,
            memory={
                "summaries": self.memory["summaries"].copy(),
                "markets": self.memory["markets"].copy(),
                "trend": self.memory["trend"].copy()
            }
        )
        self.analysis_worker.moveToThread(self.analysis_thread)
        
        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.finished.connect(self._update_analysis)
        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.finished.connect(self.analysis_worker.deleteLater)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)
        self.analysis_thread.finished.connect(lambda: self.progress.hide())
        
        self.analysis_thread.start()
        
    def _update_translation(self, batch_num: int, segments: list):
        if not segments:
            return
            
        now = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Header for the batch
        header_html = f'''<div style="font-size:10px; color:#606070; margin-top:8px; margin-bottom:4px; border-bottom:1px solid #2a2a3a;">BATCH #{batch_num} • {now}</div>'''
        
        cursor = self.thai_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(header_html)
        
        colors = ["#6366f1", "#a855f7", "#22c55e", "#ef4444", "#f59e0b"]
        
        for seg in segments:
            speaker = seg.get("speaker", "?")
            text = seg.get("text", "")
            
            # Determine color based on speaker
            try:
                idx = int(''.join(filter(str.isdigit, speaker)) or 0)
            except:
                idx = 0
            color = colors[idx % len(colors)]
            
            html = f'''<table style="width:100%; margin-bottom:6px; border-collapse:collapse;">
        <tr>
        <td style="width:90px; vertical-align:top; padding-right:8px;">
        <span style="font-size:10px; color:{color}; font-weight:bold;">{speaker}</span>
        </td>
        <td style="vertical-align:top; border-left:2px solid {color}; padding-left:10px;">
        <span style="font-size:13px; color:#e0e0e0;">{text}</span>
        </td>
        </tr>
        </table>'''
            cursor.insertHtml(html)
            
        self.thai_view.ensureCursorVisible()
        
    def _update_analysis(self, result: dict):
        if "error" in result:
            print(f"Analysis Error: {result['error']}")
            return
            
        batch_num = result.get("batch_num", 0)
        summary = result.get("summary", "-")
        prediction = result.get("prediction", "-")
        sentiment = result.get("sentiment", "NEUTRAL").upper()
        signal_strength = result.get("signal_strength", "MEDIUM")
        consistency_note = result.get("consistency_note", "")
        gold = result.get("gold", "-")
        forex = result.get("forex", "-")
        stock = result.get("stock", "-")
        
        # 🧠 Enhanced Memory Storage
        self.memory["summaries"].append({"batch": batch_num, "summary": summary, "sentiment": sentiment})
        self.memory["markets"].append({"batch": batch_num, "gold": gold, "forex": forex, "stock": stock})
        
        # Update trend counter
        if "HAWK" in sentiment:
            self.memory["trend"]["hawkish"] += 1
        elif "DOVE" in sentiment:
            self.memory["trend"]["dovish"] += 1
        else:
            self.memory["trend"]["neutral"] += 1
        
        # Keep max 10 entries
        if len(self.memory["summaries"]) > 10:
            self.memory["summaries"].pop(0)
        if len(self.memory["markets"]) > 10:
            self.memory["markets"].pop(0)
        
        # Update trend indicator in header
        self._update_trend_indicator()
        
        print(f"🧠 Memory: {len(self.memory['summaries'])} summaries, Trend: {self.memory['trend']}")
        
        now = datetime.datetime.now().strftime("%H:%M:%S")
        
        s_color = "#606070"
        s_bg = "#1a1a24"
        if "HAWK" in sentiment:
            s_color = "#ef4444"
            s_bg = "#2a1a1a"
        elif "DOVE" in sentiment:
            s_color = "#22c55e"
            s_bg = "#1a2a1a"
        
        # Signal strength styling
        str_color = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#606070"}.get(signal_strength, "#606070")
        
        html = f'''<table style="width:100%; margin-bottom:14px; background:#1a1a24; border-radius:8px; border:1px solid #2a2a3a;">
<tr><td style="padding:12px;">
<div style="margin-bottom:8px; font-size:10px; color:#606070;">
BATCH #{batch_num} • {now}
<span style="margin-left:8px; color:{str_color}; font-size:9px;">⚡{signal_strength}</span>
<span style="float:right; color:{s_color}; font-weight:bold; background:{s_bg}; padding:2px 8px; border-radius:4px;">{sentiment}</span>
</div>

<div style="margin-bottom:10px;">
<div style="font-size:10px; color:#6366f1; font-weight:bold; margin-bottom:3px;">📝 SUMMARY</div>
<div style="font-size:12px; color:#e0e0e0;">{summary}</div>
{f'<div style="font-size:10px; color:#808090; margin-top:3px;">🔗 {consistency_note}</div>' if consistency_note else ''}
</div>

<div style="margin-bottom:10px;">
<div style="font-size:10px; color:#a855f7; font-weight:bold; margin-bottom:3px;">🔮 PREDICTION</div>
<div style="font-size:11px; color:#a0a0b0;">{prediction}</div>
</div>

<div style="background:#0f0f14; padding:10px; border-radius:6px;">
<div style="font-size:10px; color:#22c55e; font-weight:bold; margin-bottom:6px;">📊 MARKET IMPACT</div>
<div style="font-size:11px; color:#f59e0b; margin-bottom:4px;">🥇 Gold: <span style="color:#e0e0e0;">{gold}</span></div>
<div style="font-size:11px; color:#3b82f6; margin-bottom:4px;">💱 Forex: <span style="color:#e0e0e0;">{forex}</span></div>
<div style="font-size:11px; color:#ec4899;">📈 Stock: <span style="color:#e0e0e0;">{stock}</span></div>
</div>
</td></tr>
</table>'''
        
        cursor = self.ai_feed.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.insertHtml(html)
    
    def _update_trend_indicator(self):
        """Update the overall trend indicator in header"""
        trend = self.memory["trend"]
        total = trend["hawkish"] + trend["dovish"] + trend["neutral"]
        if total == 0:
            return
        
        # Find dominant trend
        dominant = max(trend, key=trend.get)
        count = trend[dominant]
        pct = int(count / total * 100)
        
        # Set color and text
        if dominant == "hawkish":
            color = "#ef4444"
            bg = "#2a1a1a"
            icon = "🦅"
        elif dominant == "dovish":
            color = "#22c55e"
            bg = "#1a2a1a"
            icon = "🕊️"
        else:
            color = "#f59e0b"
            bg = "#2a2a1a"
            icon = "⚖️"
        
        self.trend_label.setText(f"{icon} TREND: {dominant.upper()} ({count}/{total} = {pct}%)")
        self.trend_label.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: bold; padding: 4px 10px; background: {bg}; border-radius: 4px;")
        
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
