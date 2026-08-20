import argparse
import os
import sys
import time
import hashlib
import ctypes

# Preload CUDA to avoid ORT/TensorRT init failure
base_path = next((p for p in sys.path if p.endswith("site-packages")), None)
if base_path:
    cuda_runtime_lib = os.path.join(base_path, "nvidia", "cu13", "lib", "libcudart.so.13")
    if os.path.exists(cuda_runtime_lib):
        ctypes.CDLL(cuda_runtime_lib, mode=ctypes.RTLD_GLOBAL)

import tensorrt as trt

def build_engine(onnx_path, output_path, precision, workspace_gib):
    print(f"--- TENSORRT ENGINE BUILDER ---")
    print(f"TensorRT Version: {trt.__version__}")

    if os.path.exists(output_path):
        raise FileExistsError(f"Refusing to overwrite existing engine: {output_path}")
    
    TRT_LOGGER = trt.Logger(trt.Logger.INFO)
    builder = trt.Builder(TRT_LOGGER)
    
    # In TRT 10+, builder.create_network() creates explicit batch network
    network = builder.create_network(0)
    config = builder.create_builder_config()
    
    # Disable TF32 to ensure strict FP32 reference
    config.clear_flag(trt.BuilderFlag.TF32)
    
    if precision.lower() == "fp16":
        if not hasattr(trt.BuilderFlag, "FP16"):
            raise RuntimeError(
                "TensorRT 11 removed BuilderFlag.FP16 and requires a strongly typed "
                "mixed-precision ONNX model. Refusing to build the canonical FP32 ONNX "
                "and mislabel the resulting engine as FP16. Convert a distinct derived "
                "ONNX with NVIDIA ModelOpt AutoCast before building."
            )
        if not getattr(builder, "platform_has_fast_fp16", True):
            print("WARNING: Platform does not report fast FP16 support.")
        config.set_flag(trt.BuilderFlag.FP16)
        
    elif precision.lower() == "int8":
        raise RuntimeError("INT8 is locked and this builder has no valid quantization path.")
        
    # Set Memory Pool Limit
    workspace_bytes = int(workspace_gib * 1024 * 1024 * 1024)
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, workspace_bytes)
    
    # Parse ONNX
    parser = trt.OnnxParser(network, TRT_LOGGER)
    with open(onnx_path, "rb") as model:
        if not parser.parse(model.read()):
            print("ERROR: Failed to parse the ONNX file.")
            for error in range(parser.num_errors):
                print(parser.get_error(error))
            sys.exit(1)
            
    print(f"ONNX parsed successfully. Compiling engine for {precision.upper()}...")
    
    start_time = time.time()
    engine_bytes = builder.build_serialized_network(network, config)
    build_duration = time.time() - start_time
    
    if engine_bytes is None:
        print("ERROR: Engine build failed. Try increasing workspace fallback.")
        sys.exit(1)
        
    print(f"Build completed in {build_duration:.2f} seconds.")
    
    # Save engine
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    engine_buffer = memoryview(engine_bytes)
    with open(output_path, "wb") as f:
        bytes_written = f.write(engine_buffer)
        
    if bytes_written != engine_bytes.nbytes:
        print(f"WARNING: Wrote {bytes_written} bytes, but engine size is {engine_bytes.nbytes}")
        
    engine_size_mb = engine_bytes.nbytes / (1024 * 1024)
    engine_sha = hashlib.sha256(engine_buffer).hexdigest()
    
    print(f"Engine saved to {output_path}")
    print(f"Engine Size: {engine_size_mb:.2f} MB")
    print(f"Engine SHA-256: {engine_sha}")
    print("-------------------------------")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TensorRT Engine Builder")
    parser.add_argument("--onnx", type=str, required=True, help="Path to input ONNX model")
    parser.add_argument("--output", type=str, required=True, help="Path to output TRT engine")
    parser.add_argument("--precision", type=str, choices=["fp32", "fp16", "int8"], required=True)
    parser.add_argument("--workspace-gib", type=float, default=2.0, help="Workspace memory limit in GiB")
    args = parser.parse_args()
    
    build_engine(args.onnx, args.output, args.precision, args.workspace_gib)
