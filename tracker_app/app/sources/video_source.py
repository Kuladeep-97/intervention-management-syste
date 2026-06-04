import cv2
import time

class VideoSource:
    def __init__(self, path: str):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video file: {path}")
            
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps == 0 or self.fps != self.fps:
            self.fps = 30.0
            
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_time = 1.0 / self.fps

    def get_frames(self):
        """
        Generator that yields frames and simulates real-time camera timing.
        """
        while True:
            start_time = time.time()
            ret, frame = self.cap.read()
            
            if not ret:
                # Loop video for continuous testing
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
                
            yield frame

            # Simulate real-time by sleeping the remainder of the frame time
            elapsed = time.time() - start_time
            sleep_time = self.frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def release(self):
        self.cap.release()
