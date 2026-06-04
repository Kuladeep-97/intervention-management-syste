import cv2
from app.pipeline.onnx_engine import ONNXEngine

model = ONNXEngine('../best.onnx')
frame = cv2.imread('../frame_500.jpg')  # I know this file exists from earlier ls
results = model.predict(frame, imgsz=320, conf=0.15)[0]

overlay = frame.copy()
if results.masks is not None:
    for mask_xy in results.masks.xy:
        import numpy as np
        poly = np.array(mask_xy, dtype=np.int32)
        cv2.polylines(overlay, [poly], True, (0, 255, 0), 2)

cv2.imwrite('test_onnx_output.jpg', overlay)
