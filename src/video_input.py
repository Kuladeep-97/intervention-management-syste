"""
Video Input Module
==================
Wraps cv2.VideoCapture with metadata extraction and frame iteration.
"""

import cv2
import os


class VideoInput:
    """Load a video file and provide frame-by-frame iteration with metadata."""

    def __init__(self, video_path: str):
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)

        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration_sec = self.total_frames / self.fps if self.fps > 0 else 0

        # Parse video start time from filename if possible
        self.video_start_time = self._parse_start_time()

    def _parse_start_time(self) -> str:
        """Try to extract start time from filename pattern: Camera~Date~StartTime~EndTime~..."""
        basename = os.path.basename(self.video_path)
        parts = basename.replace(".mp4", "").split("~")
        if len(parts) >= 3:
            return parts[2].replace("_", ":")
        return "00:00:00"

    def get_first_frame(self):
        """Return the first frame of the video without advancing the iterator."""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = self.cap.read()
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if not ret:
            raise RuntimeError("Could not read first frame")
        return frame

    def frame_to_timestamp(self, frame_idx: int) -> float:
        """Convert frame index to timestamp in seconds."""
        return frame_idx / self.fps if self.fps > 0 else 0.0

    def frame_to_time_str(self, frame_idx: int) -> str:
        """Convert frame index to HH:MM:SS.ff string."""
        total_sec = self.frame_to_timestamp(frame_idx)
        hours = int(total_sec // 3600)
        minutes = int((total_sec % 3600) // 60)
        seconds = total_sec % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"

    def iter_frames(self):
        """Yield (frame_idx, frame) tuples. frame_idx is 1-based."""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        frame_idx = 0
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame_idx += 1
            yield frame_idx, frame

    def release(self):
        """Release the video capture."""
        if self.cap.isOpened():
            self.cap.release()

    def get_info(self) -> dict:
        """Return video metadata as a dictionary."""
        return {
            "path": self.video_path,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "total_frames": self.total_frames,
            "duration_sec": round(self.duration_sec, 2),
            "start_time": self.video_start_time,
        }

    def __del__(self):
        self.release()
