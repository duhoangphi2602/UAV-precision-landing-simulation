import json
import numpy as np
from ultralytics import YOLO

def find_best_conf(model_path, data_yaml):
    print(f"Finding best conf for {model_path} on validation set...")
    model = YOLO(model_path)

    best_f1 = 0
    best_conf = 0.25

    for conf in [0.20, 0.25, 0.30]:
        metrics = model.val(data=data_yaml, split="val", imgsz=960, conf=conf, verbose=False, plots=False)
        p = metrics.results_dict['metrics/precision(B)']
        r = metrics.results_dict['metrics/recall(B)']
        f1 = (2 * p * r) / (p + r + 1e-16)
        if f1 > best_f1:
            best_f1 = f1
            best_conf = conf

    return best_conf

def evaluate_test(model_path, data_yaml, conf):
    print(f"Evaluating {model_path} on test set with conf={conf}...")
    model = YOLO(model_path)
    metrics = model.val(data=data_yaml, split="test", imgsz=960, conf=conf, verbose=False, plots=False)

    precision = metrics.results_dict['metrics/precision(B)']
    recall = metrics.results_dict['metrics/recall(B)']
    f1 = (2 * precision * recall) / (precision + recall + 1e-16)

    # Estimate NMS latency from speed dict
    nms_latency = metrics.speed['postprocess']

    return {
        "best_conf": conf,
        "test_precision": precision,
        "test_recall": recall,
        "test_f1": f1,
        "nms_latency_ms": nms_latency
    }

if __name__ == "__main__":
    data = "ml/configs/uavdt_vehicle_v1.yaml"
    model_A = "ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt"
    model_B = "ml/experiments/yolov8n_p2_uavdt_vehicle_960_v1/weights/best.pt"

    # Candidate A
    conf_A = find_best_conf(model_A, data)
    res_A = evaluate_test(model_A, data, conf_A)

    # Candidate B
    conf_B = find_best_conf(model_B, data)
    res_B = evaluate_test(model_B, data, conf_B)

    results = {
        "Candidate_A": res_A,
        "Candidate_B": res_B
    }

    with open("ml/reports/operating_point_fairness.json", "w") as f:
        json.dump(results, f, indent=4)

    print(json.dumps(results, indent=4))
