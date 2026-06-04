"""
Pipeline Runner (CLI)
=====================
Orchestrates the full video analytics pipeline:
Video → ROI → Motion Detection → Event Classification → Recording → Deviations
"""

import os
import sys
import time
import argparse
import yaml
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.video_input import VideoInput
from src.roi_manager import ROIManager
from src.motion_detector import MotionDetector
from src.event_classifier import EventClassifier
from src.event_recorder import EventRecorder
from src.deviation_checker import DeviationChecker


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_pipeline(
    video_path: str,
    config_path: str = "config.yaml",
    progress_callback=None,
):
    """
    Run the complete video analytics pipeline.

    Args:
        video_path: Path to input video file
        config_path: Path to config YAML
        progress_callback: Optional callable(frame_idx, total_frames, events_so_far)

    Returns:
        dict with results: events, deviations, summary, video_info
    """
    # ---- Load config ----
    config = load_config(config_path)

    detection_cfg = config.get("detection", {})
    events_cfg = config.get("events", {})
    limits_cfg = config.get("limits", {})
    output_cfg = config.get("output", {})

    output_dir = output_cfg.get("directory", "output")

    # ---- Video Input ----
    print(f"📹 Loading video: {video_path}")
    video = VideoInput(video_path)
    info = video.get_info()
    print(f"   Resolution: {info['width']}x{info['height']}")
    print(f"   FPS: {info['fps']:.2f}")
    print(f"   Total frames: {info['total_frames']}")
    print(f"   Duration: {info['duration_sec']:.1f}s")

    # ---- ROI Manager ----
    roi_manager = ROIManager(config_path)
    roi_manager.load_from_config()

    if not roi_manager.has_rois():
        print("\n⚠️  No ROIs defined in config.yaml!")
        print("   Please define ROIs in config.yaml or use the Streamlit dashboard.")
        return None

    print(f"\n📍 Loaded {len(roi_manager.rois)} ROI(s)")

    # Validate ROIs
    warnings = roi_manager.validate_rois()
    for w in warnings:
        print(f"   {w}")

    # Build exclusive masks
    roi_manager.build_exclusive_masks(info["height"], info["width"])
    print("   ✅ Exclusive masks built (overlap prevention active)")

    # ---- Initialize detectors ----
    detectors = []
    for i in range(len(roi_manager.rois)):
        detector = MotionDetector(
            roi_index=i,
            ssim_threshold=detection_cfg.get("ssim_threshold", 0.08),
            ema_beta=detection_cfg.get("ema_beta", 0.2),
            history_size=detection_cfg.get("history_size", 25),
            min_motion_votes=detection_cfg.get("min_motion_votes", 10),
            resize_factor=detection_cfg.get("resize_factor", 0.5),
        )
        detectors.append(detector)

    # ---- Initialize classifiers ----
    classifiers = []
    for i in range(len(roi_manager.rois)):
        classifier = EventClassifier(
            roi_index=i,
            fps=info["fps"],
            min_active_frames=events_cfg.get("min_active_frames", 5),
            cooldown_frames=events_cfg.get("cooldown_frames", 15),
            min_intervention_duration_sec=events_cfg.get("min_intervention_duration_sec", 2.0),
        )
        classifiers.append(classifier)

    # ---- Event Recorder ----
    recorder = EventRecorder(
        output_dir=output_dir,
        save_snapshots=output_cfg.get("save_snapshots", True),
        snapshot_format=output_cfg.get("snapshot_format", "jpg"),
        snapshot_quality=output_cfg.get("snapshot_quality", 90),
    )

    # ---- Deviation Checker ----
    deviation_checker = DeviationChecker(
        max_intervention_count=limits_cfg.get("max_intervention_count", 20),
        max_total_duration_sec=limits_cfg.get("max_total_duration_sec", 300.0),
        output_dir=output_dir,
    )

    # ---- Process video ----
    print(f"\n🔄 Processing video...")
    start_time = time.time()
    all_events = []

    for frame_idx, frame in video.iter_frames():
        # Process each ROI
        for i in range(len(roi_manager.rois)):
            # Extract ROI crop with exclusive masking
            roi_crop = roi_manager.get_roi_crop(frame, i)

            # Detect motion
            motion_result = detectors[i].process_frame(roi_crop)

            # Classify event
            event = classifiers[i].process_frame(frame_idx, motion_result["is_active"])

            # Record completed event
            if event is not None:
                # Draw ROIs on frame for snapshot
                states = [c.get_state() for c in classifiers]
                annotated = roi_manager.draw_rois(frame, states)
                recorder.record_event(event, annotated)
                all_events.append(event)

                # Check for deviations
                summary = recorder.get_summary()
                deviation_checker.check(
                    total_count=summary["total_events"],
                    total_duration_sec=summary["total_duration_sec"],
                    latest_event=event,
                )

                print(f"   🔔 Event #{event['event_id']} @ Port {event['roi_index']+1}: "
                      f"{event['start_time']} → {event['end_time']} "
                      f"({event['duration_sec']:.1f}s)")

        # Progress reporting
        if frame_idx % 100 == 0:
            elapsed = time.time() - start_time
            pct = (frame_idx / info["total_frames"]) * 100
            fps = frame_idx / elapsed if elapsed > 0 else 0
            if progress_callback:
                progress_callback(frame_idx, info["total_frames"], all_events)
            else:
                print(f"   Frame {frame_idx}/{info['total_frames']} "
                      f"({pct:.1f}%) | {fps:.1f} FPS")

    # ---- Finalize open events ----
    for i, classifier in enumerate(classifiers):
        event = classifier.finalize(info["total_frames"])
        if event is not None:
            recorder.record_event(event)
            all_events.append(event)

            summary = recorder.get_summary()
            deviation_checker.check(
                total_count=summary["total_events"],
                total_duration_sec=summary["total_duration_sec"],
                latest_event=event,
            )

    # ---- Save outputs ----
    json_path, csv_path = recorder.save_all()
    dev_path = deviation_checker.save_deviations()

    total_time = time.time() - start_time
    avg_fps = info["total_frames"] / total_time if total_time > 0 else 0

    # ---- Summary ----
    summary = recorder.get_summary()
    status = deviation_checker.get_status(
        summary["total_events"],
        summary["total_duration_sec"],
    )

    print(f"\n{'='*50}")
    print(f"✅ Processing complete!")
    print(f"   Total time: {total_time:.1f}s | Avg FPS: {avg_fps:.1f}")
    print(f"\n📊 Summary")
    print(f"   Total interventions: {summary['total_events']}")
    print(f"   Total duration: {summary['total_duration_sec']:.1f}s")

    for label, port_data in summary.get("events_by_port", {}).items():
        print(f"   {label}: {port_data['count']} events, "
              f"{port_data['total_duration_sec']:.1f}s total")

    # Motion statistics
    print(f"\n📈 Motion Statistics (per port)")
    for det in detectors:
        stats = det.get_stats()
        total = stats["total_moving"] + stats["total_static"]
        pct = (stats["total_moving"] / total * 100) if total > 0 else 0
        print(f"   Port {stats['roi_index']+1}: "
              f"{stats['total_moving']} MOVING / {stats['total_static']} STATIC "
              f"({pct:.1f}% motion)")

    if deviation_checker.has_deviations():
        print(f"\n⚠️  DEVIATIONS DETECTED:")
        for d in deviation_checker.get_deviations():
            print(f"   🚨 {d['message']}")
    else:
        print(f"\n✅ No deviations — within limits")

    print(f"\n📁 Output files:")
    print(f"   Events JSON: {json_path}")
    print(f"   Events CSV:  {csv_path}")
    print(f"   Deviations:  {dev_path}")
    print(f"   Snapshots:   {os.path.join(output_dir, 'snapshots')}/")

    # Release
    video.release()

    return {
        "events": all_events,
        "summary": summary,
        "deviations": deviation_checker.get_deviations(),
        "status": status,
        "video_info": info,
        "processing_time_sec": round(total_time, 2),
        "avg_fps": round(avg_fps, 2),
        "motion_stats": [d.get_stats() for d in detectors],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Glove-Port Video Analytics Pipeline"
    )
    parser.add_argument(
        "--video", "-v",
        required=True,
        help="Path to input video file",
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to config YAML (default: config.yaml)",
    )
    args = parser.parse_args()

    result = run_pipeline(args.video, args.config)

    if result is None:
        sys.exit(1)

    # Save full result as JSON
    result_path = os.path.join("output", "pipeline_result.json")
    # Events contain numpy types sometimes, so convert
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n   Full result: {result_path}")


if __name__ == "__main__":
    main()
