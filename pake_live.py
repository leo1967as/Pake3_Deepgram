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

# Detect venv Python path (works even if VS Code uses wrong interpreter)
SCRIPT_DIR = Path(__file__).parent.resolve()
VENV_PYTHON = SCRIPT_DIR / ".venv310" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = sys.executable  # Fallback

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_KEY", "").strip()
AUDIO_URL = os.getenv("AUDIO_URL", "").strip()
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()

if not DEEPGRAM_API_KEY:
    print("Error: DEEPGRAM_KEY not found in .env")
    sys.exit(1)

if not AUDIO_URL:
    print("Error: AUDIO_URL not found in .env")
    sys.exit(1)

# Batch Configuration
BATCH_SIZE = 10          # Send every N segments
BATCH_INTERVAL = 30      # Or every N seconds
CONTEXT_WINDOW = 500     # Characters of previous context to include

# Local GUI Broadcast Config
LOCAL_WS_URL = "ws://localhost:8765"
ENABLE_LOCAL_BROADCAST = True

# Global session data
session_data = {
    "meta": {
        "url": AUDIO_URL,
        "title": "Fetching...",
        "started_at": datetime.datetime.now().isoformat()
    },
    "segments": []
}

# Batch processing state
batch_state = {
    "buffer": [],              # Current batch buffer
    "last_send_time": None,    # Last batch send time
    "batch_count": 0,          # Total batches sent
    "sent_context": ""         # Rolling context from previously sent batches
}

# Persistent GUI Connection State
gui_socket = None

def connect_to_gui():
    """Establish TCP connection to GUI server"""
    global gui_socket
    if not ENABLE_LOCAL_BROADCAST:
        return False
        
    import socket
    max_retries = 10
    for i in range(max_retries):
        try:
            print(f"🔗 Connecting to GUI... (attempt {i+1}/{max_retries})")
            gui_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            gui_socket.connect(('localhost', 8765))
            print(f"✅ GUI Connected!")
            return True
        except Exception as e:
            print(f"⚠️ GUI not ready: {e}")
            if gui_socket:
                gui_socket.close()
                gui_socket = None
            time.sleep(1)
    
    print("❌ Could not connect to GUI. Running without GUI.")
    return False

def broadcast_to_gui(payload):
    """Send data to local GUI via TCP socket"""
    global gui_socket
    if not ENABLE_LOCAL_BROADCAST or not gui_socket:
        return
        
    try:
        # Send JSON with newline delimiter
        message = json.dumps(payload) + '\n'
        gui_socket.sendall(message.encode('utf-8'))
    except Exception as e:
        print(f"⚠️ GUI send error: {e}")
        # Try to reconnect
        connect_to_gui()


def get_video_title():
    print("🎬 Fetching video title...")
    try:
        # Use venv Python to ensure yt-dlp is found
        cmd = [str(VENV_PYTHON), "-m", "yt_dlp", "--get-title", "--no-warnings", AUDIO_URL]
        title = subprocess.check_output(cmd, text=True).strip()
        session_data["meta"]["title"] = title
        print(f"✅ Title: {title}")
    except Exception as e:
        print(f"⚠️ Could not fetch title: {e}")
        session_data["meta"]["title"] = "Unknown Video"

def add_to_batch(segment: dict):
    """Add segment to batch buffer and check if should send"""
    batch_state["buffer"].append(segment)
    
    # Initialize timer on first segment
    if batch_state["last_send_time"] is None:
        batch_state["last_send_time"] = time.time()
    
    # Check hybrid trigger: count OR time
    time_elapsed = time.time() - batch_state["last_send_time"]
    should_send = (
        len(batch_state["buffer"]) >= BATCH_SIZE or
        time_elapsed >= BATCH_INTERVAL
    )
    
    # Broadcast individual segment to GUI for real-time display
    broadcast_to_gui({
        "type": "segment",
        "data": segment
    })
    
    if should_send:
        send_batch()

def send_batch():
    """Send current batch with rolling context"""
    if not batch_state["buffer"]:
        return
    
    # Create unique clip_id once per session
    if "clip_id" not in session_data["meta"]:
        session_data["meta"]["clip_id"] = f"dg_{int(time.time())}"
    
    # Build batch text
    batch_text = " ".join([s["text"] for s in batch_state["buffer"]])
    
    # Calculate time range
    start_time = batch_state["buffer"][0]["start"]
    end_time = batch_state["buffer"][-1]["end"]
    
    batch_state["batch_count"] += 1
    
    payload = {
        "event": "batch_segments",
        "clip_id": session_data["meta"]["clip_id"],
        "batch_number": batch_state["batch_count"],
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
        # 🔥 KEY: Include previous context for AI understanding
        "previous_context": batch_state["sent_context"][-CONTEXT_WINDOW:] if batch_state["sent_context"] else "",
        "current_batch": {
            "text": batch_text,
            "segments": batch_state["buffer"].copy(),
            "segment_count": len(batch_state["buffer"])
        },
        # Combined text for easy AI consumption
        "full_text_with_context": (
            batch_state["sent_context"][-CONTEXT_WINDOW:] + " " + batch_text
        ).strip() if batch_state["sent_context"] else batch_text
    }
    
    # Update rolling context (keep last 3x window for safety)
    batch_state["sent_context"] = (batch_state["sent_context"] + " " + batch_text)[-CONTEXT_WINDOW*3:]
    
    # Broadcast batch to GUI for AI analysis
    broadcast_to_gui({
        "type": "batch",
        "data": payload
    })
    
    # Reset buffer
    batch_state["buffer"] = []
    batch_state["last_send_time"] = time.time()
    
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

