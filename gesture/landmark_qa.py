#!/usr/bin/env python3
"""Focused quality audit for the frozen 63D gesture landmark features."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors

from gesture.contracts import GESTURE_CLASSES


PALM_SCALE_HARD_MIN = 1e-6
PALM_SCALE_NEAR_ZERO = 0.05
NEAR_DUPLICATE_RMS = 0.015
GROSS_FEATURE_ABS_MAX = 3.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-root", type=Path, default=Path("gesture/data/v1")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authoritative-manifest", type=Path)
    return parser.parse_args()


def quantiles(values: np.ndarray) -> dict[str, float]:
    points = np.quantile(values, (0.0, 0.01, 0.5, 0.99, 1.0))
    return dict(zip(("min", "p01", "median", "p99", "max"), map(float, points)))


def main() -> int:
    args = parse_args()
    dataset_root = args.dataset_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else dataset_root / "qa" / "landmark_qa.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    authoritative_path = (
        args.authoritative_manifest.resolve()
        if args.authoritative_manifest is not None
        else dataset_root / "manifests" / "authoritative_samples.jsonl"
    )
    authoritative_rows = [
        json.loads(line)
        for line in authoritative_path.read_text().splitlines()
        if line.strip()
    ]
    authoritative_ids = {row["sample_id"] for row in authoritative_rows}
    if len(authoritative_ids) != len(authoritative_rows):
        raise ValueError("authoritative manifest contains duplicate sample IDs")

    rows: list[dict[str, Any]] = []
    malformed: list[str] = []
    session_ids: set[str] = set()
    original_source_samples = 0
    for session_directory in sorted(
        path for path in (dataset_root / "sessions").iterdir() if path.is_dir()
    ):
        metadata = json.loads((session_directory / "session.json").read_text())
        session_ids.add(metadata["session_id"])
        for line in (session_directory / "manifest.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            original_source_samples += 1
            if row["sample_id"] not in authoritative_ids:
                continue
            feature = np.asarray(row.get("normalized_feature"), dtype=np.float32)
            landmarks = np.asarray(row.get("image_landmarks"), dtype=np.float32)
            if feature.shape != (63,) or landmarks.shape != (21, 3):
                malformed.append(row.get("sample_id", "UNKNOWN"))
                continue
            row["session_hand"] = metadata["hand_scope"]
            row["feature_array"] = feature
            row["landmark_array"] = landmarks
            rows.append(row)

    loaded_ids = {row["sample_id"] for row in rows}
    if loaded_ids != authoritative_ids:
        missing = sorted(authoritative_ids - loaded_ids)
        raise ValueError(f"authoritative samples missing from source manifests: {missing}")

    features = np.stack([row["feature_array"] for row in rows])
    landmarks = np.stack([row["landmark_array"] for row in rows])
    labels = np.asarray([row["label"] for row in rows])
    hands = np.asarray([row["session_hand"] for row in rows])
    detected_hands = np.asarray([row["handedness"].lower() for row in rows])
    sample_ids = np.asarray([row["sample_id"] for row in rows])
    finite_rows = np.isfinite(features).all(axis=1)
    palm_scales = np.linalg.norm(
        landmarks[:, 9, :2] - landmarks[:, 0, :2], axis=1
    )

    handedness_mismatch_indices = np.where(hands != detected_hands)[0]
    handedness_mismatches = [
        {
            "sample_id": str(sample_ids[index]),
            "label": str(labels[index]),
            "session_hand": str(hands[index]),
            "detected_handedness": str(detected_hands[index]),
            "score": float(rows[index]["handedness_score"]),
        }
        for index in handedness_mismatch_indices
    ]

    vector_hashes = Counter(
        hashlib.sha256(feature.tobytes()).hexdigest() for feature in features
    )
    duplicate_groups = [count for count in vector_hashes.values() if count > 1]

    nearest = NearestNeighbors(n_neighbors=2, metric="euclidean").fit(features)
    nearest_distances, _ = nearest.kneighbors(features)
    nearest_rms = nearest_distances[:, 1] / math.sqrt(63)
    near_duplicate_by_class = {
        label: int(np.sum(nearest_rms[labels == label] < NEAR_DUPLICATE_RMS))
        for label in GESTURE_CLASSES
    }

    consecutive_rms: list[float] = []
    for session_id in sorted(session_ids):
        session_features = np.stack(
            [
                row["feature_array"]
                for row in rows
                if row["session_id"] == session_id
            ]
        )
        if len(session_features) > 1:
            distances = np.linalg.norm(np.diff(session_features, axis=0), axis=1)
            consecutive_rms.extend((distances / math.sqrt(63)).tolist())
    consecutive_array = np.asarray(consecutive_rms)

    per_class_centroid = {
        label: features[labels == label].mean(axis=0) for label in GESTURE_CLASSES
    }
    within_class_rms = {
        label: float(
            np.mean(
                np.linalg.norm(
                    features[labels == label] - per_class_centroid[label], axis=1
                )
                / math.sqrt(63)
            )
        )
        for label in GESTURE_CLASSES
    }
    centroid_pairs: list[dict[str, Any]] = []
    for first_index, first in enumerate(GESTURE_CLASSES):
        for second in GESTURE_CLASSES[first_index + 1 :]:
            centroid_pairs.append(
                {
                    "first": first,
                    "second": second,
                    "rms_distance": float(
                        np.linalg.norm(
                            per_class_centroid[first] - per_class_centroid[second]
                        )
                        / math.sqrt(63)
                    ),
                }
            )
    centroid_pairs.sort(key=lambda value: value["rms_distance"])
    centroid_predictions = np.asarray(
        [
            min(
                GESTURE_CLASSES,
                key=lambda label: np.linalg.norm(
                    feature - per_class_centroid[label]
                ),
            )
            for feature in features
        ]
    )

    cross_hand_centroid_accuracy: dict[str, float] = {}
    hand_gaps: dict[str, dict[str, float]] = {}
    for train_hand, eval_hand in (("right", "left"), ("left", "right")):
        hand_centroids = {
            label: features[(labels == label) & (hands == train_hand)].mean(axis=0)
            for label in GESTURE_CLASSES
        }
        predictions = np.asarray(
            [
                min(
                    GESTURE_CLASSES,
                    key=lambda label: np.linalg.norm(feature - hand_centroids[label]),
                )
                for feature in features[hands == eval_hand]
            ]
        )
        cross_hand_centroid_accuracy[f"{train_hand}_to_{eval_hand}"] = float(
            np.mean(predictions == labels[hands == eval_hand])
        )
    for label in GESTURE_CLASSES:
        right_centroid = features[(labels == label) & (hands == "right")].mean(
            axis=0
        )
        left_centroid = features[(labels == label) & (hands == "left")].mean(
            axis=0
        )
        gap = float(np.linalg.norm(right_centroid - left_centroid) / math.sqrt(63))
        hand_gaps[label] = {
            "centroid_rms": gap,
            "relative_to_within_class_rms": gap / within_class_rms[label],
        }

    class_centroid_distance = np.asarray(
        [
            np.linalg.norm(feature - per_class_centroid[label]) / math.sqrt(63)
            for feature, label in zip(features, labels)
        ]
    )
    robust_scores = np.zeros(len(rows), dtype=np.float64)
    for label in GESTURE_CLASSES:
        mask = labels == label
        values = class_centroid_distance[mask]
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        robust_scores[mask] = (values - median) / max(1.4826 * mad, 1e-9)
    gross_mask = np.max(np.abs(features), axis=1) > GROSS_FEATURE_ABS_MAX
    top_outlier_indices = np.argsort(robust_scores)[-20:][::-1]

    structural_pass = (
        not malformed
        and bool(np.all(finite_rows))
        and len(rows) == len(authoritative_ids)
        and len(set(sample_ids.tolist())) == len(rows)
        and len(session_ids) == 14
        and set(labels.tolist()) == set(GESTURE_CLASSES)
    )
    issues: list[str] = []
    if handedness_mismatches:
        issues.append(f"handedness_session_mismatch={len(handedness_mismatches)}")
    near_zero_count = int(np.sum(palm_scales < PALM_SCALE_NEAR_ZERO))
    hard_scale_count = int(np.sum(palm_scales <= PALM_SCALE_HARD_MIN))
    if near_zero_count:
        issues.append(f"near_zero_palm_scale={near_zero_count}")
    gross_count = int(np.sum(gross_mask))
    if gross_count:
        issues.append(f"gross_feature_outliers={gross_count}")
    qa_pass = structural_pass and not issues and hard_scale_count == 0

    report: dict[str, Any] = {
        "contract": "FROZEN_63D_LANDMARK_QA",
        "verdict": "PASS" if qa_pass else "FAIL",
        "dataset": {
            "original_source_samples": original_source_samples,
            "excluded_samples": original_source_samples - len(rows),
            "samples": len(rows),
            "sessions": len(session_ids),
            "classes": dict(sorted(Counter(labels.tolist()).items())),
            "hands": dict(sorted(Counter(hands.tolist()).items())),
            "sessions_per_class": {
                label: len(
                    {
                        row["session_id"]
                        for row in rows
                        if row["label"] == label
                    }
                )
                for label in GESTURE_CLASSES
            },
            "samples_per_class_and_hand": {
                label: {
                    hand: int(np.sum((labels == label) & (hands == hand)))
                    for hand in ("right", "left")
                }
                for label in GESTURE_CLASSES
            },
            "unique_sample_ids": len(set(sample_ids.tolist())),
            "authoritative_manifest": str(authoritative_path),
            "authoritative_manifest_sha256": hashlib.sha256(
                authoritative_path.read_bytes()
            ).hexdigest(),
        },
        "integrity": {
            "malformed_feature_or_landmark_rows": malformed,
            "non_finite_feature_rows": int(np.sum(~finite_rows)),
            "feature_dimension": 63,
            "structural_pass": structural_pass,
        },
        "palm_scale": {
            "hard_min_threshold": PALM_SCALE_HARD_MIN,
            "near_zero_threshold": PALM_SCALE_NEAR_ZERO,
            "hard_failures": hard_scale_count,
            "hard_failure_sample_ids": sample_ids[
                palm_scales <= PALM_SCALE_HARD_MIN
            ].tolist(),
            "near_zero_count": near_zero_count,
            "near_zero_sample_ids": sample_ids[
                palm_scales < PALM_SCALE_NEAR_ZERO
            ].tolist(),
            "distribution": quantiles(palm_scales),
        },
        "handedness": {
            "mismatch_count": len(handedness_mismatches),
            "mismatch_rate": len(handedness_mismatches) / len(rows),
            "mismatches": handedness_mismatches,
        },
        "duplicates": {
            "exact_duplicate_groups": len(duplicate_groups),
            "samples_in_exact_duplicate_groups": sum(duplicate_groups),
            "nearest_neighbor_rms": quantiles(nearest_rms),
            "nearest_neighbor_below_0_015": int(
                np.sum(nearest_rms < NEAR_DUPLICATE_RMS)
            ),
            "nearest_neighbor_below_0_015_by_class": near_duplicate_by_class,
            "consecutive_rms": quantiles(consecutive_array),
            "consecutive_below_0_015": int(
                np.sum(consecutive_array < NEAR_DUPLICATE_RMS)
            ),
        },
        "normalized_coordinates": {
            "global_min": float(np.min(features)),
            "global_max": float(np.max(features)),
            "absolute_distribution": quantiles(np.abs(features).ravel()),
            "wrist_absolute_max": float(
                np.max(np.abs(features.reshape(-1, 21, 3)[:, 0]))
            ),
            "palm_axis_x_absolute_max": float(
                np.max(np.abs(features.reshape(-1, 21, 3)[:, 9, 0]))
            ),
            "palm_axis_y_error_max": float(
                np.max(np.abs(features.reshape(-1, 21, 3)[:, 9, 1] + 1.0))
            ),
        },
        "outliers": {
            "gross_abs_threshold": GROSS_FEATURE_ABS_MAX,
            "gross_count": gross_count,
            "gross_sample_ids": sample_ids[gross_mask].tolist(),
            "robust_z_above_6": int(np.sum(robust_scores > 6.0)),
            "robust_z_above_10": int(np.sum(robust_scores > 10.0)),
            "top_robust_outliers": [
                {
                    "sample_id": str(sample_ids[index]),
                    "label": str(labels[index]),
                    "robust_z": float(robust_scores[index]),
                    "centroid_rms": float(class_centroid_distance[index]),
                    "feature_abs_max": float(np.max(np.abs(features[index]))),
                }
                for index in top_outlier_indices
            ],
        },
        "separability": {
            "nearest_centroid_accuracy": float(
                np.mean(centroid_predictions == labels)
            ),
            "silhouette_score": float(
                silhouette_score(features, labels, metric="euclidean")
            ),
            "within_class_rms": within_class_rms,
            "closest_centroid_pairs": centroid_pairs[:10],
            "cross_hand_centroid_accuracy": cross_hand_centroid_accuracy,
            "left_right_centroid_gap": hand_gaps,
        },
        "issues": issues,
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(output)
    print(f"LANDMARK_QA={report['verdict']}")
    print(f"DATA_QUALITY_ISSUES={','.join(issues) if issues else 'NONE'}")
    print(f"LANDMARK_QA_REPORT={output}")
    return 0 if qa_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
