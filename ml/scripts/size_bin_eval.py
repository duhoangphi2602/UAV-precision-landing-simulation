import glob
import os
import cv2
import numpy as np
from ultralytics import YOLO

def box_iou(box1, box2):
    # box: [x_center, y_center, width, height] (normalized)
    # Convert to [x1, y1, x2, y2]
    b1_x1, b1_y1 = box1[0] - box1[2]/2, box1[1] - box1[3]/2
    b1_x2, b1_y2 = box1[0] + box1[2]/2, box1[1] + box1[3]/2

    b2_x1, b2_y1 = box2[0] - box2[2]/2, box2[1] - box2[3]/2
    b2_x2, b2_y2 = box2[0] + box2[2]/2, box2[1] + box2[3]/2

    inter_x1 = max(b1_x1, b2_x1)
    inter_y1 = max(b1_y1, b2_y1)
    inter_x2 = min(b1_x2, b2_x2)
    inter_y2 = min(b1_y2, b2_y2)

    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    b1_area = (b1_x2 - b1_x1) * (b1_y2 - b1_y1)
    b2_area = (b2_x2 - b2_x1) * (b2_y2 - b2_y1)

    union_area = b1_area + b2_area - inter_area
    if union_area == 0:
        return 0
    return inter_area / union_area

def evaluate_size_bins(model_path, images, labels_dir, conf_thres=0.25, iou_thres=0.5):
    model = YOLO(model_path)

    # Bins: tiny < 16, small 16-32, medium 32-96, large > 96
    bins = {
        "tiny": {"gt": 0, "tp": 0},
        "small": {"gt": 0, "tp": 0},
        "medium": {"gt": 0, "tp": 0},
        "large": {"gt": 0, "tp": 0}
    }

    for img_path in images:
        label_path = os.path.join(labels_dir, os.path.basename(img_path).replace(".jpg", ".txt"))
        if not os.path.exists(label_path):
            continue

        with open(label_path, "r") as f:
            lines = f.readlines()

        gt_boxes = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) == 5:
                # cls, x, y, w, h
                gt_boxes.append([float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])])

        if not gt_boxes:
            continue

        res = model.predict(img_path, imgsz=960, verbose=False, device=0, conf=conf_thres)[0]
        pred_boxes = []
        for box in res.boxes:
            # normalized cx, cy, w, h
            nbox = box.xywhn[0].cpu().numpy()
            pred_boxes.append(nbox)

        # Match GT to Pred
        for gt in gt_boxes:
            # size in pixels at 960
            max_dim = max(gt[2], gt[3]) * 960

            if max_dim < 16:
                bin_key = "tiny"
            elif max_dim < 32:
                bin_key = "small"
            elif max_dim < 96:
                bin_key = "medium"
            else:
                bin_key = "large"

            bins[bin_key]["gt"] += 1

            # Find best match
            best_iou = 0
            for pred in pred_boxes:
                iou = box_iou(gt, pred)
                if iou > best_iou:
                    best_iou = iou

            if best_iou >= iou_thres:
                bins[bin_key]["tp"] += 1

    results = {}
    for k, v in bins.items():
        recall = v["tp"] / v["gt"] if v["gt"] > 0 else 0
        results[k] = {"gt": v["gt"], "tp": v["tp"], "recall": recall}

    return results

if __name__ == "__main__":
    img_dir = "ml/datasets/derived/uavdt_vehicle_v1/test/images"
    lbl_dir = "ml/datasets/derived/uavdt_vehicle_v1/test/labels"

    images = list(glob.glob(img_dir + "/*.jpg"))[:200]  # Subset for speed

    model_A = "ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt"
    model_B = "ml/experiments/yolov8n_p2_uavdt_vehicle_960_v1/weights/best.pt"

    res_A = evaluate_size_bins(model_A, images, lbl_dir)
    res_B = evaluate_size_bins(model_B, images, lbl_dir)

    import json
    with open("ml/reports/size_bin_eval.json", "w") as f:
        json.dump({"Candidate_A": res_A, "Candidate_B": res_B}, f, indent=4)

    print(json.dumps({"Candidate_A": res_A, "Candidate_B": res_B}, indent=4))
