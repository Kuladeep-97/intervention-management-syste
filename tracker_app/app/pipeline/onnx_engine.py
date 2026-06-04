import cv2
import numpy as np
import onnxruntime as ort

def letterbox(im, new_shape=(320, 320), color=(114, 114, 114)):
    # Resize and pad image while meeting stride-multiple constraints
    shape = im.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

    # Compute padding
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding

    dw /= 2  # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad:  # resize
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
    return im, (r, r), (dw, dh)

def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -100, 100)))

class _Masks:
    def __init__(self, xy):
        self.xy = xy

class ONNXResults:
    def __init__(self, masks_xy):
        self.masks = _Masks(masks_xy) if masks_xy else None

class ONNXEngine:
    def __init__(self, model_path: str, conf_thres: float = 0.15, iou_thres: float = 0.45):
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres

    def predict(self, frame, imgsz=320, **kwargs):
        # 1. Preprocess
        img, ratio, (dw, dh) = letterbox(frame, new_shape=imgsz)
        # BGR to RGB
        blob = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        blob = blob.transpose((2, 0, 1))  # HWC to CHW
        blob = np.ascontiguousarray(blob)
        blob = blob.astype(np.float32) / 255.0
        blob = np.expand_dims(blob, axis=0)
        
        # 2. Inference
        outputs = self.session.run(None, {self.input_name: blob})
        
        # YOLOv8 Seg outputs:
        # outputs[0]: shape [1, 37, 2100] (boxes + scores + mask_coefs)
        # outputs[1]: shape [1, 32, 80, 80] (mask prototypes)
        
        if len(outputs) == 2:
            preds = outputs[0][0]  # [37, 2100]
            protos = outputs[1][0] # [32, 80, 80]
        else:
            preds = outputs[0][0]
            protos = None
            
        preds = preds.T  # [2100, 37]
        
        # 3. Postprocess
        # boxes = preds[:, :4]
        # confs = preds[:, 4] (assuming 1 class)
        # mask_coefs = preds[:, 5:]
        
        boxes = preds[:, :4]
        scores = preds[:, 4]
        
        # Read conf threshold from kwargs
        conf = kwargs.get('conf', self.conf_thres)
            
        # Apply confidence threshold
        mask = scores > conf
        boxes = boxes[mask]
        scores = scores[mask]
        
        if protos is not None:
            mask_coefs = preds[mask, 5:]
        
        if len(boxes) == 0:
            return [ONNXResults([])]
            
        # xywh to xyxy
        x, y, w, h = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        boxes_xyxy = np.column_stack([x - w/2, y - h/2, x + w/2, y + h/2])
        
        # NMS
        # cv2.dnn.NMSBoxes expects boxes as [x_top_left, y_top_left, width, height]
        boxes_for_nms = np.column_stack([x - w/2, y - h/2, w, h]).tolist()
        indices = cv2.dnn.NMSBoxes(boxes_for_nms, scores.tolist(), conf, self.iou_thres)
        
        if len(indices) == 0:
            return [ONNXResults([])]
            
        indices = indices.flatten()
        det_boxes = boxes_xyxy[indices]
        det_scores = scores[indices]
        
        masks_xy = []
        if protos is not None:
            det_mask_coefs = mask_coefs[indices]
            
            # [N, 32] @ [32, 80*80] -> [N, 6400]
            c, mh, mw = protos.shape
            protos_flat = protos.reshape(c, -1)
            mask_logits = det_mask_coefs @ protos_flat
            masks_sig = sigmoid(mask_logits)
            masks_sig = masks_sig.reshape(-1, mh, mw)
            
            # Process each mask
            for i in range(len(det_boxes)):
                box = det_boxes[i]
                mask = masks_sig[i]
                
                # Scale mask up to imgsz
                mask = cv2.resize(mask, (imgsz, imgsz), interpolation=cv2.INTER_LINEAR)
                mask = mask > 0.5
                
                # Crop mask to bbox
                x1, y1, x2, y2 = map(int, box)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(imgsz, x2), min(imgsz, y2)
                
                cropped = np.zeros_like(mask)
                cropped[y1:y2, x1:x2] = mask[y1:y2, x1:x2]
                
                # Scale back to original image shape
                inv_mask = np.zeros((imgsz, imgsz), dtype=np.uint8)
                inv_mask[cropped] = 255
                
                # Remove padding and resize to original
                orig_h, orig_w = frame.shape[:2]
                inv_mask = inv_mask[int(dh):int(imgsz-dh), int(dw):int(imgsz-dw)]
                inv_mask = cv2.resize(inv_mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
                
                contours, _ = cv2.findContours(inv_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if len(contours) > 0:
                    # Find largest contour
                    contour = max(contours, key=cv2.contourArea)
                    masks_xy.append(contour.reshape(-1, 2).tolist())
        
        return [ONNXResults(masks_xy)]
