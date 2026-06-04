import asyncio
import websockets
import json

async def test_ws():
    print("Connecting...")
    async with websockets.connect('ws://localhost:8000/ws/video') as ws:
        print("Connected!")
        data = await ws.recv()
        try:
            payload = json.loads(data)
            print("Keys:", payload.keys())
            if "image" in payload:
                print("Image base64 length:", len(payload["image"]))
                print("Image header:", payload["image"][:50])
            if "metrics" in payload:
                print("Metrics:", payload["metrics"])
        except Exception as e:
            print("Error parsing JSON:", e)
            print("Data received:", data[:100])

if __name__ == "__main__":
    asyncio.run(test_ws())
