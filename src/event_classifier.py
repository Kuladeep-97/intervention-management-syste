"""
Event Classifier Module
========================
State machine per ROI that converts motion signals into intervention events.
States: IDLE → ACTIVE → IDLE
"""

from typing import Dict, List, Optional


class EventClassifier:
    """
    Per-ROI state machine that classifies motion into intervention events.

    Transitions:
        IDLE → ACTIVE:  min_active_frames consecutive active frames
        ACTIVE → IDLE:  cooldown_frames consecutive inactive frames

    Events shorter than min_intervention_duration_sec are discarded.
    """

    def __init__(
        self,
        roi_index: int,
        fps: float,
        min_active_frames: int = 5,
        cooldown_frames: int = 15,
        min_intervention_duration_sec: float = 2.0,
    ):
        self.roi_index = roi_index
        self.fps = fps
        self.min_active_frames = min_active_frames
        self.cooldown_frames = cooldown_frames
        self.min_intervention_duration_sec = min_intervention_duration_sec

        # State machine
        self.state: str = "IDLE"  # IDLE or ACTIVE
        self.active_streak: int = 0
        self.idle_streak: int = 0

        # Current intervention tracking
        self.current_start_frame: Optional[int] = None
        self.current_start_sec: Optional[float] = None

        # Completed events
        self.events: List[Dict] = []
        self.event_counter: int = 0

    def process_frame(self, frame_idx: int, is_active: bool) -> Optional[Dict]:
        """
        Process one frame's motion result.
        Returns a completed event dict if an intervention just ended, else None.
        """
        timestamp_sec = frame_idx / self.fps if self.fps > 0 else 0.0

        if self.state == "IDLE":
            if is_active:
                self.active_streak += 1
                self.idle_streak = 0

                # Transition to ACTIVE
                if self.active_streak >= self.min_active_frames:
                    self.state = "ACTIVE"
                    # Start time is when the streak began
                    self.current_start_frame = frame_idx - self.min_active_frames + 1
                    self.current_start_sec = self.current_start_frame / self.fps
            else:
                self.active_streak = 0
                self.idle_streak += 1

        elif self.state == "ACTIVE":
            if not is_active:
                self.idle_streak += 1
                self.active_streak = 0

                # Transition to IDLE — intervention ended
                if self.idle_streak >= self.cooldown_frames:
                    self.state = "IDLE"

                    # Calculate event
                    end_frame = frame_idx - self.cooldown_frames
                    end_sec = end_frame / self.fps
                    duration_sec = end_sec - self.current_start_sec

                    # Filter short events
                    if duration_sec >= self.min_intervention_duration_sec:
                        self.event_counter += 1
                        event = {
                            "event_id": self.event_counter,
                            "roi_index": self.roi_index,
                            "roi_label": f"Port {self.roi_index + 1}",
                            "start_frame": self.current_start_frame,
                            "end_frame": end_frame,
                            "start_sec": round(self.current_start_sec, 2),
                            "end_sec": round(end_sec, 2),
                            "duration_sec": round(duration_sec, 2),
                            "start_time": self._sec_to_time(self.current_start_sec),
                            "end_time": self._sec_to_time(end_sec),
                        }
                        self.events.append(event)

                        # Reset
                        self.current_start_frame = None
                        self.current_start_sec = None

                        return event

                    # Reset without recording
                    self.current_start_frame = None
                    self.current_start_sec = None
            else:
                self.active_streak += 1
                self.idle_streak = 0

        return None

    def finalize(self, total_frames: int) -> Optional[Dict]:
        """
        Call at end of video to close any open intervention.
        """
        if self.state == "ACTIVE" and self.current_start_sec is not None:
            end_frame = total_frames
            end_sec = end_frame / self.fps
            duration_sec = end_sec - self.current_start_sec

            if duration_sec >= self.min_intervention_duration_sec:
                self.event_counter += 1
                event = {
                    "event_id": self.event_counter,
                    "roi_index": self.roi_index,
                    "roi_label": f"Port {self.roi_index + 1}",
                    "start_frame": self.current_start_frame,
                    "end_frame": end_frame,
                    "start_sec": round(self.current_start_sec, 2),
                    "end_sec": round(end_sec, 2),
                    "duration_sec": round(duration_sec, 2),
                    "start_time": self._sec_to_time(self.current_start_sec),
                    "end_time": self._sec_to_time(end_sec),
                }
                self.events.append(event)
                self.state = "IDLE"
                return event

        return None

    def get_state(self) -> str:
        """Return current state."""
        return self.state

    def get_events(self) -> List[Dict]:
        """Return all completed events."""
        return self.events

    def get_summary(self) -> Dict:
        """Return summary statistics."""
        total_duration = sum(e["duration_sec"] for e in self.events)
        return {
            "roi_index": self.roi_index,
            "roi_label": f"Port {self.roi_index + 1}",
            "total_events": len(self.events),
            "total_duration_sec": round(total_duration, 2),
        }

    @staticmethod
    def _sec_to_time(seconds: float) -> str:
        """Convert seconds to HH:MM:SS.ff format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"
