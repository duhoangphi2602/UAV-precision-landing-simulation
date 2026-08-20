#!/usr/bin/env python3
"""Train and evaluate the fixed Slice 5 MLP with grouped cross-hand 2-fold CV."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/gesture-matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from gesture.contracts import GESTURE_CLASSES
from gesture.mlp_baseline import (
    FeatureStandardizer,
    GestureMLP,
    LoadedManifest,
    classification_metrics,
    confidence_distribution,
    load_manifest,
    parameter_count,
    safety_class_metrics,
    set_determinism,
    validate_grouped_fold,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=Path("gesture/configs/mlp_v1.json")
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate config/folds/normalization without training or writing outputs",
    )
    return parser.parse_args()


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def validate_config(config: dict[str, Any]) -> None:
    if config.get("device") != "cpu":
        raise ValueError("MLP v1 is CPU-only")
    expected_model = {
        "input_dim": 63,
        "hidden_dims": [128, 64],
        "dropout": [0.2, 0.15],
        "output_dim": 7,
    }
    if config.get("model") != expected_model:
        raise ValueError("config does not match the frozen MLP v1 architecture")
    training = config["training"]
    if training.get("optimizer") != "AdamW":
        raise ValueError("MLP v1 requires AdamW")
    if training.get("loss") != "CrossEntropyLoss":
        raise ValueError("MLP v1 requires CrossEntropyLoss")
    if training.get("class_weighting") is not False:
        raise ValueError("MLP v1 does not use class weighting")
    if training.get("checkpoint_policy") != "FINAL_EPOCH_NO_EVAL_SELECTION":
        raise ValueError("checkpoint selection must not use cross-hand eval metrics")
    if training.get("early_stopping") is not False:
        raise ValueError("early stopping is disabled for the first baseline")


def load_and_validate_folds(
    config: dict[str, Any]
) -> dict[str, tuple[LoadedManifest, LoadedManifest, dict[str, Any]]]:
    loaded: dict[str, tuple[LoadedManifest, LoadedManifest, dict[str, Any]]] = {}
    expected_hands = {
        "RIGHT_TO_LEFT": ("right", "left"),
        "LEFT_TO_RIGHT": ("left", "right"),
    }
    for fold_name in ("fold_a", "fold_b"):
        fold_config = config["folds"][fold_name]
        direction = fold_config["direction"]
        train_hand, eval_hand = expected_hands[direction]
        train = load_manifest(resolve_repo_path(fold_config["train_manifest"]))
        evaluation = load_manifest(resolve_repo_path(fold_config["eval_manifest"]))
        integrity = validate_grouped_fold(
            train, evaluation, train_hand, eval_hand
        )
        scaler = FeatureStandardizer.fit(
            train.features, [row["sample_id"] for row in train.records]
        )
        if scaler.fit_sample_count != len(train.records):
            raise AssertionError("standardizer was not fit on exactly the train fold")
        loaded[fold_name] = (train, evaluation, integrity)
    return loaded


def evaluate_model(
    model: nn.Module,
    features: np.ndarray,
    targets: np.ndarray,
    batch_size: int,
) -> dict[str, Any]:
    loader = DataLoader(
        TensorDataset(
            torch.from_numpy(features), torch.from_numpy(targets.astype(np.int64))
        ),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )
    loss_function = nn.CrossEntropyLoss()
    total_loss = 0.0
    probabilities: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for batch_features, batch_targets in loader:
            logits = model(batch_features)
            loss = loss_function(logits, batch_targets)
            total_loss += float(loss.item()) * len(batch_targets)
            probabilities.append(torch.softmax(logits, dim=1).cpu().numpy())
    probability_array = np.concatenate(probabilities, axis=0)
    predictions = probability_array.argmax(axis=1).astype(np.int64)
    confidences = probability_array.max(axis=1)
    return {
        "loss": total_loss / len(targets),
        "predictions": predictions,
        "confidences": confidences,
        "probabilities": probability_array,
        "accuracy": float(np.mean(predictions == targets)),
    }


def plot_training_curves(history: dict[str, list[float]], path: Path) -> None:
    epochs = np.arange(1, len(history["train_loss"]) + 1)
    figure, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(epochs, history["train_loss"], label="train")
    axes[0].plot(epochs, history["eval_loss"], label="cross-hand eval")
    axes[0].set_title("Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].legend()
    axes[1].plot(epochs, history["train_accuracy"], label="train")
    axes[1].plot(epochs, history["eval_accuracy"], label="cross-hand eval")
    axes[1].set_title("Accuracy")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylim(0.0, 1.02)
    axes[1].legend()
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def plot_confusion(matrix: np.ndarray, title: str, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(7.5, 6.5))
    image = axis.imshow(matrix, interpolation="nearest", cmap="Blues")
    figure.colorbar(image, ax=axis)
    axis.set(
        xticks=np.arange(len(GESTURE_CLASSES)),
        yticks=np.arange(len(GESTURE_CLASSES)),
        xticklabels=GESTURE_CLASSES,
        yticklabels=GESTURE_CLASSES,
        xlabel="Predicted",
        ylabel="True",
        title=title,
    )
    plt.setp(axis.get_xticklabels(), rotation=45, ha="right")
    threshold = float(matrix.max()) / 2.0 if matrix.size else 0.0
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(
                column,
                row,
                str(int(matrix[row, column])),
                ha="center",
                va="center",
                color="white" if matrix[row, column] > threshold else "black",
            )
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def train_fold(
    fold_name: str,
    direction: str,
    train: LoadedManifest,
    evaluation: LoadedManifest,
    integrity: dict[str, Any],
    config: dict[str, Any],
    output: Path,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    training = config["training"]
    evaluation_config = config["evaluation"]
    seed = int(config["seed"])
    set_determinism(seed, int(config["torch_num_threads"]))

    scaler = FeatureStandardizer.fit(
        train.features, [row["sample_id"] for row in train.records]
    )
    train_features = scaler.transform(train.features)
    eval_features = scaler.transform(evaluation.features)
    generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(
        TensorDataset(
            torch.from_numpy(train_features), torch.from_numpy(train.targets)
        ),
        batch_size=int(training["batch_size"]),
        shuffle=bool(training["shuffle_train"]),
        num_workers=int(training["num_workers"]),
        generator=generator,
    )

    model = GestureMLP()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )
    loss_function = nn.CrossEntropyLoss()
    history: dict[str, list[float]] = {
        "train_loss": [],
        "train_accuracy": [],
        "eval_loss": [],
        "eval_accuracy": [],
    }
    started = time.perf_counter()
    for epoch in range(1, int(training["epochs"]) + 1):
        model.train()
        total_loss = 0.0
        correct = 0
        seen = 0
        for batch_features, batch_targets in train_loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(batch_features)
            loss = loss_function(logits, batch_targets)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * len(batch_targets)
            correct += int(torch.sum(logits.argmax(dim=1) == batch_targets).item())
            seen += len(batch_targets)
        diagnostic_eval = evaluate_model(
            model,
            eval_features,
            evaluation.targets,
            int(training["batch_size"]),
        )
        history["train_loss"].append(total_loss / seen)
        history["train_accuracy"].append(correct / seen)
        history["eval_loss"].append(float(diagnostic_eval["loss"]))
        history["eval_accuracy"].append(float(diagnostic_eval["accuracy"]))
        if epoch == 1 or epoch % 10 == 0 or epoch == int(training["epochs"]):
            print(
                f"{fold_name} epoch={epoch:03d} "
                f"train_loss={history['train_loss'][-1]:.6f} "
                f"train_acc={history['train_accuracy'][-1]:.4f} "
                f"eval_acc={history['eval_accuracy'][-1]:.4f}",
                flush=True,
            )

    final_train = evaluate_model(
        model, train_features, train.targets, int(training["batch_size"])
    )
    final_eval = evaluate_model(
        model, eval_features, evaluation.targets, int(training["batch_size"])
    )
    predictions = final_eval["predictions"]
    confidences = final_eval["confidences"]
    correct_mask = predictions == evaluation.targets
    metrics = classification_metrics(evaluation.targets, predictions)
    metrics["safety_classes"] = {
        label: safety_class_metrics(evaluation.targets, predictions, label)
        for label in ("TAKEOFF", "AUTO_LAND")
    }
    metrics["confidence_distribution"] = confidence_distribution(
        confidences,
        correct_mask,
        int(evaluation_config["confidence_histogram_bins"]),
    )
    threshold = float(evaluation_config["high_confidence_error_threshold"])
    prediction_rows: list[dict[str, Any]] = []
    for index, record in enumerate(evaluation.records):
        prediction_rows.append(
            {
                "sample_id": record["sample_id"],
                "session_id": record["session_id"],
                "true_label": GESTURE_CLASSES[int(evaluation.targets[index])],
                "predicted_label": GESTURE_CLASSES[int(predictions[index])],
                "confidence": float(confidences[index]),
                "correct": bool(correct_mask[index]),
            }
        )
    errors = [row for row in prediction_rows if not row["correct"]]
    high_confidence_errors = [
        row for row in errors if row["confidence"] >= threshold
    ]
    metrics.update(
        {
            "fold": fold_name,
            "direction": direction,
            "terminology": config["terminology"],
            "checkpoint_policy": training["checkpoint_policy"],
            "train_samples": len(train.records),
            "eval_samples": len(evaluation.records),
            "final_train_loss": float(final_train["loss"]),
            "final_train_accuracy": float(final_train["accuracy"]),
            "final_eval_loss": float(final_eval["loss"]),
            "generalization_accuracy_gap": float(
                final_train["accuracy"] - final_eval["accuracy"]
            ),
            "misclassified_count": len(errors),
            "misclassified_sample_ids": [row["sample_id"] for row in errors],
            "high_confidence_error_threshold": threshold,
            "high_confidence_error_count": len(high_confidence_errors),
            "elapsed_seconds": time.perf_counter() - started,
            "fold_integrity": integrity,
        }
    )

    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "standardization.json", scaler.to_dict())
    write_json(output / "training_history.json", history)
    write_json(output / "metrics.json", metrics)
    write_json(
        output / "misclassifications.json",
        {"errors": errors, "high_confidence_errors": high_confidence_errors},
    )
    prediction_path = output / "predictions.jsonl"
    prediction_path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in prediction_rows)
    )
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "class_order": list(GESTURE_CLASSES),
            "standardization": scaler.to_dict(),
            "model_config": config["model"],
            "training_config": training,
            "fold": fold_name,
            "direction": direction,
        },
        output / "model_final_epoch.pt",
    )
    plot_training_curves(history, output / "training_curves.png")
    matrix = np.asarray(metrics["confusion_matrix"], dtype=np.int64)
    plot_confusion(matrix, f"{fold_name} {direction}", output / "confusion_matrix.png")
    return metrics, evaluation.targets, predictions


def main() -> int:
    args = parse_args()
    config_path = resolve_repo_path(args.config)
    config = json.loads(config_path.read_text())
    validate_config(config)
    set_determinism(int(config["seed"]), int(config["torch_num_threads"]))
    model = GestureMLP()
    parameters = parameter_count(model)
    if parameters != 16903:
        raise AssertionError(f"unexpected MLP v1 parameter count: {parameters}")
    folds = load_and_validate_folds(config)
    if args.validate_only:
        for fold_name, (_, _, integrity) in folds.items():
            print(
                f"{fold_name.upper()}_TRAIN={integrity['train_samples']} "
                f"{fold_name.upper()}_EVAL={integrity['eval_samples']} "
                "SESSION_LEAKAGE=NO SAMPLE_LEAKAGE=NO"
            )
        print(f"CLASS_ORDER={','.join(GESTURE_CLASSES)}")
        print(f"PARAMETERS={parameters}")
        print("NORMALIZATION_SCOPE=TRAIN_FOLD_ONLY")
        print("READY_TO_TRAIN=YES")
        return 0

    output = resolve_repo_path(config["output_directory"])
    if output.exists():
        raise FileExistsError(f"experiment output already exists: {output}")
    output.mkdir(parents=True)
    snapshot = dict(config)
    snapshot["resolved_class_order"] = list(GESTURE_CLASSES)
    snapshot["parameter_count"] = parameters
    snapshot["source_config"] = str(config_path)
    write_json(output / "config.json", snapshot)
    shutil.copy2(config_path, output / "config.source.json")

    fold_metrics: dict[str, dict[str, Any]] = {}
    aggregate_targets: list[np.ndarray] = []
    aggregate_predictions: list[np.ndarray] = []
    for fold_name in ("fold_a", "fold_b"):
        train, evaluation, integrity = folds[fold_name]
        direction = config["folds"][fold_name]["direction"]
        metrics, targets, predictions = train_fold(
            fold_name,
            direction,
            train,
            evaluation,
            integrity,
            config,
            output / fold_name,
        )
        fold_metrics[fold_name] = metrics
        aggregate_targets.append(targets)
        aggregate_predictions.append(predictions)

    accuracies = [fold_metrics[name]["accuracy"] for name in ("fold_a", "fold_b")]
    macro_f1 = [fold_metrics[name]["macro_f1"] for name in ("fold_a", "fold_b")]
    all_targets = np.concatenate(aggregate_targets)
    all_predictions = np.concatenate(aggregate_predictions)
    aggregate = classification_metrics(all_targets, all_predictions)
    summary = {
        "terminology": config["terminology"],
        "independent_final_held_out_test": False,
        "checkpoint_policy": config["training"]["checkpoint_policy"],
        "fold_a": {
            "direction": config["folds"]["fold_a"]["direction"],
            "accuracy": fold_metrics["fold_a"]["accuracy"],
            "macro_f1": fold_metrics["fold_a"]["macro_f1"],
        },
        "fold_b": {
            "direction": config["folds"]["fold_b"]["direction"],
            "accuracy": fold_metrics["fold_b"]["accuracy"],
            "macro_f1": fold_metrics["fold_b"]["macro_f1"],
        },
        "mean_accuracy": float(np.mean(accuracies)),
        "mean_macro_f1": float(np.mean(macro_f1)),
        "accuracy_fold_spread": float(max(accuracies) - min(accuracies)),
        "macro_f1_fold_spread": float(max(macro_f1) - min(macro_f1)),
        "aggregate": aggregate,
        "aggregate_safety_classes": {
            label: safety_class_metrics(all_targets, all_predictions, label)
            for label in ("TAKEOFF", "AUTO_LAND")
        },
        "baseline_assessment": "PENDING_EVIDENCE_REVIEW",
    }
    write_json(output / "cv_summary.json", summary)
    plot_confusion(
        np.asarray(aggregate["confusion_matrix"], dtype=np.int64),
        "Aggregate grouped cross-hand 2-fold CV",
        output / "aggregate_confusion_matrix.png",
    )
    print(f"CV_SUMMARY={output / 'cv_summary.json'}")
    print("TRAINING_COMPLETE=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
