import time
import glob
import cv2
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction, get_prediction
from ultralytics import YOLO

def benchmark(model_path, img_dir, num_samples=50):
    images = list(glob.glob(img_dir + '/*.jpg'))[:num_samples]

    detection_model = AutoDetectionModel.from_pretrained(
        model_type="yolov8",
        model_path=model_path,
        confidence_threshold=0.3,
        device="cuda:0", # Use GPU
    )

    total_std_latency = 0
    total_sahi_latency = 0
    total_std_dets = 0
    total_sahi_dets = 0

    for img_path in images:
        img = cv2.imread(img_path)

        # Standard
        t0 = time.time()
        std_result = get_prediction(img_path, detection_model)
        total_std_latency += (time.time() - t0)
        total_std_dets += len(std_result.object_prediction_list)

        # SAHI
        t0 = time.time()
        sahi_result = get_sliced_prediction(
            img_path,
            detection_model,
            slice_height=640,
            slice_width=640,
            overlap_height_ratio=0.2,
            overlap_width_ratio=0.2
        )
        total_sahi_latency += (time.time() - t0)
        total_sahi_dets += len(sahi_result.object_prediction_list)

    avg_std_ms = (total_std_latency / num_samples) * 1000
    avg_sahi_ms = (total_sahi_latency / num_samples) * 1000

    print("=== SAHI BENCHMARK RESULTS ===")
    print(f"Subset size: {num_samples}")
    print(f"Standard Avg End-to-End Latency: {avg_std_ms:.2f} ms")
    print(f"SAHI Avg End-to-End Latency: {avg_sahi_ms:.2f} ms")
    print(f"Standard Detections: {total_std_dets}")
    print(f"SAHI Detections: {total_sahi_dets}")

    if avg_sahi_ms > 33.3:
        print("SAHI_STATUS=DEFERRED_TOO_SLOW_OR_LOW_GAIN")
    else:
        print("SAHI_STATUS=VIABLE")

if __name__ == "__main__":
    benchmark(
        'ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt',
        'ml/datasets/derived/uavdt_vehicle_v1/test/images'
    )
