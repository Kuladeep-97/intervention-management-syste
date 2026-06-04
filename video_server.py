import os
import cv2
import time
import yaml
from flask import Flask, Response
from src.video_input import VideoInput
from src.roi_manager import ROIManager
from src.motion_detector import MotionDetector

app = Flask(__name__)

# Basic streaming configurator
VIDEO = "Camera02~21_Dec_2025~00_39_43~00_48_09~HDD~00.mp4"
CONFIG_PATH = "config.yaml"

def generate_frames():
    """Generator function that yields JPEG frames."""
    
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
        
    roi_configs = config.get("rois", [])
    
    # Initialize components
    video = VideoInput(VIDEO)
    vi = video.get_info()
    
    roi_manager = ROIManager()
    roi_manager.set_rois(roi_configs)
    roi_manager.build_exclusive_masks(vi["height"], vi["width"])
    
    detectors = [
        MotionDetector(
            roi_index=i, 
            ssim_threshold=config["detection"].get("ssim_threshold", 0.08),
            ema_beta=config["detection"].get("ema_beta", 0.2), 
            history_size=config["detection"].get("history_size", 25),
            min_motion_votes=config["detection"].get("min_motion_votes", 10),
            resize_factor=config["detection"].get("resize_factor", 0.5),
        ) for i in range(len(roi_configs))
    ]

    for frame_idx, frame in video.iter_frames():
        # Process frame
        states = []
        for i in range(len(roi_configs)):
            roi_crop = roi_manager.get_roi_crop(frame, i)
            motion_result = detectors[i].process_frame(roi_crop)
            
            # Simple state mapping for visualization without classifiers
            state = {
                "label": "MOVING" if motion_result["is_active"] else "STATIC",
                "color": (0, 0, 255) if motion_result["is_active"] else (0, 255, 0),
                "thickness": 3 if motion_result["is_active"] else 2,
                "score": motion_result.get("smoothed_score", 0.0),
                "is_active": motion_result["is_active"]
            }
            states.append(state)

        # Draw ROIs
        annotated_frame = roi_manager.draw_rois(frame, states)
        
        # Add basic info
        cv2.putText(annotated_frame, f"LIVE STREAM (Frame {frame_idx})", 
                   (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, 
                   (255, 255, 255), 2)
        
        # Encode to JPEG
        ret, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        
        # Yield in multipart content format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
               
        # Throttle loop to match roughly actual playback FPS (optional, to avoid fast-forward)
        # time.sleep(1.0 / vi["fps"])

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
                    
@app.route('/')
def index():
    return "Stream Server Running. Feed is at /video_feed"

if __name__ == '__main__':
    # Run the Flask app on port 5000
    app.run(host='0.0.0.0', port=5000, threaded=True)
