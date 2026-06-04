# ML Engineering Review: Detection Methodology & Deployment Strategy

*Prepared for meeting on 28 March 2026*

---

## Part 1 — Current Methodology: Deep Review

### What We're Detecting

We detect **glove-port interventions** — i.e., when an operator's hand enters a circular/elliptical port on an aseptic isolator. We do **not** track the hand itself (no skeleton, no keypoints). We detect **motion within a fixed spatial region** and classify that motion as "intervention active" or "static."

### Pipeline: Frame-by-Frame

```
Raw Frame (1080p, ~25 FPS)
    │
    ├─── ROI Manager: crop each port region (exclusive elliptical masks)
    │       └─ Prevents cross-port bleed when ROIs are close together
    │
    ├─── Per-ROI Preprocessing:
    │       1. BGR → Grayscale
    │       2. GaussianBlur (5×5)
    │       3. Sobel gradient X + Y → Magnitude
    │       4. Normalize to [0, 255]
    │       5. Resize by 0.5× (performance optimization)
    │
    ├─── Temporal Voting (per ROI):
    │       - Maintain rolling buffer of last 25 processed frames
    │       - Compare current frame against EVERY frame in history
    │       - Compute SSIM (Structural Similarity Index) for each pair
    │       - Motion score = 1 - SSIM
    │       - If score > threshold (0.08): cast a "motion vote"
    │       - If ≥ 10 votes out of 25: raw_moving = True
    │
    ├─── EMA Smoothing:
    │       smoothed = 0.2 × raw_score + 0.8 × previous_smoothed
    │       Final decision: smoothed > 0.08 → ACTIVE
    │
    └─── Event State Machine:
            - min_active_frames: 5 (must sustain motion for 5 frames)
            - cooldown: 15 frames (prevents re-triggering immediately)
            - min_duration: 2 seconds
            - Records: start/end time, duration, snapshot, video clip
```

### Strengths of This Approach

| Strength | Why It Matters |
|---|---|
| **No ML model needed** | Zero training data requirement. Works out of the box. |
| **No GPU required** | Runs on CPU — cheap edge hardware. |
| **Deterministic** | Same input always produces same output. Easy to debug and validate for GMP audits. |
| **Lighting-robust** | Sobel edge detection is more resistant to uniform brightness changes than raw pixel diff. |
| **Low false positive rate** | The 25-frame temporal voting + EMA smoothing chain requires sustained, consistent motion to trigger. Random noise gets voted out. |
| **Exclusive masking** | Overlapping port regions are cleanly separated by nearest-center assignment. |

### Weaknesses & Failure Modes

| Weakness | Impact |
|---|---|
| **Not object-aware** | Cannot distinguish hand from a tool, glove, shadow, or vibration. A rattling pipe inside the ROI triggers the same as a hand. |
| **No hand tracking** | Cannot count *which* hand, *how many* hands, or track hand trajectories inside the port. |
| **Static hand = no detection** | If a hand enters and stays perfectly still (e.g., holding a clamp), the system eventually classifies it as STATIC because the SSIM score drops. |
| **Camera motion sensitivity** | Any camera shake or zoom change triggers false positives across ALL ROIs simultaneously. |
| **Fixed ROI = fragile** | If the camera angle shifts by even a few pixels (thermal drift, vibration), the ROI no longer aligns with the port. |
| **O(n²) per frame per ROI** | Comparing against 25 history frames × SSIM computation is expensive. At 4 ROIs × 25 cameras = quadratic scaling concern. |
| **No semantic classification** | Cannot identify *what type* of intervention is happening (sampling vs. adjustment vs. jam clearance) — this is done manually via the HITL UI. |

---

## Part 2 — Alternative Methods We Could Have Used

### 1. **YOLOv8 / YOLOv11 Object Detection** ⭐ (Recommended Upgrade)
- Train a small model to detect `hand_in_port`, `glove`, `tool` classes.
- Single forward pass per frame (~5-15ms on GPU, ~50ms on CPU with ONNX).
- Gives bounding boxes with confidence — directly tells you *where* the hand is and *how confident*.
- Can distinguish hand from non-hand motion (vibration, shadow).
- **Downside**: Requires labeled training data (~500-2000 annotated frames per class).

### 2. **MediaPipe Hands** (Google)
- Real-time hand landmark detection (21 keypoints per hand).
- Can detect up to 2 hands with skeleton tracking.
- Works on CPU (~30 FPS).
- **Downside**: Designed for bare hands, not gloved hands. May fail on nitrile/latex gloves in a pharma environment. Needs testing.

### 3. **Segment Anything Model 2 (SAM2)** (Meta)
- Zero-shot segmentation — can segment "the hand" without any training.
- Extremely accurate boundaries.
- **Downside**: Very heavy (~2-4 seconds per frame). Not suitable for real-time. Could be used for offline batch analysis.

