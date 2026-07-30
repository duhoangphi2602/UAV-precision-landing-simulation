#!/bin/bash
set -e

echo "=================================================="
echo "CANDIDATE B (YOLOv8n-P2): SMOKE TEST (1 EPOCH)"
echo "=================================================="

# Check if Gazebo or PX4 is running to prevent OOM
if pgrep -x "gzserver" > /dev/null || pgrep -x "px4" > /dev/null; then
    echo "ERROR: Gazebo or PX4 is running. Please stop them before training to avoid OOM."
    exit 1
fi

source ml/.venv/bin/activate

echo "Starting YOLOv8n-P2 smoke training (1 epoch)..."
yolo train \
    model=yolov8n-p2.yaml \
    data=ml/configs/uavdt_vehicle_v1.yaml \
    imgsz=960 \
    epochs=1 \
    batch=4 \
    device=0 \
    seed=42 \
    amp=True \
    cache=False \
    project=ml/experiments \
    name=yolov8n_p2_uavdt_vehicle_960_smoke \
    exist_ok=True

echo "Smoke test complete. Check for OOM errors above."
echo "If PASS, you may run the full training."
echo "If OOM, please edit this script and the full script to use batch=2."
