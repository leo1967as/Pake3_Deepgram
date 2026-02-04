import json
import os
import subprocess
import sys
import threading
import time
import datetime
import httpx
from dotenv import load_dotenv
import websocket # pip install websocket-client
from pathlib import Path

# Load environment variables
load_dotenv()

# Detect venv Python path
SCRIPT_DIR = Path(__file__).parent.resolve()
VENV_PYTHON = SCRIPT_DIR / ".venv310" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = sys.executable

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_KEY", "").strip()
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()
# AUDIO_URL is now dynamic, removed fixed env dependency check

if not DEEPGRAM_API_KEY:
    print("Error: DEEPGRAM_KEY not found in .env")
    sys.exit(1)

# Batch Configuration
BATCH_SIZE = 10          
BATCH_INTERVAL = 30      
CONTEXT_WINDOW = 500     

# Global State
session_data = {
    "meta": {"url": "", "title": "Waiting...", "started_at": ""},
    "segments": []
}

batch_state = {
    "buffer": [],              
    "last_send_time": None,    
    "batch_count": 0,          
    "sent_context": ""         
}

# Control State
is_running = False
current_ws = None
gui_socket = None
socket_lock = threading.Lock()

# Deepgram WebSocket URL (Nova-2)
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen?"
    "encoding=linear16&sample_rate=16000&channels=1&"
    "model=nova-2&language=en&smart_format=true&"
    "interim_results=true&endpointing=300&diarize=true"
)

