import json
import glob
import time
import argparse
from ultralytics import YOLO

def verify_parity(pt_path, onnx_path, sample_dir, output_json):
    pt_model = YOLO(pt_path)
    onnx_model = YOLO(onnx_path)

    images = list(glob.glob(sample_dir + '/*.jpg'))[:20]

    report = {
        'num_samples': len(images),
        'systematic_mismatch': False,
        'average_confidence_diff': 0.0,
        'average_iou': 0.0,
        'missing_detections': 0,
        'additional_detections': 0,
        'onnx_latency_ms': 0.0,
        'pt_latency_ms': 0.0,
        'parity_pass': False
    }

    total_conf_diff = 0
    total_iou = 0
    match_count = 0
    mismatch_count = 0

    pt_time = 0
    onnx_time = 0

    for img in images:
        t0 = time.time()
        res_pt = pt_model(img, verbose=False)[0]
        pt_time += time.time() - t0

        t0 = time.time()
        res_onnx = onnx_model(img, verbose=False)[0]
        onnx_time += time.time() - t0

        boxes_pt = res_pt.boxes
        boxes_onnx = res_onnx.boxes

        if len(boxes_pt) != len(boxes_onnx):
            if len(boxes_onnx) > len(boxes_pt):
                report['additional_detections'] += len(boxes_onnx) - len(boxes_pt)
            else:
                report['missing_detections'] += len(boxes_pt) - len(boxes_onnx)

        # Match detections by maximum IoU
        matched_onnx = set()
        for i in range(len(boxes_pt)):
            b_pt = boxes_pt.xyxy[i].cpu().numpy()
            best_iou = 0
            best_j = -1

            for j in range(len(boxes_onnx)):
                if j in matched_onnx: continue
                b_onnx = boxes_onnx.xyxy[j].cpu().numpy()
                x1 = max(b_pt[0], b_onnx[0])
                y1 = max(b_pt[1], b_onnx[1])
                x2 = min(b_pt[2], b_onnx[2])
                y2 = min(b_pt[3], b_onnx[3])
                inter = max(0, x2 - x1) * max(0, y2 - y1)
                area_pt = (b_pt[2] - b_pt[0]) * (b_pt[3] - b_pt[1])
                area_onnx = (b_onnx[2] - b_onnx[0]) * (b_onnx[3] - b_onnx[1])
                iou = inter / float(area_pt + area_onnx - inter + 1e-6)

                if iou > best_iou:
                    best_iou = iou
                    best_j = j

            if best_iou > 0.5 and best_j != -1:
                matched_onnx.add(best_j)
                c_pt = int(boxes_pt.cls[i].item())
                c_onnx = int(boxes_onnx.cls[best_j].item())

                if c_pt != c_onnx:
                    mismatch_count += 1

                conf_pt = float(boxes_pt.conf[i].item())
                conf_onnx = float(boxes_onnx.conf[best_j].item())
                total_conf_diff += abs(conf_pt - conf_onnx)
                total_iou += best_iou
                match_count += 1

    if match_count > 0:
        report['systematic_mismatch'] = (mismatch_count / match_count) > 0.10
        report['average_confidence_diff'] = float(total_conf_diff / match_count)
        report['average_iou'] = float(total_iou / match_count)

    report['pt_latency_ms'] = float((pt_time / max(1, len(images))) * 1000)
    report['onnx_latency_ms'] = float((onnx_time / max(1, len(images))) * 1000)

    # Acceptance
    report['parity_pass'] = (
        not report['systematic_mismatch'] and
        report['average_iou'] > 0.95 and
        report['average_confidence_diff'] < 0.05
    )

    with open(output_json, 'w') as f:
        json.dump(report, f, indent=4)

    print(f"Parity check completed. Pass: {report['parity_pass']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--onnx-path', type=str, default='ml/exports/yolov8n_uavdt_vehicle_960_v1.onnx')
    parser.add_argument('--pt-path', type=str, default='ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt')
    parser.add_argument('--img-dir', type=str, default='ml/datasets/derived/uavdt_vehicle_v1/test/images')
    parser.add_argument('--output', type=str, default='ml/reports/onnx_parity.json')
    args = parser.parse_args()

    verify_parity(args.pt_path, args.onnx_path, args.img_dir, args.output)
