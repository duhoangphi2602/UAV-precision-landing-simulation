import tensorrt as trt
import torch
import numpy as np
import sys
import ctypes
import os

# Preload CUDA
base_path = next((p for p in sys.path if p.endswith("site-packages")), None)
if base_path:
    cuda_runtime_lib = os.path.join(base_path, "nvidia", "cu13", "lib", "libcudart.so.13")
    if os.path.exists(cuda_runtime_lib):
        ctypes.CDLL(cuda_runtime_lib, mode=ctypes.RTLD_GLOBAL)

class TensorRTEngine:
    def __init__(self, engine_path):
        self.logger = trt.Logger(trt.Logger.WARNING)
        self.runtime = trt.Runtime(self.logger)
        
        with open(engine_path, "rb") as f:
            engine_bytes = f.read()
            
        self.engine = self.runtime.deserialize_cuda_engine(engine_bytes)
        if not self.engine:
            raise RuntimeError(f"Failed to deserialize TensorRT engine from {engine_path}")
            
        self.context = self.engine.create_execution_context()
        self.stream = torch.cuda.Stream()
        
        # Verify contract
        assert self.engine.num_io_tensors == 2, f"Expected 2 IO tensors, got {self.engine.num_io_tensors}"
        self.input_name = self.engine.get_tensor_name(0)
        self.output_name = self.engine.get_tensor_name(1)
        
        in_shape = tuple(self.engine.get_tensor_shape(self.input_name))
        out_shape = tuple(self.engine.get_tensor_shape(self.output_name))
        
        assert in_shape == (1, 3, 960, 960), f"Unexpected input shape {in_shape}"
        assert out_shape == (1, 5, 18900), f"Unexpected output shape {out_shape}"
        
        # Allocate persistent buffers on GPU using Torch
        self.input_tensor = torch.empty(in_shape, dtype=torch.float32, device="cuda")
        self.output_tensor = torch.empty(out_shape, dtype=torch.float32, device="cuda")
        
        # Register buffers to execution context
        self.context.set_tensor_address(self.input_name, self.input_tensor.data_ptr())
        self.context.set_tensor_address(self.output_name, self.output_tensor.data_ptr())

    def __call__(self, input_blob: np.ndarray) -> np.ndarray:
        """
        Execute TRT Engine asynchronously using pinned memory.
        input_blob: 1x3x960x960 float32 numpy array
        returns: 1x5x18900 float32 numpy array
        """
        # H2D Copy
        self.input_tensor.copy_(torch.from_numpy(input_blob), non_blocking=True)
        
        # Execute
        self.context.execute_async_v3(stream_handle=self.stream.cuda_stream)
        
        # Sync
        self.stream.synchronize()
        
        # D2H Copy
        return self.output_tensor.cpu().numpy()
