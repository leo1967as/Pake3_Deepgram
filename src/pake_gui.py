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
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QTextEdit, QSplitter, 
                               QDockWidget, QProgressBar, QFrame, QToolBar, 
                               QStatusBar, QPushButton, QCheckBox, QScrollArea, 
                               QButtonGroup)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QSize
from PySide6.QtGui import QTextCursor, QFont, QColor, QAction, QIcon

from economic_detector import ForexFactoryScraper
from cost_logger import log_api_cost
from config_manager import config
from gui.settings_dialog import SettingsDialog
from gui.telegram_dashboard import TelegramDashboard
from telegram_manager import tg_manager

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_KEY", "")

# AI Configuration (Saved in .env)
# MODEL_TRANSLATE and MODEL_ANALYSIS are now fetched from config dynamically
# MODEL_TRANSLATE = os.getenv("MODEL_TRANSLATE", "google/gemini-2.5-flash-lite")
# MODEL_ANALYSIS = os.getenv("MODEL_ANALYSIS", "google/gemini-3-flash-preview")
MODEL_SUMMARY = os.getenv("MODEL_SUMMARY", "google/gemini-3-pro-preview")

TOKEN_LIMIT_TRANSLATE = int(os.getenv("TOKEN_LIMIT_TRANSLATE", 1000))
TOKEN_LIMIT_ANALYSIS = int(os.getenv("TOKEN_LIMIT_ANALYSIS", 2000))
TOKEN_LIMIT_SUMMARY = int(os.getenv("TOKEN_LIMIT_SUMMARY", 4096))

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
QMainWindow, QWidget { 
    background-color: #0a0a0f; 
    color: #e0e0e0; 
}
QSplitter::handle { background-color: #1a1a24; width: 2px; }
QTextEdit { 
    background-color: #1a1a1f; 
    color: #e0e0e0; 
    border: 1px solid #2a2a3a;
    font-size: 13px;
    line-height: 1.6;
}
QLineEdit {
    background-color: #1a1a1f; 
    color: #ffffff;
    border: 1px solid #333;
    padding: 4px;
}
QScrollBar:vertical {
    border: none;
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
                            "model": config.get("model_translate"),
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": TOKEN_LIMIT_TRANSLATE
                        }
                    )
                    result = resp.json()
                    
                    # 📊 Log Token Usage
                    usage = result.get("usage", {})
                    p_tok = usage.get("prompt_tokens", 0)
                    c_tok = usage.get("completion_tokens", 0)
                    t_tok = usage.get("total_tokens", 0)
                    cost = result.get("cost", 0)
                    print(f"💰 [Translate] Usage: P={p_tok}, C={c_tok}, Total={t_tok}, Cost=${cost:.6f}")
                    log_api_cost("Translate", config.get("model_translate"), usage, cost, self.batch_num)

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
                            "model": config.get("model_analysis"),
                            "messages": [{"role": "user", "content": prompt}],
                            "response_format": {"type": "json_object"},
                            "provider": {"order": ["google-vertex/global"]},
                            "max_tokens": TOKEN_LIMIT_ANALYSIS
                        }
                    )
                    result = resp.json()
                    
                    # 📊 Log Token Usage
                    usage = result.get("usage", {})
                    p_tok = usage.get("prompt_tokens", 0)
                    c_tok = usage.get("completion_tokens", 0)
                    t_tok = usage.get("total_tokens", 0)
                    cost = result.get("cost", 0)
                    print(f"💰 [Analysis] Usage: P={p_tok}, C={c_tok}, Total={t_tok}, Cost=${cost:.6f}")
                    log_api_cost("Analysis", config.get("model_analysis"), usage, cost, self.batch_num)

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
# SESSION SUMMARY WORKER (NEW: สรุปภาพรวมจากประวัติ)
# ============================================================================
class SessionSummaryWorker(QObject):
    finished = Signal(dict)

    def __init__(self, summaries_history: list):
        super().__init__()
        # ✅ Copy list to prevent thread race conditions
        self.history = list(summaries_history) 

    def run(self):
        if not OPENROUTER_API_KEY or not self.history:
            self.finished.emit({})
            return

        print(f"🌍 SessionSummaryWorker running with {len(self.history)} summaries...")

        # รวบรวมสรุปย้อนหลังมาทำเป็น text เดียว
        # Context: Last 15 batches or less
        context_text = "\n".join([f"- Batch {h['batch']}: {h['summary']} ({h['sentiment']})" for h in self.history[-15:]])

        # 🔥 New "War Room" Prompt
        prompt = f"""คุณคือ "Supreme Commander" ใน War Room ของกองทุนระดับโลก (Hedge Fund)
หน้าที่ของคุณคืออ่านข้อมูลดิบจากสนามรบ (Summaries) แล้วประเมินสถานการณ์เชิงยุทธศาสตร์

ข้อมูลจากสนามรบ:
{context_text}

จงวิเคราะห์และสร้าง "Strategic Intelligence Brief":
1. **The Core Narrative**: จริงๆ แล้ววันนี้ตลาดกำลัง "กลัว" หรือ "หวัง" เรื่องอะไรกันแน่? (อ่านให้ออกมากกว่าแค่ text)
2. **Hidden Signals**: มีสัญญาณอะไรที่คนทั่วไปมองข้ามไหม?
3. **Actionable Intel**: ถ้าคุณต้องสั่งเทรดเดี๋ยวนี้ คุณจะสั่ง Long หรือ Short อะไร? เพราะอะไร?

ตอบเป็น JSON ภาษาไทย เท่านั้น:
{{
    "main_topic": "Narrative หลักของวันนี้ (สั้นๆ กระชับ)",
    "key_points": ["ประเด็นลึกซึ้ง 1", "ประเด็นลึกซึ้ง 2", "สิ่งที่ตลาดกำลัง Price-in"],
    "overall_sentiment": "HAWKISH / DOVISH / NEUTRAL",
    "market_implication": "คำแนะนำการเทรดแบบ Actionable (เช่น 'Short Gold ถ้าระดับ 2030 รับไม่อยู่')",
    "confidence_score": "ความมั่นใจ 1-10"
}}"""

        try:
            with httpx.Client(timeout=60) as client:
                # Use token limit from config or fallback
                max_tokens = config.get("max_tokens_summary", TOKEN_LIMIT_SUMMARY)
                
                resp = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                    json={
                        "model": MODEL_SUMMARY,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                        "max_tokens": max_tokens
                    }
                )
                result = resp.json()
                
                # 📊 Log Token Usage
                usage = result.get("usage", {})
                p_tok = usage.get("prompt_tokens", 0)
                c_tok = usage.get("completion_tokens", 0)
                t_tok = usage.get("total_tokens", 0)
                cost = result.get("cost", 0)
                print(f"💰 [Summary] Usage: P={p_tok}, C={c_tok}, Total={t_tok}, Cost=${cost:.6f}")
                log_api_cost("Summary", MODEL_SUMMARY, usage, cost)

                content = result["choices"][0]["message"]["content"]
                if content.startswith("```"):
                    content = "\n".join(content.split("\n")[1:-1])
                
                parsed = json.loads(content)
                
                # ✅ Defensive Handling: Check if list
                if isinstance(parsed, list):
                    print("⚠️ AI returned list instead of dict, taking first item.")
                    parsed = parsed[0] if len(parsed) > 0 else {}
                    
                if not isinstance(parsed, dict):
                     print(f"❌ Invalid format: {type(parsed)}")
                     parsed = {}
                
                print("🌍 Big Picture Analysis Completed.")
                self.finished.emit(parsed)

        except Exception as e:
            print(f"❌ Session Summary Error: {e}")
            if 'result' in locals():
                print(f"🔍 Validating logic... Raw API Response: {result}")
            self.finished.emit({})

