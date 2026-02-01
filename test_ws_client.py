import websocket
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("DEEPGRAM_KEY", "").strip()

def test():
    # Use headers!
    uri = "wss://api.deepgram.com/v1/listen?model=nova-2&encoding=linear16&sample_rate=16000"
    headers = {"Authorization": f"Token {key}"}
    print(f"Connecting to {uri}...")
    try:
        ws = websocket.create_connection(uri, header=headers)
        print("Connected!")
        ws.send('{"type": "KeepAlive"}')
        print("Sent KeepAlive")
        result = ws.recv()
        print(f"Received: {result}")
        ws.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
