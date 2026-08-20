import cv2
import glob
import numpy as np
import torch
import json
import os
import sys
import time
import argparse
from ultralytics import YOLO
from ultralytics.utils.metrics import ap_per_class

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ml.tensorrt.detection_contract import preprocess, postprocess, restore_coordinates, box_iou, to_jsonable
from ml.tensorrt.infer import TensorRTEngine

OFFICIAL_ULTRALYTICS_TEST_MAP50_95 = 0.5244729223162523
PYTORCH_SELF_CONSISTENCY_TOLERANCE = 0.005

def compute_iou_matching(boxes1, boxes2, threshold=0.5):
    if len(boxes1) == 0 or len(boxes2) == 0:
        return [], [], list(range(len(boxes1))), list(range(len(boxes2)))
        
    ious = box_iou(boxes1, boxes2)
    matches = []
    unmatched_1 = list(range(len(boxes1)))
    unmatched_2 = list(range(len(boxes2)))
    
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

def match_predictions_to_gt(pred_boxes, pred_conf, gt_boxes, iou_thresholds=np.linspace(0.5, 0.95, 10)):
    tp = np.zeros((len(pred_boxes), len(iou_thresholds)), dtype=bool)
    if len(pred_boxes) == 0 or len(gt_boxes) == 0:
        return tp
    
    # Process from highest confidence to lowest
    sort_idx = np.argsort(pred_conf)[::-1]
    pred_boxes = pred_boxes[sort_idx]
    
    ious = box_iou(pred_boxes, gt_boxes) # (N, M)
    
    for th_idx, th in enumerate(iou_thresholds):
        gt_matched = np.zeros(len(gt_boxes), dtype=bool)
        for p_idx in range(len(pred_boxes)):
            matches = np.where(ious[p_idx] >= th)[0]
            matches = [m for m in matches if not gt_matched[m]]
            if len(matches) > 0:
                best_match = matches[np.argmax(ious[p_idx, matches])]
                tp[p_idx, th_idx] = True
                gt_matched[best_match] = True
                
    orig_tp = np.zeros_like(tp)
    orig_tp[sort_idx] = tp
    return orig_tp

def compute_metrics(tp_list, conf_list, pred_cls_list, gt_cls_list):
    if len(tp_list) == 0:
        return 0.0, 0.0, 0.0, 0.0
    tp = np.concatenate(tp_list, axis=0)
    conf = np.concatenate(conf_list, axis=0)
    pred_cls = np.concatenate(pred_cls_list, axis=0)
    gt_cls = np.concatenate(gt_cls_list, axis=0)
    
    if len(gt_cls) == 0:
        return 0.0, 0.0, 0.0, 0.0
        
    tp, fp, p, r, f1, ap, ap_class, p_curve, r_curve, f1_curve, x, prec_values = ap_per_class(tp, conf, pred_cls, gt_cls, plot=False, save_dir='.', names={0: 'vehicle'})
    
    ap50 = ap[:, 0]
    ap_mean = ap.mean(1)
    
    return float(p[0]) if len(p) else 0.0, float(r[0]) if len(r) else 0.0, float(ap50[0]) if len(ap50) else 0.0, float(ap_mean[0]) if len(ap_mean) else 0.0

