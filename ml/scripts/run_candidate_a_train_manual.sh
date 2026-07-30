#!/bin/bash
set -e

echo "=================================================="
echo "CANDIDATE A: FULL TRAINING (100 EPOCHS)"
echo "=================================================="

# Check if Gazebo or PX4 is running to prevent OOM
if pgrep -x "gzserver" > /dev/null || pgrep -x "px4" > /dev/null; then
    echo "ERROR: Gazebo or PX4 is running. Please stop them before training to avoid OOM."
    exit 1
fi

source ml/.venv/bin/activate

echo "Starting YOLOv8n full training (100 epochs)..."
yolo train \
    model=ml/experiments/yolov8n_uavdt_baseline_v1/weights/best.pt \
    data=ml/configs/uavdt_vehicle_v1.yaml \
    imgsz=960 \
    epochs=100 \
    patience=20 \
    batch=8 \
    device=0 \
    seed=42 \
    amp=True \
    project=ml/experiments \
    name=yolov8n_uavdt_vehicle_960_v1 \
    exist_ok=False

echo "Training complete. Check ml/experiments/yolov8n_uavdt_vehicle_960_v1 for results."
