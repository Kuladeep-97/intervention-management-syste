import asyncio
import cv2
import json
import base64
from typing import List
from fastapi import WebSocket

from app.sources.video_source import VideoSource
from app.pipeline.processor import PipelineProcessor

class Streamer:
    def __init__(self, config: dict):
        self.config = config
        self.active_connections: List[WebSocket] = []
        self.source = None
        self.processor = None
        self.is_streaming = False
        self.streaming_task = None
        
        # Pre-initialize processor to avoid PyTorch loading delay during websocket connection
        pipeline_cfg = self.config.get("pipeline", {})
        model_path = pipeline_cfg.get("model_path", "best.pt")
        ports_json = pipeline_cfg.get("ports_json", "ports.json")
        
        import os
        if not os.path.exists(model_path):
             model_path = os.path.join("..", model_path)
        if not os.path.exists(ports_json):
             ports_json = os.path.join("..", ports_json)

        self.processor = PipelineProcessor(model_path=model_path, ports_json=ports_json)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connected. Total clients: {len(self.active_connections)}")
        
        if not self.is_streaming:
            self.start_streaming()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"Client disconnected. Total clients: {len(self.active_connections)}")
            
        if len(self.active_connections) == 0 and self.is_streaming:
            self.stop_streaming()

    def start_streaming(self):
        print("Starting video stream...")
        self.is_streaming = True
        
        # Initialize source based on config
        source_cfg = self.config.get("source", {})
        if source_cfg.get("type") == "video":
            path = source_cfg.get("path", "test_video.avi")
            # If path is relative to repo root, we might need to adjust, but let's assume it works for now
            import os
            if not os.path.exists(path):
                 path = os.path.join("..", path)
            self.source = VideoSource(path)
        else:
            raise NotImplementedError("Only video source is supported right now.")

        # Processor is already initialized in __init__

        
        # Start background task
        self.streaming_task = asyncio.create_task(self._stream_loop())

    def stop_streaming(self):
        print("Stopping video stream due to no clients...")
        self.is_streaming = False
        if self.streaming_task:
            self.streaming_task.cancel()
        if self.source:
            self.source.release()
            self.source = None
        # Do not set self.processor to None so it can be reused without reloading PyTorch
        # self.processor = None

    async def _stream_loop(self):
        try:
            frame_gen = self.source.get_frames()
            processor_gen = self.processor.process_stream(frame_gen, self.source.fps)
            
            for processed_frame, metrics in processor_gen:
                if not self.is_streaming:
                    break
                    
                # Encode frame to JPEG
                # Lower quality to 60 to save bandwidth for websocket streaming
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60] 
                ret, buffer = cv2.imencode('.jpg', processed_frame, encode_param)
                if not ret:
                    continue
                    
                # Convert to base64
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                
                # Payload containing both image and metrics
                payload = {
                    "image": jpg_as_text,
                    "metrics": metrics,
                    "fps": self.source.fps
                }
                
                # Broadcast
                disconnected = []
                for connection in self.active_connections:
                    try:
                        await connection.send_json(payload)
                    except Exception as e:
                        disconnected.append(connection)
                        
                for conn in disconnected:
                    self.disconnect(conn)
                    
                # Yield control to the event loop
                await asyncio.sleep(0.001)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Streaming error: {e}")
        finally:
            self.is_streaming = False
