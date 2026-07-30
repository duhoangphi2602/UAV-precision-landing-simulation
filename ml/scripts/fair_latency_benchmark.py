import torch
import time
import glob
import cv2
import json
import numpy as np
from ultralytics import YOLO

def load_images(img_dir, count=500):
    paths = list(glob.glob(img_dir + "/*.jpg"))[:count]
    images = []
    for p in paths:
        # Pre-load as numpy arrays if needed, but YOLO natively takes paths or numpy.
        # We'll just pass paths to YOLO to include its preprocess in the timing accurately.
        images.append(p)
    return images

def benchmark_model(model_name, model_path, images, num_warmup=50, num_repeats=3):
    print(f"Loading {model_name}...")
    model = YOLO(model_path)

    # Warmup
    print(f"Warmup {model_name} ({num_warmup} iterations)...")
    for img in images[:num_warmup]:
        model.predict(img, imgsz=960, verbose=False, device=0, conf=0.25, iou=0.7, max_det=300)

    print(f"Benchmarking {model_name}...")

    all_preprocess = []
    all_inference = []
    all_postprocess = []

    for r in range(num_repeats):
        torch.cuda.synchronize()
        for img in images:
            res = model.predict(img, imgsz=960, verbose=False, device=0, conf=0.25, iou=0.7, max_det=300)[0]
            all_preprocess.append(res.speed['preprocess'])
            all_inference.append(res.speed['inference'])
            all_postprocess.append(res.speed['postprocess'])

    avg_pre = np.mean(all_preprocess)
    avg_inf = np.mean(all_inference)
    avg_post = np.mean(all_postprocess)

    total_latency = np.array(all_preprocess) + np.array(all_inference) + np.array(all_postprocess)

    return {
        "model": model_name,
        "mean_ms": float(np.mean(total_latency)),
        "median_ms": float(np.median(total_latency)),
        "p95_ms": float(np.percentile(total_latency, 95)),
        "p99_ms": float(np.percentile(total_latency, 99)),
        "std_ms": float(np.std(total_latency)),
        "avg_preprocess": float(avg_pre),
        "avg_inference": float(avg_inf),
        "avg_postprocess": float(avg_post)
    }

if __name__ == "__main__":
    img_dir = "ml/datasets/derived/uavdt_vehicle_v1/test/images"
    images = load_images(img_dir, 500)

    model_A = "ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt"
    model_B = "ml/experiments/yolov8n_p2_uavdt_vehicle_960_v1/weights/best.pt"

    results = []

    # Round 1: A then B
    res_A1 = benchmark_model("Candidate_A_Run1", model_A, images)
    results.append(res_A1)

    res_B1 = benchmark_model("Candidate_B_Run1", model_B, images)
    results.append(res_B1)

    # Round 2: B then A (to isolate thermal throttling or CUDA context initialization)
    res_B2 = benchmark_model("Candidate_B_Run2", model_B, images)
    results.append(res_B2)

    res_A2 = benchmark_model("Candidate_A_Run2", model_A, images)
    results.append(res_A2)

    with open("ml/reports/fair_latency_benchmark.json", "w") as f:
        json.dump(results, f, indent=4)

    print(json.dumps(results, indent=4))
