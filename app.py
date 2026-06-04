"""
Streamlit Dashboard
====================
Interactive web UI for the Glove-Port Video Analytics MVP.
Features: video processing, ROI setup, event timeline, deviation alerts.
"""

import streamlit as st
import os
import sys
import cv2
import json
import yaml
import time
import numpy as np
import pandas as pd
from PIL import Image

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.video_input import VideoInput
from src.roi_manager import ROIManager
from src.motion_detector import MotionDetector
from src.event_classifier import EventClassifier
from src.event_recorder import EventRecorder
from src.deviation_checker import DeviationChecker

# ============================================================
# Page Config
# ============================================================
st.set_page_config(
    page_title="GlovePort Analytics",
    page_icon="🧤",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Custom CSS
# ============================================================
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    }
    .glass-card {
        background: rgba(22, 27, 34, 0.8);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(48, 54, 61, 0.8);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    .metric-card {
        background: linear-gradient(135deg, rgba(22, 27, 34, 0.9), rgba(33, 38, 45, 0.9));
        border: 1px solid rgba(48, 54, 61, 0.6);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #58a6ff, #79c0ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 8px 0;
    }
    .metric-label {
        color: #8b949e;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-value.alert {
        background: linear-gradient(135deg, #f85149, #ff7b72);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-value.success {
        background: linear-gradient(135deg, #3fb950, #56d364);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .deviation-alert {
        background: linear-gradient(135deg, rgba(248, 81, 73, 0.1), rgba(248, 81, 73, 0.05));
        border: 1px solid rgba(248, 81, 73, 0.3);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .section-header {
        color: #f0f6fc;
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 2px solid rgba(88, 166, 255, 0.3);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stProgress > div > div {
        background: linear-gradient(90deg, #58a6ff, #79c0ff);
    }
    @keyframes pulse-red {
        0% { transform: scale(1); box-shadow: 0 0 15px rgba(248, 81, 73, 0.4); }
        50% { transform: scale(1.02); box-shadow: 0 0 35px rgba(248, 81, 73, 0.8), 0 0 15px rgba(248, 81, 73, 0.5) inset; border-color: #ff7b72; }
        100% { transform: scale(1); box-shadow: 0 0 15px rgba(248, 81, 73, 0.4); }
    }
    .critical-alarm {
        background: linear-gradient(135deg, rgba(248, 81, 73, 0.2), rgba(248, 81, 73, 0.05));
        border: 2px solid #f85149;
        border-radius: 12px;
        padding: 24px;
        margin: 16px 0;
        text-align: center;
        animation: pulse-red 1.5s infinite;
        position: relative;
        overflow: hidden;
    }
    .critical-alarm::before {
        content: '';
        position: absolute;
        top: 0; left: -100%; width: 50%; height: 100%;
        background: linear-gradient(to right, transparent, rgba(255, 255, 255, 0.2), transparent);
        transform: skewX(-20deg);
        animation: alarm-sweep 3s infinite;
    }
    @keyframes alarm-sweep {
        0% { left: -100%; }
        20% { left: 200%; }
        100% { left: 200%; }
    }
    .critical-alarm h2 {
        color: #ff7b72;
        margin-top: 0;
        font-weight: 800;
        letter-spacing: 2px;
        text-shadow: 0 2px 4px rgba(0,0,0,0.5);
    }
    .metric-value.warning {
        background: linear-gradient(135deg, #d29922, #e3b341);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Helper Functions
# ============================================================
def load_config(config_path="config.yaml"):
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(config, config_path="config.yaml"):
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def format_duration(seconds):
    if seconds < 3600:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}:{secs:05.2f}"
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{mins:02d}:{secs:05.2f}"


def find_video_files(directory="."):
    exts = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
    return sorted(f for f in os.listdir(directory)
                  if os.path.splitext(f)[1].lower() in exts)


# ============================================================
# Sidebar & Routing
# ============================================================
config = load_config()

with st.sidebar:
    st.markdown("## 🧤 GlovePort Analytics")
    st.markdown("---")
    
    view_mode = st.radio("Navigation", ["Live Dashboard", "🔴 Stream Mode", "Admin Settings"])
    st.markdown("---")

    # ---- Video Selection ----
    st.markdown("### 📹 Video Input")
    video_files = find_video_files(".")
    selected_video = None
    if video_files:
        selected_video = st.selectbox("Select video file", video_files)
    else:
        st.warning("No video files found.")

    st.markdown("---")
    
    # ---- Deviation Limits (Kept on both pages) ----
    st.markdown("### 🚨 Deviation Limits")
    limits_cfg = config.get("limits", {})
    max_count = st.number_input("Max Interventions", min_value=1,
        value=limits_cfg.get("max_intervention_count", 20))
    max_duration_limit = st.number_input("Max Total Duration (sec)", min_value=10.0,
        value=float(limits_cfg.get("max_total_duration_sec", 300.0)))

    st.markdown("---")
    if view_mode == "Live Dashboard":
        process_btn = st.button("🚀 Run Analysis", use_container_width=True, type="primary",
            disabled=(selected_video is None))
    else:
        process_btn = False

# Keep references to configs that will be moved to Admin page to avoid UnboundLocalError
current_rois = config.get("rois", []) or []
roi_configs = config.get("rois", []) or []
num_ports = max(len(roi_configs), 1)
detection_cfg = config.get("detection", {})
ssim_threshold = detection_cfg.get("ssim_threshold", 0.08)
ema_beta = detection_cfg.get("ema_beta", 0.2)
history_size = detection_cfg.get("history_size", 25)
min_motion_votes = detection_cfg.get("min_motion_votes", 10)
min_duration = config.get("events", {}).get("min_intervention_duration_sec", 2.0)

# ============================================================
# Admin Settings Page
# ============================================================
if view_mode == "Admin Settings":
    st.markdown("""
    <div style="text-align: center; padding: 10px 0 20px;">
        <h1 style="color: #f0f6fc; font-size: 2.2rem; font-weight: 700;">
            ⚙️ Admin Settings & Configuration
        </h1>
        <p style="color: #8b949e; font-size: 1.05rem;">
            Lock hyper-parameters and define Media Fill Standards
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col_roi, col_det = st.columns(2)
    
    with col_roi:
        st.markdown('<div class="section-header">📍 ROI Configuration</div>', unsafe_allow_html=True)
        st.info("💡 **QA Requirement:** Do not draw ROIs on the physical glass. Draw them deeper inside the tank to capture 'Full Insertion' only.")
        num_ports = st.number_input(
            "Number of glove ports",
            min_value=1, max_value=8, value=max(len(current_rois), 1),
        )

        roi_configs = []
        for i in range(int(num_ports)):
            with st.expander(f"Port {i + 1}", expanded=(i < len(current_rois))):
                defaults = current_rois[i] if i < len(current_rois) else {"center": [0, 0], "radius": 60, "shape": "circle"}
                shape = st.selectbox(
                    "Shape", ["circle", "ellipse"],
                    index=0 if defaults.get("shape", "circle") == "circle" else 1,
                    key=f"shape_{i}",
                )
                cx = st.number_input("Center X", value=defaults["center"][0], key=f"cx_{i}")
                cy = st.number_input("Center Y", value=defaults["center"][1], key=f"cy_{i}")

                if shape == "circle":
                    r = st.number_input("Radius", value=defaults.get("radius", 60), min_value=10, key=f"r_{i}")
                    roi_configs.append({"shape": "circle", "center": [int(cx), int(cy)], "radius": int(r)})
                else:
                    axes = defaults.get("axes", [60, 60])
                    rx = st.number_input("Radius X", value=axes[0], min_value=10, key=f"rx_{i}")
                    ry = st.number_input("Radius Y", value=axes[1], min_value=10, key=f"ry_{i}")
                    roi_configs.append({
                        "shape": "ellipse", "center": [int(cx), int(cy)],
                        "axes": [int(rx), int(ry)], "radius": max(int(rx), int(ry)),
                    })

        if st.button("💾 Save ROIs", use_container_width=True):
            config["rois"] = roi_configs
            save_config(config)
            st.success("ROIs saved!")
            
    with col_det:
        st.markdown('<div class="section-header">⚙️ Detection Parameters</div>', unsafe_allow_html=True)
        ssim_threshold = st.slider("SSIM Threshold", 0.01, 0.3,
            detection_cfg.get("ssim_threshold", 0.08), 0.01)
        ema_beta = st.slider("EMA Smoothing (β)", 0.05, 0.5,
            detection_cfg.get("ema_beta", 0.2), 0.05)
        history_size = st.slider("Frame History", 5, 50,
            detection_cfg.get("history_size", 25))
        min_motion_votes = st.slider("Min Motion Votes", 1, 25,
            detection_cfg.get("min_motion_votes", 10))
        min_duration = st.slider("Min Intervention (sec)", 0.5, 10.0,
            config.get("events", {}).get("min_intervention_duration_sec", 2.0), 0.5)
            
        st.markdown('<div class="section-header" style="margin-top: 2rem;">🛡️ Media Fill Standardization</div>', unsafe_allow_html=True)
        if st.button("🔒 Save as Media Fill Standard", use_container_width=True, type="primary"):
            config["rois"] = roi_configs
            config["detection"] = {
                "ssim_threshold": ssim_threshold, "ema_beta": ema_beta,
                "history_size": history_size, "min_motion_votes": min_motion_votes,
                "resize_factor": config.get("detection", {}).get("resize_factor", 0.5),
            }
            config["events"] = {
                "min_intervention_duration_sec": min_duration,
                "cooldown_frames": config.get("events", {}).get("cooldown_frames", 15),
                "min_active_frames": config.get("events", {}).get("min_active_frames", 5),
            }
            save_config(config)
            st.success("✅ Media Fill Standard Profile Saved! Hyperparameters locked for Live Dashboard.")

    # ---- Video Info (moved here from Dashboard) ----
    st.markdown("---")
    st.markdown('<div class="section-header">ℹ️ Video File Info</div>', unsafe_allow_html=True)
    if selected_video and os.path.exists(selected_video):
        try:
            _vi = VideoInput(selected_video)
            _info = _vi.get_info()
            _vi.release()
            st.markdown(f"""
            <div class="glass-card">
                <p><strong>File:</strong> {os.path.basename(_info['path'])}</p>
                <p><strong>Resolution:</strong> {_info['width']} × {_info['height']}</p>
                <p><strong>FPS:</strong> {_info['fps']:.2f}</p>
                <p><strong>Frames:</strong> {_info['total_frames']:,}</p>
                <p><strong>Duration:</strong> {format_duration(_info['duration_sec'])}</p>
                <p><strong>Start Time:</strong> {_info['start_time']}</p>
            </div>
            """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error loading video info: {e}")
    else:
        st.info("Select a video file in the sidebar to see metadata here.")

# ============================================================
# Stream Mode
# ============================================================
elif view_mode == "🔴 Stream Mode":
    st.markdown("""
    <div style="text-align: center; padding: 10px 0 20px;">
        <h1 style="color: #f0f6fc; font-size: 2.2rem; font-weight: 700;">
            📡 Real-Time Stream Analytics
        </h1>
        <p style="color: #8b949e; font-size: 1.05rem;">
            Live processing of videos from the <code>input_stream</code> directory
        </p>
    </div>
    """, unsafe_allow_html=True)

    import requests # Standard in most envs, adding here for local use

    API_BASE = "http://localhost:5000"
    
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown('<div class="section-header">📡 Live Video Feed</div>', unsafe_allow_html=True)
        # Use an iframe to embed the MJPEG stream from api_server
        st.markdown(f"""
        <div style="border: 2px solid #30363d; border-radius: 12px; overflow: hidden; background: #000;">
            <img src="{API_BASE}/stream/video_feed" style="width: 100%; display: block;">
        </div>
        """, unsafe_allow_html=True)
        
        st.caption("💡 Monitor <code>input_stream/</code> folder or start manually below.")

    with col2:
        st.markdown('<div class="section-header">🎮 Control & Status</div>', unsafe_allow_html=True)
        
        status_placeholder = st.empty()
        
        c_start, c_stop = st.columns(2)
        if c_start.button("▶️ Start", use_container_width=True, type="primary"):
            try:
                # Use default file if none specified
                resp = requests.post(f"{API_BASE}/api/stream/start", json={})
                st.toast("Stream started!", icon="🚀")
            except Exception as e:
                st.error(f"Connect error: {e}")

        if c_stop.button("⏹️ Stop", use_container_width=True):
            try:
                requests.post(f"{API_BASE}/api/stream/stop")
                st.toast("Stream stopped.", icon="⏹️")
            except: pass

        st.markdown("---")
        
        # Real-time metrics in sidebar/col2
        metrics_placeholder = st.container()
        
    # Poll for status updates
    st.markdown("---")
    st.markdown('<div class="section-header">📋 Live Event Log</div>', unsafe_allow_html=True)
    events_placeholder = st.empty()

    # Polling Loop
    if "streaming_active" not in st.session_state:
        st.session_state.streaming_active = True

    while st.session_state.streaming_active:
        try:
            r = requests.get(f"{API_BASE}/api/stream/status", timeout=1)
            if r.status_code == 200:
                data = r.json()
                is_running = data.get("is_running", False)
                progress = data.get("progress_pct", 0) / 100
                frame = data.get("frame_idx", 0)
                total = data.get("total_frames", 0)
                events = data.get("events", [])
                summary = data.get("summary", {})
                devs = data.get("deviations", [])

                with status_placeholder:
                    if is_running:
                        st.success(f"🟢 Processing: Frame {frame}/{total}")
                        st.progress(min(progress, 1.0))
                    else:
                        st.info("⚪ Idle - Waiting for video in input_stream/...")

                with metrics_placeholder:
                    m1, m2 = st.columns(2)
                    m1.metric("Interventions", len(events))
                    m2.metric("Duration", f"{summary.get('total_duration_sec', 0):.1f}s")
                    
                    if devs:
                        st.warning(f"🚨 {len(devs)} Deviations Detected!")
                
                with events_placeholder:
                    if events:
                        df_ev = pd.DataFrame(events)[["event_id", "roi_label", "start_time", "duration_sec"]].tail(5)
                        st.table(df_ev)
                    else:
                        st.write("No events detected yet.")
                
            else:
                status_placeholder.error("Cannot reach API server on port 5000.")
        except:
            status_placeholder.error("API Server Offline. Run `python api_server.py` first.")
        
        time.sleep(1)
        if not is_running and frame > 0: # If it just finished
            st.toast("Processing complete!", icon="✅")
            # st.rerun() # Refresh to show final results if needed


# ============================================================
# Main Dashboard
# ============================================================
elif view_mode == "Live Dashboard":
    st.markdown("""
<div style="text-align: center; padding: 10px 0 20px;">
    <h1 style="color: #f0f6fc; font-size: 2.2rem; font-weight: 700;">
        🧤 Glove-Port Intervention Analytics
    </h1>
    <p style="color: #8b949e; font-size: 1.05rem;">
        Automated detection &amp; monitoring of aseptic glove-port interventions
    </p>
</div>
""", unsafe_allow_html=True)

# ---- Video Preview with ROIs (full-width, no info panel) ----
if selected_video and os.path.exists(selected_video):
    st.markdown('<div class="section-header">📹 First Frame Preview</div>', unsafe_allow_html=True)
    try:
        video_input = VideoInput(selected_video)
        first_frame = video_input.get_first_frame()

        if roi_configs and any(r["center"] != [0, 0] for r in roi_configs):
            roi_mgr = ROIManager()
            roi_mgr.set_rois(roi_configs)
            annotated = roi_mgr.draw_rois(first_frame)
            annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            st.image(annotated_rgb, caption="First frame — glove-port ROI overlay", use_container_width=True)
        else:
            frame_rgb = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
            st.image(frame_rgb, caption="First frame (ROIs not yet configured — go to Admin Settings)", use_container_width=True)

        video_input.release()
    except Exception as e:
        st.error(f"Error loading video: {e}")


# ============================================================
# Processing
# ============================================================
if process_btn and selected_video:
    roi_configs = config.get("rois", []) or roi_configs

    if not roi_configs or all(r["center"] == [0, 0] for r in roi_configs):
        st.error("❌ Please configure ROI coordinates in the sidebar first.")
    else:
        st.markdown("---")
        st.markdown('<div class="section-header">🔄 Processing Video</div>', unsafe_allow_html=True)

        # Save config
        config["rois"] = roi_configs
        config["detection"] = {
            "ssim_threshold": ssim_threshold, "ema_beta": ema_beta,
            "history_size": history_size, "min_motion_votes": min_motion_votes,
            "resize_factor": config.get("detection", {}).get("resize_factor", 0.5),
        }
        config["events"] = {
            "min_intervention_duration_sec": min_duration,
            "cooldown_frames": config.get("events", {}).get("cooldown_frames", 15),
            "min_active_frames": config.get("events", {}).get("min_active_frames", 5),
        }
        config["limits"] = {
            "max_intervention_count": int(max_count),
            "max_total_duration_sec": float(max_duration_limit),
        }
        save_config(config)

        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            video = VideoInput(selected_video)
            vi = video.get_info()

            roi_manager = ROIManager()
            roi_manager.set_rois(roi_configs)
            roi_manager.build_exclusive_masks(vi["height"], vi["width"])

            detectors = [
                MotionDetector(
                    roi_index=i, ssim_threshold=ssim_threshold,
                    ema_beta=ema_beta, history_size=history_size,
                    min_motion_votes=min_motion_votes,
                    resize_factor=config["detection"].get("resize_factor", 0.5),
                ) for i in range(len(roi_configs))
            ]

            classifiers = [
                EventClassifier(
                    roi_index=i, fps=vi["fps"],
                    min_active_frames=config["events"].get("min_active_frames", 5),
                    cooldown_frames=config["events"].get("cooldown_frames", 15),
                    min_intervention_duration_sec=min_duration,
                ) for i in range(len(roi_configs))
            ]

            out_dir = config.get("output", {}).get("directory", "output")
            recorder = EventRecorder(
                output_dir=out_dir, 
                save_snapshots=True,
                fps=vi["fps"]
            )
            deviation_checker = DeviationChecker(
                max_intervention_count=int(max_count),
                max_total_duration_sec=float(max_duration_limit),
                output_dir=out_dir,
            )

            out_video_path = os.path.join(out_dir, "output_annotated.mp4")
            # Try avc1 (H264) which is often supported by browsers better than mp4v
            fourcc = cv2.VideoWriter_fourcc(*'avc1') 
            writer = cv2.VideoWriter(out_video_path, fourcc, vi["fps"], (vi["width"], vi["height"]))

            all_events = []
            start_time = time.time()

            for frame_idx, frame in video.iter_frames():
                active_events_this_frame = []
                for i in range(len(roi_configs)):
                    roi_crop = roi_manager.get_roi_crop(frame, i)
                    motion_result = detectors[i].process_frame(roi_crop)
                    
                    is_active = motion_result["is_active"]
                    recorder.buffer_frame(i, frame, is_active)
                    
                    if is_active:
                        # Construct a mock event dict for the deviation checker's simultaneous check
                        active_events_this_frame.append({
                            "roi_index": i, 
                            "event_id": getattr(classifiers[i], "current_event_id", f"temp_{i}_{frame_idx}") 
                        })

                    event = classifiers[i].process_frame(frame_idx, is_active)

                    if event is not None:
                        states = [c.get_state() for c in classifiers]
                        annotated = roi_manager.draw_rois(frame, states)
                        recorder.record_event(event, annotated)
                        all_events.append(event)
                        summary = recorder.get_summary()
                        deviation_checker.check(
                            summary["total_events"], summary["total_duration_sec"], event)
                            
                # Check for simultaneous deviations across all ports this frame
                if len(active_events_this_frame) > 1:
                    summary = recorder.get_summary()
                    new_devs = deviation_checker.check(
                        total_count=summary["total_events"], 
                        total_duration_sec=summary["total_duration_sec"], 
                        latest_event=None,
                        active_events=active_events_this_frame
                    )
                    if new_devs:
                        st.toast("🚨 Simultaneous Interventions Detected!", icon="🚨")
                
                # Draw rois and write frame to video even if no event triggered this specific frame
                states = [c.get_state() for c in classifiers]
                annotated_frame = roi_manager.draw_rois(frame, states)
                writer.write(annotated_frame)

                if frame_idx % 50 == 0:
                    pct = frame_idx / vi["total_frames"]
                    progress_bar.progress(min(pct, 1.0))
                    elapsed = time.time() - start_time
                    fps_val = frame_idx / elapsed if elapsed > 0 else 0
                    status_text.markdown(
                        f"Frame **{frame_idx:,}** / **{vi['total_frames']:,}** "
                        f"({pct*100:.1f}%) — ⚡ {fps_val:.1f} FPS — "
                        f"🔔 {len(all_events)} events")

            for clf in classifiers:
                event = clf.finalize(vi["total_frames"])
                if event:
                    recorder.record_event(event)
                    all_events.append(event)
                    summary = recorder.get_summary()
                    deviation_checker.check(
                        summary["total_events"], summary["total_duration_sec"], event)

            progress_bar.progress(1.0)
            total_time = time.time() - start_time
            recorder.save_all()
            deviation_checker.save_deviations()
            video.release()
            if writer is not None:
                writer.release()

            status_text.success(
                f"✅ Complete! {vi['total_frames']:,} frames in {total_time:.1f}s "
                f"({vi['total_frames']/total_time:.1f} FPS)")

            st.session_state["results"] = {
                "events": all_events,
                "summary": recorder.get_summary(),
                "deviations": deviation_checker.get_deviations(),
                "status": deviation_checker.get_status(
                    recorder.get_summary()["total_events"],
                    recorder.get_summary()["total_duration_sec"]),
                "motion_stats": [d.get_stats() for d in detectors],
                "video_info": vi, "processing_time": total_time,
            }
        except Exception as e:
            st.error(f"❌ Processing error: {e}")
            import traceback
            st.code(traceback.format_exc())


# ============================================================
# Results Display
# ============================================================
if "results" in st.session_state:
    results = st.session_state["results"]
    summary = results["summary"]
    status = results["status"]
    events = results["events"]
    deviations = results["deviations"]
    motion_stats = results.get("motion_stats", [])

    st.markdown("---")

    # Metrics
    st.markdown('<div class="section-header">📊 Summary Metrics</div>', unsafe_allow_html=True)
    m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)

    with m_col1:
        pct = status["count"]["percentage"]
        cls = "success" if pct <= 75 else "warning" if pct <= 85 else "alert"
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Total Interventions</div>
            <div class="metric-value {cls}">{summary['total_events']}</div>
            <div class="metric-label">Limit: {status['count']['limit']}</div>
        </div>""", unsafe_allow_html=True)

    with m_col2:
        pct = status["duration"]["percentage"]
        cls = "success" if pct <= 75 else "warning" if pct <= 85 else "alert"
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Total Duration</div>
            <div class="metric-value {cls}">{format_duration(summary['total_duration_sec'])}</div>
            <div class="metric-label">Limit: {format_duration(status['duration']['limit_sec'])}</div>
        </div>""", unsafe_allow_html=True)

    with m_col3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Count Usage</div>
            <div class="metric-value">{status['count']['percentage']:.0f}%</div>
            <div class="metric-label">of allowed limit</div>
        </div>""", unsafe_allow_html=True)

    with m_col4:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Duration Usage</div>
            <div class="metric-value">{status['duration']['percentage']:.0f}%</div>
            <div class="metric-label">of allowed limit</div>
        </div>""", unsafe_allow_html=True)

    with m_col5:
        avg_dur = summary['total_duration_sec'] / max(summary['total_events'], 1)
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Avg Duration</div>
            <div class="metric-value">{avg_dur:.1f}s</div>
            <div class="metric-label">per event</div>
        </div>""", unsafe_allow_html=True)

    with m_col6:
        vid_mins = max(results.get("video_info", {}).get("duration_sec", 0) / 60.0, 0.01)
        freq = summary['total_events'] / vid_mins
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Frequency</div>
            <div class="metric-value">{freq:.1f}</div>
            <div class="metric-label">events / min</div>
        </div>""", unsafe_allow_html=True)

    # Deviations
    if deviations:
        st.markdown("---")
        st.markdown('<div class="section-header">🚨 Deviation Alerts</div>', unsafe_allow_html=True)
        
        has_critical = any(d.get("severity") == "CRITICAL" for d in deviations)
        if has_critical or status["count"]["percentage"] > 85 or status["duration"]["percentage"] > 85:
            st.markdown("""
            <div class="critical-alarm">
                <h2>🚨 CRITICAL DEVIATION: REGULATORY LIMIT EXCEEDED 🚨</h2>
                <p style="color: #f0f6fc; margin-top: 10px;">Immediate QA Review Required. Validating standard operating procedures...</p>
            </div>
            """, unsafe_allow_html=True)
            
        for d in deviations:
            st.markdown(f"""<div class="deviation-alert">
                <strong>⚠️ {d['type']}</strong><br>{d['message']}<br>
                <small>Severity: {d.get('severity', 'N/A')}</small>
            </div>""", unsafe_allow_html=True)
    else:
        st.success("✅ All metrics within permissible limits.")

    # Output Video
    st.markdown("---")
    
    video_view = st.radio("Select Video View", ["Annotated Output File", "Live MJPEG Stream"])
    
    if video_view == "Annotated Output File":
        st.markdown('<div class="section-header">🎬 Annotated Video Output</div>', unsafe_allow_html=True)
        out_video_path = os.path.join(config.get("output", {}).get("directory", "output"), "output_annotated.mp4")
        if os.path.exists(out_video_path):
            st.video(out_video_path)
        else:
            st.info("Annotated video not found. Run analysis to generate.")
    else:
        st.markdown('<div class="section-header">📡 Live Video Stream (Flask)</div>', unsafe_allow_html=True)
        st.info("💡 Make sure `video_server.py` is running in the background on port 5000.")
        import streamlit.components.v1 as components
        components.iframe("http://localhost:5000/video_feed", width=800, height=600)

    # Event Timeline (HITL Classification)
    st.markdown("---")
    st.markdown('<div class="section-header">📋 Intervention Classification (HITL Review)</div>', unsafe_allow_html=True)
    st.info("💡 **Auditor Instructions**: Review the video clip for each event and select the specific Intervention Type.")
    if events:
        df = pd.DataFrame(events)
        
        # Add intervention_type column if it doesn't exist yet
        if "intervention_type" not in df.columns:
            df["intervention_type"] = "Unclassified"
            
        cols_to_show = ["event_id", "roi_label", "start_time", "duration_sec", "intervention_type", "clip_path"]
        avail = [c for c in cols_to_show if c in df.columns]
        
        if avail:
            df_d = df[avail].copy()
            # Rename for display
            display_cols = {"event_id": "#", "roi_label": "Port", "start_time": "Start Time", 
                            "duration_sec": "Duration (s)", "intervention_type": "Intervention Type",
                            "clip_path": "Video Clip Path"}
            df_d = df_d.rename(columns=display_cols)
            
            # Make it an editable table with a dropdown for the Type
            intervention_types = [
                "Unclassified", "Fallen Vial Recovery", "Stopper Adjustment", 
                "Environmental Monitoring", "Needle Replacement", 
                "Cleared Jam", "Other (SOP Exception)"
            ]
            
            edited_df = st.data_editor(
                df_d,
                column_config={
                    "Intervention Type": st.column_config.SelectboxColumn(
                        "Intervention Type",
                        help="Select the exact SOP intervention performed",
                        width="medium",
                        options=intervention_types,
                        required=True,
                    ),
                    "#": st.column_config.NumberColumn(disabled=True),
                    "Port": st.column_config.TextColumn(disabled=True),
                    "Start Time": st.column_config.TextColumn(disabled=True),
                    "Duration (s)": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Video Clip Path": st.column_config.TextColumn(disabled=True),
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Allow playing specific clips
            st.markdown("#### 🔍 Playback Specific Intervention")
            cols = st.columns(min(len(df), 4))
            for idx, row in df.head(8).iterrows():
                clip = row.get("clip_path")
                if clip and os.path.exists(clip):
                    with cols[idx % 4]:
                        st.markdown(f"**Event #{row['event_id']} ({row['roi_label']})**")
                        st.video(clip)
            
            # Save classifications back
            if st.button("💾 Save Audited Classifications", type="secondary"):
                out_dir = config.get("output", {}).get("directory", "output")
                
                # Update events list with new types
                for i, row in edited_df.iterrows():
                    events[i]["intervention_type"] = row["Intervention Type"]
                    
                json_path = os.path.join(out_dir, "events.json")
                with open(json_path, "w") as f:
                    json.dump(events, f, indent=2)
                st.success("Classifications saved to audit log file ✅")
                
    else:
        st.info("No intervention events detected.")

    # Per-Port + Motion
    st.markdown("---")
    col_p, col_m = st.columns(2)
    with col_p:
        st.markdown('<div class="section-header">📍 Per-Port Summary</div>', unsafe_allow_html=True)
        port_data = summary.get("events_by_port", {})
        if port_data:
            st.dataframe(pd.DataFrame([
                {"Port": k, "Events": v["count"], "Duration (s)": round(v["total_duration_sec"], 2)}
                for k, v in port_data.items()
            ]), use_container_width=True, hide_index=True)

    with col_m:
        st.markdown('<div class="section-header">📈 Motion Statistics</div>', unsafe_allow_html=True)
        if motion_stats:
            st.dataframe(pd.DataFrame([
                {"Port": f"Port {s['roi_index']+1}", "Moving": s["total_moving"],
                 "Static": s["total_static"],
                 "Motion %": round(s["total_moving"] / max(s["total_moving"] + s["total_static"], 1) * 100, 1)}
                for s in motion_stats
            ]), use_container_width=True, hide_index=True)

    # Snapshots
    st.markdown("---")
    st.markdown('<div class="section-header">📸 Event Snapshots</div>', unsafe_allow_html=True)
    snap_dir = os.path.join(config.get("output", {}).get("directory", "output"), "snapshots")
    if os.path.exists(snap_dir):
        snaps = sorted(f for f in os.listdir(snap_dir) if f.lower().endswith((".jpg", ".png")))
        if snaps:
            cols = st.columns(3)
            for idx, s in enumerate(snaps[:12]):
                with cols[idx % 3]:
                    st.image(Image.open(os.path.join(snap_dir, s)), caption=s, use_container_width=True)

    # Downloads
    st.markdown("---")
    st.markdown('<div class="section-header">📥 Download Results</div>', unsafe_allow_html=True)
    dl1, dl2, dl3 = st.columns(3)
    out_dir = config.get("output", {}).get("directory", "output")
    for col, fname, label, mime in [
        (dl1, "events.json", "📄 Events JSON", "application/json"),
        (dl2, "events.csv", "📊 Events CSV", "text/csv"),
        (dl3, "deviations.json", "⚠️ Deviations", "application/json"),
    ]:
        fpath = os.path.join(out_dir, fname)
        if os.path.exists(fpath):
            with col:
                with open(fpath, "r") as f:
                    st.download_button(label, f.read(), file_name=fname, mime=mime, use_container_width=True)

elif selected_video:
    out_dir = config.get("output", {}).get("directory", "output")
    if os.path.exists(os.path.join(out_dir, "events.json")):
        st.info("💡 Previous results found. Click **Run Analysis** or load previous results.")
        if st.button("📂 Load Previous Results"):
            try:
                with open(os.path.join(out_dir, "events.json"), "r") as f:
                    events = json.load(f)
                devs = []
                dp = os.path.join(out_dir, "deviations.json")
                if os.path.exists(dp):
                    with open(dp, "r") as f:
                        devs = json.load(f)
                tc, td = len(events), sum(e.get("duration_sec", 0) for e in events)
                
                # Simple attempt to find the video to calculate accurate frequency on load
                v_info = {"duration_sec": 0}
                if selected_video and os.path.exists(selected_video):
                    try:
                        v_in = VideoInput(selected_video)
                        v_info = v_in.get_info()
                        v_in.release()
                    except: pass
                
                dc = DeviationChecker(
                    max_intervention_count=limits_cfg.get("max_intervention_count", 20),
                    max_total_duration_sec=limits_cfg.get("max_total_duration_sec", 300.0))
                st.session_state["results"] = {
                    "events": events, "summary": {"total_events": tc, "total_duration_sec": td, "events_by_port": {}},
                    "deviations": devs, "status": dc.get_status(tc, td),
                    "motion_stats": [], "video_info": v_info, "processing_time": 0}
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.info("👈 Configure ROIs in the sidebar and click **Run Analysis**.")
else:
    st.info("👈 Select a video file in the sidebar to begin.")
