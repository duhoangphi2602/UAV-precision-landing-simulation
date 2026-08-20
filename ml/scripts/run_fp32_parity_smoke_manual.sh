#!/bin/bash
set -e

echo "============================================="
echo " FP32 SMOKE PARITY EVALUATION (MANUAL)"
echo "============================================="

if [ ! -d "ml/.venv-tensorrt" ]; then
    echo "ERROR: ml/.venv-tensorrt not found."
    exit 1
fi

source ml/.venv-tensorrt/bin/activate

if ! python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "ERROR: CUDA not available in Torch."
    exit 1
fi

PYTORCH_CKPT=${PYTORCH_CKPT:-"ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt"}
FP32_ENGINE=${FP32_ENGINE:-"ml/exports/tensorrt/yolov8n_uavdt_vehicle_960_v1_fp32.engine"}

python ml/scripts/fp32_smoke_parity.py --checkpoint "$PYTORCH_CKPT" --engine "$FP32_ENGINE"
echo "Smoke evaluation completed successfully."