### 4. **Background Subtraction (MOG2 / KNN)**
- OpenCV's built-in `BackgroundSubtractorMOG2` or `KNN`.
- Automatically learns a background model and detects foreground changes.
- Much simpler than our SSIM + Sobel approach.
- **Downside**: Sensitive to lighting changes and shadows. No semantic understanding.

### 5. **Optical Flow (Farneback / RAFT)**
- Dense optical flow computes per-pixel motion vectors.
- Can detect *direction* and *speed* of motion, not just presence.
- Could differentiate "hand entering" vs "hand leaving" vs "vibration."
- **Downside**: CPU-heavy for dense flow. Sparse (Lucas-Kanade) is faster but less informative.

### 6. **Temporal Convolutional Networks (TCN) / SlowFast**
- Video action recognition models that consider multiple frames.
- Can classify "intervention type" directly from video clips.
- **Downside**: Requires large labeled video datasets. High GPU memory.

### 7. **Anomaly Detection (Autoencoders / VAE)**
- Train on "normal" footage (empty port). Any deviation from learned normal = anomaly.
- No need to label "what" the anomaly is.
- **Downside**: Unsupervised — high false positive rate without careful tuning.

### Comparison Matrix

| Method | Accuracy | Speed | GPU Needed | Training Data | Hand-Specific |
|---|---|---|---|---|---|
| **Current (SSIM+Sobel)** | Medium | Fast (CPU) | ❌ | None | ❌ |
| YOLOv8 Detection | High | Fast | ✅ (or ONNX CPU) | ~1000 images | ✅ |
| MediaPipe Hands | High | Fast (CPU) | ❌ | None | ✅ (bare hands) |
| SAM2 | Very High | Very Slow | ✅ (heavy) | None | ❌ |
| MOG2 Background Sub | Low-Medium | Very Fast | ❌ | None | ❌ |
| Optical Flow | Medium | Medium | ❌ | None | ❌ |
| TCN / SlowFast | High | Slow | ✅ | Large | ✅ |
| Autoencoder | Medium | Medium | ✅ | Unlabeled video | ❌ |

---

## Part 3 — Improvement Plans (Discuss With the ML Engineer)

### Phase 1: Quick Wins (No Model Training)

1. **Replace SSIM temporal voting with MOG2 background subtraction**
   - 10× faster. Single maintained background model per ROI instead of 25-frame buffer.
   - Use `cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50)`.
   - Reduces O(n²) to O(1) per frame per ROI.

2. **Add camera stability detection**
   - Compute global frame-to-frame SSIM/hash.
   - If the *entire* frame shifts → suppress all ROI detections (camera shake filter).

3. **Auto-ROI alignment via ArUco markers**
   - Place fiducial markers (ArUco or QR) near each port.
   - System automatically detects markers and adjusts ROI positions each frame.
   - Eliminates the "camera drift" failure mode permanently.

### Phase 2: ML-Based Detection (Requires Data Collection)

4. **Train YOLOv8n on gloved-hand detection**
   - Collect ~1000 annotated frames from existing recorded clips.
   - Classes: `hand_in_port`, `tool_in_port`, `empty_port`.
   - Run inference on ROI crops only (not full frame) for speed.
   - Export to ONNX for CPU-only edge deployment.

5. **Two-stage pipeline**
   - Stage 1: Current SSIM method as a **cheap pre-filter** (detects "something changed").
   - Stage 2: YOLOv8 runs **only** on frames where Stage 1 fires (detects "is it a hand?").
   - Reduces GPU load by ~80% while maintaining high accuracy.

### Phase 3: Advanced (Future)

6. **Intervention type auto-classification**
   - Fine-tune a video classification model (SlowFast, X3D, or TimeSFormer) on labeled intervention clips.
   - Input: 2–5 second clip. Output: class label (sampling / adjustment / jam / environmental).
   - Eliminates manual HITL classification.

7. **Multi-camera fusion**
   - Correlate events across adjacent cameras to detect if the same operator is intervening on multiple ports simultaneously (which is already flagged as a CRITICAL deviation).

---

## Part 4 — Deployment Strategy at Client Site

### Architecture

