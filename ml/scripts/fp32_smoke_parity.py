import cv2
import glob
import numpy as np
import torch
import json
import os
from ultralytics import YOLO

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ml.tensorrt.detection_contract import preprocess, postprocess, restore_coordinates, box_iou, to_jsonable
from ml.tensorrt.infer import TensorRTEngine

def compute_iou_matching(boxes1, boxes2, threshold=0.5):
    """Greedy matching of boxes"""
    if len(boxes1) == 0 or len(boxes2) == 0:
        return [], [], list(range(len(boxes1))), list(range(len(boxes2)))
        
    ious = box_iou(boxes1, boxes2)
    
    matches = []
    unmatched_1 = list(range(len(boxes1)))
    unmatched_2 = list(range(len(boxes2)))
    
    # Greedy assign
    for i in range(len(boxes1)):
        best_j = -1
        best_iou = threshold
        for j in unmatched_2:
            if ious[i, j] > best_iou:
                best_iou = ious[i, j]
                best_j = j
                
        if best_j != -1:
            matches.append((i, best_j, best_iou))
            unmatched_1.remove(i)
            unmatched_2.remove(best_j)
            
    return matches, unmatched_1, unmatched_2

import argparse

def main():
    print("--- TENSORRT FP32 SMOKE PARITY ---")
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=str, required=True, help="Path to TRT engine")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to PyTorch pt file")
    args = parser.parse_args()
    
    engine_path = args.engine
    ckpt_path = args.checkpoint
    img_dir = "ml/datasets/derived/uavdt_vehicle_v1/test/images/"
    
    if not os.path.exists(engine_path):
        raise FileNotFoundError(f"Engine not found: {engine_path}")
    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")
        
    trt_engine = TensorRTEngine(engine_path)
    print("TRT Engine loaded.")
    
    pt_model = YOLO(ckpt_path).model.cuda().eval()
    print("PyTorch Model loaded.")
    
    img_paths = sorted(glob.glob(os.path.join(img_dir, "*.jpg")))[:10]
    
    results = {
        "images_tested": len(img_paths),
        "total_pt_detections": 0,
        "total_trt_detections": 0,
        "matched_detections": 0,
        "missing_detections": 0,
        "extra_detections": 0,
        "mean_matched_iou": 0.0,
        "min_matched_iou": 1.0,
        "mean_conf_drift": 0.0,
        "max_conf_drift": 0.0,
        "all_outputs_finite": True,
        "status": "PASS"
    }
    
    iou_accum = 0.0
    conf_drift_accum = 0.0
    
    for img_path in img_paths:
        img_bgr = cv2.imread(img_path)
        blob, ratio, pad_w, pad_h = preprocess(img_bgr)
        
        # PyTorch Reference
        with torch.no_grad():
            inp_tensor = torch.from_numpy(blob).cuda()
            pt_out = pt_model(inp_tensor)
            if isinstance(pt_out, tuple):
                pt_out = pt_out[0]
            pt_out = pt_out.cpu().numpy()
            
        pt_dets = postprocess(pt_out)
        pt_dets = restore_coordinates(pt_dets, ratio, pad_w, pad_h)
        
        # TRT Execution
        trt_out = trt_engine(blob)
        if not np.all(np.isfinite(trt_out)):
            results["all_outputs_finite"] = False
            
        trt_dets = postprocess(trt_out)
        trt_dets = restore_coordinates(trt_dets, ratio, pad_w, pad_h)
        
        results["total_pt_detections"] += len(pt_dets)
        results["total_trt_detections"] += len(trt_dets)
        
        # Match boxes
        if len(pt_dets) > 0 and len(trt_dets) > 0:
            matches, un1, un2 = compute_iou_matching(pt_dets[:, :4], trt_dets[:, :4])
            results["matched_detections"] += len(matches)
            results["missing_detections"] += len(un1)
            results["extra_detections"] += len(un2)
            
            for (idx_pt, idx_trt, iou) in matches:
                iou_accum += iou
                results["min_matched_iou"] = min(results["min_matched_iou"], float(iou))
                
                conf_pt = pt_dets[idx_pt, 4]
                conf_trt = trt_dets[idx_trt, 4]
                drift = abs(conf_pt - conf_trt)
                conf_drift_accum += drift
                results["max_conf_drift"] = max(results["max_conf_drift"], float(drift))
        else:
            results["missing_detections"] += len(pt_dets)
            results["extra_detections"] += len(trt_dets)

    if results["matched_detections"] > 0:
        results["mean_matched_iou"] = iou_accum / results["matched_detections"]
        results["mean_conf_drift"] = conf_drift_accum / results["matched_detections"]
        
    # Evaluate Pass/Fail
    if not results["all_outputs_finite"]:
        results["status"] = "FAIL (Non-finite outputs)"
    elif results["mean_matched_iou"] < 0.98 and results["matched_detections"] > 0:
        results["status"] = "FAIL (Mean IoU < 0.98)"
    elif results["mean_conf_drift"] > 0.01 and results["matched_detections"] > 0:
        results["status"] = "FAIL (Mean Confidence Drift > 0.01)"
    elif results["missing_detections"] > results["total_pt_detections"] * 0.1: # simple systemic check
        results["status"] = "FAIL (Systematic missing detections)"
        
    results = to_jsonable(results)
    print(json.dumps(results, indent=4))
    
    os.makedirs("ml/reports", exist_ok=True)
    report_path = "ml/reports/tensorrt_fp32_smoke_parity.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=4)
    print(f"Report saved to {report_path}")
    
    if results["status"] != "PASS":
        sys.exit(1)

if __name__ == "__main__":
    main()
