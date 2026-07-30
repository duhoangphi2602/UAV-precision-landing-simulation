import os
import argparse
from ultralytics import YOLO

def export_model(model_path, output_dir, imgsz=960, name="yolov8n_uavdt_vehicle_960_v1"):
    model = YOLO(model_path)

    # Export to ONNX
    onnx_path = model.export(
        format='onnx',
        imgsz=imgsz,
        batch=1,
        dynamic=False,
        simplify=True
    )

    # Move to desired output canonical location
    os.makedirs(output_dir, exist_ok=True)
    import shutil
    final_path = os.path.join(output_dir, f'{name}.onnx')
    shutil.move(onnx_path, final_path)
    print(f"Exported ONNX to {final_path}")
    return final_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', type=str, default='ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt')
    parser.add_argument('--output-dir', type=str, default='ml/exports/')
    parser.add_argument('--imgsz', type=int, default=960)
    parser.add_argument('--name', type=str, default='yolov8n_uavdt_vehicle_960_v1')
    args = parser.parse_args()

    export_model(args.weights, args.output_dir, args.imgsz, args.name)