def save_transcript():
    if not session_data["segments"]:
        return

    # Sanitize filename
    safe_title = "".join([c for c in session_data["meta"]["title"] if c.isalnum() or c in " -_"])[:50]
    timestamp = int(time.time())
    filename = f"transcripts/[LIVE] {safe_title}_{timestamp}.json"
    
    os.makedirs("transcripts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved transcript to: {filename}")

# Deepgram WebSocket URL
# We use linear16 encoding (raw PCM) at 16000Hz, mono
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen?"
    "encoding=linear16&"
    "sample_rate=16000&"
    "channels=1&"
    "model=nova-2&"
    "language=en&"
    "smart_format=true&"
    "interim_results=true&"
    "endpointing=300&"
    "diarize=true"
)

def on_message(ws, message):
    try:
        data = json.loads(message)
        
        # Handle transcription results
        if "channel" in data:
            alternatives = data["channel"]["alternatives"]
            if alternatives:
                transcript = alternatives[0]["transcript"]
                is_final = data.get("is_final", False)
                
                if transcript.strip():
                    # Try to get speaker from the first word
                    speaker_id = 0
                    words = alternatives[0].get("words", [])
                    if words and "speaker" in words[0]:
                        speaker_id = words[0]["speaker"]
                    
                    speaker_label = f"[Speaker {speaker_id}] "
                    
                    if is_final:
                        # Calculate start/end time from words
                        start_time = data.get("start", 0.0)
                        duration = data.get("duration", 0.0)
                        end_time = start_time + duration
                        
                        # Store segment
                        segment = {
                            "speaker": f"Speaker {speaker_id}",
                            "text": transcript,
                            "start": start_time,
                            "end": end_time
                        }
                        session_data["segments"].append(segment)
                        
                        # Add to batch buffer (hybrid: sends when 10 segments OR 30s elapsed)
                        add_to_batch(segment)

                        sys.stdout.write(f"\r[ FINAL ] {speaker_label}{transcript} ({start_time:.1f}s - {end_time:.1f}s)\n")
                        sys.stdout.flush()
                    else:
                        sys.stdout.write(f"\r[Interim] {speaker_label}{transcript}")
                        sys.stdout.flush()
    except Exception as e:
        # Ignore parse errors
        pass

def on_error(ws, error):
    print(f"\nWebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("\nConnection closed")

def on_open(ws):
    print("✅ Connected to Deepgram!")
    
    # 1. Send a small burst of silence immediately to prevent "NET-0001" (no audio within 10s)
    # 16000Hz * 2 bytes * 0.2s = ~6400 bytes
    silence = b'\x00' * 6400
    ws.send(silence, opcode=websocket.ABNF.OPCODE_BINARY)
    
    # 2. Start KeepAlive heartbeat in background (prevent timeouts during stalled pipeline)
    def keep_alive_worker():
        while True:
            time.sleep(3) # Send every 3 seconds
            try:
                if not ws.sock or not ws.sock.connected:
                    break
                ws.send('{"type": "KeepAlive"}')
            except Exception:
                break
    
    ka_thread = threading.Thread(target=keep_alive_worker)
    ka_thread.daemon = True
    ka_thread.start()

    def send_audio():
        print(f"🚀 Starting Audio Pipeline for: {AUDIO_URL}")
        
        # Start the audio pipeline
        # Use venv Python to run yt-dlp as a module
        # Note: ffmpeg must be in system PATH
        pipeline_cmd = (
            f'"{VENV_PYTHON}" -m yt_dlp "{AUDIO_URL}" -o - -q --no-warnings | '
            'ffmpeg -hide_banner -loglevel panic -i pipe:0 -f s16le -ac 1 -ar 16000 pipe:1'
        )
        
        try:
            process = subprocess.Popen(
                pipeline_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                bufsize=10**6
            )
            
            print("🎧 Listening... (Press Ctrl+C to stop)")
            
            while True:
                # Read 4k chunks
                data = process.stdout.read(4096)
                if not data:
                    ws.send('{"type": "CloseStream"}')
                    break
                ws.send(data, opcode=websocket.ABNF.OPCODE_BINARY)
                
        except Exception as e:
            print(f"\nAudio Pipeline Error: {e}")
        finally:
            if 'process' in locals():
                process.terminate()
            ws.close()

    # Run sender in a separate thread so it doesn't block receiving
    sender_thread = threading.Thread(target=send_audio)
    sender_thread.daemon = True
    sender_thread.start()

def run_transcription():
    # Enable header auth
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
    
    ws = websocket.WebSocketApp(
        DEEPGRAM_URL,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    ws.run_forever()

if __name__ == "__main__":
    try:
        get_video_title()
        connect_to_gui()  # Connect to GUI before starting transcription
        run_transcription()
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        save_transcript()
        send_final_summary()
        print("✅ Transcript sent (if webhook configured)")
