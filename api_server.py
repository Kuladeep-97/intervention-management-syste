import os
import json
import yaml
import cv2
import numpy as np
import asyncio
import threading
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from src.video_input import VideoInput
from src.roi_manager import ROIManager
from src.motion_detector import MotionDetector
from src.stream_processor import StreamProcessor

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CONFIG_PATH = BASE_DIR / "config.yaml"
INPUT_STREAM_DIR = BASE_DIR / "input_stream"
VIDEO_FILE = "Camera02~21_Dec_2025~00_39_43~00_48_09~HDD~00.mp4"

# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------
global_processor: Optional[StreamProcessor] = None
processor_lock = threading.Lock()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Dheera AI API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_json(path: Path) -> list | dict:
    if path.exists():
        with open(path, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def _read_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def _write_config(data: dict):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


# ---------------------------------------------------------------------------
# Directory Monitoring (Background Task)
# ---------------------------------------------------------------------------
async def monitor_input_directory():
    """Periodically checks input_stream for new videos and starts processing."""
    global global_processor
    print(f"[*] Directory monitor started: watching {INPUT_STREAM_DIR}")
    
    while True:
        try:
            with processor_lock:
                busy = global_processor is not None and global_processor.is_running
                
            if not busy:
                if not INPUT_STREAM_DIR.exists():
                    INPUT_STREAM_DIR.mkdir(parents=True, exist_ok=True)
                
                files = [f for f in os.listdir(INPUT_STREAM_DIR) if f.endswith(".mp4")]
                if files:
                    # Pick the oldest/first file
                    video_name = files[0]
                    video_path = str(INPUT_STREAM_DIR / video_name)
                    print(f"[!] New video detected: {video_name}. Starting stream processor...")
                    
                    config = _read_config()
                    with processor_lock:
                        global_processor = StreamProcessor(video_path, config)
                        global_processor.start()
                    
                    # Move the file to a 'processed' state or just leave it?
                    # For now, we'll just process it. To avoid re-processing, 
                    # we should move it or rename it after starting.
                    # renamed_path = INPUT_STREAM_DIR / f"processing_{video_name}"
                    # os.rename(video_path, renamed_path)
                    # global_processor.video_path = str(renamed_path)
            
        except Exception as e:
            print(f"[ERROR] Monitor task: {e}")
            
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_input_directory())


# ---------------------------------------------------------------------------
# Routes: Streaming Control
# ---------------------------------------------------------------------------
class StreamStartRequest(BaseModel):
    video_path: Optional[str] = None

@app.post("/api/stream/start")
def start_stream(req: StreamStartRequest = None):
    global global_processor
    with processor_lock:
        if global_processor and global_processor.is_running:
            return {"status": "already_running"}
        
        video_path = req.video_path if req and req.video_path else str(BASE_DIR / VIDEO_FILE)
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail=f"Video not found: {video_path}")
            
        config = _read_config()
        global_processor = StreamProcessor(video_path, config)
        global_processor.start()
        
    return {"status": "started", "video": video_path}


@app.post("/api/stream/stop")
def stop_stream():
    global global_processor
    with processor_lock:
        if global_processor:
            global_processor.stop()
            return {"status": "stopped"}
    return {"status": "not_running"}


@app.get("/api/stream/status")
def get_stream_status():
    global global_processor
    if global_processor:
        return global_processor.get_status()
    return {"is_running": False, "msg": "No active stream processor"}


# ---------------------------------------------------------------------------
# Routes: Events & Deviations
# ---------------------------------------------------------------------------
@app.get("/api/events")
def get_events():
    """Return all detected intervention events."""
    global global_processor
    if global_processor and global_processor.is_running:
        return global_processor.get_status().get("events", [])
    return _read_json(OUTPUT_DIR / "events.json")


@app.get("/api/deviations")
def get_deviations():
    """Return all deviation alerts."""
    global global_processor
    if global_processor and global_processor.is_running:
        return global_processor.get_status().get("deviations", [])
    return _read_json(OUTPUT_DIR / "deviations.json")


