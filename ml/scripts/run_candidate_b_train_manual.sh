#!/bin/bash
set -e

echo "=================================================="
echo "CANDIDATE B (YOLOv8n-P2): FULL TRAINING (100 EPOCHS)"
echo "=================================================="

# Check if Gazebo or PX4 is running to prevent OOM
if pgrep -x "gzserver" > /dev/null || pgrep -x "px4" > /dev/null; then
    echo "ERROR: Gazebo or PX4 is running. Please stop them before training to avoid OOM."
    exit 1
fi

source ml/.venv/bin/activate

echo "Starting YOLOv8n-P2 full training (100 epochs)..."
yolo train \
    model=yolov8n-p2.yaml \
    data=ml/configs/uavdt_vehicle_v1.yaml \
    imgsz=960 \
    epochs=100 \
    patience=20 \
    batch=4 \
    device=0 \
    seed=42 \
    amp=True \
    cache=False \
    project=ml/experiments \
    name=yolov8n_p2_uavdt_vehicle_960_v1 \
    exist_ok=False

echo "Training complete. Check ml/experiments/yolov8n_p2_uavdt_vehicle_960_v1 for results."
