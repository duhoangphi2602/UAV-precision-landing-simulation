"""Reusable contracts for the Slice 5 PyTorch MLP baseline."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from torch import nn

from gesture.contracts import GESTURE_CLASSES


CLASS_TO_INDEX = {label: index for index, label in enumerate(GESTURE_CLASSES)}


@dataclass(frozen=True)
class LoadedManifest:
    path: Path
    records: list[dict[str, Any]]
    features: np.ndarray
    targets: np.ndarray


@dataclass(frozen=True)
class FeatureStandardizer:
    mean: np.ndarray
    std: np.ndarray
    fit_sample_count: int
    fit_sample_ids_sha256: str

    @classmethod
    def fit(
        cls, features: np.ndarray, sample_ids: Sequence[str]
    ) -> "FeatureStandardizer":
        values = np.asarray(features, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != 63 or len(values) == 0:
            raise ValueError("standardizer expects a non-empty [N, 63] train array")
        if len(sample_ids) != len(values):
            raise ValueError("sample ID count does not match standardizer rows")
        mean = values.mean(axis=0, dtype=np.float64).astype(np.float32)
        std = values.std(axis=0, dtype=np.float64).astype(np.float32)
        std = np.where(std < 1e-8, 1.0, std).astype(np.float32)
        digest = hashlib.sha256("\n".join(sample_ids).encode("utf-8")).hexdigest()
        return cls(mean, std, len(values), digest)

    def transform(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != 63:
            raise ValueError("standardizer transform expects [N, 63]")
        transformed = (values - self.mean) / self.std
        if not np.isfinite(transformed).all():
            raise ValueError("standardized features contain NaN or infinity")
        return transformed.astype(np.float32, copy=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "fit_sample_count": self.fit_sample_count,
            "fit_sample_ids_sha256": self.fit_sample_ids_sha256,
            "fit_scope": "TRAIN_FOLD_ONLY",
        }


class GestureMLP(nn.Module):
    """Frozen compact v1 architecture: 63→128→64→7."""

    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(63, 128),
            nn.ReLU(),
            nn.Dropout(0.20),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(64, len(GESTURE_CLASSES)),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features)


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def set_determinism(seed: int, torch_num_threads: int = 1) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(torch_num_threads)
    torch.use_deterministic_algorithms(True)


def load_manifest(path: Path) -> LoadedManifest:
    resolved = path.resolve()
    records = [
        json.loads(line) for line in resolved.read_text().splitlines() if line.strip()
    ]
    if not records:
        raise ValueError(f"empty manifest: {resolved}")
    sample_ids = [row["sample_id"] for row in records]
    frame_paths = [row["frame_path"] for row in records]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError(f"duplicate sample IDs in {resolved}")
    if len(frame_paths) != len(set(frame_paths)):
        raise ValueError(f"duplicate frame paths in {resolved}")

    features = np.asarray(
        [row["normalized_feature"] for row in records], dtype=np.float32
    )
    if features.shape != (len(records), 63):
        raise ValueError(f"manifest features must be [N, 63]: {resolved}")
    if not np.isfinite(features).all():
        raise ValueError(f"manifest contains NaN or infinity: {resolved}")
    try:
        targets = np.asarray(
            [CLASS_TO_INDEX[row["label"]] for row in records], dtype=np.int64
        )
    except KeyError as error:
        raise ValueError(f"unknown class in {resolved}: {error}") from error
    return LoadedManifest(resolved, records, features, targets)


def validate_grouped_fold(
    train: LoadedManifest,
    evaluation: LoadedManifest,
    expected_train_hand: str,
    expected_eval_hand: str,
) -> dict[str, Any]:
    train_samples = {row["sample_id"] for row in train.records}
    eval_samples = {row["sample_id"] for row in evaluation.records}
    train_paths = {row["frame_path"] for row in train.records}
    eval_paths = {row["frame_path"] for row in evaluation.records}
    train_sessions = {row["session_id"] for row in train.records}
    eval_sessions = {row["session_id"] for row in evaluation.records}
    train_hands = {row["hand_scope"] for row in train.records}
    eval_hands = {row["hand_scope"] for row in evaluation.records}
    train_classes = {row["label"] for row in train.records}
    eval_classes = {row["label"] for row in evaluation.records}
    expected_classes = set(GESTURE_CLASSES)

    if train_samples & eval_samples:
        raise ValueError("sample leakage between train and eval")
    if train_paths & eval_paths:
        raise ValueError("frame-path leakage between train and eval")
    if train_sessions & eval_sessions:
        raise ValueError("session leakage between train and eval")
    if train_hands != {expected_train_hand}:
        raise ValueError(f"unexpected train hand group: {train_hands}")
    if eval_hands != {expected_eval_hand}:
        raise ValueError(f"unexpected eval hand group: {eval_hands}")
    if train_classes != expected_classes or eval_classes != expected_classes:
        raise ValueError("all seven classes must appear on both fold sides")

    return {
        "train_samples": len(train.records),
        "eval_samples": len(evaluation.records),
        "train_sessions": sorted(train_sessions),
        "eval_sessions": sorted(eval_sessions),
        "sample_overlap": 0,
        "path_overlap": 0,
        "session_overlap": 0,
        "train_hand": expected_train_hand,
        "eval_hand": expected_eval_hand,
    }


def classification_metrics(
    targets: np.ndarray, predictions: np.ndarray
) -> dict[str, Any]:
    labels = np.arange(len(GESTURE_CLASSES))
    precision, recall, f1, support = precision_recall_fscore_support(
        targets,
        predictions,
        labels=labels,
        zero_division=0,
    )
    matrix = confusion_matrix(targets, predictions, labels=labels)
    return {
        "accuracy": float(np.mean(targets == predictions)),
        "macro_precision": float(np.mean(precision)),
        "macro_recall": float(np.mean(recall)),
        "macro_f1": float(np.mean(f1)),
        "per_class": {
            label: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index, label in enumerate(GESTURE_CLASSES)
        },
        "confusion_matrix": matrix.tolist(),
    }


def safety_class_metrics(
    targets: np.ndarray, predictions: np.ndarray, class_label: str
) -> dict[str, Any]:
    class_index = CLASS_TO_INDEX[class_label]
    positives = targets == class_index
    negatives = ~positives
    predicted_positive = predictions == class_index
    false_positive_count = int(np.sum(negatives & predicted_positive))
    false_negative_count = int(np.sum(positives & ~predicted_positive))
    return {
        "false_positive_count": false_positive_count,
        "false_positive_rate": false_positive_count / max(int(np.sum(negatives)), 1),
        "false_negative_count": false_negative_count,
        "false_negative_rate": false_negative_count / max(int(np.sum(positives)), 1),
        "positive_support": int(np.sum(positives)),
        "negative_support": int(np.sum(negatives)),
    }


def confidence_distribution(
    confidences: np.ndarray, correct: np.ndarray, bins: int
) -> dict[str, Any]:
    edges = np.linspace(0.0, 1.0, bins + 1)

    def summarize(values: np.ndarray) -> dict[str, Any]:
        histogram, _ = np.histogram(values, bins=edges)
        if len(values) == 0:
            return {
                "count": 0,
                "mean": None,
                "p50": None,
                "p90": None,
                "histogram": histogram.tolist(),
            }
        return {
            "count": len(values),
            "mean": float(np.mean(values)),
            "p50": float(np.quantile(values, 0.5)),
            "p90": float(np.quantile(values, 0.9)),
            "histogram": histogram.tolist(),
        }

    return {
        "bin_edges": edges.tolist(),
        "all": summarize(confidences),
        "correct": summarize(confidences[correct]),
        "errors": summarize(confidences[~correct]),
    }
