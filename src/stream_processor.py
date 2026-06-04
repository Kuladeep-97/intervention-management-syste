"""
Stream Processor Module
=======================
Handles real-time video processing by wrapping the detection pipeline.
Provides a threaded frame consumer and an MJPEG-compatible frame buffer.
"""

import cv2
import time
import os
import threading
import queue
import numpy as np
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.video_input import VideoInput
from src.roi_manager import ROIManager
from src.motion_detector import MotionDetector
from src.event_classifier import EventClassifier
from src.event_recorder import EventRecorder
from src.deviation_checker import DeviationChecker

class StreamProcessor:
    """
    Simulates or handles a real-time video stream.
    Processes frames sequentially and provides live results.
    """

    def __init__(self, video_path: str, config: dict, output_dir: str = "output"):
        self.video_path = video_path
        self.config = config
        self.output_dir = output_dir
        
        # Components
        self.video = None
        self.roi_manager = None
        self.detectors = []
        self.classifiers = []
        self.recorder = None
        self.deviation_checker = None
        
        # Threading & Control
        self.is_running = False
        self.stop_requested = False
        self.thread = None
        
        # Buffers for consumers
        self.output_frame_buffer = deque(maxlen=30) # Store last 30 annotated frames for MJPEG
        self.status = {
            "frame_idx": 0,
            "total_frames": 0,
            "progress_pct": 0.0,
            "fps": 0.0,
            "is_running": False,
            "events": [],
            "deviations": [],
            "summary": {},
            "start_time": None,
            "elapsed_sec": 0.0
        }
        
        self._lock = threading.Lock()

    def _initialize(self):
        """Initialize all processing components based on config."""
        self.video = VideoInput(self.video_path)
        vi = self.video.get_info()
        
        # Update status
        with self._lock:
            self.status["total_frames"] = vi["total_frames"]
            self.status["fps"] = vi["fps"]
            self.status["start_time"] = datetime.now().isoformat()

        roi_configs = self.config.get("rois", [])
        detection_cfg = self.config.get("detection", {})
        event_cfg = self.config.get("events", {})
        limit_cfg = self.config.get("limits", {})

        self.roi_manager = ROIManager()
        self.roi_manager.set_rois(roi_configs)
        self.roi_manager.build_exclusive_masks(vi["height"], vi["width"])

        self.detectors = [
            MotionDetector(
                roi_index=i,
                ssim_threshold=detection_cfg.get("ssim_threshold", 0.08),
                ema_beta=detection_cfg.get("ema_beta", 0.2),
                history_size=detection_cfg.get("history_size", 25),
                min_motion_votes=detection_cfg.get("min_motion_votes", 10),
                resize_factor=detection_cfg.get("resize_factor", 0.5),
            ) for i in range(len(roi_configs))
        ]

        self.classifiers = [
            EventClassifier(
                roi_index=i,
                fps=vi["fps"],
                min_active_frames=event_cfg.get("min_active_frames", 5),
                cooldown_frames=event_cfg.get("cooldown_frames", 15),
                min_intervention_duration_sec=event_cfg.get("min_intervention_duration_sec", 2.0),
            ) for i in range(len(roi_configs))
        ]

        self.recorder = EventRecorder(
            output_dir=self.output_dir,
            save_snapshots=self.config.get("output", {}).get("save_snapshots", True),
            fps=vi["fps"]
        )
        
        self.deviation_checker = DeviationChecker(
            max_intervention_count=limit_cfg.get("max_intervention_count", 20),
            max_total_duration_sec=limit_cfg.get("max_total_duration_sec", 300.0),
            output_dir=self.output_dir
        )

    def start(self):
        """Start processing in a background thread."""
        if self.is_running:
            return
        
        self._initialize()
        self.is_running = True
        self.stop_requested = False
        self.thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Request the processing to stop."""
        self.stop_requested = True
        if self.thread:
            self.thread.join(timeout=2.0)
        self.is_running = False

    def _processing_loop(self):
        """Main loop that pulls frames and runs the pipeline."""
        start_ts = time.time()
        fps = self.status["fps"]
        frame_interval = 1.0 / fps if fps > 0 else 0.03

        try:
            for frame_idx, frame in self.video.iter_frames():
                if self.stop_requested:
                    break

                proc_start = time.time()
                
                # 1. Processing
                active_events_this_frame = []
                for i in range(len(self.detectors)):
                    roi_crop = self.roi_manager.get_roi_crop(frame, i)
                    motion_result = self.detectors[i].process_frame(roi_crop)
                    
                    is_active = motion_result["is_active"]
                    self.recorder.buffer_frame(i, frame, is_active)
                    
                    if is_active:
                        active_events_this_frame.append({
                            "roi_index": i,
                            "event_id": f"temp_{frame_idx}"
                        })

                    event = self.classifiers[i].process_frame(frame_idx, is_active)
                    if event is not None:
                        # Draw ROIs for the snapshot
                        states = [c.get_state() for c in self.classifiers]
                        annotated = self.roi_manager.draw_rois(frame.copy(), states)
                        self.recorder.record_event(event, annotated)
                        
                        # Check deviations
                        summary = self.recorder.get_summary()
                        self.deviation_checker.check(
                            summary["total_events"], summary["total_duration_sec"], event)

                # Simultaneous check
                if len(active_events_this_frame) > 1:
                    summary = self.recorder.get_summary()
                    self.deviation_checker.check(
                        total_count=summary["total_events"],
                        total_duration_sec=summary["total_duration_sec"],
                        latest_event=None,
                        active_events=active_events_this_frame
                    )

                # 2. Visualization/Buffering
                states = [c.get_state() for c in self.classifiers]
                # Map states to the format ROIManager expects (labels)
                state_labels = [s if isinstance(s, str) else s.get("label", "STATIC") for s in states]
                # Or wait, looking at app.py:800, roi_manager.draw_rois(frame, states)
                # Looking at video_server.py:61, roi_manager.draw_rois(frame, states)
                # ROIManager's draw_rois seems to take either labels or state dicts.
                annotated_frame = self.roi_manager.draw_rois(frame, state_labels)
                
                # Add basic info overlay
                cv2.putText(annotated_frame, f"STREAMING: Frame {frame_idx}", 
                           (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

                with self._lock:
                    self.output_frame_buffer.append(annotated_frame)
                    
                    # Update status
                    self.status["frame_idx"] = frame_idx
                    if self.status["total_frames"] > 0:
                        self.status["progress_pct"] = (frame_idx / self.status["total_frames"]) * 100
                    self.status["elapsed_sec"] = time.time() - start_ts
                    self.status["events"] = self.recorder.get_events()
                    self.status["deviations"] = self.deviation_checker.get_deviations()
                    self.status["summary"] = self.recorder.get_summary()
                    self.status["is_running"] = True

                # 3. Throttling for "Simulated Delay" and real-time playback
                proc_time = time.time() - proc_start
                sleep_time = max(0, frame_interval - proc_time)
                # Introduce a tiny extra delay as requested by user ("Some delay in streamoutput is permissible")
                # This ensures the browser has time to consume MJPEG and mimics non-local network delay
                time.sleep(sleep_time + 0.005)

            # Finalize
            total_f = self.status["frame_idx"]
            for clf in self.classifiers:
                event = clf.finalize(total_f)
                if event:
                    self.recorder.record_event(event)
                    summary = self.recorder.get_summary()
                    self.deviation_checker.check(
                        summary["total_events"], summary["total_duration_sec"], event)

            self.recorder.save_all()
            self.deviation_checker.save_deviations()

        finally:
            with self._lock:
                self.status["is_running"] = False
            self.is_running = False
            if self.video:
                self.video.release()

    def get_status(self) -> dict:
        """Returns the current status dictionary (thread-safe)."""
        with self._lock:
            return self.status.copy()

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Returns the latest annotated frame (thread-safe)."""
        with self._lock:
            if self.output_frame_buffer:
                return self.output_frame_buffer[-1]
        return None
