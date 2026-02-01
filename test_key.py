import os
import httpx
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("DEEPGRAM_KEY", "").strip()

print(f"Testing Key: {key[:5]}...")

try:
    resp = httpx.get(
        "https://api.deepgram.com/v1/projects",
        headers={"Authorization": f"Token {key}"}
    )
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
