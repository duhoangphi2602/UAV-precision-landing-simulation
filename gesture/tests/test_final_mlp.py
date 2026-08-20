"""Static gates for the frozen all-data production MLP recipe."""

import json
from pathlib import Path

from gesture.contracts import PREPROCESSING_VERSION
from gesture.train_final_mlp import contains_runtime_path_dependency, validate_final_config


def test_final_config_exactly_inherits_frozen_mlp_v1_recipe():
    final = json.loads(Path("gesture/configs/mlp_v1_final.json").read_text())
    baseline = json.loads(Path("gesture/configs/mlp_v1.json").read_text())
    validate_final_config(final, baseline)
    assert final["expected_sample_count"] == 2786
    assert final["preprocessing_version"] == PREPROCESSING_VERSION
    assert final["training"]["epochs"] == 80


def test_runtime_dependency_guard_rejects_paths_but_accepts_hash_metadata():
    assert not contains_runtime_path_dependency(
        {"manifest_sha256": "a" * 64, "class_order": ["HOLD", "AUTO_LAND"]}
    )
    assert contains_runtime_path_dependency({"manifest": "gesture/data/data.jsonl"})
