"""Unit gates for the fixed PyTorch grouped-CV MLP baseline."""

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from gesture.contracts import GESTURE_CLASSES
from gesture.mlp_baseline import (
    CLASS_TO_INDEX,
    FeatureStandardizer,
    GestureMLP,
    LoadedManifest,
    classification_metrics,
    load_manifest,
    parameter_count,
    safety_class_metrics,
    validate_grouped_fold,
)
from gesture.train_mlp_cv import validate_config


def synthetic_manifest(hand: str, prefix: str) -> LoadedManifest:
    records = []
    features = []
    targets = []
    for index, label in enumerate(GESTURE_CLASSES):
        records.append(
            {
                "sample_id": f"{prefix}-{index}",
                "session_id": f"{prefix}-{label.lower()}",
                "frame_path": f"sessions/{prefix}/{index}.jpg",
                "hand_scope": hand,
                "label": label,
            }
        )
        feature = np.zeros(63, dtype=np.float32)
        feature[index] = float(index + 1)
        features.append(feature)
        targets.append(index)
    return LoadedManifest(
        Path(f"/{prefix}.jsonl"),
        records,
        np.stack(features),
        np.asarray(targets, dtype=np.int64),
    )


def test_class_mapping_and_model_architecture_are_frozen():
    assert tuple(CLASS_TO_INDEX) == GESTURE_CLASSES
    assert CLASS_TO_INDEX == {
        label: index for index, label in enumerate(GESTURE_CLASSES)
    }
    model = GestureMLP()
    output = model(torch.zeros(3, 63))
    assert output.shape == (3, 7)
    assert parameter_count(model) == 16903


def test_standardizer_uses_only_explicit_train_rows():
    train = np.stack(
        (np.zeros(63, dtype=np.float32), np.full(63, 2.0, dtype=np.float32))
    )
    evaluation = np.full((1, 63), 100.0, dtype=np.float32)
    scaler = FeatureStandardizer.fit(train, ("train-1", "train-2"))
    np.testing.assert_allclose(scaler.mean, 1.0)
    np.testing.assert_allclose(scaler.std, 1.0)
    np.testing.assert_allclose(scaler.transform(train).mean(axis=0), 0.0)
    assert float(scaler.transform(evaluation).mean()) == pytest.approx(99.0)
    assert scaler.fit_sample_count == 2
    assert scaler.to_dict()["fit_scope"] == "TRAIN_FOLD_ONLY"


def test_grouped_fold_integrity_accepts_cross_hand_and_rejects_session_leakage():
    train = synthetic_manifest("right", "right")
    evaluation = synthetic_manifest("left", "left")
    integrity = validate_grouped_fold(train, evaluation, "right", "left")
    assert integrity["sample_overlap"] == 0
    assert integrity["session_overlap"] == 0

    evaluation.records[0]["session_id"] = train.records[0]["session_id"]
    with pytest.raises(ValueError, match="session leakage"):
        validate_grouped_fold(train, evaluation, "right", "left")


def test_manifest_loader_rejects_wrong_feature_dimension(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(
            {
                "sample_id": "sample-1",
                "session_id": "session-1",
                "frame_path": "frame.jpg",
                "hand_scope": "right",
                "label": "HOLD",
                "normalized_feature": [0.0] * 62,
            }
        )
        + "\n"
    )
    with pytest.raises(ValueError, match=r"\[N, 63\]"):
        load_manifest(path)


def test_classification_and_safety_metrics_have_explicit_denominators():
    targets = np.asarray([0, 0, 1, 2, 6, 6, 5], dtype=np.int64)
    predictions = np.asarray([0, 1, 0, 2, 6, 5, 6], dtype=np.int64)
    metrics = classification_metrics(targets, predictions)
    assert np.asarray(metrics["confusion_matrix"]).shape == (7, 7)

    takeoff = safety_class_metrics(targets, predictions, "TAKEOFF")
    assert takeoff["false_positive_count"] == 1
    assert takeoff["false_negative_count"] == 1
    assert takeoff["positive_support"] == 2
    assert takeoff["negative_support"] == 5

    auto_land = safety_class_metrics(targets, predictions, "AUTO_LAND")
    assert auto_land["false_positive_count"] == 1
    assert auto_land["false_negative_count"] == 1


def test_checked_in_config_matches_frozen_recipe():
    config = json.loads(Path("gesture/configs/mlp_v1.json").read_text())
    validate_config(config)
    assert config["training"]["checkpoint_policy"] == (
        "FINAL_EPOCH_NO_EVAL_SELECTION"
    )
    assert config["training"]["early_stopping"] is False