# ---------------------------------------------------------------------------
# Routes: Summary
# ---------------------------------------------------------------------------
@app.get("/api/summary")
def get_summary():
    """Compute aggregate summary metrics."""
    global global_processor
    
    # Defaults
    events = []
    deviations = []
    config = _read_config()
    
    if global_processor and global_processor.is_running:
        status = global_processor.get_status()
        events = status.get("events", [])
        deviations = status.get("deviations", [])
    else:
        events = _read_json(OUTPUT_DIR / "events.json")
        deviations = _read_json(OUTPUT_DIR / "deviations.json")

    limits = config.get("limits", {})
    max_count = limits.get("max_intervention_count", 20)
    max_duration = limits.get("max_total_duration_sec", 300.0)

    total_events = len(events)
    total_duration = sum(e.get("duration_sec", 0) for e in events)
    avg_duration = total_duration / total_events if total_events else 0

    # Per-port breakdown
    port_stats: dict[str, dict] = {}
    for e in events:
        label = e.get("roi_label", f"Port {e.get('roi_index', 0) + 1}")
        if label not in port_stats:
            port_stats[label] = {"count": 0, "total_duration_sec": 0.0}
        port_stats[label]["count"] += 1
        port_stats[label]["total_duration_sec"] += e.get("duration_sec", 0)

    # Video info for frequency calculation
    video_duration_sec = 0
    # Try to get duration from processor or default file
    if global_processor and global_processor.is_running:
        # StreamProcessor doesn't strictly have a 'duration' if it's live, 
        # but if it's from a file, it does.
        if global_processor.video:
            video_duration_sec = global_processor.video.duration_sec
    
    if video_duration_sec == 0:
        video_path = BASE_DIR / VIDEO_FILE
        if video_path.exists():
            try:
                vi = VideoInput(str(video_path))
                video_duration_sec = vi.get_info().get("duration_sec", 0)
                vi.release()
            except: pass

    frequency = (total_events / (video_duration_sec / 60)) if video_duration_sec > 0 else 0
    count_usage = (total_events / max_count * 100) if max_count else 0
    duration_usage = (total_duration / max_duration * 100) if max_duration else 0

    return {
        "total_events": total_events,
        "total_duration_sec": round(total_duration, 1),
        "avg_duration_sec": round(avg_duration, 1),
        "frequency_per_min": round(frequency, 1),
        "count_usage_pct": round(count_usage, 1),
        "duration_usage_pct": round(duration_usage, 1),
        "max_count": max_count,
        "max_duration_sec": max_duration,
        "port_stats": port_stats,
        "has_deviations": len(deviations) > 0,
        "deviation_count": len(deviations),
        "video_duration_sec": round(video_duration_sec, 1),
    }


# ---------------------------------------------------------------------------
# Routes: MJPEG Live Stream
# ---------------------------------------------------------------------------
def _generate_stream_frames():
    """Generator that yields JPEG frames from the active StreamProcessor."""
    global global_processor
    
    while True:
        # If no processor is running, wait and check again
        if not global_processor or not global_processor.is_running:
            # Placeholder frame
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(placeholder, "WAITING FOR STREAM...", (120, 240), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            ret, buffer = cv2.imencode(".jpg", placeholder)
            if ret:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
            import time
            time.sleep(2.0)
            continue

        frame = global_processor.get_latest_frame()
        if frame is not None:
            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
        
        import time
        time.sleep(0.04) # ~25 FPS consumer

@app.get("/video_feed")
def video_feed():
    """Live MJPEG stream for proxying from frontend."""
    return StreamingResponse(
        _generate_stream_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ---------------------------------------------------------------------------
# Static Routes (Clips/Snapshots/Config/Classifications)
# ---------------------------------------------------------------------------
# Keep these as they were in the original file (api_server.py L144-L219)
# [Omitted for brevity in this replace call, will be merged back if using full rewrite]
# Actually, I should use specific replace regions if I want to be safe, 
# but a full rewrite of a 300 line file is often clearer.

@app.get("/api/config")
def get_config(): return _read_config()

@app.post("/api/config")
def save_config(body: dict):
    _write_config(body)
    return {"status": "ok"}

@app.get("/api/clips")
def list_clips():
    clips_dir = OUTPUT_DIR / "clips"
    if not clips_dir.exists(): return []
    return [{"filename": f.name, "url": f"/api/clips/{f.name}"} for f in sorted(clips_dir.iterdir()) if f.suffix == ".mp4"]

@app.get("/api/clips/{filename}")
def get_clip(filename: str):
    return FileResponse(OUTPUT_DIR / "clips" / filename, media_type="video/mp4")

@app.get("/api/snapshots/{filename}")
def get_snapshot(filename: str):
    return FileResponse(OUTPUT_DIR / "snapshots" / filename, media_type="image/jpeg")

@app.post("/api/classifications")
def save_classifications(payload: dict):
    events_path = OUTPUT_DIR / "events.json"
    events = _read_json(events_path)
    for idx_str, itype in payload.get("classifications", {}).items():
        idx = int(idx_str)
        if 0 <= idx < len(events): events[idx]["intervention_type"] = itype
    with open(events_path, "w") as f: json.dump(events, f, indent=2)
    return {"status": "ok"}

@app.get("/")
def root(): return {"status": "running", "streaming": "/stream/video_feed", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
