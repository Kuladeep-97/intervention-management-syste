"""
ROI Manager Module
==================
Manages glove-port region definitions with overlap prevention.
Supports circles AND ellipses for better ROI capture.
Includes interactive canvas-based setup and exclusive masking.
"""

import cv2
import numpy as np
import yaml
import math
from typing import List, Dict, Tuple, Optional


class ROIManager:
    """Manages ROI definitions for glove-port regions. Supports circle and ellipse shapes."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.rois: List[Dict] = []
        self.frame_shape: Optional[Tuple[int, int]] = None  # (height, width)
        self.exclusive_masks: List[Optional[np.ndarray]] = []

    def load_from_config(self) -> List[Dict]:
        """Load ROI definitions from config file."""
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        self.rois = config.get("rois", []) or []
        # Ensure all ROIs have a shape type
        for roi in self.rois:
            if "shape" not in roi:
                roi["shape"] = "circle"
            # Ensure ellipses have axes
            if roi["shape"] == "ellipse" and "axes" not in roi:
                roi["axes"] = [roi.get("radius", 60), roi.get("radius", 60)]
        return self.rois

    def save_to_config(self):
        """Save current ROIs back to config file."""
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        config["rois"] = self.rois

        with open(self.config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

    def set_rois(self, rois: List[Dict]):
        """Set ROIs directly (from Streamlit UI or other source)."""
        self.rois = rois
        self.exclusive_masks = []

    @staticmethod
    def from_canvas_objects(canvas_json: dict, scale_x: float = 1.0, scale_y: float = 1.0) -> List[Dict]:
        """
        Convert streamlit-drawable-canvas JSON output to ROI definitions.
        Supports circles and ellipses drawn on the canvas.

        Canvas objects have:
        - circle: {type: "circle", left, top, radius, scaleX, scaleY, ...}
        - ellipse: {type: "ellipse", left, top, rx, ry, scaleX, scaleY, ...}
        - rect treated as ellipse: compute bounding ellipse from rect

        scale_x/scale_y: ratio of original image size to canvas display size
        """
        rois = []
        objects = canvas_json.get("objects", [])

        for i, obj in enumerate(objects):
            obj_type = obj.get("type", "")
            obj_scale_x = obj.get("scaleX", 1.0)
            obj_scale_y = obj.get("scaleY", 1.0)

            if obj_type == "circle":
                # Canvas circle: center = (left + radius*scaleX, top + radius*scaleY)
                radius = obj.get("radius", 50)
                cx = (obj.get("left", 0) + radius * obj_scale_x) * scale_x
                cy = (obj.get("top", 0) + radius * obj_scale_y) * scale_y
                scaled_radius = radius * max(obj_scale_x, obj_scale_y) * max(scale_x, scale_y)

                rois.append({
                    "shape": "circle",
                    "center": [int(cx), int(cy)],
                    "radius": int(scaled_radius),
                    "label": f"Port {i + 1}",
                })

            elif obj_type == "ellipse":
                # Canvas ellipse: center = (left, top) with rx, ry
                rx = obj.get("rx", 50) * obj_scale_x
                ry = obj.get("ry", 50) * obj_scale_y
                cx = (obj.get("left", 0)) * scale_x
                cy = (obj.get("top", 0)) * scale_y

                rois.append({
                    "shape": "ellipse",
                    "center": [int(cx), int(cy)],
                    "axes": [int(rx * scale_x), int(ry * scale_y)],
                    "radius": int(max(rx * scale_x, ry * scale_y)),  # for compatibility
                    "label": f"Port {i + 1}",
                })

            elif obj_type == "rect":
                # Convert rectangle to ellipse (inscribed)
                width = obj.get("width", 100) * obj_scale_x
                height = obj.get("height", 100) * obj_scale_y
                left = obj.get("left", 0)
                top = obj.get("top", 0)

                cx = (left + width / 2) * scale_x
                cy = (top + height / 2) * scale_y
                rx = (width / 2) * scale_x
                ry = (height / 2) * scale_y

                rois.append({
                    "shape": "ellipse",
                    "center": [int(cx), int(cy)],
                    "axes": [int(rx), int(ry)],
                    "radius": int(max(rx, ry)),
                    "label": f"Port {i + 1}",
                })

        return rois

    # ---------------------------------------------------------
    # Overlap Detection
    # ---------------------------------------------------------
    def _get_effective_radius(self, roi: Dict) -> float:
        """Get the max effective radius of a ROI (for overlap checking)."""
        if roi.get("shape") == "ellipse" and "axes" in roi:
            return max(roi["axes"])
        return roi.get("radius", 60)

    def check_overlap(self, roi_a: Dict, roi_b: Dict) -> float:
        """
        Check if two ROIs overlap.
        Returns overlap ratio (0 = no overlap, 1 = identical).
        """
        cx_a, cy_a = roi_a["center"]
        cx_b, cy_b = roi_b["center"]
        r_a = self._get_effective_radius(roi_a)
        r_b = self._get_effective_radius(roi_b)

        distance = math.sqrt((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2)
        sum_radii = r_a + r_b

        if distance >= sum_radii:
            return 0.0

        overlap = max(0, sum_radii - distance) / min(r_a, r_b)
        return min(overlap, 1.0)

    def validate_rois(self, min_separation: int = 20) -> List[str]:
        """Validate that ROIs don't overlap. Returns list of warning messages."""
        warnings = []
        for i in range(len(self.rois)):
            for j in range(i + 1, len(self.rois)):
                overlap = self.check_overlap(self.rois[i], self.rois[j])
                if overlap > 0:
                    warnings.append(
                        f"⚠️ Port {i + 1} and Port {j + 1} overlap "
                        f"(ratio: {overlap:.2f}). Reduce size or increase separation."
                    )

                cx_a, cy_a = self.rois[i]["center"]
                cx_b, cy_b = self.rois[j]["center"]
                r_a = self._get_effective_radius(self.rois[i])
                r_b = self._get_effective_radius(self.rois[j])
                distance = math.sqrt((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2)
                gap = distance - r_a - r_b

                if 0 < gap < min_separation:
                    warnings.append(
                        f"⚠️ Port {i + 1} and Port {j + 1} are very close "
                        f"(gap: {gap:.0f}px). Recommend ≥{min_separation}px separation."
                    )

        return warnings

    # ---------------------------------------------------------
    # Exclusive Masking
    # ---------------------------------------------------------
    def _draw_roi_mask(self, mask: np.ndarray, roi: Dict):
        """Draw a single ROI onto a mask (filled white)."""
        cx, cy = roi["center"]
        shape = roi.get("shape", "circle")

        if shape == "ellipse" and "axes" in roi:
            rx, ry = roi["axes"]
            cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)
        else:
            r = roi.get("radius", 60)
            cv2.circle(mask, (cx, cy), r, 255, -1)

    def build_exclusive_masks(self, frame_height: int, frame_width: int):
        """
        Build exclusive binary masks for each ROI.
        If pixels fall in multiple ROIs, they are assigned to the nearest center.
        """
        self.frame_shape = (frame_height, frame_width)
        self.exclusive_masks = []

        if not self.rois:
            return

        # Create individual masks
        individual_masks = []
        for roi in self.rois:
            mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
            self._draw_roi_mask(mask, roi)
            individual_masks.append(mask)

        # Handle overlapping pixels
        for i, roi_i in enumerate(self.rois):
            mask = individual_masks[i].copy()

            for j, roi_j in enumerate(self.rois):
                if i == j:
                    continue

                overlap = cv2.bitwise_and(individual_masks[i], individual_masks[j])
                overlap_coords = np.where(overlap > 0)

                if len(overlap_coords[0]) == 0:
                    continue

                cx_i, cy_i = roi_i["center"]
                cx_j, cy_j = roi_j["center"]

                for y, x in zip(overlap_coords[0], overlap_coords[1]):
                    dist_i = math.sqrt((x - cx_i) ** 2 + (y - cy_i) ** 2)
                    dist_j = math.sqrt((x - cx_j) ** 2 + (y - cy_j) ** 2)
                    if dist_j < dist_i:
                        mask[y, x] = 0

            self.exclusive_masks.append(mask)

    def get_roi_crop(self, frame: np.ndarray, roi_index: int) -> np.ndarray:
        """Extract the ROI region from a frame with exclusive masking."""
        roi = self.rois[roi_index]
        cx, cy = roi["center"]
        r = self._get_effective_radius(roi)
        h, w = frame.shape[:2]

        x1 = max(cx - r, 0)
        y1 = max(cy - r, 0)
        x2 = min(cx + r, w)
        y2 = min(cy + r, h)

        crop = frame[y1:y2, x1:x2].copy()

        if self.exclusive_masks:
            mask_crop = self.exclusive_masks[roi_index][y1:y2, x1:x2]
            if len(crop.shape) == 3:
                crop = cv2.bitwise_and(crop, crop, mask=mask_crop)
            else:
                crop = cv2.bitwise_and(crop, mask_crop)

        return crop

    def get_roi_bbox(self, roi_index: int, frame_width: int, frame_height: int) -> Tuple[int, int, int, int]:
        """Get bounding box (x1, y1, x2, y2) for a ROI."""
        roi = self.rois[roi_index]
        cx, cy = roi["center"]
        r = self._get_effective_radius(roi)
        x1 = max(cx - r, 0)
        y1 = max(cy - r, 0)
        x2 = min(cx + r, frame_width)
        y2 = min(cy + r, frame_height)
        return x1, y1, x2, y2

    # ---------------------------------------------------------
    # Visualization
    # ---------------------------------------------------------
    def draw_rois(self, frame: np.ndarray, states: Optional[List[str]] = None) -> np.ndarray:
        """Draw ROI shapes on frame with state-based coloring."""
        display = frame.copy()

        for i, roi in enumerate(self.rois):
            cx, cy = roi["center"]
            shape = roi.get("shape", "circle")

            if states and i < len(states):
                # Handle both "ACTIVE" (legacy) and "MOVING" (new) states
                if states[i] in ["ACTIVE", "MOVING"]:
                    color = (0, 0, 255)
                    thickness = 3
                else:
                    color = (0, 255, 0)
                    thickness = 2
            else:
                color = (255, 255, 0)
                thickness = 2

            if shape == "ellipse" and "axes" in roi:
                rx, ry = roi["axes"]
                cv2.ellipse(display, (cx, cy), (rx, ry), 0, 0, 360, color, thickness)
            else:
                r = roi.get("radius", 60)
                cv2.circle(display, (cx, cy), r, color, thickness)

            label = roi.get("label", f"Port {i + 1}")
            if states and i < len(states):
                label += f": {states[i]}"

            # Draw label above the shape
            r_eff = self._get_effective_radius(roi)
            cv2.putText(
                display, label,
                (cx - 50, cy - r_eff - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6, color, 2
            )

        return display

    def has_rois(self) -> bool:
        """Check if any ROIs are defined."""
        return len(self.rois) > 0
