import os
import glob
import json
import yaml
from pathlib import Path
from PIL import Image

def validate_dataset(yaml_path, output_report_path):
    with open(yaml_path, 'r') as f:
        data_cfg = yaml.safe_load(f)

    base_path = Path(yaml_path).parent.parent
    if 'path' in data_cfg:
        base_path = Path(data_cfg['path'])
        if not base_path.is_absolute():
            # Assume relative to the script's cwd
            base_path = Path.cwd() / base_path

    nc = data_cfg.get('nc', 0)
    splits = ['train', 'val', 'test']

    report = {
        'split_image_counts': {'train': 0, 'val': 0, 'test': 0},
        'split_label_counts': {'train': 0, 'val': 0, 'test': 0},
        'per_class_counts': {i: 0 for i in range(nc)},
        'empty_label_images': 0,
        'malformed_label_rows': 0,
        'invalid_class_ids': 0,
        'invalid_bounding_boxes': 0,
        'corrupted_images': 0,
        'orphaned_images': 0,
        'orphaned_labels': 0,
        'total_images': 0,
        'total_objects': 0,
    }

    all_image_stems = set()
    duplicate_stems = 0

    for split in splits:
        if split not in data_cfg:
            continue

        split_path = base_path / data_cfg[split]
        if not split_path.exists():
            continue

        label_path = split_path.parent / 'labels'

        image_files = list(split_path.glob('*.jpg')) + list(split_path.glob('*.png'))
        report['split_image_counts'][split] = len(image_files)
        report['total_images'] += len(image_files)

        for img_file in image_files:
            if img_file.stem in all_image_stems:
                duplicate_stems += 1
            all_image_stems.add(img_file.stem)

            try:
                with Image.open(img_file) as img:
                    img.verify()
                    w, h = img.size
                    if w <= 0 or h <= 0:
                        report['corrupted_images'] += 1
            except Exception:
                report['corrupted_images'] += 1
                continue

            lbl_file = label_path / f"{img_file.stem}.txt"
            if not lbl_file.exists():
                report['orphaned_images'] += 1
                continue

            report['split_label_counts'][split] += 1

            try:
                with open(lbl_file, 'r') as f:
                    lines = f.readlines()
            except Exception:
                report['malformed_label_rows'] += 1
                continue

            if not lines:
                report['empty_label_images'] += 1
                continue

            for line in lines:
                parts = line.strip().split()
                if len(parts) != 5:
                    report['malformed_label_rows'] += 1
                    continue

                try:
                    c = int(parts[0])
                    x, y, bw, bh = map(float, parts[1:])
                except ValueError:
                    report['malformed_label_rows'] += 1
                    continue

                if c < 0 or c >= nc:
                    report['invalid_class_ids'] += 1

                if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < bw <= 1 and 0 < bh <= 1):
                    report['invalid_bounding_boxes'] += 1

                if x - bw/2 < 0 or x + bw/2 > 1 or y - bh/2 < 0 or y + bh/2 > 1:
                    report['invalid_bounding_boxes'] += 1

                if c in report['per_class_counts']:
                    report['per_class_counts'][c] += 1
                report['total_objects'] += 1

        if label_path.exists():
            for lbl_file in label_path.glob('*.txt'):
                img_jpg = split_path / f"{lbl_file.stem}.jpg"
                img_png = split_path / f"{lbl_file.stem}.png"
                if not (img_jpg.exists() or img_png.exists()):
                    report['orphaned_labels'] += 1

    report['duplicate_stems'] = duplicate_stems

    gate_pass = (
        report['malformed_label_rows'] == 0 and
        report['invalid_class_ids'] == 0 and
        report['invalid_bounding_boxes'] == 0 and
        report['corrupted_images'] == 0
    )

    report['GATE_STATUS'] = "PASS" if gate_pass else "FAIL"

    os.makedirs(os.path.dirname(output_report_path), exist_ok=True)
    with open(output_report_path, 'w') as f:
        json.dump(report, f, indent=4)

    print(f"Validation complete. Gate Status: {report['GATE_STATUS']}")

if __name__ == "__main__":
    validate_dataset('ml/configs/uavdt_aerial_vehicles_v1.yaml', 'ml/reports/dataset_validation.json')
