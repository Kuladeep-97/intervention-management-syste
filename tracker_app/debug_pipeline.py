import sys
sys.path.append("/home/dmin/IMS/tracker_app")
from app.sources.video_source import VideoSource
from app.pipeline.processor import PipelineProcessor

print("Loading processor...")
proc = PipelineProcessor(model_path="/home/dmin/IMS/best.pt", ports_json="/home/dmin/IMS/ports.json")
print("Processor loaded. Opening video...")
src = VideoSource("/home/dmin/IMS/input_stream/test_video.avi")
frame_gen = src.get_frames()

print("Getting first frame...")
frame = next(frame_gen)
print(f"First frame shape: {frame.shape}")

print("Processing stream...")
gen = proc.process_stream([frame], src.fps)

print("Waiting for processed frame...")
try:
    proc_frame, metrics = next(gen)
    print("Success! Processed frame shape:", proc_frame.shape)
except Exception as e:
    print("Error:", e)
