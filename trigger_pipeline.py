import asyncio
import websockets
import time

async def run_pipeline_client():
    print("Connecting to pipeline websocket to trigger execution...")
    try:
        async with websockets.connect('ws://localhost:8000/ws/video') as ws:
            print("Connected! Pipeline is now processing the video.")
            frames_received = 0
            start_time = time.time()
            try:
                while True:
                    data = await ws.recv()
                    frames_received += 1
                    if frames_received % 100 == 0:
                        elapsed = time.time() - start_time
                        fps = frames_received / elapsed
                        print(f"Processed {frames_received} frames... ({fps:.1f} FPS)")
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed. Video processing completed.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline_client())
