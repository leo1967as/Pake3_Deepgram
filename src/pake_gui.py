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

DECISION_RULES = """
### 🚨 กฎการตัดสินใจ (ต้องปฏิบัติตาม 100% - ห้ามใช้ "ทรงตัว" เมื่อมีคำเหล่านี้)

#### 🦅 HAWKISH (ต้องตอบ "HAWKISH" หากมีคำเหล่านี้ในคำพูดประธานเฟด):
- เงินเฟ้อเพิ่มขึ้น: "inflation rising", "inflation accelerating", "price pressures increasing"
- ความกังวลเงินเฟ้อ: "inflation concerns", "inflation risks", "unsustainable inflation"
- นโยบายเข้มงวด: "tighten policy", "restrictive stance", "higher for longer"
- ขึ้นดอกเบี้ย: "rate hike", "raise rates", "not cutting soon"
- หนี้ไม่ยั่งยืน: "unsustainable debt", "unsustainable deficit", "fiscal trajectory concerns"
- ตลาดแรงงานร้อนแรง: "tight labor market", "strong job growth", "wage pressures"

#### 🕊️ DOVISH (ต้องตอบ "DOVISH" หากมีคำเหล่านี้ในคำพูดประธานเฟด):
- เงินเฟ้อลดลง: "inflation falling", "disinflation", "inflation coming down", "progress on inflation"
- แนวโน้มเงินเฟ้อดีขึ้น: "inflation 3.5% → 3.2%", "core PCE below 3%", "inflation near 2%"
- ตลาดแรงงานอ่อนตัว: "labor market softening", "cooling labor market", "unemployment rising"
- ผ่อนคลายนโยบาย: "ease policy", "accommodative stance", "rate cuts possible"
- ภาษีส่งผ่านแล้ว: "tariff pass-through complete", "tariff effects fading", "one-time price increase"
- ผลิตภาพเพิ่ม: "productivity growth", "AI boosts productivity", "wage growth from productivity"

#### ⚖️ NEUTRAL (ใช้ได้เฉพาะกรณี):
- นักข่าวถามคำถาม (ยังไม่มีคำตอบจากประธานเฟด)
- เรื่องทั่วไปที่ไม่เกี่ยวกับนโยบาย: "Fed independence", "appointment process", "congressional testimony"

### 📊 กฎการวิเคราะห์ตลาด (ต้องเชื่อมโยงกับแนวโน้ม):
- HAWKISH → Gold: ลง | Forex: แข็ง | Stock: ลง (โดยเฉพาะ growth stocks)
- DOVISH → Gold: ขึ้น | Forex: อ่อน | Stock: ขึ้น (โดยเฉพาะ rate-sensitive sectors)
- NEUTRAL → ทรงตัว (แต่ต้องอธิบายว่า "รอคำตอบจากประธานเฟด")

### ⚠️ ห้ามใช้คำว่า "รอดูข้อมูลเพิ่มเติม" — ต้องใช้เหตุผลเชิงปริมาณ:
❌ ห้าม: "รอดูข้อมูลเศรษฐกิจเพิ่มเติม"
✅ ต้อง: "เงินเฟ้อลดจาก 3.5% → 3.2% → dovish pressure on rates"
"""

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
        print(f"🚀 TranslateWorker.run() started for Batch #{self.batch_num}")
        if not OPENROUTER_API_KEY or not self.segments:
            print(f"❌ No API Key or no segments!")
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
                print(f"📡 Calling Translation API (Attempt {attempt+1})...")
                with httpx.Client(timeout=60) as client:
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
        print(f"🚀 AnalysisWorker.run() started for Batch #{self.batch_num}")
        if not OPENROUTER_API_KEY:
            print("❌ No OPENROUTER_API_KEY!")
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
            
        prompt = f"""คุณคือนักวิเคราะห์การเงินมืออาชีพ วิเคราะห์แบบเรียลไทม์โดยใช้กฎต่อไปนี้:

{DECISION_RULES}

🧠 บริบทย้อนหลัง (สำคัญ):
{context_section}

🎯 บทสนทนาปัจจุบัน (Batch #{self.batch_num}):
{self.text}

ตอบเป็น JSON เท่านั้น (ภาษาไทย):
{{
    "speaker_identified": "ประธานเฟด/นักข่าว",
    "summary": "สรุป 1 ประโยค + ระบุบทบาทผู้พูด",
    "prediction": "คาดการณ์ 1 ประโยค",
    "sentiment": "HAWKISH|DOVISH|NEUTRAL (ต้องเลือกตามกฎข้างต้น)",
    "signal_strength": "HIGH|MEDIUM|LOW",
    "consistency_note": "อธิบายว่าทำไมเลือก sentiment นี้ (อ้างอิงคำสำคัญ)",
    "gold": "ขึ้น/ลง/ทรงตัว: เหตุผลเชิงปริมาณ",
    "forex": "แข็ง/อ่อน/ทรงตัว: เหตุผลเชิงปริมาณ",
    "stock": "ขึ้น/ลง/ทรงตัว: หมวด + เหตุผลเชิงปริมาณ"
}}"""

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                print(f"📡 Calling Analysis API (Attempt {attempt+1})...")
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
        
        # Keep references to prevent garbage collection (use lists for multiple concurrent threads)
        self.active_threads = []  # List to hold all active threads
        self.active_workers = []  # List to hold all active workers (CRITICAL!)
        
        # Enhanced Memory System
        self.memory = {
            "summaries": [],      # [{batch, summary, sentiment}, ...]
            "markets": [],        # [{batch, gold, forex, stock}, ...]
            "trend": {"hawkish": 0, "dovish": 0, "neutral": 0}
        }
        
        # New: Tracking numeric trends
        self.trend_tracker = {
            "inflation": [],      # เก็บค่า % เงินเฟ้อ เช่น [3.5, 3.3, 3.2]
            "unemployment": [],   # เก็บค่า % การว่างงาน
            "last_direction": None  # "up" หรือ "down"
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
            
    def _track_numeric_trends(self, text: str):
        """ติดตามแนวโน้มตัวเลขจากข้อความ"""
        import re
        
        # ดึง % เงินเฟ้อ (เช่น "3.5%", "3.2%")
        # ค้นหาตัวเลขที่ตามด้วย % และมีคำว่า inflation, pce, cpi อยู่ใกล้ๆ (แบบง่าย)
        inflation_matches = re.findall(r"(\d+\.?\d*)\s*%.*?(?:inflation|pce|cpi)", text.lower())
        
        # ถ้าไม่เจอแบบแรก ให้ลองหาคำ inflation... แล้วตามด้วยตัวเลข %
        if not inflation_matches:
             inflation_matches = re.findall(r"(?:inflation|pce|cpi).*?(\d+\.?\d*)\s*%", text.lower())

        for match in inflation_matches[:3]:  # เก็บแค่ 3 ค่าแรก
            try:
                value = float(match)
                self.trend_tracker["inflation"].append(value)
                # จำกัดขนาดให้เหลือแค่ 5 ค่าล่าสุด
                if len(self.trend_tracker["inflation"]) > 5:
                    self.trend_tracker["inflation"].pop(0)
            except:
                pass
        
        # วิเคราะห์ทิศทางแนวโน้ม
        if len(self.trend_tracker["inflation"]) >= 2:
            last = self.trend_tracker["inflation"][-1]
            prev = self.trend_tracker["inflation"][-2]
            if last < prev:
                self.trend_tracker["last_direction"] = "down"  # แนวโน้มลดลง = DOVISH
            elif last > prev:
                self.trend_tracker["last_direction"] = "up"    # แนวโน้มเพิ่มขึ้น = HAWKISH
        
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
        
    def _cleanup_finished_threads(self):
        """Remove finished threads and workers from the active lists"""
        self.active_threads = [t for t in self.active_threads if t.isRunning()]
        # Workers will be cleaned up by deleteLater
        
    def _process_batch(self, batch: dict):
        self.progress.show()
        
        # Cleanup finished threads first
        self._cleanup_finished_threads()
        
        current_batch = batch.get("current_batch", {})
        text = current_batch.get("text", "")
        segments = current_batch.get("segments", [])
        batch_num = batch.get("batch_number", 0)
        
        # ดึง previous_context จาก batch (ถ้ามี)
        previous_context = batch.get("previous_context", "")
        self.last_context = previous_context  # เก็บไว้ใช้ต่อ
        
        # --- Start Translation Thread ---
        if self.show_thai:
            print(f"🔄 Starting Translation Thread for Batch #{batch_num}")
            translate_thread = QThread()
            translate_worker = TranslateWorker(segments, batch_num)
            translate_worker.moveToThread(translate_thread)
            
            translate_thread.started.connect(translate_worker.run)
            translate_worker.finished.connect(self._update_translation)
            translate_worker.finished.connect(translate_thread.quit)
            translate_worker.finished.connect(translate_worker.deleteLater)
            translate_thread.finished.connect(translate_thread.deleteLater)
            translate_thread.finished.connect(lambda: self._cleanup_finished_threads())
            
            # Keep reference to prevent garbage collection - CRITICAL!
            self.active_threads.append(translate_thread)
            self.active_workers.append(translate_worker)
            translate_thread.start()
        
        # --- Start Analysis Thread (with full memory) ---
        print(f"🔄 Starting Analysis Thread for Batch #{batch_num}")
        analysis_thread = QThread()
        analysis_worker = AnalysisWorker(
            text, batch_num, 
            previous_context=previous_context,
            memory={
                "summaries": self.memory["summaries"].copy(),
                "markets": self.memory["markets"].copy(),
                "trend": self.memory["trend"].copy()
            }
        )
        analysis_worker.moveToThread(analysis_thread)
        
        analysis_thread.started.connect(analysis_worker.run)
        analysis_worker.finished.connect(self._update_analysis)
        analysis_worker.finished.connect(analysis_thread.quit)
        analysis_worker.finished.connect(analysis_worker.deleteLater)
        analysis_thread.finished.connect(analysis_thread.deleteLater)
        analysis_thread.finished.connect(lambda: self.progress.hide())
        analysis_thread.finished.connect(lambda: self._cleanup_finished_threads())
        
        # Keep reference to prevent garbage collection - CRITICAL!
        self.active_threads.append(analysis_thread)
        self.active_workers.append(analysis_worker)
        analysis_thread.start()
        
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
            
        summary = result.get("summary", "-")
        # 🔥 เพิ่ม: ติดตามแนวโน้มตัวเลข
        self._track_numeric_trends(summary)
        
        batch_num = result.get("batch_num", 0)
        prediction = result.get("prediction", "-")
        sentiment = result.get("sentiment", "NEUTRAL").upper()
        signal_strength = result.get("signal_strength", "MEDIUM")
        consistency_note = result.get("consistency_note", "")
        
        # เพิ่มข้อมูลแนวโน้มใน consistency_note
        trend_note = ""
        if self.trend_tracker["last_direction"] == "down":
            trend_note = " (แนวโน้มเงินเฟ้อลดลง → dovish)"
        elif self.trend_tracker["last_direction"] == "up":
            trend_note = " (แนวโน้มเงินเฟ้อเพิ่มขึ้น → hawkish)"
        
        if trend_note:
            consistency_note += trend_note
        speaker_identified = result.get("speaker_identified", "")
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
{f'<div style="font-size:9px; color:#808090; margin-bottom:6px;">👥 {speaker_identified}</div>' if speaker_identified else ''}

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
        # Stop server first
        self.server.stop()
        self.server.wait(1000)
        
        # Wait for all active threads to finish
        for thread in self.active_threads:
            if thread.isRunning():
                thread.quit()
                thread.wait(2000)  # Wait up to 2 seconds per thread
        
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
