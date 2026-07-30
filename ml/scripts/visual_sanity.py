import os
import yaml
import glob
import random
from pathlib import Path
import cv2
import matplotlib.pyplot as plt

def generate_visual_sanity(yaml_path, output_image_path):
    with open(yaml_path, 'r') as f:
        data_cfg = yaml.safe_load(f)

    base_path = Path(yaml_path).parent.parent
    if 'path' in data_cfg:
        base_path = Path(data_cfg['path'])
        if not base_path.is_absolute():
            base_path = Path.cwd() / base_path

    names = data_cfg.get('names', {})

    splits_to_sample = {'train': 4, 'val': 4, 'test': 4}
    sampled_images = []

    for split, num_samples in splits_to_sample.items():
        if split not in data_cfg:
            continue

        split_path = base_path / data_cfg[split]
        if not split_path.exists():
            continue

        image_files = list(split_path.glob('*.jpg')) + list(split_path.glob('*.png'))
        if not image_files:
            continue

        # Try to find images with labels
        valid_images = []
        for img in image_files:
            lbl = split_path.parent / 'labels' / f"{img.stem}.txt"
            if lbl.exists() and lbl.stat().st_size > 0:
                valid_images.append((img, lbl))

        if len(valid_images) > num_samples:
            sampled = random.sample(valid_images, num_samples)
        else:
            sampled = valid_images

        sampled_images.extend([(split, img, lbl) for img, lbl in sampled])

    if not sampled_images:
        print("No images to sample.")
        return

    num_total = len(sampled_images)
    cols = 4
    rows = (num_total + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(cols * 5, rows * 4))
    axes = axes.flatten()

    colors = [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (0,255,255), (255,0,255)]

    for idx, (split, img_path, lbl_path) in enumerate(sampled_images):
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, _ = img.shape

        with open(lbl_path, 'r') as f:
            lines = f.readlines()

        for line in lines:
            parts = line.strip().split()
            if len(parts) == 5:
                c = int(parts[0])
                cx, cy, bw, bh = map(float, parts[1:])
                x1 = int((cx - bw/2) * w)
                y1 = int((cy - bh/2) * h)
                x2 = int((cx + bw/2) * w)
                y2 = int((cy + bh/2) * h)

                color = colors[c % len(colors)]
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

                label_name = names.get(c, str(c))
                cv2.putText(img, label_name, (x1, max(y1 - 5, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        ax = axes[idx]
        ax.imshow(img)
        ax.set_title(f"{split} - {img_path.name}")
        ax.axis('off')

    for idx in range(num_total, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
    plt.savefig(output_image_path, dpi=150)
    print(f"Saved visual sanity check to {output_image_path}")

if __name__ == "__main__":
    generate_visual_sanity('ml/configs/uavdt_aerial_vehicles_v1.yaml', 'ml/reports/dataset_visual_sanity.jpg')