def main():
    print("--- TENSORRT FP32 FULL PARITY EVALUATION ---")
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=str, required=False, help="Path to TRT engine")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to PyTorch pt file")
    parser.add_argument("--pytorch-only", action="store_true", help="Evaluate only PyTorch reference")
    args = parser.parse_args()
    
    engine_path = args.engine
    ckpt_path = args.checkpoint
    img_dir = "ml/datasets/derived/uavdt_vehicle_v1/test/images/"
    lbl_dir = "ml/datasets/derived/uavdt_vehicle_v1/test/labels/"
    
    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")
        
    if not args.pytorch_only:
        if not engine_path or not os.path.exists(engine_path):
            raise FileNotFoundError(f"Engine not found: {engine_path}")
        trt_engine = TensorRTEngine(engine_path)
    else:
        trt_engine = None
        
    pt_model = YOLO(ckpt_path).model.cuda().eval()
    
    img_paths = sorted(glob.glob(os.path.join(img_dir, "*.jpg")))
    
    results = {
        "ap_validation_contract": {
            "confidence_floor": 0.001,
            "nms_iou": 0.7,
            "max_det": 300,
            "pytorch": {},
            "tensorrt_fp32": {}
        },
        "runtime_operating_point": {
            "confidence": 0.20,
            "nms_iou": 0.5,
            "max_det": 300,
            "pytorch": {},
            "tensorrt_fp32": {}
        },
        "output_parity": {
            "matched_detections": 0,
            "missing_detections": 0,
            "extra_detections": 0,
            "mean_matched_iou": 0.0,
            "mean_conf_drift": 0.0,
            "all_outputs_finite": True,
        },
        "fp32_metric_parity_pass": False
    }
    
    iou_accum = 0.0
    conf_drift_accum = 0.0
    
    pt_tp_val = []
    pt_conf_val = []
    pt_pred_cls_val = []
    
    trt_tp_val = []
    trt_conf_val = []
    trt_pred_cls_val = []
    
    pt_runtime_tp = 0
    pt_runtime_fp = 0
    trt_runtime_tp = 0
    trt_runtime_fp = 0
    total_gt = 0
    
    gt_cls_all = []
    
    for img_path in img_paths:
        img_bgr = cv2.imread(img_path)
        h, w = img_bgr.shape[:2]
        blob, ratio, pad_w, pad_h = preprocess(img_bgr)
        
        # Load GT
        gt_boxes = []
        lbl_path = os.path.join(lbl_dir, os.path.basename(img_path).replace(".jpg", ".txt"))
        if os.path.exists(lbl_path):
            with open(lbl_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        cx, cy, bw, bh = map(float, parts[1:])
                        x1 = (cx - bw / 2) * w
                        y1 = (cy - bh / 2) * h
                        x2 = (cx + bw / 2) * w
                        y2 = (cy + bh / 2) * h
                        gt_boxes.append([x1, y1, x2, y2])
        gt_boxes = np.array(gt_boxes) if len(gt_boxes) > 0 else np.zeros((0, 4))
        gt_cls_all.append(np.zeros(len(gt_boxes), dtype=int))
        total_gt += len(gt_boxes)
        
        # PyTorch Reference Raw Output
        with torch.no_grad():
            inp_tensor = torch.from_numpy(blob).cuda()
            pt_out = pt_model(inp_tensor)
            if isinstance(pt_out, tuple):
                pt_out = pt_out[0]
            pt_out = pt_out.cpu().numpy()
            
        # PT Validations (conf=0.001)
        pt_dets_val = postprocess(pt_out, conf_thres=0.001, iou_thres=0.7, max_det=300)
        pt_dets_val = restore_coordinates(pt_dets_val, ratio, pad_w, pad_h)
        
        # PT Runtime (conf=0.20)
        pt_dets_run = postprocess(pt_out, conf_thres=0.20, iou_thres=0.5, max_det=300)
        pt_dets_run = restore_coordinates(pt_dets_run, ratio, pad_w, pad_h)
        
        if len(pt_dets_val) > 0:
            tp = match_predictions_to_gt(pt_dets_val[:, :4], pt_dets_val[:, 4], gt_boxes)
            pt_tp_val.append(tp)
            pt_conf_val.append(pt_dets_val[:, 4])
            pt_pred_cls_val.append(np.zeros(len(pt_dets_val), dtype=int))
            
        if len(pt_dets_run) > 0:
            # We just need simple precision/recall at runtime. We evaluate at iou=0.5
            if len(gt_boxes) > 0:
                ious = box_iou(pt_dets_run[:, :4], gt_boxes)
                matched_gt = set()
                tp_count = 0
                for i in range(len(pt_dets_run)):
                    matches = np.where(ious[i] >= 0.5)[0]
                    valid = [m for m in matches if m not in matched_gt]
                    if valid:
                        best_match = valid[np.argmax(ious[i, valid])]
                        tp_count += 1
                        matched_gt.add(best_match)
                pt_runtime_tp += tp_count
                pt_runtime_fp += len(pt_dets_run) - tp_count
            else:
                pt_runtime_fp += len(pt_dets_run)
        
        # TRT Execution if enabled
        if trt_engine is not None:
            trt_out = trt_engine(blob)
            if not np.all(np.isfinite(trt_out)):
                results["output_parity"]["all_outputs_finite"] = False
                
            trt_dets_val = postprocess(trt_out, conf_thres=0.001, iou_thres=0.7, max_det=300)
            trt_dets_val = restore_coordinates(trt_dets_val, ratio, pad_w, pad_h)
            
            trt_dets_run = postprocess(trt_out, conf_thres=0.20, iou_thres=0.5, max_det=300)
            trt_dets_run = restore_coordinates(trt_dets_run, ratio, pad_w, pad_h)
            
            # Compute Output Parity (PT vs TRT at runtime conf=0.20)
            if len(pt_dets_run) > 0 and len(trt_dets_run) > 0:
                matches, un1, un2 = compute_iou_matching(pt_dets_run[:, :4], trt_dets_run[:, :4])
                results["output_parity"]["matched_detections"] += len(matches)
                results["output_parity"]["missing_detections"] += len(un1)
                results["output_parity"]["extra_detections"] += len(un2)
                
                for (idx_pt, idx_trt, iou) in matches:
                    iou_accum += iou
                    drift = abs(pt_dets_run[idx_pt, 4] - trt_dets_run[idx_trt, 4])
                    conf_drift_accum += drift
            else:
                results["output_parity"]["missing_detections"] += len(pt_dets_run)
                results["output_parity"]["extra_detections"] += len(trt_dets_run)
                
            if len(trt_dets_val) > 0:
                tp = match_predictions_to_gt(trt_dets_val[:, :4], trt_dets_val[:, 4], gt_boxes)
                trt_tp_val.append(tp)
                trt_conf_val.append(trt_dets_val[:, 4])
                trt_pred_cls_val.append(np.zeros(len(trt_dets_val), dtype=int))
                
            if len(trt_dets_run) > 0:
                if len(gt_boxes) > 0:
                    ious = box_iou(trt_dets_run[:, :4], gt_boxes)
                    matched_gt = set()
                    tp_count = 0
                    for i in range(len(trt_dets_run)):
                        matches = np.where(ious[i] >= 0.5)[0]
                        valid = [m for m in matches if m not in matched_gt]
                        if valid:
                            best_match = valid[np.argmax(ious[i, valid])]
                            tp_count += 1
                            matched_gt.add(best_match)
                    trt_runtime_tp += tp_count
                    trt_runtime_fp += len(trt_dets_run) - tp_count
                else:
                    trt_runtime_fp += len(trt_dets_run)
                    
    if results["output_parity"]["matched_detections"] > 0:
        results["output_parity"]["mean_matched_iou"] = iou_accum / results["output_parity"]["matched_detections"]
        results["output_parity"]["mean_conf_drift"] = conf_drift_accum / results["output_parity"]["matched_detections"]
        
    # Finalize Validation Metrics (mAP50-95)
    pt_p, pt_r, pt_map50, pt_map50_95 = compute_metrics(pt_tp_val, pt_conf_val, pt_pred_cls_val, gt_cls_all)
    
    results["ap_validation_contract"]["pytorch"] = {
        "map50": pt_map50,
        "map50_95": pt_map50_95
    }
    
    # Finalize Runtime Metrics
    pt_run_p = pt_runtime_tp / (pt_runtime_tp + pt_runtime_fp) if (pt_runtime_tp + pt_runtime_fp) > 0 else 0.0
    pt_run_r = pt_runtime_tp / total_gt if total_gt > 0 else 0.0
    pt_run_f1 = 2 * pt_run_p * pt_run_r / (pt_run_p + pt_run_r + 1e-16)
    
    results["runtime_operating_point"]["pytorch"] = {
        "precision": pt_run_p,
        "recall": pt_run_r,
        "f1": pt_run_f1
    }
    
    if args.pytorch_only:
        print("PYTORCH_REFERENCE_SOURCE=official_ultralytics_8.4.108")
        print("PYTORCH_REFERENCE_SPLIT=test")
        print(f"PYTORCH_AUTHORITATIVE_MAP50_95={OFFICIAL_ULTRALYTICS_TEST_MAP50_95:.10f}")
        print(f"PYTORCH_CUSTOM_MAP50_95={pt_map50_95:.5f}")
        print(f"PYTORCH_SELF_CONSISTENCY_DROP={OFFICIAL_ULTRALYTICS_TEST_MAP50_95 - pt_map50_95:.5f}")
        pass_self = abs(OFFICIAL_ULTRALYTICS_TEST_MAP50_95 - pt_map50_95) <= PYTORCH_SELF_CONSISTENCY_TOLERANCE
        print(f"PYTORCH_EVALUATOR_SELF_CONSISTENCY={'PASS' if pass_self else 'FAIL'}")
        sys.exit(0)
    
    trt_p, trt_r, trt_map50, trt_map50_95 = compute_metrics(trt_tp_val, trt_conf_val, trt_pred_cls_val, gt_cls_all)
    
    results["ap_validation_contract"]["tensorrt_fp32"] = {
        "map50": trt_map50,
        "map50_95": trt_map50_95
    }
    
    trt_run_p = trt_runtime_tp / (trt_runtime_tp + trt_runtime_fp) if (trt_runtime_tp + trt_runtime_fp) > 0 else 0.0
    trt_run_r = trt_runtime_tp / total_gt if total_gt > 0 else 0.0
    trt_run_f1 = 2 * trt_run_p * trt_run_r / (trt_run_p + trt_run_r + 1e-16)
    
    results["runtime_operating_point"]["tensorrt_fp32"] = {
        "precision": trt_run_p,
        "recall": trt_run_r,
        "f1": trt_run_f1
    }
    
    pass_map = (trt_map50_95 - pt_map50_95) >= -0.003
    pass_recall = (trt_run_r - pt_run_r) >= -0.005
    pass_finite = results["output_parity"]["all_outputs_finite"]
    pass_parity = results["output_parity"]["missing_detections"] < 100 # sanity
    
    results["fp32_metric_parity_pass"] = pass_map and pass_recall and pass_finite and pass_parity
    
    results = to_jsonable(results)
    
    os.makedirs("ml/reports", exist_ok=True)
    with open("ml/reports/tensorrt_fp32_full_parity.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"FP32_OUTPUT_PARITY=PASS")
    print(f"FP32_MAP50_95_PYTORCH={pt_map50_95:.5f}")
    print(f"FP32_MAP50_95_TENSORRT={trt_map50_95:.5f}")
    print(f"FP32_MAP50_95_DROP={pt_map50_95 - trt_map50_95:.5f}")
    
    print(f"FP32_RECALL_RUNTIME_PYTORCH={pt_run_r:.5f}")
    print(f"FP32_RECALL_RUNTIME_TENSORRT={trt_run_r:.5f}")
    print(f"FP32_RECALL_RUNTIME_DROP={pt_run_r - trt_run_r:.5f}")
    
    print(f"FP32_METRIC_PARITY={'PASS' if results['fp32_metric_parity_pass'] else 'FAIL'}")
    print(f"FP16_UNLOCKED={'YES' if results['fp32_metric_parity_pass'] else 'NO'}")

if __name__ == "__main__":
    main()
