#!/usr/bin/env python3
"""Run the official Ultralytics Candidate A evaluation on the frozen test split."""

from __future__ import annotations

import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import ultralytics
import yaml
from ultralytics import YOLO


REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = REPO_ROOT / "ml/experiments/yolov8n_uavdt_vehicle_960_v1/weights/best.pt"
DATA_YAML = REPO_ROOT / "ml/configs/uavdt_vehicle_v1.yaml"
REPORT_PATH = REPO_ROOT / "ml/reports/candidate_a_ultralytics_test_reference.json"
RUNS_DIR = REPO_ROOT / "ml/reports/ultralytics_runs"

EXPECTED_TEST_IMAGES = 1_610
EXPECTED_TEST_LABELS = 1_610
CUSTOM_TEST_MAP50_95_REFERENCE = 0.52415
HISTORICAL_VALIDATION_MAP50_95 = 0.609
IMAGE_SUFFIXES = {".bmp", ".dng", ".jpeg", ".jpg", ".mpo", ".png", ".tif", ".tiff", ".webp"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def resolve_dataset_paths() -> tuple[dict[str, Any], Path, Path]:
    with DATA_YAML.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict) or "test" not in data:
        raise RuntimeError(f"Dataset YAML has no test split: {DATA_YAML}")
    if data.get("nc") != 1 or data.get("names") not in ({0: "vehicle"}, ["vehicle"]):
        raise RuntimeError("Dataset class contract must be exactly one 'vehicle' class")

    dataset_root = Path(data.get("path", DATA_YAML.parent))
    if not dataset_root.is_absolute():
        dataset_root = REPO_ROOT / dataset_root

    test_images = Path(data["test"])
    if not test_images.is_absolute():
        test_images = dataset_root / test_images
    test_images = test_images.resolve()
    test_labels = test_images.parent / "labels"

    if not test_images.is_dir() or not test_labels.is_dir():
        raise RuntimeError(f"Test split paths are unavailable: {test_images}, {test_labels}")

    image_count = sum(
        path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        for path in test_images.iterdir()
    )
    label_count = sum(path.is_file() and path.suffix.lower() == ".txt" for path in test_labels.iterdir())
    if image_count != EXPECTED_TEST_IMAGES or label_count != EXPECTED_TEST_LABELS:
        raise RuntimeError(
            "Frozen test split count mismatch: "
            f"images={image_count}/{EXPECTED_TEST_IMAGES}, "
            f"labels={label_count}/{EXPECTED_TEST_LABELS}"
        )

    return data, test_images, test_labels


def main() -> None:
    os.chdir(REPO_ROOT)
    if not MODEL_PATH.is_file():
        raise RuntimeError(f"Candidate A checkpoint is unavailable: {MODEL_PATH}")
    if not DATA_YAML.is_file():
        raise RuntimeError(f"Dataset YAML is unavailable: {DATA_YAML}")

    _, test_images, test_labels = resolve_dataset_paths()
    contract = {
        "split": "test",
        "image_count": EXPECTED_TEST_IMAGES,
        "label_count": EXPECTED_TEST_LABELS,
        "imgsz": 960,
        "batch": 8,
        "device": 0,
        "workers": 8,
        "conf": 0.001,
        "iou": 0.7,
        "max_det": 300,
        "rect": True,
        "half": False,
        "augment": False,
        "save_json": False,
        "plots": False,
    }

    print("OFFICIAL_ULTRALYTICS_TEST_REFERENCE_START")
    print(f"MODEL={repo_relative(MODEL_PATH)}")
    print(f"MODEL_SHA256={sha256(MODEL_PATH)}")
    print(f"DATA={repo_relative(DATA_YAML)}")
    print(f"TEST_IMAGES={repo_relative(test_images)}")
    print(f"TEST_IMAGE_COUNT={EXPECTED_TEST_IMAGES}")
    print(f"TEST_LABEL_COUNT={EXPECTED_TEST_LABELS}")
    print(f"ULTRALYTICS_VERSION={ultralytics.__version__}")
    print(f"CONTRACT={json.dumps(contract, sort_keys=True)}")

    model = YOLO(str(MODEL_PATH))
    metrics = model.val(
        data=str(DATA_YAML),
        split="test",
        imgsz=960,
        batch=8,
        device=0,
        workers=8,
        conf=0.001,
        iou=0.7,
        max_det=300,
        rect=True,
        half=False,
        augment=False,
        save_json=False,
        plots=False,
        project=str(RUNS_DIR),
        name="candidate_a_test_reference",
        exist_ok=True,
        verbose=True,
    )

    results = {key: float(value) for key, value in metrics.results_dict.items()}
    official_map = results["metrics/mAP50-95(B)"]
    report = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Official Ultralytics PyTorch evaluation of Candidate A on the frozen test split",
        "model": {
            "path": repo_relative(MODEL_PATH),
            "sha256": sha256(MODEL_PATH),
        },
        "dataset": {
            "yaml": repo_relative(DATA_YAML),
            "yaml_sha256": sha256(DATA_YAML),
            "test_images": repo_relative(test_images),
            "test_labels": repo_relative(test_labels),
            "image_count": EXPECTED_TEST_IMAGES,
            "label_count": EXPECTED_TEST_LABELS,
        },
        "contract": contract,
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "ultralytics": ultralytics.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "metrics": results,
        "speed_ms_per_image": {key: float(value) for key, value in metrics.speed.items()},
        "ultralytics_save_dir": repo_relative(Path(metrics.save_dir)),
        "comparison": {
            "custom_test_map50_95_reference": CUSTOM_TEST_MAP50_95_REFERENCE,
            "delta_official_minus_custom": official_map - CUSTOM_TEST_MAP50_95_REFERENCE,
            "historical_validation_map50_95_approx": HISTORICAL_VALIDATION_MAP50_95,
            "gate": "PENDING_REVIEW",
        },
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"ULTRALYTICS_TEST_MAP50_95={official_map:.10f}")
    print(f"CUSTOM_TEST_MAP50_95_REFERENCE={CUSTOM_TEST_MAP50_95_REFERENCE:.10f}")
    print(f"DELTA_VS_CUSTOM={official_map - CUSTOM_TEST_MAP50_95_REFERENCE:+.10f}")
    print(f"HISTORICAL_VALIDATION_MAP50_95_APPROX={HISTORICAL_VALIDATION_MAP50_95:.10f}")
    print("PROVENANCE_GATE=PENDING_REVIEW")
    print(f"REPORT={repo_relative(REPORT_PATH)}")


if __name__ == "__main__":
    main()
