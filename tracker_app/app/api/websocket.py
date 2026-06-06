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
    except WebSocketDisconnect as e:
        streamer.disconnect(websocket, code=e.code)

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
            "event_id": session.get("event_id", i + 1),
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
            "snapshot_path": session.get("snapshot_path", ""),
            "clip_path": session.get("clip_path", ""),
            "intervention_type": "Completed"
        })
        
    # Process active sessions
    offset = len(streamer.processor.completed_sessions)
    for i, (port, session) in enumerate(streamer.processor.active_sessions.items()):
        events.append({
            "event_id": session.get("event_id", offset + i + 1),
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
            "snapshot_path": session.get("snapshot_path", ""),
            "clip_path": session.get("clip_path", ""),
            "intervention_type": "In Progress"
        })
        
    return events

def get_metrics_data():
    if not streamer or not streamer.processor:
        return {"total_events": 0, "total_duration": 0, "port_stats": {}, "deviations": []}
        
    metrics = streamer.processor.metrics
    total_events = metrics.get("in_count", 0)
    
    total_duration = 0
    port_stats = {}
    
    all_sessions = list(streamer.processor.completed_sessions) + list(streamer.processor.active_sessions.values())
    for session in all_sessions:
        dur = session.get("total_duration", 0)
        total_duration += dur
        roi = session.get("port_name", "unknown")
        if roi not in port_stats:
            port_stats[roi] = {"count": 0, "total_duration_sec": 0}
        port_stats[roi]["count"] += 1
        port_stats[roi]["total_duration_sec"] += dur
        
    # Round duration in port stats
    for p in port_stats.values():
        p["total_duration_sec"] = round(p["total_duration_sec"], 2)
        
    deviations = []
    if total_events > 20:
        deviations.append({
            "type": "COUNT_LIMIT",
            "message": f"Interventions ({total_events}) exceeded limit of 20",
            "current_value": total_events,
            "limit": 20,
            "severity": "HIGH",
            "detected_at": "Active Session",
            "trigger_event": total_events,
            "trigger_time": "N/A"
        })
    if total_duration > 300:
        deviations.append({
            "type": "DURATION_LIMIT",
            "message": f"Duration ({round(total_duration, 1)}s) exceeded limit of 300s",
            "current_value": round(total_duration, 1),
            "limit": 300,
            "severity": "HIGH",
            "detected_at": "Active Session",
            "trigger_event": total_events,
            "trigger_time": "N/A"
        })
        
    return {
        "total_events": total_events,
        "total_duration": total_duration,
        "port_stats": port_stats,
        "deviations": deviations
    }

@router.get("/api/summary")
def get_summary():
    data = get_metrics_data()
    total_events = data["total_events"]
    total_duration = data["total_duration"]
    port_stats = data["port_stats"]
    deviations = data["deviations"]
    
    avg_duration = total_duration / total_events if total_events > 0 else 0
    
    video_sec = (streamer.processor.frame_count / streamer.source.fps) if streamer and streamer.source and streamer.source.fps > 0 else 1
    video_min = max(video_sec / 60.0, 0.01) 
    frequency = total_events / video_min
    
    duration_usage_pct = (total_duration / 300) * 100
    
    return {
        "total_events": total_events,
        "total_duration_sec": round(total_duration, 2),
        "avg_duration_sec": round(avg_duration, 2),
        "frequency_per_min": round(frequency, 2),
        "count_usage_pct": round((total_events / 20) * 100, 2),
        "duration_usage_pct": round(duration_usage_pct, 2),
        "max_count": 20,
        "max_duration_sec": 300,
        "port_stats": port_stats,
        "has_deviations": len(deviations) > 0,
        "deviation_count": len(deviations),
        "video_duration_sec": round(video_sec, 2)
    }

import os

@router.get("/api/clips")
def get_clips():
    clips = []
    clips_dir = "output/clips"
    if os.path.exists(clips_dir):
        for filename in os.listdir(clips_dir):
            if filename.endswith(".webm") or filename.endswith(".mp4"):
                clips.append({
                    "filename": filename,
                    "url": f"/output/clips/{filename}"
                })
    return clips

@router.get("/api/deviations")
def get_deviations():
    return get_metrics_data()["deviations"]

@router.get("/api/stream/status")
def get_stream_status():
    is_running = streamer is not None and streamer.is_streaming
    return {"is_running": is_running}

@router.post("/api/stream/reset")
def reset_stream_endpoint():
    if streamer and streamer.processor:
        streamer.processor.reset()
    return {"status": "ok"}
