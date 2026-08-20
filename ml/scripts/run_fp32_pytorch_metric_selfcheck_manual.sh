#!/bin/bash
set -e

echo "============================================="
echo " PYTORCH EVALUATOR SELF-CONSISTENCY (MANUAL)"
echo "============================================="

if [ ! -d "ml/.venv-tensorrt" ]; then
    echo "ERROR: ml/.venv-tensorrt not found."
    exit 1
fi

source ml/.venv-tensorrt/bin/activate

PYTORCH_CKPT=${PYTORCH_CKPT:-"ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt"}

python ml/scripts/fp32_full_parity.py --checkpoint "$PYTORCH_CKPT" --pytorch-only
echo "PyTorch metric self-check completed."
