"""
Motion Detector Module
=======================
SSIM + Sobel gradient-based motion detection per ROI.
Based on reference implementation with improvements:
- Exclusive ROI masking to prevent cross-ROI bleed
- Per-ROI independent background history
"""

import cv2
import numpy as np
from collections import deque
from skimage.metrics import structural_similarity as ssim
from typing import Dict, Tuple


class MotionDetector:
    """
    Detects motion within a circular ROI using SSIM on Sobel gradient images.
    Each ROI gets its own instance with independent frame history.
    """

    def __init__(
        self,
        roi_index: int,
        ssim_threshold: float = 0.08,
        ema_beta: float = 0.2,
        history_size: int = 25,
        min_motion_votes: int = 10,
        resize_factor: float = 0.5,
    ):
        self.roi_index = roi_index
        self.ssim_threshold = ssim_threshold
        self.ema_beta = ema_beta
        self.history_size = history_size
        self.min_motion_votes = min_motion_votes
        self.resize_factor = resize_factor

        # Frame history for temporal voting
        self.frame_history: deque = deque(maxlen=history_size)

        # EMA smoothed score
        self.smoothed_score: float = 0.0

        # Statistics
        self.total_moving_frames: int = 0
        self.total_static_frames: int = 0

    def preprocess(self, roi_crop: np.ndarray) -> np.ndarray:
        """
        Preprocess ROI crop: grayscale → blur → Sobel gradient magnitude.
        Same pipeline as reference implementation.
        """
        # Convert to grayscale if color
        if len(roi_crop.shape) == 3:
            gray = cv2.cvtColor(roi_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi_crop.copy()

        # Gaussian blur
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        # Sobel gradient magnitude
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        grad = cv2.magnitude(gx, gy)

        # Normalize to 0-255
        grad = cv2.normalize(grad, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # Resize for performance
        if self.resize_factor != 1.0 and grad.size > 0:
            grad = cv2.resize(
                grad, (0, 0),
                fx=self.resize_factor,
                fy=self.resize_factor,
            )

        return grad

    def compute_motion_score(self, current: np.ndarray, past: np.ndarray) -> float:
        """Compute motion score as 1 - SSIM."""
        if current.shape != past.shape or current.size == 0:
            return 0.0

        # SSIM needs minimum image size
        min_dim = min(current.shape[:2])
        if min_dim < 7:
            return 0.0

        win_size = min(7, min_dim)
        if win_size % 2 == 0:
            win_size -= 1

        try:
            similarity = ssim(past, current, win_size=win_size)
            return max(0.0, 1.0 - similarity)
        except Exception:
            return 0.0

    def temporal_vote(self, current_processed: np.ndarray) -> Tuple[bool, float]:
        """
        Compare current frame against history using temporal voting.
        Returns (is_moving, average_motion_score).
        """
        if len(self.frame_history) == 0:
            return False, 0.0

        motion_votes = 0
        motion_scores = []

        for past_frame in self.frame_history:
            if past_frame.shape != current_processed.shape:
                continue

            score = self.compute_motion_score(current_processed, past_frame)
            motion_scores.append(score)

            if score > self.ssim_threshold:
                motion_votes += 1
                if motion_votes >= self.min_motion_votes:
                    break

        is_moving = motion_votes >= self.min_motion_votes
        avg_score = float(np.mean(motion_scores)) if motion_scores else 0.0

        return is_moving, avg_score

    def process_frame(self, roi_crop: np.ndarray) -> Dict:
        """
        Process a single frame's ROI crop.
        Returns dict with motion detection results.
        """
        # Preprocess
        processed = self.preprocess(roi_crop)

        # Temporal voting
        raw_moving, raw_score = self.temporal_vote(processed)

        # EMA smoothing
        self.smoothed_score = (
            self.ema_beta * raw_score
            + (1 - self.ema_beta) * self.smoothed_score
        )

        # Final decision based on smoothed score
        is_active = self.smoothed_score > self.ssim_threshold

        # Update statistics
        if is_active:
            self.total_moving_frames += 1
        else:
            self.total_static_frames += 1

        # Update history
        self.frame_history.append(processed)

        return {
            "roi_index": self.roi_index,
            "raw_score": raw_score,
            "smoothed_score": self.smoothed_score,
            "is_active": is_active,
            "label": "MOVING" if is_active else "STATIC",
        }

    def get_stats(self) -> Dict:
        """Return detector statistics."""
        return {
            "roi_index": self.roi_index,
            "total_moving": self.total_moving_frames,
            "total_static": self.total_static_frames,
            "smoothed_score": self.smoothed_score,
        }

    def reset(self):
        """Reset detector state."""
        self.frame_history.clear()
        self.smoothed_score = 0.0
        self.total_moving_frames = 0
        self.total_static_frames = 0
