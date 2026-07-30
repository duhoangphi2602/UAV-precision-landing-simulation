import torch
import time
import glob
import cv2
import json
import numpy as np
import onnxruntime as ort
from ultralytics import YOLO

def benchmark_pytorch(model_path, images, num_warmup=50):
    model = YOLO(model_path)
    # Warmup
    print("PyTorch Warmup...")
    for img in images[:num_warmup]:
        model.predict(img, imgsz=960, verbose=False, device=0)

    print("PyTorch Benchmark...")
    torch.cuda.synchronize()
    t0 = time.time()

    total_preprocess = 0
    total_inference = 0
    total_postprocess = 0

    for img in images:
        # We can use Ultralytics internal timers from the result object
        res = model.predict(img, imgsz=960, verbose=False, device=0)[0]
        total_preprocess += res.speed['preprocess']
        total_inference += res.speed['inference']
        total_postprocess += res.speed['postprocess']

    torch.cuda.synchronize()
    t1 = time.time()

    avg_total = (t1 - t0) / len(images) * 1000
    avg_pre = total_preprocess / len(images)
    avg_inf = total_inference / len(images)
    avg_post = total_postprocess / len(images)

    return {
        "engine": "PyTorch CUDA",
        "avg_total_ms": avg_total,
        "avg_preprocess_ms": avg_pre,
        "avg_inference_ms": avg_inf,
        "avg_postprocess_ms": avg_post,
        "fps": 1000 / avg_total
    }

def benchmark_onnx(model_path, images, provider, num_warmup=50):
    try:
        session = ort.InferenceSession(model_path, providers=[provider])
    except Exception as e:
        print(f"ONNX provider {provider} not available.")
        return None

    input_name = session.get_inputs()[0].name

    # Warmup
    print(f"ONNX {provider} Warmup...")
    warmup_img = np.random.randn(1, 3, 960, 960).astype(np.float32)
    for _ in range(num_warmup):
        session.run(None, {input_name: warmup_img})

    print(f"ONNX {provider} Benchmark...")
    if 'CUDA' in provider:
        torch.cuda.synchronize()

    total_time = 0

    for img_path in images:
        # Basic preprocessing for ONNX
        t_pre_start = time.time()
        img = cv2.imread(img_path)
        img = cv2.resize(img, (960, 960))
        img = img.transpose(2, 0, 1)
        img = np.expand_dims(img, axis=0)
        img = img.astype(np.float32) / 255.0

        if 'CUDA' in provider:
            torch.cuda.synchronize()
        t_inf_start = time.time()

        session.run(None, {input_name: img})

        if 'CUDA' in provider:
            torch.cuda.synchronize()
        t_inf_end = time.time()

        total_time += (t_inf_end - t_pre_start)

    avg_total = (total_time / len(images)) * 1000

    return {
        "engine": f"ONNX {provider}",
        "avg_total_ms": avg_total,
        "fps": 1000 / avg_total
    }

if __name__ == "__main__":
    img_dir = "ml/datasets/derived/uavdt_vehicle_v1/test/images"
    pt_model = "ml/experiments/yolov8n_p2_uavdt_vehicle_960_v1/weights/best.pt"
    onnx_model = "ml/exports/yolov8n_p2_uavdt_vehicle_960_v1.onnx"

    images = list(glob.glob(img_dir + "/*.jpg"))[:500]
    if len(images) < 500:
        print(f"Warning: only found {len(images)} images.")

    results = []

    # PyTorch
    pt_res = benchmark_pytorch(pt_model, images)
    results.append(pt_res)

    # ONNX CUDA
    onnx_cuda = benchmark_onnx(onnx_model, images, 'CUDAExecutionProvider')
    if onnx_cuda: results.append(onnx_cuda)

    # ONNX CPU
    onnx_cpu = benchmark_onnx(onnx_model, images, 'CPUExecutionProvider')
    if onnx_cpu: results.append(onnx_cpu)

    # Save report
    with open("ml/reports/candidate_a_latency.json", "w") as f:
        json.dump(results, f, indent=4)

    for r in results:
        print(r)
