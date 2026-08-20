import sys
import ctypes
import os

# Preload CUDA to avoid ORT init failure
base_path = next((p for p in sys.path if p.endswith("site-packages")), None)
if base_path:
    cuda_runtime_lib = os.path.join(base_path, "nvidia", "cu13", "lib", "libcudart.so.13")
    if os.path.exists(cuda_runtime_lib):
        ctypes.CDLL(cuda_runtime_lib, mode=ctypes.RTLD_GLOBAL)

import onnx
from onnx import shape_inference
import onnxruntime as ort
import tensorrt as trt
import hashlib
import glob
import numpy as np
import cv2

model_path = "ml/exports/yolov8n_uavdt_vehicle_960_v1.onnx"

print("--- ONNX CONTRACT INSPECTION ---")
print(f"Model path: {model_path}")

with open(model_path, "rb") as f:
    file_bytes = f.read()
    print(f"SHA-256: {hashlib.sha256(file_bytes).hexdigest()}")

model = onnx.load(model_path)
print(f"Opset: {model.opset_import[0].version}")

onnx.checker.check_model(model)
print("ONNX Checker: PASS")

inferred_model = shape_inference.infer_shapes(model)
print("Shape Inference: PASS")

input_tensor = model.graph.input[0]
in_shape = [d.dim_value for d in input_tensor.type.tensor_type.shape.dim]
print(f"Input Name: {input_tensor.name}")
print(f"Input Shape: {in_shape}")
print(f"Input Dtype: {input_tensor.type.tensor_type.elem_type}")
static_dims = all(d > 0 for d in in_shape)
print(f"Static Dimensions: {static_dims}")

for output in model.graph.output:
    out_shape = [d.dim_value for d in output.type.tensor_type.shape.dim]
    print(f"Output Name: {output.name}, Shape: {out_shape}")

# TRT Dry run
TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
builder = trt.Builder(TRT_LOGGER)
network = builder.create_network(0)
parser = trt.OnnxParser(network, TRT_LOGGER)
if not parser.parse(file_bytes):
    print("TRT Parser Errors:")
    for error in range(parser.num_errors):
        print(parser.get_error(error))
else:
    print("TensorRT ONNX Parser Dry-Run: PASS")

print("--- ORT CUDA INFERENCE ON 10 IMAGES ---")
session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider'])
in_name = session.get_inputs()[0].name

img_paths = list(glob.glob("ml/datasets/derived/uavdt_vehicle_v1/test/images/*.jpg"))[:10]
all_finite = True
for img_path in img_paths:
    img = cv2.imread(img_path)
    # Simple resize for dry run (ignoring aspect ratio just for finite check)
    img = cv2.resize(img, (960, 960))
    img = img.transpose(2, 0, 1)
    img = img[np.newaxis, :, :, :].astype(np.float32) / 255.0
    
    out = session.run(None, {in_name: img})[0]
    if not np.all(np.isfinite(out)):
        all_finite = False
        print(f"Non-finite output on {img_path}")

if all_finite:
    print("Finite Output Assertion: PASS")
