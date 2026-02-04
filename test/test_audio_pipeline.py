
import subprocess
import sys
import os
from pathlib import Path

# Detect venv Python path
SCRIPT_DIR = Path(__file__).parent.resolve()
# Use the same logic as pake_live.py, but assuming running from 'test' folder
VENV_PYTHON = SCRIPT_DIR.parent / ".venv310" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = sys.executable

def test_pipeline(url):
    print(f"🧪 Testing Audio Pipeline for: {url}")
    print(f"🐍 Python Path: {VENV_PYTHON}")
    
    # Check if ffmpeg is in path
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print("✅ ffmpeg found in PATH")
    except Exception as e:
        print("❌ ffmpeg NOT found or error: ", e)
        return

    pipeline_cmd = (
        f'"{VENV_PYTHON}" -m yt_dlp "{url}" -o - -q --no-warnings | '
        'ffmpeg -hide_banner -loglevel panic -i pipe:0 -f s16le -ac 1 -ar 16000 pipe:1'
    )
    
    print(f"🚀 Running command:\n{pipeline_cmd}")
    
    try:
        process = subprocess.Popen(pipeline_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, bufsize=10**6)
        
        print("⏳ Reading output (waiting for first 4096 bytes)...")
        data = process.stdout.read(4096)
        
        if data:
            print(f"✅ Success! Received {len(data)} bytes from pipeline.")
        else:
            print("❌ No data received from pipeline.")
            # Check stderr
            _, stderr = process.communicate()
            if stderr:
                print(f"⚠️ Pipeline Stderr: {stderr.decode('utf-8', errors='ignore')}")
                
        process.terminate()
        
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_url = "https://www.youtube.com/watch?v=DnbxnlxSH4U" # The URL user failed with
    test_pipeline(test_url)
