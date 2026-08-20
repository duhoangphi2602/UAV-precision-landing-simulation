import os
import sys
import ctypes

# Try loading libcudart directly if it exists in site-packages
base_path = next((p for p in sys.path if p.endswith("site-packages")), None)
if base_path:
    cuda_runtime_lib = os.path.join(base_path, "nvidia", "cu13", "lib", "libcudart.so.13")
    if os.path.exists(cuda_runtime_lib):
        print(f"Preloading {cuda_runtime_lib} via ctypes...")
        ctypes.CDLL(cuda_runtime_lib, mode=ctypes.RTLD_GLOBAL)
    else:
        print(f"Could not find {cuda_runtime_lib}")

try:
    import onnxruntime as ort
    print(f"ONNX Runtime: {ort.__version__}")
    print(f"Available Providers: {ort.get_available_providers()}")
except Exception as e:
    print(f"ORT import failed: {e}")
