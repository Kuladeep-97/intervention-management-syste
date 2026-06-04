"""
Event Recorder Module
======================
Records intervention events to JSON/CSV and captures snapshots.
"""

import os
import json
import csv
import cv2
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from collections import deque


class EventRecorder:
    """Records intervention events, captures snapshots, and generates video clips."""

    def __init__(
        self,
        output_dir: str = "output",
        save_snapshots: bool = True,
        snapshot_format: str = "jpg",
        snapshot_quality: int = 90,
        fps: float = 25.0,
    ):
        self.output_dir = output_dir
        self.save_snapshots = save_snapshots
        self.snapshot_format = snapshot_format
        self.snapshot_quality = snapshot_quality
        self.fps = fps

        self.events: List[Dict] = []
        self.snapshot_paths: List[str] = []
        
        # Buffer for video clips (e.g. 2 seconds pre-buffer)
        self.buffer_size = int(fps * 2) 
        self.frame_buffers: Dict[int, deque] = {}
        self.active_writers: Dict[int, dict] = {}

        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        if save_snapshots:
            self.snapshot_dir = os.path.join(output_dir, "snapshots")
            self.clips_dir = os.path.join(output_dir, "clips")
            os.makedirs(self.snapshot_dir, exist_ok=True)
            os.makedirs(self.clips_dir, exist_ok=True)

    def buffer_frame(self, roi_index: int, frame: np.ndarray, is_active: bool):
        """Keeps a rolling buffer of frames or writes to an active event clip."""
        if not self.save_snapshots: return
        
        if roi_index not in self.frame_buffers:
            self.frame_buffers[roi_index] = deque(maxlen=self.buffer_size)
            
        if not is_active:
            # Just keep rolling buffer of pre-event frames
            self.frame_buffers[roi_index].append(frame.copy())
        else:
            # We are active.
            if roi_index not in self.active_writers:
                # Need to start a new writer for this port's active event
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Use AVC1 for H264 which tends to have better browser support
                clip_name = f"clip_port{roi_index + 1}_{ts}.mp4"
                clip_path = os.path.join(self.clips_dir, clip_name)
                
                fourcc = cv2.VideoWriter_fourcc(*'vp80')
                h, w = frame.shape[:2]
                writer = cv2.VideoWriter(clip_path, fourcc, self.fps, (w, h))
                self.active_writers[roi_index] = {"writer": writer, "path": clip_path}
                
                # Flush the pre-buffer into the writer
                while self.frame_buffers[roi_index]:
                    writer.write(self.frame_buffers[roi_index].popleft())
                    
            # Write current frame
            self.active_writers[roi_index]["writer"].write(frame)

    def record_event(self, event: Dict, frame: Optional[np.ndarray] = None):
        """
        Record a completed intervention event.
        Optionally saves a snapshot of the frame.
        """
        # Add metadata
        event["recorded_at"] = datetime.now().isoformat()

        # Save snapshot
        if self.save_snapshots and frame is not None:
            snapshot_name = (
                f"event_{event['event_id']}_"
                f"port{event['roi_index'] + 1}_"
                f"f{event.get('start_frame', 0)}"
                f".{self.snapshot_format}"
            )
            snapshot_path = os.path.join(self.snapshot_dir, snapshot_name)

            if self.snapshot_format == "jpg":
                cv2.imwrite(
                    snapshot_path, frame,
                    [cv2.IMWRITE_JPEG_QUALITY, self.snapshot_quality]
                )
            else:
                cv2.imwrite(snapshot_path, frame)

            event["snapshot_path"] = snapshot_path
            self.snapshot_paths.append(snapshot_path)
            
            # Close the video writer if it exists for this port and link the clip path
            roi_idx = event['roi_index']
            if roi_idx in self.active_writers:
                self.active_writers[roi_idx]["writer"].release()
                
                # Rename the clip now that we have the event_id
                old_path = self.active_writers[roi_idx]["path"]
                start_frame = event.get("start_frame", 0)
                new_name = f"event_{event['event_id']}_port{roi_idx + 1}_f{start_frame}.mp4"
                new_path = os.path.join(self.clips_dir, new_name)
                
                try:
                    os.rename(old_path, new_path)
                    event["clip_path"] = new_path
                except OSError:
                    event["clip_path"] = old_path # Fallback if rename fails
                    
                del self.active_writers[roi_idx]

        self.events.append(event)
        self.save_all()

    def save_json(self, filepath: Optional[str] = None):
        """Save all events to JSON file."""
        if filepath is None:
            filepath = os.path.join(self.output_dir, "events.json")

        with open(filepath, "w") as f:
            json.dump(self.events, f, indent=2)

        return filepath

    def save_csv(self, filepath: Optional[str] = None):
        """Save all events to CSV file."""
        if filepath is None:
            filepath = os.path.join(self.output_dir, "events.csv")

        if not self.events:
            # Write empty CSV with headers
            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "event_id", "roi_label", "start_time", "end_time",
                    "duration_sec", "start_frame", "end_frame",
                ])
            return filepath

        # Use first event's keys as headers
        fieldnames = [
            "event_id", "roi_index", "roi_label",
            "start_frame", "end_frame",
            "start_sec", "end_sec", "duration_sec",
            "start_time", "end_time",
            "snapshot_path", "clip_path", "intervention_type", "recorded_at",
        ]

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.events)

        return filepath

    def get_summary(self) -> Dict:
        """Return summary of all recorded events."""
        if not self.events:
            return {
                "total_events": 0,
                "total_duration_sec": 0.0,
                "port_stats": {},
            }

        total_duration = sum(e.get("duration_sec", 0) for e in self.events)

        # Group by port
        port_stats = {}
        for e in self.events:
            label = e.get("roi_label", "Unknown")
            if label not in port_stats:
                port_stats[label] = {"count": 0, "total_duration_sec": 0.0}
            port_stats[label]["count"] += 1
            port_stats[label]["total_duration_sec"] += e.get("duration_sec", 0)

        return {
            "total_events": len(self.events),
            "total_duration_sec": round(total_duration, 2),
            "port_stats": port_stats,
        }

    def get_events(self) -> List[Dict]:
        """Return all events."""
        return self.events

    def save_all(self):
        """Save events to both JSON and CSV."""
        json_path = self.save_json()
        csv_path = self.save_csv()
        return json_path, csv_path
