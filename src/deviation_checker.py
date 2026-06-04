"""
Deviation Checker Module
=========================
Compares intervention metrics against predefined limits.
Flags deviations when counts or durations exceed thresholds.
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime


class DeviationChecker:
    """Checks intervention metrics against configurable limits and flags deviations."""

    def __init__(
        self,
        max_intervention_count: int = 20,
        max_total_duration_sec: float = 300.0,
        output_dir: str = "output",
    ):
        self.max_intervention_count = max_intervention_count
        self.max_total_duration_sec = max_total_duration_sec
        self.output_dir = output_dir

        self.deviations: List[Dict] = []

    def check(
        self,
        total_count: int,
        total_duration_sec: float,
        latest_event: Optional[Dict] = None,
        active_events: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        Check current metrics against limits.
        Returns list of new deviations found (if any).
        """
        new_deviations = []

        # Check count limit
        if total_count > self.max_intervention_count:
            deviation = {
                "type": "COUNT_EXCEEDED",
                "message": (
                    f"Intervention count ({total_count}) exceeds "
                    f"limit ({self.max_intervention_count})"
                ),
                "current_value": total_count,
                "limit": self.max_intervention_count,
                "severity": "HIGH",
                "detected_at": datetime.now().isoformat(),
            }
            if latest_event:
                deviation["trigger_event"] = latest_event.get("event_id")
                deviation["trigger_time"] = latest_event.get("end_time")

            # Only add if not already flagged
            if not any(d["type"] == "COUNT_EXCEEDED" for d in self.deviations):
                self.deviations.append(deviation)
                new_deviations.append(deviation)

        # Check duration limit
        if total_duration_sec > self.max_total_duration_sec:
            deviation = {
                "type": "DURATION_EXCEEDED",
                "message": (
                    f"Total duration ({total_duration_sec:.1f}s) exceeds "
                    f"limit ({self.max_total_duration_sec:.1f}s)"
                ),
                "current_value": round(total_duration_sec, 2),
                "limit": self.max_total_duration_sec,
                "severity": "HIGH",
                "detected_at": datetime.now().isoformat(),
            }
            if latest_event:
                deviation["trigger_event"] = latest_event.get("event_id")
                deviation["trigger_time"] = latest_event.get("end_time")

            # Only add if not already flagged
            if not any(d["type"] == "DURATION_EXCEEDED" for d in self.deviations):
                self.deviations.append(deviation)
                new_deviations.append(deviation)

        return new_deviations

    def get_deviations(self) -> List[Dict]:
        """Return all detected deviations."""
        return self.deviations

    def has_deviations(self) -> bool:
        """Check if any deviations were detected."""
        return len(self.deviations) > 0

    def get_status(self, total_count: int, total_duration_sec: float) -> Dict:
        """
        Return current compliance status.
        """
        count_pct = (total_count / self.max_intervention_count * 100) if self.max_intervention_count > 0 else 0
        duration_pct = (total_duration_sec / self.max_total_duration_sec * 100) if self.max_total_duration_sec > 0 else 0

        return {
            "count": {
                "current": total_count,
                "limit": self.max_intervention_count,
                "percentage": round(count_pct, 1),
                "exceeded": total_count > self.max_intervention_count,
            },
            "duration": {
                "current_sec": round(total_duration_sec, 2),
                "limit_sec": self.max_total_duration_sec,
                "percentage": round(duration_pct, 1),
                "exceeded": total_duration_sec > self.max_total_duration_sec,
            },
            "has_deviations": self.has_deviations(),
            "total_deviations": len(self.deviations),
        }

    def save_deviations(self, filepath: Optional[str] = None):
        """Save deviations to JSON file."""
        if filepath is None:
            filepath = os.path.join(self.output_dir, "deviations.json")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w") as f:
            json.dump(self.deviations, f, indent=2)

        return filepath
