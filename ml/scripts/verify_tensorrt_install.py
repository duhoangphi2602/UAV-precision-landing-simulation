import sys
import ctypes
import os

def preload_cuda():
    base_path = next((p for p in sys.path if p.endswith("site-packages")), None)
    if base_path:
        cuda_runtime_lib = os.path.join(base_path, "nvidia", "cu13", "lib", "libcudart.so.13")
        if os.path.exists(cuda_runtime_lib):
            ctypes.CDLL(cuda_runtime_lib, mode=ctypes.RTLD_GLOBAL)

preload_cuda()

try:
    import tensorrt as trt
    print("TENSORRT_IMPORT=PASS")
    print(f"TensorRT Version: {trt.__version__}")
    
    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    print("TENSORRT_BUILDER=PASS")
except Exception as e:
    print(f"TENSORRT_IMPORT=FAIL ({e})")
    sys.exit(1)

try:
    import torch
    if torch.cuda.is_available():
        print("CUDA_RUNTIME=PASS")
    else:
        print("CUDA_RUNTIME=FAIL (CUDA not available in Torch)")
except Exception as e:
    print(f"CUDA_RUNTIME=FAIL ({e})")

try:
    import onnxruntime as ort
    if 'CUDAExecutionProvider' in ort.get_available_providers():
        print("ORT_CUDA_EP=PASS")
    else:
        print("ORT_CUDA_EP=FAIL (CUDA EP not in available providers)")
except Exception as e:
    print(f"ORT_CUDA_EP=FAIL ({e})")

# ONNX Inference test
try:
    import onnxruntime as ort
    model_path = "ml/exports/yolov8n_uavdt_vehicle_960_v1.onnx"
    if not os.path.exists(model_path):
        print(f"ONNX_INFERENCE=FAIL (Model not found at {model_path})")
    else:
        session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider'])
        import numpy as np
        dummy_input = np.random.randn(1, 3, 960, 960).astype(np.float32)
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: dummy_input})
        if np.all(np.isfinite(outputs[0])):
            print("ONNX_INFERENCE=PASS")
        else:
            print("ONNX_INFERENCE=FAIL (Non-finite outputs)")
except Exception as e:
    print(f"ONNX_INFERENCE=FAIL ({e})")
