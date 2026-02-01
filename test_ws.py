import asyncio
import websockets
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("DEEPGRAM_KEY", "").strip()

async def test():
    # minimalist auth test
    uri = f"wss://api.deepgram.com/v1/listen?token={key}"
    print(f"Connecting to {uri.split('token=')[0]}token=REDACTED")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected!")
            await ws.send("{}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
