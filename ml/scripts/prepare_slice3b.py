import os
import json
import glob
from pathlib import Path
import shutil
import numpy as np

def create_derived_dataset(raw_dir, derived_dir):
    print("Creating derived single-class dataset...")
    splits = ['train', 'valid', 'test']

    total_boxes = 0
    malformed = 0
    invalid_boxes = 0
    missing_images = 0

    for split in splits:
        raw_split_dir = raw_dir / split
        if not raw_split_dir.exists():
            # some datasets use 'val' instead of 'valid' for folder name
            raw_split_dir = raw_dir / ('val' if split == 'valid' else split)
            if not raw_split_dir.exists(): continue

        der_split_dir = derived_dir / split
        der_img_dir = der_split_dir / 'images'
        der_lbl_dir = der_split_dir / 'labels'

        os.makedirs(der_img_dir, exist_ok=True)
        os.makedirs(der_lbl_dir, exist_ok=True)

        raw_img_dir = raw_split_dir / 'images'
        raw_lbl_dir = raw_split_dir / 'labels'

        for img_path in list(raw_img_dir.glob('*.jpg')) + list(raw_img_dir.glob('*.png')):
            der_img = der_img_dir / img_path.name
            if not der_img.exists():
                os.symlink(img_path.resolve(), der_img)

            raw_lbl = raw_lbl_dir / f"{img_path.stem}.txt"
            der_lbl = der_lbl_dir / f"{img_path.stem}.txt"

            if raw_lbl.exists():
                with open(raw_lbl, 'r') as f_in, open(der_lbl, 'w') as f_out:
                    lines = f_in.readlines()
                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) == 5:
                            # remap class to 0
                            try:
                                cx, cy, bw, bh = map(float, parts[1:])
                                if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < bw <= 1 and 0 < bh <= 1):
                                    invalid_boxes += 1
                                f_out.write(f"0 {cx} {cy} {bw} {bh}\n")
                                total_boxes += 1
                            except ValueError:
                                malformed += 1
                        else:
                            malformed += 1
            else:
                # empty image
                pass

    print(f"Validation Gate:")
    print(f"- Total bboxes: {total_boxes}")
    print(f"- Malformed rows: {malformed}")
    print(f"- Invalid boxes: {invalid_boxes}")
    print(f"- Missing images: {missing_images}")

def analyze_small_objects(raw_dir):
    print("Analyzing small objects...")
    splits = ['train', 'valid', 'test']

    widths = []
    heights = []
    max_dims = []
    areas = []

    for split in splits:
        raw_lbl_dir = raw_dir / split / 'labels'
        if not raw_lbl_dir.exists():
            raw_lbl_dir = raw_dir / ('val' if split == 'valid' else split) / 'labels'

        if not raw_lbl_dir.exists(): continue

        for lbl in raw_lbl_dir.glob('*.txt'):
            with open(lbl, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        _, _, bw, bh = map(float, parts[1:])
                        # Original size is 960x720
                        w_px = bw * 960
                        h_px = bh * 720

                        widths.append(w_px)
                        heights.append(h_px)
                        max_dims.append(max(w_px, h_px))
                        areas.append(w_px * h_px)

    max_dims = np.array(max_dims)
    print(f"Total objects analyzed: {len(max_dims)}")
    print(f"Median width: {np.median(widths):.2f} px (at 960x720)")
    print(f"Median height: {np.median(heights):.2f} px (at 960x720)")
    print(f"<8 px max dim: {(max_dims < 8).mean() * 100:.2f}%")
    print(f"<16 px max dim: {(max_dims < 16).mean() * 100:.2f}%")
    print(f"<32 px max dim: {(max_dims < 32).mean() * 100:.2f}%")
    print(f">=32 px max dim: {(max_dims >= 32).mean() * 100:.2f}%")

if __name__ == "__main__":
    raw = Path("ml/datasets/raw/uavdt/aerial_vehicles_v1")
    derived = Path("ml/datasets/derived/uavdt_vehicle_v1")

    analyze_small_objects(raw)
    create_derived_dataset(raw, derived)
