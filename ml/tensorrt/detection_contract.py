import cv2
import numpy as np
import torch
from pathlib import Path

def to_jsonable(obj):
    """Recursively convert objects to JSON serializable formats."""
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.generic, np.number)):
        return obj.item()
    elif isinstance(obj, torch.Tensor):
        return obj.detach().cpu().tolist()
    elif isinstance(obj, Path):
        return str(obj)
    return obj

# CONTRACT:
# - batch=1; input 960x960; RGB; float32; scale 1/255; NCHW; contiguous; static shape.

def preprocess(img_bgr, target_size=(960, 960)):
    """
    Preprocess image exactly matching Ultralytics YOLOv8 letterbox.
    Returns:
        blob: 1x3x960x960 float32 NCHW tensor
        ratio: resize ratio
        pad_w, pad_h: padding added
    """
    h, w = img_bgr.shape[:2]
    r = min(target_size[0] / h, target_size[1] / w)
    
    new_unpad = int(round(w * r)), int(round(h * r))
    dw, dh = target_size[1] - new_unpad[0], target_size[0] - new_unpad[1]
    
    # Ultralytics padding policy (divide padding equally to both sides)
    dw /= 2
    dh /= 2
    
    if (w, h) != new_unpad:
        img = cv2.resize(img_bgr, new_unpad, interpolation=cv2.INTER_LINEAR)
    else:
        img = img_bgr.copy()
        
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    
    # Value 114 is exact padding value used in ultralytics
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
    
    # Convert BGR to RGB, HWC to NCHW, uint8 to float32 [0.0, 1.0], contiguous memory
    img = img[:, :, ::-1].transpose(2, 0, 1)
    img = np.ascontiguousarray(img)
    blob = img.astype(np.float32) / 255.0
    blob = np.expand_dims(blob, axis=0)
    
    return blob, r, left, top

def xywh2xyxy(x):
    """Convert [x, y, w, h] to [x1, y1, x2, y2]."""
    y = np.copy(x)
    y[..., 0] = x[..., 0] - x[..., 2] / 2  # top left x
    y[..., 1] = x[..., 1] - x[..., 3] / 2  # top left y
    y[..., 2] = x[..., 0] + x[..., 2] / 2  # bottom right x
    y[..., 3] = x[..., 1] + x[..., 3] / 2  # bottom right y
    return y

def box_iou(box1, box2):
    # Vectorized IoU
    tl = np.maximum(box1[:, None, :2], box2[:, :2])
    br = np.minimum(box1[:, None, 2:], box2[:, 2:])
    hw = np.maximum(br - tl, 0)
    inter_area = hw[:, :, 0] * hw[:, :, 1]
    
    area1 = (box1[:, 2] - box1[:, 0]) * (box1[:, 3] - box1[:, 1])
    area2 = (box2[:, 2] - box2[:, 0]) * (box2[:, 3] - box2[:, 1])
    
    iou = inter_area / (area1[:, None] + area2 - inter_area)
    return iou

def postprocess(predictions, conf_thres=0.20, iou_thres=0.5, max_det=300):
    """
    Process YOLOv8 output [1, 5, 18900] -> [N, 6] (x1, y1, x2, y2, conf, cls)
    """
    # Remove batch dim and transpose to [18900, 5]
    preds = predictions[0].T
    
    # confidence = obj_conf (class 0)
    boxes = preds[:, :4]
    scores = preds[:, 4]
    
    # Filter by conf
    mask = scores > conf_thres
    boxes = boxes[mask]
    scores = scores[mask]
    
    if len(boxes) == 0:
        return np.zeros((0, 6))
        
    boxes = xywh2xyxy(boxes)
    
    # NMS
    order = scores.argsort()[::-1]
    keep = []
    
    while len(order) > 0 and len(keep) < max_det:
        i = order[0]
        keep.append(i)
        if len(order) == 1:
            break
        
        ious = box_iou(boxes[i:i+1], boxes[order[1:]])[0]
        inds = np.where(ious <= iou_thres)[0]
        order = order[inds + 1]
        
    keep = keep[:max_det]
    boxes = boxes[keep]
    scores = scores[keep]
    classes = np.zeros_like(scores) # only class 0
    
    result = np.column_stack((boxes, scores, classes))
    return result

def restore_coordinates(boxes, r, pad_w, pad_h):
    """
    Restore coordinates from 960x960 back to original image size
    """
    boxes[:, [0, 2]] -= pad_w  # x padding
    boxes[:, [1, 3]] -= pad_h  # y padding
    boxes[:, :4] /= r
    return boxes

if __name__ == "__main__":
    # Unit tests
    print("Running detection_contract unit tests...")
    
    # Test letterbox
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    blob, r, pad_w, pad_h = preprocess(img, (960, 960))
    assert blob.shape == (1, 3, 960, 960)
    assert r == 960 / 1280
    assert pad_w == 0 # width limits resize
    assert pad_h == (960 - 720 * r) / 2
    
    # Test empty det
    preds = np.zeros((1, 5, 18900))
    res = postprocess(preds)
    assert res.shape == (0, 6)
    
    # Test NMS
    preds = np.zeros((1, 5, 10))
    # Two identical boxes with different conf
    preds[0, 0, 0] = 100
    preds[0, 1, 0] = 100
    preds[0, 2, 0] = 50
    preds[0, 3, 0] = 50
    preds[0, 4, 0] = 0.9
    
    preds[0, 0, 1] = 100
    preds[0, 1, 1] = 100
    preds[0, 2, 1] = 50
    preds[0, 3, 1] = 50
    preds[0, 4, 1] = 0.8
    
    res = postprocess(preds)
    assert res.shape == (1, 6)
    assert res[0, 4] == 0.9
    
    print("All tests passed.")