```
┌─────────────────────────────────────────────────┐
│                 CLIENT SITE                     │
│                                                 │
│  ┌──────────┐   RTSP    ┌──────────────────┐   │
│  │ 29 IP    │ ────────► │  EDGE SERVER     │   │
│  │ Cameras  │           │  (GPU Optional)  │   │
│  └──────────┘           │                  │   │
│                         │  ┌─── Ingest ───┐│   │
│                         │  │ RTSP Reader   ││   │
│                         │  │ Frame Queue   ││   │
│                         │  └───────┬───────┘│   │
│                         │          │        │   │
│                         │  ┌───────▼───────┐│   │
│                         │  │ Detection     ││   │
│                         │  │ Workers (×N)  ││   │
│                         │  │ SSIM / YOLO   ││   │
│                         │  └───────┬───────┘│   │
│                         │          │        │   │
│                         │  ┌───────▼───────┐│   │
│                         │  │ Event Engine  ││   │
│                         │  │ + Clip Writer ││   │
│                         │  └───────┬───────┘│   │
│                         │          │        │   │
│                         │  ┌───────▼───────┐│   │
│                         │  │ FastAPI       ││   │
│                         │  │ (REST + WS)   ││   │
│                         │  └───────────────┘│   │
│                         └──────────────────┘│   │
│                                │             │   │
│                    ┌───────────▼──────────┐  │   │
│                    │ React Dashboard      │  │   │
│                    │ (served by Nginx)    │  │   │
│                    │ Accessible on LAN    │  │   │
│                    └─────────────────────┘  │   │
└─────────────────────────────────────────────────┘
         │ HTTPS (events + clips sync)
         ▼
┌──────────────────────┐
│     AWS CLOUD        │
│                      │
│  S3: Clip Archival   │
│  RDS: Event History  │
│  Dashboard Mirror    │
└──────────────────────┘
```

### Deployment Steps

| Step | Action | Owner |
|---|---|---|
| 1 | Install cameras, PoE switches, cabling | Site Infra Team |
| 2 | Provision edge server (rack-mount) | LiquidLights |
| 3 | Configure RTSP URLs per camera in `config.yaml` | LiquidLights |
| 4 | Draw ROIs for each port via Admin UI | Client QA + LiquidLights |
| 5 | Set compliance limits per product/line | Client QA |
| 6 | Run validation batch (media fill) | Client QA |
| 7 | Deploy dashboard access on LAN | LiquidLights |
| 8 | Configure S3 sync for archival | LiquidLights |
| 9 | Operator training (1 session) | LiquidLights |

### MLOps Considerations

- **Model versioning**: If we move to YOLOv8, use MLflow or DVC to track model weights and performance metrics.
- **Data pipeline**: New annotated frames from the HITL classification should flow back into a retraining dataset.
- **A/B testing**: Run SSIM and YOLO in parallel for 2 weeks. Compare false positive / false negative rates before switching.
- **Rollback**: Keep the current SSIM pipeline as a fallback. If the YOLO model degrades, auto-switch back.
- **Monitoring**: Track `events_per_hour`, `avg_confidence`, `false_positive_rate` in a time-series DB (Prometheus + Grafana).

---

## Part 5 — Questions to Ask the ML Engineer

### On Detection Methodology

1. **"We're using SSIM on Sobel gradients with a 25-frame temporal voting buffer. For a fixed-camera, fixed-ROI scenario — would you recommend switching entirely to background subtraction (MOG2), or is there value in keeping the temporal voting approach?"**

2. **"If we move to YOLOv8 for hand detection — should we train on full frames or just on the ROI crops? What are the tradeoffs for each in terms of data requirements and model generalization?"**

3. **"Our biggest failure mode is a static hand — a hand enters the port and holds still. SSIM can't detect it after a few seconds. What approach would you recommend for detecting 'presence' rather than 'motion'?"**
   - *(Possible answers: background subtraction baseline comparison, semantic segmentation, depth camera)*

4. **"For gloved hands specifically — have you seen MediaPipe or similar hand landmark models work reliably with latex/nitrile gloves? Or would a custom-trained detector be necessary?"**

5. **"We're considering a two-stage pipeline: cheap SSIM pre-filter → YOLO only on triggered frames. Is this a common pattern? What are the pitfalls?"**

6. **"How much labeled data would we realistically need for a reliable glove-hand detector? And what annotation strategy do you recommend — bounding boxes, instance segmentation, or keypoints?"**

### On Deployment & MLOps

7. **"For 25 cameras running simultaneously on a single edge server — what's the best way to parallelize? Multi-process with shared memory, or async with a frame queue?"**

8. **"If we deploy a YOLO model on an edge server without a GPU — what's the best inference runtime? ONNX Runtime, OpenVINO, or TensorRT with CPU fallback?"**

9. **"How should we handle model updates in production? Docker containers with model baked in, or a model registry with hot-reload?"**

10. **"For monitoring model drift in production — what metrics would you track, and how would you set up alerting? We can't afford false negatives in a pharma environment."**

11. **"We're syncing event data and clips to AWS S3 nightly. Is there a better pattern for a hybrid edge-cloud architecture? Should we use MQTT, or just scheduled rsync?"**

12. **"For the people-counting door cameras — would you recommend a separate model per door, or one shared model with multi-stream batching?"**

---

> **Tip for the meeting**: Focus questions 1–3 and 7–8 first. These directly impact the next iteration. Save 6 and 9–12 for if the conversation goes towards a longer engagement.
