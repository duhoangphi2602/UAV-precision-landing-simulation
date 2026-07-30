#!/bin/bash
set -e

echo "=================================================="
echo "CANDIDATE A: SMOKE TEST (1 EPOCH)"
echo "=================================================="

# Check if Gazebo or PX4 is running to prevent OOM
if pgrep -x "gzserver" > /dev/null || pgrep -x "px4" > /dev/null; then
    echo "ERROR: Gazebo or PX4 is running. Please stop them before training to avoid OOM."
    exit 1
fi

source ml/.venv/bin/activate

echo "Starting YOLOv8n smoke training (1 epoch)..."
yolo train \
    model=yolov8n.pt \
    data=ml/configs/uavdt_vehicle_v1.yaml \
    imgsz=960 \
    epochs=1 \
    batch=8 \
    device=0 \
    seed=42 \
    amp=True \
    project=ml/experiments \
    name=yolov8n_uavdt_vehicle_960_smoke \
    exist_ok=True

echo "Smoke test complete. Check for OOM errors above."
echo "If PASS, you may run the full training."