# ============================================================================
# ECONOMIC NEWS WIDGET
# ============================================================================
class FetchNewsWorker(QObject):
    finished = Signal(list)
    
    def __init__(self, source="forexfactory", timeframe="today"):
        super().__init__()
        self.source = source
        self.timeframe = timeframe
        
    def run(self):
        try:
            data = []
            if self.source == "mt5":
                print("🏭 Fetching from MetaTrader 5...")
                fetcher = MT5NewsFetcher()
                data = fetcher.fetch_news(timeframe=self.timeframe)
            else:
                print("🌎 Fetching from ForexFactory...")
                scraper = ForexFactoryScraper()
                data = scraper.fetch_news(timeframe=self.timeframe)
                
            self.finished.emit(data)
        except Exception as e:
            print(f"Fetch Error: {e}")
            self.finished.emit([])

class EconomicNewsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.data = []
        self.timeframe = "today"
        self.source = "forexfactory" # Default
        self.setup_ui()
        self.load_cache()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- HEADER ---
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet("background: #14141c; border-bottom: 1px solid #2a2a3a;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)
        
        title = QLabel("Economic Calendar")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #e0e0e0;")
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(30, 30)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setToolTip("Refresh Data")
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        h_layout.addWidget(title)
        h_layout.addStretch()
        h_layout.addWidget(self.refresh_btn)
        layout.addWidget(header)
        
        # --- CONTROLS ---
        controls = QFrame()
        controls.setStyleSheet("background: #14141c; padding: 10px;")
        c_layout = QVBoxLayout(controls)
        c_layout.setSpacing(10)
        c_layout.setContentsMargins(10, 5, 10, 5)
        
        # Source "Slide" (Segmented Control)
        source_layout = QHBoxLayout()
        source_lbl = QLabel("Source:")
        source_lbl.setStyleSheet("color: #808090; font-size: 11px;")
        
        self.btn_ff = QPushButton("ForexFactory")
        self.btn_mt5 = QPushButton("MetaTrader 5")
        
        self.btn_ff = QPushButton("ForexFactory")
        self.btn_mt5 = QPushButton("MetaTrader 5")
        
        for btn in [self.btn_ff, self.btn_mt5]:
            btn.setCheckable(True)
            btn.setFixedHeight(35) # Increased size
            btn.setCursor(Qt.PointingHandCursor)
            
        self.btn_ff.setChecked(True)
        self.source_group = QButtonGroup(self)
        self.source_group.addButton(self.btn_ff)
        self.source_group.addButton(self.btn_mt5)
        self.source_group.buttonClicked.connect(self.on_source_changed)
        
        self.apply_source_style()
        
        source_layout.addWidget(source_lbl)
        source_layout.addSpacing(15) # Add spacing after label
        # Invisible Spacer Label as requested "ข้อความมองไม่เห็น"
        # spacer_lbl = QLabel("   ") 
        # source_layout.addWidget(spacer_lbl)
        
        source_layout.addWidget(self.btn_ff)
        source_layout.addWidget(self.btn_mt5)
        source_layout.addStretch() # Push everything to left
        
        c_layout.addLayout(source_layout)
        
        # Toggle: Today / Week
        toggle_layout = QHBoxLayout()
        self.btn_today = QPushButton("Today")
        self.btn_week = QPushButton("Week")
        
        for btn in [self.btn_today, self.btn_week]:
            btn.setCheckable(True)
            btn.setFixedHeight(35) # Increased size
            btn.setCursor(Qt.PointingHandCursor)
            
        self.btn_today.setChecked(True)
        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.btn_today)
        self.btn_group.addButton(self.btn_week)
        
        self.btn_group.buttonClicked.connect(self.on_timeframe_changed)
        
        self.apply_toggle_style()
        
        toggle_layout.addWidget(self.btn_today)
        toggle_layout.addWidget(self.btn_week)
        c_layout.addLayout(toggle_layout)
        
        # Auto Snipe Checkbox
        self.chk_auto = self.create_checkbox("⚡ Auto Snipe (T-1m, +10s, +1m)", "#22c55e", False)
        self.chk_auto.setToolTip("Automatically refresh before and after High Impact news")
        self.chk_auto.stateChanged.connect(self.schedule_next_refresh)
        c_layout.addWidget(self.chk_auto)
        
        # Filters
        filter_layout = QHBoxLayout()
        self.chk_high = self.create_checkbox("High", "#ef4444", True)
        self.chk_med = self.create_checkbox("Med", "#f59e0b", True)
        self.chk_low = self.create_checkbox("Low", "#eab308", True) # Yellowish
        self.chk_none = self.create_checkbox("None", "#606070", False) # Default unchecked
        
        filter_layout.addWidget(self.chk_high)
        filter_layout.addWidget(self.chk_med)
        filter_layout.addWidget(self.chk_low)
        filter_layout.addWidget(self.chk_none)
        c_layout.addLayout(filter_layout)
        
        layout.addWidget(controls)
        
        # --- NEWS LIST ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: #0f0f14; }")
        
        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: #0f0f14;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(10, 10, 10, 10)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch() # Push items to top
        
        self.scroll.setWidget(self.list_container)
        layout.addWidget(self.scroll)
        
        # Status Bar
        self.lbl_updated = QLabel("Last update: -")
        self.lbl_updated.setAlignment(Qt.AlignCenter)
        self.lbl_updated.setStyleSheet("color: #606070; font-size: 10px; padding: 5px;")
        layout.addWidget(self.lbl_updated)
        
        # Auto Refresh Timer
        self.snipe_timer = QTimer()
        self.snipe_timer.setSingleShot(True)
        self.snipe_timer.timeout.connect(self.on_snipe_trigger)

    def create_checkbox(self, text, color, checked=True):
        chk = QCheckBox(text)
        chk.setChecked(checked)
        chk.setStyleSheet(f"""
            QCheckBox {{ color: {color}; font-size: 11px; font-weight: bold; }}
            QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 3px; border: 1px solid #3a3a4a; background: #2a2a3a; }}
            QCheckBox::indicator:checked {{ background: {color}; border-color: {color}; }}
        """)
        # Don't connect stateChanged here for general filters, logic is handled in render_list
        if text not in ["⚡ Auto Snipe (T-1m, +10s, +1m)"]:
             chk.stateChanged.connect(self.render_list)
        return chk
        
    def parse_news_time(self, time_str):
        """Parse '2:30pm' string to a datetime object for TODAY."""
        if not time_str or "Day" in time_str or "Tentative" in time_str:
            return None
        
        try:
            # Parse time string like "2:30pm"
            # Note: This assumes the news time is relative to the current system date
            now = datetime.datetime.now()
            dt = datetime.datetime.strptime(time_str, "%I:%M%p")
            news_dt = now.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
            return news_dt
        except:
            return None

    def schedule_next_refresh(self):
        """Find the next refresh target (T-1m, T+10s, T+1m)"""
        self.snipe_timer.stop()
        
        if not self.chk_auto.isChecked() or not self.data:
            self.lbl_updated.setText(f"Last update: {datetime.datetime.now().strftime('%H:%M:%S')}")
            return

        now = datetime.datetime.now()
        targets = []
        
        # Collect all triggers
        for item in self.data:
            # Only snipe High/Medium impact events
            impact = item.get("impact", "")
            if impact not in ["High", "Medium"]:
                continue
                
            news_dt = self.parse_news_time(item.get("time", ""))
            if not news_dt:
                continue
            
            # 1. T - 1 minute (Preparation)
            targets.append((news_dt - datetime.timedelta(minutes=1), "Prep"))
            # 2. T + 10 seconds (Immediate Result)
            targets.append((news_dt + datetime.timedelta(seconds=10), "Catch"))
            # 3. T + 1 minute (Confirmation)
            targets.append((news_dt + datetime.timedelta(minutes=1), "Confirm"))

        # Find nearest future target
        targets.sort(key=lambda x: x[0])
        next_target = None
        
        for t, label in targets:
            if t > now:
                next_target = (t, label)
                break
        
        if next_target:
            t_obj, label = next_target
            delta_ms = int((t_obj - now).total_seconds() * 1000)
            self.snipe_timer.start(delta_ms)
            
            time_str = t_obj.strftime("%H:%M:%S")
            self.lbl_updated.setText(f"⏳ Next: {time_str} ({label})")
            print(f"🎯 Snipe scheduled at {time_str} ({label})")
        else:
            self.lbl_updated.setText(f"Updated: {now.strftime('%H:%M')}. No more/future events.")

    def on_snipe_trigger(self):
        print("⚡ Snipe Trigger executing...")
        self.refresh_data() # This will reload data, and on_data_fetched will call schedule_next_refresh again

    def apply_source_style(self):
        active = "background: #2a2a3a; color: #e0e0e0; border: 1px solid #6366f1;"
        inactive = "background: #1a1a24; color: #606070; border: 1px solid #2a2a3a;"
        
        if self.btn_ff.isChecked():
            self.btn_ff.setStyleSheet(active + "border-top-left-radius: 4px; border-bottom-left-radius: 4px;")
            self.btn_mt5.setStyleSheet(inactive + "border-top-right-radius: 4px; border-bottom-right-radius: 4px;")
        else:
            self.btn_ff.setStyleSheet(inactive + "border-top-left-radius: 4px; border-bottom-left-radius: 4px;")
            self.btn_mt5.setStyleSheet(active + "border-top-right-radius: 4px; border-bottom-right-radius: 4px;")

    def on_source_changed(self):
        self.apply_source_style()
        if self.btn_ff.isChecked():
            self.source = "forexfactory"
        else:
            self.source = "mt5"
        self.refresh_data()

    def apply_toggle_style(self):
        active_style = "background: #6366f1; color: white; border: none; font-weight: bold;"
        inactive_style = "background: #2a2a3a; color: #808090; border: 1px solid #3a3a4a;"
        
        if self.btn_today.isChecked():
            self.btn_today.setStyleSheet(active_style + "border-top-left-radius: 6px; border-bottom-left-radius: 6px;")
            self.btn_week.setStyleSheet(inactive_style + "border-top-right-radius: 6px; border-bottom-right-radius: 6px; border-left: none;")
        else:
            self.btn_today.setStyleSheet(inactive_style + "border-top-left-radius: 6px; border-bottom-left-radius: 6px; border-right: none;")
            self.btn_week.setStyleSheet(active_style + "border-top-right-radius: 6px; border-bottom-right-radius: 6px;")

    def on_timeframe_changed(self):
        self.apply_toggle_style()
        if self.btn_today.isChecked():
            self.timeframe = "today"
        else:
            self.timeframe = "week"
        # Refresh on change
        self.refresh_data()

    def get_cache_path(self):
        return os.path.join("data", "news_cache.json")

    def load_cache(self):
        try:
            path = self.get_cache_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                    self.data = cache.get("data", [])
                    last_update = cache.get("last_update", "-")
                    self.lbl_updated.setText(f"Last update: {last_update}")
                    self.timeframe = cache.get("timeframe", "today")
                    self.source = cache.get("source", "forexfactory")
                    
                    if self.timeframe == "week":
                        self.btn_week.setChecked(True)
                    else:
                        self.btn_today.setChecked(True)
                    self.apply_toggle_style()
                    
                    if self.source == "mt5":
                        self.btn_mt5.setChecked(True)
                    else:
                        self.btn_ff.setChecked(True)
                    self.apply_source_style()
                    
                    self.render_list()
                    self.schedule_next_refresh() # Restore schedule
        except Exception as e:
            print(f"Cache load error: {e}")

    def save_cache(self):
        try:
            os.makedirs("data", exist_ok=True)
            with open(self.get_cache_path(), "w", encoding="utf-8") as f:
                json.dump({
                    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "timeframe": self.timeframe,
                    "source": self.source,
                    "data": self.data
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Cache save error: {e}")
            
    def refresh_data(self):
        self.refresh_btn.setEnabled(False)
        self.lbl_updated.setText("⏳ Updating...")
        
        # Use worker thread to avoid freezing UI
        self.worker_thread = QThread()
        self.worker = FetchNewsWorker(source=self.source, timeframe=self.timeframe)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_data_fetched)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()
        
    def on_data_fetched(self, data):
        self.data = data
        self.save_cache()
        self.render_list()
        self.schedule_next_refresh()
        self.refresh_btn.setEnabled(True)
        
        # Only set text if NOT auto-sniping (scheduler overwrites it otherwise)
        if not self.chk_auto.isChecked():
             self.lbl_updated.setText(f"Last update: {datetime.datetime.now().strftime('%H:%M:%S')}")

    def render_list(self):
        # Clear existing items
        while self.list_layout.count() > 1: # Keep the stretch item at end
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.data:
            lbl = QLabel("No Data")
            lbl.setStyleSheet("color: #606070; font-style: italic; margin-top: 20px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.list_layout.insertWidget(0, lbl)
            return

        # 1. Filter items first
        filtered_items = []
        for item in self.data:
            impact = item.get("impact", "Unknown")
            # Filtering
            if impact == "High" and not self.chk_high.isChecked(): continue
            if impact == "Medium" and not self.chk_med.isChecked(): continue
            if impact == "Low" and not self.chk_low.isChecked(): continue
            if (impact == "Non-Econ" or impact == "Unknown") and not self.chk_none.isChecked(): continue
            filtered_items.append(item)

        # 2. Find Next Event (Closest future event)
        now = datetime.datetime.now()
        pinned_item = None
        candidates = []
        
        for item in filtered_items:
            dt = self.parse_news_time(item.get("time"))
            if dt and dt > now:
                candidates.append((dt, item))
        
        if candidates:
            # Sort by time
            candidates.sort(key=lambda x: x[0])
            pinned_item = candidates[0][1]
            
        # 3. Render Items
        insert_idx = 0
        
        # If we have a pinned item, render it FIRST
        if pinned_item:
            # Pinned Card
            card = self.create_pinned_card(pinned_item)
            self.list_layout.insertWidget(insert_idx, card)
            insert_idx += 1
            
            # Separator/Label
            sep_lbl = QLabel("👇 UPCOMING / PAST")
            sep_lbl.setStyleSheet("color: #606070; font-size: 10px; font-weight: bold; margin-top: 8px; margin-bottom: 4px; border-bottom: 1px solid #2a2a3a;")
            sep_lbl.setAlignment(Qt.AlignCenter)
            self.list_layout.insertWidget(insert_idx, sep_lbl)
            insert_idx += 1

        # Render the rest
        for item in filtered_items:
            if item == pinned_item: 
                continue # Skip because we already showed it at top
                
            card = self.create_news_card(item)
            self.list_layout.insertWidget(insert_idx, card)
            insert_idx += 1

    def create_pinned_card(self, item):
        frame = self.create_news_card(item)
        
        impact = item.get("impact", "Low")
        color = "#eab308"
        if impact == "High": color = "#ef4444"
        elif impact == "Medium": color = "#f59e0b"
        
        # Override style for Pinned Item
        frame.setStyleSheet(f"""
            QFrame {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(30, 30, 40, 1), stop:1 rgba(20, 20, 25, 1));
                border: 2px solid {color}; 
                border-radius: 6px; 
            }}
            QFrame:hover {{ border-color: white; }}
        """)
        
        # Add a "NEXT EVENT" badge overlay or modify layout?
        # Simpler: Modify the layout of the existing frame instance
        # Retrieve layout and insert a badge at the top
        # But layout structure is hard to modify after creation.
        # Instead, we just rely on the thick border and position (Top).
        
        return frame
            
    def create_news_card(self, item):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame { background: #1a1a24; border-radius: 6px; border: 1px solid #2a2a3a; }
            QFrame:hover { border-color: #3a3a4a; background: #20202a; }
        """)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        # Time & Currency Column
        left_col = QVBoxLayout()
        left_col.setSpacing(2)
        
        time_lbl = QLabel(item.get("time", ""))
        time_lbl.setStyleSheet("color: #808090; font-size: 11px;")
        
        curr_lbl = QLabel(item.get("currency", ""))
        curr_lbl.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 12px;")
        
        # Flag logic (simple unicode or text)
        # Replacing currency with simple colored label could work too
        
        left_col.addWidget(time_lbl)
        left_col.addWidget(curr_lbl)
        layout.addLayout(left_col)
        
        # Impact Bar
        impact = item.get("impact", "Low")
        color = "#eab308" # Low
        if impact == "High": color = "#ef4444"
        elif impact == "Medium": color = "#f59e0b"
        elif impact == "Non-Econ": color = "#606070"
        
        bar = QFrame()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background: {color}; border-radius: 2px;")
        layout.addWidget(bar)
        
        # Title & Data
        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        
        title = QLabel(item.get("title", ""))
        title.setWordWrap(True)
        title.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        
        # Data string: "Act: 0.4% | Fcst: 0.3%"
        actual = item.get("actual", "")
        forecast = item.get("forecast", "")
        if actual or forecast:
            data_str = f"Act: <span style='color:#ffffff'>{actual}</span> | Fcst: {forecast}"
            data_lbl = QLabel(data_str)
            data_lbl.setStyleSheet("color: #808090; font-size: 10px;")
            data_lbl.setTextFormat(Qt.RichText)
            right_col.addWidget(title)
            right_col.addWidget(data_lbl)
        else:
            right_col.addWidget(title)
            
        layout.addLayout(right_col, stretch=1)
        
        return frame

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
        
        # System State
        self.is_running = False  # Start in PAUSED state
        
        # New: Tracking numeric trends
        self.trend_tracker = {
            "inflation": [],      # เก็บค่า % เงินเฟ้อ เช่น [3.5, 3.3, 3.2]
            "unemployment": [],   # เก็บค่า % การว่างงาน
            "last_direction": None  # "up" หรือ "down"
        }
        self.last_big_picture_time = 0  # Cooldown tracker
        self.last_context = ""
        
        self._build_ui()
        self._start_server()
        
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- TOOLBAR ---
        toolbar = QToolBar("Main Toolbar")
        toolbar.setStyleSheet("background-color: #0a0a0f; border-bottom: 1px solid #1a1a24; padding: 4px;")
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        
        # Title Label
        title_label = QLabel("PAKE LIVE ANALYZER")
        title_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #6366f1; letter-spacing: 2px; margin-left: 8px;")
        toolbar.addWidget(title_label)
        
        # --- START/STOP BUTTON ---
        self.btn_start = QPushButton("▶ START")
        self.btn_start.setCheckable(True)
        self.btn_start.setStyleSheet("""
            QPushButton { 
                background-color: #22c55e; 
                color: white; 
                font-weight: bold; 
                border-radius: 4px; 
                padding: 6px 16px;
                font-size: 12px;
                margin-left: 20px;
            }
            QPushButton:checked { 
                background-color: #ef4444; 
                border: 2px solid #b91c1c;
            }
            QPushButton:hover { opacity: 0.9; }
        """)
        self.btn_start.clicked.connect(self.toggle_processing)
        toolbar.addWidget(self.btn_start)
        
        # Overall Trend Indicator
        self.trend_label = QLabel("📊 TREND: -")
        self.trend_label.setStyleSheet("font-size: 11px; color: #606070; padding: 4px 10px; background: #1a1a24; border-radius: 4px; margin-left: 20px;")
        toolbar.addWidget(self.trend_label)
        
        toolbar.addSeparator()

        # Toggle Thai Button
        self.toggle_btn = QPushButton("🇹🇭 Thai ON")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.clicked.connect(self._toggle_thai)
        self.toggle_btn.setStyleSheet("""
            QPushButton { background: #1a1a24; border: 1px solid #2a2a3a; color: #a0a0b0; border-radius: 4px; padding: 4px 10px; font-size: 11px; }
            QPushButton:hover { background: #2a2a3a; color: #e0e0e0; }
            QPushButton:checked { background: #6366f1; color: white; border-color: #6366f1; }
        """)
        toolbar.addWidget(self.toggle_btn)

        # Toggle News Button
        self.btn_news = QPushButton("📅 News")
        self.btn_news.setCheckable(True)
        self.btn_news.setStyleSheet("""
            QPushButton { background: #1a1a24; border: 1px solid #2a2a3a; color: #a0a0b0; border-radius: 4px; padding: 4px 10px; font-size: 11px; }
            QPushButton:hover { background: #2a2a3a; color: #e0e0e0; }
            QPushButton:checked { background: #6366f1; color: white; border-color: #6366f1; }
        """)
        self.btn_news.clicked.connect(self.toggle_news_panel)
        toolbar.addWidget(self.btn_news)
        
        toolbar.addSeparator()

        # Settings Action
        settings_action = QAction(QIcon(), "⚙️ Settings", self)
        settings_action.setStatusTip("Open system settings")
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        # Telegram Dashboard Action
        tg_action = QAction(QIcon(), "📡 Telegram", self)
        tg_action.setStatusTip("Open Telegram Newsroom")
        tg_action.triggered.connect(self.open_telegram)
        toolbar.addAction(tg_action)

        # Spacer to push status to the right
        toolbar.addSeparator()
        toolbar.addWidget(QWidget()) # Invisible widget to push content
        
        self.status = QLabel("● WAITING")
        self.status.setStyleSheet("font-size: 11px; color: #606070; margin-right: 8px;")
        toolbar.addWidget(self.status)

        # --- NEWS DOCK ---
        self.news_dock = QDockWidget("Economic Calendar", self)
        self.news_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.news_dock.setFeatures(QDockWidget.DockWidgetClosable) # No float/move for simplicity
        
        self.news_widget = EconomicNewsWidget()
        self.news_dock.setWidget(self.news_widget)
        self.news_dock.hide() # Hidden by default
        self.addDockWidget(Qt.RightDockWidgetArea, self.news_dock)
        
        # Connect dock close event to button uncheck
        self.news_dock.visibilityChanged.connect(self.btn_news.setChecked)
        
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
        
        # Column 3: AI Intelligence (ปรับแก้ตรงนี้)
        col3 = QWidget()
        col3_layout = QVBoxLayout(col3)
        col3_layout.setContentsMargins(6, 10, 12, 12)
        
        # --- ส่วนที่ 1: Big Picture Dashboard (ของใหม่) ---
        lbl3_top = QLabel("🌍 BIG PICTURE (LIVE SUMMARY)")
        lbl3_top.setStyleSheet("font-size: 10px; font-weight: bold; margin-bottom: 6px; color: #f59e0b;")
        col3_layout.addWidget(lbl3_top)

        self.big_picture_view = QTextEdit()
        self.big_picture_view.setReadOnly(True)
        self.big_picture_view.setFixedHeight(280) # เพิ่มความสูงตาม Request
        self.big_picture_view.setStyleSheet("""
            QTextEdit { 
                background-color: #1a1a1f; 
                border: 1px solid #f59e0b; 
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                line-height: 1.4;
            }
        """)
        col3_layout.addWidget(self.big_picture_view)
        
        # --- ส่วนที่ 2: Live Feed (ของเดิม) ---
        col3_layout.addSpacing(10)
        lbl3_btm = QLabel("🧠 LIVE INTELLIGENCE FEED")
        lbl3_btm.setStyleSheet("font-size: 10px; font-weight: bold; margin-bottom: 6px;")
        col3_layout.addWidget(lbl3_btm)
        
        self.ai_feed = QTextEdit()
        self.ai_feed.setReadOnly(True)
        col3_layout.addWidget(self.ai_feed)
        
        self.splitter.addWidget(col1)
        self.splitter.addWidget(self.col2)
        self.splitter.addWidget(col3)
        self.splitter.setSizes([450, 450, 700])
        layout.addWidget(self.splitter)
        
        self.setStatusBar(QStatusBar(self))
        self._set_status("● PAUSED", "#606070")

    def toggle_processing(self):
        """Toggle Start/Stop state"""
        if self.btn_start.isChecked():
            # START STATE
            self.is_running = True
            self.btn_start.setText("⏹ STOP")
            self._set_status("● LISTENING", "#22c55e")
            self.transcript.append("<span style='color: #22c55e;'>--- SYSTEM STARTED ---</span>")
        else:
            # STOP STATE
            self.is_running = False
            self.btn_start.setText("▶ START")
            self._set_status("● PAUSED", "#ef4444")
            self.transcript.append("<span style='color: #ef4444;'>--- SYSTEM PAUSED ---</span>")
        
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
        
    def toggle_news_panel(self):
        if self.btn_news.isChecked():
            self.news_dock.show()
        else:
            self.news_dock.hide()

    def _set_status(self, text: str, color: str):
        self.status.setText(text)
        self.status.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: bold;")
        
    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def open_telegram(self):
        dlg = TelegramDashboard(self)
        dlg.exec()

    def _handle_telegram_auto_post(self, data, raw_text):
        """Check rules and send Telegram message"""
        cfg = tg_manager.config
        sentiment = data.get("sentiment", "NEUTRAL")
        
        should_post = False
        
        if cfg.get("auto_post_all", False):
            should_post = True
        elif cfg.get("auto_post_hawk_dove", False):
            if sentiment in ["HAWKISH", "DOVISH"]:
                should_post = True
                
        if should_post:
            template = cfg["templates"].get("analysis_update", "")
            if not template:
                return
                
            # Formatting
            impact_text = f"Gold: {data.get('gold')} | Forex: {data.get('forex')}"
            
            msg = template.replace("{sentiment}", sentiment)
            msg = msg.replace("{impact}", impact_text)
            msg = msg.replace("{summary}", data.get("summary"))
            msg = msg.replace("{prediction}", data.get("prediction"))
            msg = msg.replace("{raw_text}", raw_text)
            
            print(f"📡 Auto-Posting to Telegram: {sentiment}")
            tg_manager.send_to_all(msg)

    def _on_message(self, payload: dict):
        # Always allow connection status updates, but filter content if paused
        msg_type = payload.get("type")
        data = payload.get("data", {})
        
        # Allow heartbeat/status, block DATA if paused
        if not self.is_running:
            # Maybe show status only? For now strict block of heavy lifting
            return

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
        """Deprecated: Unsafe."""
        pass

    def _safe_remove_thread(self, thread, worker):
        """Safely remove finished thread/worker from tracking lists."""
        if thread in self.active_threads:
            self.active_threads.remove(thread)
        if worker in self.active_workers:
            self.active_workers.remove(worker)
        # print(f"♻️ Cleaned up thread. Active: {len(self.active_threads)}")
        
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
        if config.get("enable_translation"):
            print(f"🔄 Starting Translation Thread for Batch #{batch_num}")
            translate_thread = QThread()
            translate_worker = TranslateWorker(segments, batch_num)
            translate_worker.moveToThread(translate_thread)
            
            translate_thread.started.connect(translate_worker.run)
            translate_worker.finished.connect(self._update_translation)
            translate_worker.finished.connect(translate_thread.quit)
            translate_worker.finished.connect(translate_worker.deleteLater)
            translate_thread.finished.connect(translate_thread.deleteLater)
            
            # SAFE Thread Cleanup
            translate_thread.finished.connect(lambda: self._safe_remove_thread(translate_thread, translate_worker))
            
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
        
        # SAFE Thread Cleanup
        analysis_thread.finished.connect(lambda: self._safe_remove_thread(analysis_thread, analysis_worker))
        
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

        # 🔥 TRIGGER BIG PICTURE UPDATE
        # อัปเดตทุกๆ 10 Batches (ลดความถี่ลงจาก 5) หรือถ้าเพิ่งเริ่ม (Batch 1)
        if len(self.memory["summaries"]) > 0 and (len(self.memory["summaries"]) % 10 == 0 or len(self.memory["summaries"]) == 1):
            print("🌍 Triggering Global Summary Update...")
            
            # สร้าง Thread สำหรับ Summary แยกต่างหาก
            summary_thread = QThread()
            # ส่งประวัติสรุปทั้งหมดไปให้ AI วิเคราะห์ (Copy of list created in __init__)
            summary_worker = SessionSummaryWorker(self.memory["summaries"]) 
            summary_worker.moveToThread(summary_thread)
            
            summary_thread.started.connect(summary_worker.run)
            summary_worker.finished.connect(self._update_big_picture) # สร้างฟังก์ชันนี้รับผล
            summary_worker.finished.connect(summary_thread.quit)
            summary_worker.finished.connect(summary_worker.deleteLater)
            summary_thread.finished.connect(summary_thread.deleteLater)
            summary_thread.finished.connect(lambda: self._cleanup_finished_threads())
            
            self.active_threads.append(summary_thread)
            # self.active_workers.append(summary_worker)  <-- Delete later handles this, no need to keep strict ref if deleteLater is connected
            # But we keep it to be safe against GC during execution
            self.active_workers.append(summary_worker)
            summary_thread.start()

    # เพิ่มฟังก์ชันใหม่สำหรับแสดงผล Big Picture
    def _update_big_picture(self, data: dict):
        if not data: return
        
        topic = data.get("main_topic", "-")
        points = data.get("key_points", [])
        sentiment = data.get("overall_sentiment", "NEUTRAL")
        market = data.get("market_implication", "-")
        confidence = data.get("confidence_score", "-")
        
        # สร้าง HTML สวยๆ
        points_html = "".join([f"<li style='margin-bottom:4px;'>{p}</li>" for p in points])
        
        color = "#f59e0b"
        bg_color = "rgba(245, 158, 11, 0.1)"
        if "HAWK" in sentiment: 
            color = "#ef4444"
            bg_color = "rgba(239, 68, 68, 0.1)"
        elif "DOVE" in sentiment: 
            color = "#22c55e"
            bg_color = "rgba(34, 197, 94, 0.1)"
        
        html = f"""
        <div style='font-weight:bold; font-size:16px; color:#e0e0e0; margin-bottom:8px; border-bottom: 1px solid #2a2a3a; padding-bottom:5px;'>
            📌 {topic}
        </div>
        
        <div style='background:{bg_color}; border-left: 3px solid {color}; padding: 8px; margin-bottom: 10px; border-radius: 4px;'>
            <div style='font-size:10px; color:{color}; font-weight:bold; margin-bottom:2px;'>INTELLIGENCE ASSESSMENT</div>
            <span style='font-size:12px; font-weight:bold; color:#e0e0e0;'>SENTIMENT: {sentiment}</span>
            <span style='float:right; font-size:10px; color:#808090;'>Confidence: {confidence}/10</span>
        </div>
        
        <ul style='margin:0; padding-left:15px; color:#b0b0c0; font-size:13px; margin-bottom:12px;'>
            {points_html}
        </ul>
        
        <div style='background:#2a2a3a; padding:8px; border-radius:4px;'>
                <div style='font-size:12px; color:#e0e0e0; font-style:italic;'>"{market}"</div>
        </div>
        """
        
        self.big_picture_view.setHtml(html)
        
        # Scroll to top just in case
        self.big_picture_view.verticalScrollBar().setValue(0)
        
        # 🚀 Auto-Post to Telegram with Cooldown
        self._handle_telegram_big_picture_post(data)
    
    def _handle_telegram_big_picture_post(self, data: dict):
        """Send Big Picture update to Telegram if auto-post is enabled."""
        import time
        # 1. Check specific toggle for Big Picture
        if not tg_manager.config.get("auto_post_summary", False):
             print("🚫 [Telegram] Big Picture Auto-Post skipped (Disabled in Settings)")
             return

        # 2. Cooldown Check (5 Minutes)
        current_time = time.time()
        if current_time - self.last_big_picture_time < 300: # 300 seconds = 5 mins
            print(f"⏳ [Telegram] Big Picture skipped (Cooldown active: {int(300 - (current_time - self.last_big_picture_time))}s remaining)")
            return

        try:
            # Fallback default template if config is missing or empty
            default_template = "🌍 <b>BIG PICTURE UPDATE</b>\n\n<b>{title}</b>\n\n{bullets}\n\n🔮 <b>Strategy:</b> {strategy}"
            template = tg_manager.config.get("templates", {}).get("session_summary", "")
            
            if not template:
                print("⚠️ [Telegram] Template 'session_summary' missing, using default fallback.")
                template = default_template
            
            # Format Bullets
            bullets = "\n".join([f"• {b}" for b in data.get("key_points", [])])
            
            msg = template.format(
                title=data.get("main_topic", "Market Update"),
                bullets=bullets,
                strategy=data.get("market_implication", "Wait and see.")
            )
            
            tg_manager.send_to_all(msg)
            tg_manager.log_activity("BIG_PICTURE", f"Sent summary: {data.get('main_topic')}")
            print("📤 [Telegram] Sent Big Picture Update")
            self.last_big_picture_time = current_time
            
        except Exception as e:
            print(f"❌ [Telegram] Big Picture Send Error: {e}")
            tg_manager.log_activity("ERROR", f"Big Picture Error: {e}")
    
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
