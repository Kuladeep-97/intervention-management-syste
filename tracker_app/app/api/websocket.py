from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.streaming.streamer import Streamer

router = APIRouter()

# The streamer instance will be injected or set from the main app
streamer: Streamer = None

@router.websocket("/ws/video")
async def websocket_endpoint(websocket: WebSocket):
    if streamer is None:
        await websocket.accept()
        await websocket.send_text("Streamer not initialized")
        await websocket.close()
        return

    await streamer.connect(websocket)
    try:
        while True:
            # Keep connection open and listen for potential client messages
            data = await websocket.receive_text()
            # We don't really expect data from the dashboard right now, 
            # but we need to receive to detect disconnects gracefully
    except WebSocketDisconnect:
        streamer.disconnect(websocket)

from fastapi.responses import Response
import csv
import io

@router.get("/api/analytics/csv")
def download_csv():
    if not streamer or not streamer.processor:
        return Response("Processor not running", status_code=400)
        
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Glove ID", "Port", "Start Time", "End Time", "Status", "Active Duration", "Idle Duration", "Total Duration", "Intervention Num"])
    
    # Combine active and completed sessions
    sessions = streamer.processor.completed_sessions.copy()
    
    for session_port, data in streamer.processor.active_sessions.items():
         sessions.append({
             "glove_id": data["glove_id"],
             "port_name": session_port,
             "start_time": data["start_time"],
             "end_time": "Active",
             "status": "In Progress",
             "active_duration": data["active_duration"],
             "idle_duration": data["idle_duration"],
             "total_duration": data["total_duration"],
             "intervention_num": data["intervention_num"]
         })
         
    for s in sessions:
        writer.writerow([
            s.get("glove_id"), 
            s.get("port_name"), 
            f"{s.get('start_time', 0):.2f}s", 
            f"{s.get('end_time', 'N/A')}s" if isinstance(s.get('end_time'), float) else s.get('end_time', 'N/A'), 
            s.get("status", "Completed"),
            f"{s.get('active_duration', 0):.2f}s",
            f"{s.get('idle_duration', 0):.2f}s",
            f"{s.get('total_duration', 0):.2f}s",
            s.get("intervention_num", "")
        ])
        
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pharma_tracker_analytics.csv"}
    )

@router.get("/api/events")
def get_events():
    if not streamer or not streamer.processor:
        return []
        
    events = []
    
    # Process completed sessions
    for i, session in enumerate(streamer.processor.completed_sessions):
        events.append({
            "event_id": i + 1,
            "roi_index": 0,
            "roi_label": session.get("port_name", "Unknown"),
            "start_frame": 0,
            "end_frame": 0,
            "start_sec": session.get("start_time", 0),
            "end_sec": session.get("end_time", 0),
            "duration_sec": session.get("total_duration", 0),
            "start_time": f"{session.get('start_time', 0):.1f}s",
            "end_time": f"{session.get('end_time', 0):.1f}s",
            "recorded_at": "",
            "snapshot_path": "",
            "intervention_type": "Completed"
        })
        
    # Process active sessions
    offset = len(streamer.processor.completed_sessions)
    for i, (port, session) in enumerate(streamer.processor.active_sessions.items()):
        events.append({
            "event_id": offset + i + 1,
            "roi_index": 0,
            "roi_label": port,
            "start_frame": 0,
            "end_frame": 0,
            "start_sec": session.get("start_time", 0),
            "end_sec": 0,
            "duration_sec": session.get("total_duration", 0),
            "start_time": f"{session.get('start_time', 0):.1f}s",
            "end_time": "Now",
            "recorded_at": "",
            "snapshot_path": "",
            "intervention_type": "In Progress"
        })
        
    return events

@router.get("/api/summary")
def get_summary():
    if not streamer or not streamer.processor:
        return {
            "total_events": 0,
            "total_duration_sec": 0,
            "avg_duration_sec": 0,
            "frequency_per_min": 0,
            "count_usage_pct": 0,
            "duration_usage_pct": 0,
            "max_count": 20,
            "max_duration_sec": 300,
            "port_stats": {},
            "has_deviations": False,
            "deviation_count": 0,
            "video_duration_sec": 0
        }
        
    metrics = streamer.processor.metrics
    return {
        "total_events": metrics.get("in_count", 0),
        "total_duration_sec": 0,
        "avg_duration_sec": 0,
        "frequency_per_min": 0,
        "count_usage_pct": (metrics.get("in_count", 0) / 20) * 100,
        "duration_usage_pct": 0,
        "max_count": 20,
        "max_duration_sec": 300,
        "port_stats": {},
        "has_deviations": False,
        "deviation_count": 0,
        "video_duration_sec": 0
    }

@router.get("/api/clips")
def get_clips():
    return []

@router.get("/api/deviations")
def get_deviations():
    return []

@router.get("/api/stream/status")
def get_stream_status():
    is_running = streamer is not None and streamer.is_streaming
    return {"is_running": is_running}