def connect_to_gui():
    """Establish TCP connection to GUI server and start listener"""
    global gui_socket
    import socket
    
    while True:
        try:
            print(f"🔗 Connecting to GUI (localhost:8765)...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('localhost', 8765))
            gui_socket = s
            print(f"✅ GUI Connected! Waiting for commands...")
            
            # Start listener thread
            threading.Thread(target=listen_to_gui, args=(s,), daemon=True).start()
            return
        except Exception as e:
            print(f"⚠️ GUI connection failed: {e}. Retrying in 3s...")
            time.sleep(3)

def listen_to_gui(sock):
    """Listen for commands from GUI"""
    global is_running
    buffer = ""
    while True:
        try:
            data = sock.recv(4096).decode('utf-8')
            if not data:
                print("❌ GUI Disconnected")
                os._exit(0) # Exit if GUI closes
            
            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip(): continue
                handle_command(json.loads(line))
        except Exception as e:
            print(f"❌ Socket Read Error: {e}")
            break

def handle_command(cmd):
    """Process incoming JSON commands"""
    global is_running
    print(f"📩 Command Received: {cmd}")
    
    msg_type = cmd.get("type")
    
    if msg_type == "START":
        url = cmd.get("url")
        if not url: return
        print(f"🚀 START COMMAND: {url}")
        if is_running:
            stop_transcription()
        start_transcription(url)
        
    elif msg_type == "STOP":
        print("🛑 STOP COMMAND")
        stop_transcription()

def broadcast_to_gui(payload):
    """Send data to local GUI via TCP socket"""
    global gui_socket
    if not gui_socket: return
        
    try:
        with socket_lock:
            message = json.dumps(payload) + '\n'
            gui_socket.sendall(message.encode('utf-8'))
    except Exception as e:
        print(f"⚠️ GUI send error: {e}")

# --- Core Logic ---

def get_video_title(url):
    print(f"🎬 Fetching title for: {url}")
    try:
        cmd = [str(VENV_PYTHON), "-m", "yt_dlp", "--get-title", "--no-warnings", url]
        title = subprocess.check_output(cmd, text=True).strip()
        print(f"✅ Title: {title}")
        return title
    except Exception:
        return "Live Stream / Unknown"

def start_transcription(url):
    global is_running, session_data, batch_state
    
    is_running = True
    
    # Reset State
    session_data = {
        "meta": {
            "url": url,
            "title": get_video_title(url),
            "started_at": datetime.datetime.now().isoformat()
        },
        "segments": []
    }
    batch_state = {
        "buffer": [], "last_send_time": None, "batch_count": 0, "sent_context": ""
    }
    
    # Run in separate thread
    threading.Thread(target=run_deepgram_pipeline, args=(url,), daemon=True).start()

def stop_transcription():
    global is_running, current_ws
    is_running = False
    if current_ws:
        current_ws.close()
    
    # Trigger Final Save & Report
    save_transcript()
    send_final_summary()
    print("✅ Stopped.")

def run_deepgram_pipeline(url):
    global current_ws
    
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
    
    # Audio Pipeline Function
    def send_audio(ws):
        import queue
        audio_queue = queue.Queue(maxsize=100)
        
        print(f"🎧 Starting Audio Stream: {url}")
        
        # 1. Audio Producer Thread
        def producer():
            pipeline_cmd = (
                f'"{VENV_PYTHON}" -m yt_dlp "{url}" -o - -q --no-warnings | '
                'ffmpeg -hide_banner -loglevel panic -i pipe:0 -f s16le -ac 1 -ar 16000 pipe:1'
            )
            process = None
            try:
                process = subprocess.Popen(pipeline_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, bufsize=10**6)
                while is_running:
                    data = process.stdout.read(4096)
                    if not data: break
                    audio_queue.put(data)
            except Exception as e:
                print(f"❌ Producer Error: {e}")
            finally:
                if process: process.terminate()
                audio_queue.put(None) # Signal end
        
        threading.Thread(target=producer, daemon=True).start()
        
        # 2. Audio Consumer (with Keep-Alive)
        last_data_time = time.time()
        silence_chunk = b'\x00' * 3200 # 100ms of silence
        
        try:
            while is_running:
                try:
                    # Non-blocking get from queue with small timeout
                    chunk = audio_queue.get(timeout=0.1)
                    if chunk is None: break
                    
                    ws.send(chunk, opcode=websocket.ABNF.OPCODE_BINARY)
                    last_data_time = time.time()
                except queue.Empty:
                    # If queue is empty for more than 1 second, send silence to keep connection alive
                    if time.time() - last_data_time > 1.0:
                        ws.send(silence_chunk, opcode=websocket.ABNF.OPCODE_BINARY)
                        last_data_time = time.time()
            
            ws.send('{"type": "CloseStream"}')
        except Exception as e:
            print(f"❌ Audio Consumer Error: {e}")
        finally:
            ws.close()

    # WebSocket Callbacks
    def on_open(ws):
        print("🟢 Deepgram Connected")
        threading.Thread(target=send_audio, args=(ws,), daemon=True).start()

    def on_message(ws, message):
        if not is_running: return
        try:
            process_deepgram_message(json.loads(message))
        except: pass

    def on_error(ws, error):
        print(f"\nWebSocket Error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print("\nDeepgram Connection closed")
        
    current_ws = websocket.WebSocketApp(
        DEEPGRAM_URL, header=headers,
        on_open=on_open, on_message=on_message,
        on_error=on_error, on_close=on_close
    )
    current_ws.run_forever()

def process_deepgram_message(data):
    if "channel" in data:
        alternatives = data["channel"]["alternatives"]
        if alternatives:
            transcript = alternatives[0]["transcript"]
            is_final = data.get("is_final", False)
            
            if transcript.strip():
                # Speaker Logic
                speaker_id = 0
                words = alternatives[0].get("words", [])
                if words and "speaker" in words[0]:
                    speaker_id = words[0]["speaker"]
                
                speaker_label = f"[Speaker {speaker_id}] "
                
                if is_final:
                    start = data.get("start", 0.0)
                    end = start + data.get("duration", 0.0)
                    
                    segment = {
                        "speaker": f"Speaker {speaker_id}",
                        "text": transcript,
                        "start": start,
                        "end": end
                    }
                    session_data["segments"].append(segment)
                    add_to_batch(segment)
                    
                    sys.stdout.write(f"\r[ FINAL ] {speaker_label}{transcript}\n")
                    sys.stdout.flush()
                else:
                    sys.stdout.write(f"\r[Interim] {speaker_label}{transcript}")
                    sys.stdout.flush()

def add_to_batch(segment):
    batch_state["buffer"].append(segment)
    if batch_state["last_send_time"] is None:
        batch_state["last_send_time"] = time.time()
    
    # Send to GUI immediately
    broadcast_to_gui({"type": "segment", "data": segment})
    
    # Check Batch trigger
    elapsed = time.time() - batch_state["last_send_time"]
    if len(batch_state["buffer"]) >= BATCH_SIZE or elapsed >= BATCH_INTERVAL:
        send_batch()

def send_batch():
    if not batch_state["buffer"]: return
    
    # Create unique clip_id once per session
    if "clip_id" not in session_data["meta"]:
        session_data["meta"]["clip_id"] = f"dg_{int(time.time())}"

    batch_text = " ".join([s["text"] for s in batch_state["buffer"]])
    
    # Update Context
    sent_context = batch_state["sent_context"]

    # Calculate time range
    start_time = batch_state["buffer"][0]["start"]
    end_time = batch_state["buffer"][-1]["end"]
    
    payload = {
        "event": "batch_segments",
        "clip_id": session_data["meta"]["clip_id"],
        "batch_number": batch_state["batch_count"] + 1,
        "metadata": {
            "url": session_data["meta"]["url"],
            "title": session_data["meta"]["title"],
            "started_at": session_data["meta"]["started_at"],
            "model": "nova-2",
            "language": "en"
        },
        "time_range": {
            "start": start_time,
            "end": end_time,
            "duration": end_time - start_time
        },
        "previous_context": sent_context[-CONTEXT_WINDOW:] if sent_context else "",
        "current_batch": {
            "text": batch_text,
            "segments": batch_state["buffer"].copy(),
            "segment_count": len(batch_state["buffer"])
        },
        "full_text_with_context": (
            sent_context[-CONTEXT_WINDOW:] + " " + batch_text
        ).strip() if sent_context else batch_text
    }
    
    batch_state["sent_context"] = (sent_context + " " + batch_text)[-CONTEXT_WINDOW*3:]
    batch_state["batch_count"] += 1
    batch_state["last_send_time"] = time.time()
    
    # Broadcast batch to GUI for AI analysis
    broadcast_to_gui({"type": "batch", "data": payload})
    print(f"📤 Sent Batch #{payload['batch_number']}")

    # Send non-blocking via Webhook (Only if configured)
    if N8N_WEBHOOK_URL:
        def send_async():
            try:
                with httpx.Client(timeout=10.0) as client:
                    client.post(N8N_WEBHOOK_URL, json=payload)
                print(f"\n📤 Batch #{payload['batch_number']} sent ({payload['current_batch']['segment_count']} segments, {payload['time_range']['duration']:.1f}s)")
            except Exception as e:
                print(f"\n⚠️ Webhook failed: {str(e)[:50]}")
        
        threading.Thread(target=send_async, daemon=True).start()
    else:
        print(f"\n✅ Batch #{payload['batch_number']} broadcast to GUI ({payload['current_batch']['segment_count']} segments)")

    batch_state["buffer"] = []


def save_transcript():
    if not session_data["segments"]: return
    safe_title = "".join([c for c in session_data["meta"]["title"] if c.isalnum() or c in " -_"])[:50]
    timestamp = int(time.time())
    filename = f"transcripts/[FINAL] {safe_title}_{timestamp}.json"
    os.makedirs("transcripts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)
    print(f"💾 Saved: {filename}")

def send_final_summary():
    """Send complete transcription summary"""
    # Force send remaining buffer first
    if batch_state["buffer"]:
        send_batch()
    
    if not N8N_WEBHOOK_URL or not session_data["segments"]:
        return
    
    full_text = " ".join([s["text"] for s in session_data["segments"]])
    
    payload = {
        "event": "transcription_complete",
        "clip_id": session_data["meta"].get("clip_id", f"dg_{int(time.time())}"),
        "metadata": session_data["meta"],
        "total_batches": batch_state["batch_count"],
        "summary": {
            "total_segments": len(session_data["segments"]),
            "total_duration": session_data["segments"][-1]["end"] if session_data["segments"] else 0,
            "full_text": full_text
        },
        "segments": session_data["segments"]
    }
    
    def send_async():
        try:
            with httpx.Client(timeout=15.0) as client:
                client.post(N8N_WEBHOOK_URL, json=payload)
            print(f"\n📤 Final summary sent ({len(session_data['segments'])} total segments)")
        except Exception as e:
            print(f"\n⚠️ Final webhook failed: {str(e)[:50]}")
    
    threading.Thread(target=send_async, daemon=True).start()

if __name__ == "__main__":
    try:
        connect_to_gui() # BLOCKS until connected
        # Loop forever to keep listener alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServer Closed.")
