import json
from ultralytics import YOLO
import itertools

def sweep_operating_points():
    model = YOLO("ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt")

    confs = [0.15, 0.20, 0.25, 0.30, 0.40]
    ious = [0.50, 0.60, 0.70]
    max_dets = [300, 600, 1000]

    results = []

    # We use validation split as requested
    for conf, iou, max_det in itertools.product(confs, ious, max_dets):
        print(f"Sweeping conf={conf}, iou={iou}, max_det={max_det}...")

        # YOLO val handles the thresholding and NMS internally if provided
        # But wait, YOLO val doesn't strictly allow overriding conf/iou in all versions easily via kwargs,
        # Actually it does in ultralytics 8+.
        metrics = model.val(
            data="ml/configs/uavdt_vehicle_v1.yaml",
            split="val",
            imgsz=960,
            conf=conf,
            iou=iou,
            max_det=max_det,
            verbose=False,
            plots=False
        )

        # Extract metrics
        precision = metrics.results_dict['metrics/precision(B)']
        recall = metrics.results_dict['metrics/recall(B)']
        mAP50 = metrics.results_dict['metrics/mAP50(B)']
        mAP50_95 = metrics.results_dict['metrics/mAP50-95(B)']
        f1 = (2 * precision * recall) / (precision + recall + 1e-16)

        results.append({
            "conf": conf,
            "iou": iou,
            "max_det": max_det,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "mAP50": mAP50,
            "mAP50_95": mAP50_95
        })

    with open("ml/reports/candidate_a_operating_point.json", "w") as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    sweep_operating_points()
