#!/usr/bin/env python3
"""Evaluate the frozen thumb-extension safety veto without MLP retraining."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from gesture.contracts import GESTURE_CLASSES
from gesture.mlp_baseline import (
    CLASS_TO_INDEX,
    classification_metrics,
    load_manifest,
    safety_class_metrics,
)
from gesture.thumb_veto import (
    ALLOWED,
    AUTO_LAND,
    REJECTED_BY_THUMB_VETO,
    derive_train_only_threshold,
    thumb_extension_score,
    thumb_veto_status,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REJECTED_COMMAND_INDEX = -1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=Path("gesture/configs/thumb_veto_v1.json")
    )
    return parser.parse_args()


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def validate_config(config: dict[str, Any]) -> None:
    rule = config["rule"]
    if config.get("terminology") != "GROUPED CROSS-HAND 2-FOLD CV":
        raise ValueError("thumb veto must retain grouped cross-hand CV terminology")
    if rule.get("name") != "THUMB_STRAIGHTNESS_TIMES_PALM_REACH":
        raise ValueError("unexpected thumb rule")
    if rule.get("applies_only_when_predicted_class") != AUTO_LAND:
        raise ValueError("thumb veto may only gate AUTO_LAND")
    if rule.get("rejected_status") != REJECTED_BY_THUMB_VETO:
        raise ValueError("unexpected veto status")
    if rule.get("threshold_scope") != "TRAIN_FOLD_ONLY":
        raise ValueError("threshold must be fit on the train fold only")


def command_metrics(targets: np.ndarray, commands: np.ndarray) -> dict[str, Any]:
    """Score seven commands while keeping rejection outside the class set."""

    metrics = classification_metrics(targets, commands)
    metrics["rejected_command_count"] = int(
        np.sum(commands == REJECTED_COMMAND_INDEX)
    )
    metrics["confusion_matrix_note"] = (
        "REJECTED commands are false negatives for their true class and are not "
        "silently assigned to any of the seven class columns."
    )
    metrics["rejected_by_true_class"] = {
        label: int(
            np.sum(
                (targets == CLASS_TO_INDEX[label])
                & (commands == REJECTED_COMMAND_INDEX)
            )
        )
        for label in GESTURE_CLASSES
    }
    return metrics


def evaluate_fold(
    fold_name: str, fold_config: dict[str, Any], config: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray, np.ndarray, np.ndarray]:
    train = load_manifest(resolve_repo_path(fold_config["train_manifest"]))
    evaluation = load_manifest(resolve_repo_path(fold_config["eval_manifest"]))
    prediction_path = resolve_repo_path(fold_config["predictions"])
    prediction_rows = read_jsonl(prediction_path)
    raw_metrics = json.loads(resolve_repo_path(fold_config["raw_metrics"]).read_text())

    if len(prediction_rows) != len(evaluation.records):
        raise ValueError(f"{fold_name}: prediction/eval row count mismatch")
    prediction_by_id = {row["sample_id"]: row for row in prediction_rows}
    if len(prediction_by_id) != len(prediction_rows):
        raise ValueError(f"{fold_name}: duplicate prediction sample IDs")
    eval_ids = {row["sample_id"] for row in evaluation.records}
    if set(prediction_by_id) != eval_ids:
        raise ValueError(f"{fold_name}: prediction/eval sample IDs differ")

    minimum_retention = float(config["rule"]["minimum_train_auto_land_retention"])
    auto_land_train = train.features[train.targets == CLASS_TO_INDEX[AUTO_LAND]]
    threshold = derive_train_only_threshold(auto_land_train, minimum_retention)

    targets: list[int] = []
    raw_predictions: list[int] = []
    filtered_commands: list[int] = []
    decisions: list[dict[str, Any]] = []
    for record, target in zip(evaluation.records, evaluation.targets):
        prediction = prediction_by_id[record["sample_id"]]
        true_label = GESTURE_CLASSES[int(target)]
        if prediction["true_label"] != true_label:
            raise ValueError(f"{fold_name}: true-label mismatch for {record['sample_id']}")
        predicted_label = prediction["predicted_label"]
        score = thumb_extension_score(record["normalized_feature"])
        status = thumb_veto_status(predicted_label, score, threshold.value)
        raw_index = CLASS_TO_INDEX[predicted_label]
        command_index = (
            REJECTED_COMMAND_INDEX
            if status == REJECTED_BY_THUMB_VETO
            else raw_index
        )
        targets.append(int(target))
        raw_predictions.append(raw_index)
        filtered_commands.append(command_index)
        decisions.append(
            {
                "sample_id": record["sample_id"],
                "session_id": record["session_id"],
                "true_label": true_label,
                "raw_predicted_label": predicted_label,
                "raw_confidence": float(prediction["confidence"]),
                "thumb_extension_score": score,
                "thumb_threshold": threshold.value,
                "prediction_status": status,
                "effective_command": (
                    None if command_index == REJECTED_COMMAND_INDEX else predicted_label
                ),
            }
        )

    target_array = np.asarray(targets, dtype=np.int64)
    raw_array = np.asarray(raw_predictions, dtype=np.int64)
    command_array = np.asarray(filtered_commands, dtype=np.int64)
    recomputed_raw = classification_metrics(target_array, raw_array)
    for key in ("accuracy", "macro_precision", "macro_recall", "macro_f1"):
        if not np.isclose(recomputed_raw[key], raw_metrics[key], atol=1e-12):
            raise AssertionError(f"{fold_name}: raw {key} does not match MLP artifact")

    veto_mask = command_array == REJECTED_COMMAND_INDEX
    auto_land_index = CLASS_TO_INDEX[AUTO_LAND]
    correct_veto_mask = veto_mask & (target_array != auto_land_index)
    incorrect_veto_mask = veto_mask & (target_array == auto_land_index)
    right_index = CLASS_TO_INDEX["RIGHT"]
    right_to_auto_before = int(
        np.sum((target_array == right_index) & (raw_array == auto_land_index))
    )
    right_to_auto_after = int(
        np.sum(
            (target_array == right_index)
            & (command_array == auto_land_index)
        )
    )
    raw_safety = {
        label: safety_class_metrics(target_array, raw_array, label)
        for label in ("TAKEOFF", AUTO_LAND)
    }
    filtered_safety = {
        label: safety_class_metrics(target_array, command_array, label)
        for label in ("TAKEOFF", AUTO_LAND)
    }
    result = {
        "fold": fold_name,
        "direction": fold_config["direction"],
        "terminology": config["terminology"],
        "threshold": threshold.to_dict(),
        "threshold_inputs": {
            "manifest": str(resolve_repo_path(fold_config["train_manifest"])),
            "class": AUTO_LAND,
            "evaluation_rows_used": 0,
        },
        "raw_mlp_metrics": recomputed_raw,
        "raw_safety": raw_safety,
        "safety_filtered_command_metrics": command_metrics(
            target_array, command_array
        ),
        "filtered_safety": filtered_safety,
        "veto_activations": int(np.sum(veto_mask)),
        "correct_vetoes": int(np.sum(correct_veto_mask)),
        "incorrect_vetoes": int(np.sum(incorrect_veto_mask)),
        "true_auto_land_vetoed": int(np.sum(incorrect_veto_mask)),
        "right_to_auto_land_before": right_to_auto_before,
        "right_to_auto_land_after": right_to_auto_after,
        "takeoff_safety_metrics_unchanged": (
            raw_safety["TAKEOFF"] == filtered_safety["TAKEOFF"]
        ),
    }
    return result, decisions, target_array, raw_array, command_array


def main() -> int:
    args = parse_args()
    config_path = resolve_repo_path(args.config)
    config = json.loads(config_path.read_text())
    validate_config(config)
    output = resolve_repo_path(config["output_directory"])
    if output.exists():
        raise FileExistsError(f"thumb-veto output already exists: {output}")
    output.mkdir(parents=True)
    shutil.copy2(config_path, output / "config.source.json")

    fold_results: dict[str, dict[str, Any]] = {}
    all_targets: list[np.ndarray] = []
    all_raw: list[np.ndarray] = []
    all_commands: list[np.ndarray] = []
    for fold_name in ("fold_a", "fold_b"):
        fold_output = output / fold_name
        fold_output.mkdir()
        result, decisions, targets, raw, commands = evaluate_fold(
            fold_name, config["folds"][fold_name], config
        )
        fold_results[fold_name] = result
        all_targets.append(targets)
        all_raw.append(raw)
        all_commands.append(commands)
        write_json(fold_output / "summary.json", result)
        (fold_output / "decisions.jsonl").write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in decisions)
        )

    targets = np.concatenate(all_targets)
    raw = np.concatenate(all_raw)
    commands = np.concatenate(all_commands)
    raw_safety = {
        label: safety_class_metrics(targets, raw, label)
        for label in ("TAKEOFF", AUTO_LAND)
    }
    filtered_safety = {
        label: safety_class_metrics(targets, commands, label)
        for label in ("TAKEOFF", AUTO_LAND)
    }
    veto_mask = commands == REJECTED_COMMAND_INDEX
    auto_land_index = CLASS_TO_INDEX[AUTO_LAND]
    before = raw_safety[AUTO_LAND]
    after = filtered_safety[AUTO_LAND]
    recall_before = 1.0 - before["false_negative_rate"]
    recall_after = 1.0 - after["false_negative_rate"]
    fp_reduction = (
        (before["false_positive_count"] - after["false_positive_count"])
        / max(before["false_positive_count"], 1)
    )
    acceptance = config["acceptance"]
    takeoff_unchanged = raw_safety["TAKEOFF"] == filtered_safety["TAKEOFF"]
    accepted = (
        after["false_positive_rate"]
        <= float(acceptance["maximum_auto_land_false_positive_rate"])
        and recall_before - recall_after
        <= float(acceptance["maximum_auto_land_recall_loss"]) + 1e-12
        and fp_reduction
        >= float(acceptance["minimum_auto_land_false_positive_reduction_fraction"])
        and takeoff_unchanged
        and all(
            result["threshold_inputs"]["evaluation_rows_used"] == 0
            for result in fold_results.values()
        )
    )
    summary = {
        "experiment": "DETERMINISTIC_THUMB_EXTENSION_VETO_FOR_AUTO_LAND",
        "terminology": config["terminology"],
        "independent_final_held_out_test": False,
        "pipeline": [
            "raw_learned_classifier",
            "semantic_thumb_topology_check",
            "safety_filtered_command",
        ],
        "rule": {
            "formula": (
                "(||L4-L2|| / (||L3-L2|| + ||L4-L3||)) * "
                "||L4-mean(L0,L5,L9,L13,L17)||"
            ),
            "source_representation": "FROZEN_WRIST_PALM_CANONICAL_63D",
            "applies_only_when": "raw_predicted_label == AUTO_LAND",
            "rejection_status": REJECTED_BY_THUMB_VETO,
            "automatic_relabel": False,
        },
        "threshold_policy": config["rule"]["threshold_derivation"],
        "fold_a": fold_results["fold_a"],
        "fold_b": fold_results["fold_b"],
        "aggregate": {
            "raw_mlp_metrics": classification_metrics(targets, raw),
            "raw_safety": raw_safety,
            "safety_filtered_command_metrics": command_metrics(targets, commands),
            "filtered_safety": filtered_safety,
            "veto_activations": int(np.sum(veto_mask)),
            "correct_vetoes": int(
                np.sum(veto_mask & (targets != auto_land_index))
            ),
            "incorrect_vetoes": int(
                np.sum(veto_mask & (targets == auto_land_index))
            ),
            "true_auto_land_vetoed": int(
                np.sum(veto_mask & (targets == auto_land_index))
            ),
            "right_to_auto_land_before": sum(
                result["right_to_auto_land_before"] for result in fold_results.values()
            ),
            "right_to_auto_land_after": sum(
                result["right_to_auto_land_after"] for result in fold_results.values()
            ),
            "auto_land_recall_before": recall_before,
            "auto_land_recall_after": recall_after,
            "auto_land_recall_loss": recall_before - recall_after,
            "auto_land_false_positive_reduction_fraction": fp_reduction,
            "takeoff_safety_metrics_unchanged": takeoff_unchanged,
        },
        "acceptance_contract": acceptance,
        "decision": {
            "thumb_veto": "ACCEPT" if accepted else "REJECT",
            "ready_to_freeze_model_recipe": accepted,
            "ready_for_all_data_training": accepted,
        },
        "later_runtime_gates_not_implemented": [
            "temporal_stability",
            "mission_state_authorization",
            "target_ready_authorization",
        ],
    }
    write_json(output / "summary.json", summary)
    print(f"THUMB_VETO={summary['decision']['thumb_veto']}")
    print(
        "AUTO_LAND_FP="
        f"{before['false_positive_count']}->{after['false_positive_count']}"
    )
    print(f"AUTO_LAND_RECALL={recall_before:.6f}->{recall_after:.6f}")
    print(f"THUMB_VETO_SUMMARY={output / 'summary.json'}")
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
