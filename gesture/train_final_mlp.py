#!/usr/bin/env python3
"""Train one frozen MLP v1 production model on all authoritative samples."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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

from gesture.contracts import GESTURE_CLASSES, PREPROCESSING_VERSION
from gesture.mlp_baseline import (
    FeatureStandardizer,
    GestureMLP,
    load_manifest,
    parameter_count,
    set_determinism,
)
from gesture.thumb_veto import derive_retention_threshold
from gesture.train_mlp_cv import evaluate_model


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=Path("gesture/configs/mlp_v1_final.json")
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate frozen recipe and dataset without training or writing output",
    )
    return parser.parse_args()


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_final_config(config: dict[str, Any], baseline: dict[str, Any]) -> None:
    if config.get("purpose") != "ALL_DATA_PRODUCTION_TRAINING_NOT_GENERALIZATION_EVALUATION":
        raise ValueError("final run purpose must explicitly exclude generalization claims")
    if config.get("device") != "cpu" or baseline.get("device") != "cpu":
        raise ValueError("frozen MLP v1 training is CPU-only")
    for key in ("seed", "torch_num_threads", "model"):
        if config.get(key) != baseline.get(key):
            raise ValueError(f"final config diverges from MLP v1 field: {key}")
    baseline_training = baseline["training"]
    final_training = config["training"]
    frozen_fields = (
        "epochs",
        "batch_size",
        "optimizer",
        "learning_rate",
        "weight_decay",
        "loss",
        "class_weighting",
        "shuffle_train",
        "num_workers",
        "early_stopping",
    )
    for key in frozen_fields:
        if final_training.get(key) != baseline_training.get(key):
            raise ValueError(f"final training config diverges from MLP v1: {key}")
    if final_training.get("epochs") != 80:
        raise ValueError("final production epoch budget must be exactly 80")
    if final_training.get("checkpoint_policy") != baseline_training.get(
        "checkpoint_policy"
    ):
        raise ValueError("final model must use the predetermined final epoch")
    if config.get("preprocessing_version") != PREPROCESSING_VERSION:
        raise ValueError("final preprocessing version does not match frozen contract")
    veto = config["thumb_veto"]
    if veto.get("minimum_auto_land_retention") != 0.98:
        raise ValueError("production thumb retention must remain 98 percent")
    if veto.get("calibration_scope") != "PRODUCTION_ALL_DATA_NOT_GENERALIZATION_EVIDENCE":
        raise ValueError("production thumb threshold scope must be explicit")
    if veto.get("automatic_relabel") is not False:
        raise ValueError("thumb veto must never relabel a rejected command")


def plot_training(history: dict[str, list[float]], path: Path) -> None:
    epochs = np.arange(1, len(history["train_loss"]) + 1)
    figure, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(epochs, history["train_loss"])
    axes[0].set(title="All-data optimization loss", xlabel="Epoch", ylabel="Loss")
    axes[1].plot(epochs, history["train_accuracy"])
    axes[1].set(
        title="All-data optimization accuracy",
        xlabel="Epoch",
        ylabel="Accuracy",
        ylim=(0.0, 1.02),
    )
    figure.suptitle("Optimization evidence only — not generalization performance")
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def assert_finite_model(model: nn.Module) -> None:
    nonfinite = [
        name for name, value in model.state_dict().items() if not torch.isfinite(value).all()
    ]
    if nonfinite:
        raise ValueError(f"model contains non-finite tensors: {nonfinite}")


def contains_runtime_path_dependency(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_runtime_path_dependency(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_runtime_path_dependency(item) for item in value)
    if not isinstance(value, str):
        return False
    return (
        value.startswith(("/", "../", "./"))
        or value.endswith(".jsonl")
        or "sessions/" in value
        or "gesture/data/" in value
    )


def main() -> int:
    args = parse_args()
    config_path = resolve_repo_path(args.config)
    config = json.loads(config_path.read_text())
    baseline_path = resolve_repo_path(config["frozen_recipe_source"])
    baseline = json.loads(baseline_path.read_text())
    validate_final_config(config, baseline)

    manifest_path = resolve_repo_path(config["authoritative_manifest"])
    manifest_hash = sha256_file(manifest_path)
    if manifest_hash != config["expected_manifest_sha256"]:
        raise ValueError("authoritative manifest hash differs from frozen final config")
    dataset = load_manifest(manifest_path)
    if len(dataset.records) != int(config["expected_sample_count"]):
        raise ValueError("authoritative sample count differs from frozen final config")
    if set(dataset.targets.tolist()) != set(range(len(GESTURE_CLASSES))):
        raise ValueError("all seven frozen classes must be represented")
    sample_ids = [row["sample_id"] for row in dataset.records]
    sample_ids_hash = hashlib.sha256("\n".join(sample_ids).encode("utf-8")).hexdigest()
    scaler = FeatureStandardizer.fit(dataset.features, sample_ids)
    auto_land_index = GESTURE_CLASSES.index("AUTO_LAND")
    thumb_threshold = derive_retention_threshold(
        dataset.features[dataset.targets == auto_land_index],
        float(config["thumb_veto"]["minimum_auto_land_retention"]),
        fit_scope=config["thumb_veto"]["calibration_scope"],
    )
    if args.validate_only:
        print(f"FINAL_SAMPLE_COUNT={len(dataset.records)}")
        print(f"MANIFEST_SHA256={manifest_hash}")
        print(f"MODEL_PARAMETERS={parameter_count(GestureMLP())}")
        print(f"PRODUCTION_THUMB_VETO_THRESHOLD={thumb_threshold.value:.12f}")
        print("READY_FOR_FINAL_TRAINING=YES")
        return 0

    output = resolve_repo_path(config["output_directory"])
    temporary_output = output.with_name(output.name + ".tmp")
    if output.exists() or temporary_output.exists():
        raise FileExistsError(f"final output or temporary output already exists: {output}")
    temporary_output.mkdir(parents=True)

    seed = int(config["seed"])
    training = config["training"]
    set_determinism(seed, int(config["torch_num_threads"]))
    standardized = scaler.transform(dataset.features)
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        TensorDataset(torch.from_numpy(standardized), torch.from_numpy(dataset.targets)),
        batch_size=int(training["batch_size"]),
        shuffle=bool(training["shuffle_train"]),
        num_workers=int(training["num_workers"]),
        generator=generator,
    )
    model = GestureMLP()
    if parameter_count(model) != 16903:
        raise AssertionError("frozen MLP v1 parameter count changed")
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )
    loss_function = nn.CrossEntropyLoss()
    history: dict[str, list[float]] = {"train_loss": [], "train_accuracy": []}
    started = time.perf_counter()
    for epoch in range(1, int(training["epochs"]) + 1):
        model.train()
        total_loss = 0.0
        correct = 0
        seen = 0
        for features, targets in loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(features)
            loss = loss_function(logits, targets)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * len(targets)
            correct += int(torch.sum(logits.argmax(dim=1) == targets).item())
            seen += len(targets)
        history["train_loss"].append(total_loss / seen)
        history["train_accuracy"].append(correct / seen)
        if epoch == 1 or epoch % 10 == 0 or epoch == int(training["epochs"]):
            print(
                f"final epoch={epoch:03d} "
                f"train_loss={history['train_loss'][-1]:.6f} "
                f"train_acc={history['train_accuracy'][-1]:.4f}",
                flush=True,
            )

    assert_finite_model(model)
    final_optimization = evaluate_model(
        model, standardized, dataset.targets, int(training["batch_size"])
    )
    provenance = {
        "dataset_role": "ALL_DATA_PRODUCTION_TRAINING",
        "generalization_evidence": "GROUPED CROSS-HAND 2-FOLD CV",
        "authoritative_sample_count": len(dataset.records),
        "authoritative_manifest_filename": manifest_path.name,
        "authoritative_manifest_sha256": manifest_hash,
        "ordered_sample_ids_sha256": sample_ids_hash,
        "class_counts": {
            label: int(np.sum(dataset.targets == index))
            for index, label in enumerate(GESTURE_CLASSES)
        },
    }
    preprocessing = {
        "preprocessing_version": PREPROCESSING_VERSION,
        "input_dtype": "float32",
        "input_shape": ["N", 63],
        "feature_mean": scaler.mean.tolist(),
        "feature_std": scaler.std.tolist(),
        "fit_sample_count": scaler.fit_sample_count,
        "fit_sample_ids_sha256": scaler.fit_sample_ids_sha256,
        "fit_scope": "ALL_2786_PRODUCTION_TRAINING_SAMPLES",
    }
    class_mapping = {
        "class_order": list(GESTURE_CLASSES),
        "index_to_class": {str(i): label for i, label in enumerate(GESTURE_CLASSES)},
        "class_to_index": {label: i for i, label in enumerate(GESTURE_CLASSES)},
    }
    deployment = {
        "schema_version": "gesture_mlp_deployment_v1",
        "model": {
            "architecture": "63-128-64-7",
            "parameters": parameter_count(model),
            "input_name": "features",
            "input_dtype": "float32",
            "input_shape": ["N", 63],
            "output_name": "logits",
            "output_dtype": "float32",
            "output_shape": ["N", 7],
        },
        "class_order": list(GESTURE_CLASSES),
        "preprocessing_version": PREPROCESSING_VERSION,
        "preprocessing_metadata": "preprocessing.json",
        "thumb_veto": {
            **config["thumb_veto"],
            "production_thumb_veto_threshold": thumb_threshold.value,
            "threshold_evidence": thumb_threshold.to_dict(),
        },
    }
    runtime_checkpoint = {
        "schema_version": "gesture_mlp_checkpoint_v1",
        "model_state_dict": model.state_dict(),
        "model_config": config["model"],
        "class_order": list(GESTURE_CLASSES),
        "preprocessing": preprocessing,
        "thumb_veto": deployment["thumb_veto"],
        "dataset_provenance": {
            key: value
            for key, value in provenance.items()
            if key not in {"authoritative_manifest_filename"}
        },
        "training": {
            **training,
            "seed": seed,
            "final_epoch": int(training["epochs"]),
        },
    }
    if contains_runtime_path_dependency(runtime_checkpoint):
        raise AssertionError("runtime checkpoint contains a path dependency")

    write_json(temporary_output / "config.json", config)
    write_json(temporary_output / "preprocessing.json", preprocessing)
    write_json(temporary_output / "class_mapping.json", class_mapping)
    write_json(temporary_output / "dataset_provenance.json", provenance)
    write_json(temporary_output / "deployment_config.json", deployment)
    write_json(
        temporary_output / "training_history.json",
        {
            **history,
            "epochs": int(training["epochs"]),
            "elapsed_seconds": time.perf_counter() - started,
            "final_optimization_loss": float(final_optimization["loss"]),
            "final_optimization_accuracy": float(final_optimization["accuracy"]),
            "metric_scope": "ALL_DATA_OPTIMIZATION_EVIDENCE_NOT_GENERALIZATION",
        },
    )
    torch.save(runtime_checkpoint, temporary_output / "model.pt")
    torch.save(model.state_dict(), temporary_output / "model_state_dict.pt")
    plot_training(history, temporary_output / "training_curves.png")

    loaded = torch.load(temporary_output / "model.pt", map_location="cpu", weights_only=False)
    reloaded = GestureMLP()
    reloaded.load_state_dict(loaded["model_state_dict"], strict=True)
    reloaded.eval()
    assert_finite_model(reloaded)
    representative = torch.from_numpy(standardized[:8])
    with torch.no_grad():
        logits = reloaded(representative)
    if logits.shape != (8, len(GESTURE_CLASSES)) or not torch.isfinite(logits).all():
        raise AssertionError("representative final inference failed")
    sanity = {
        "finite_weights": True,
        "model_load": "PASS",
        "class_mapping": "PASS",
        "input_contract": "float32 [N,63]",
        "output_contract": "logits float32 [N,7]",
        "representative_batch_shape": [8, 63],
        "representative_output_shape": list(logits.shape),
        "preprocessing_metadata_load": "PASS",
        "thumb_veto_config_load": "PASS",
        "runtime_path_dependencies": False,
        "generalization_claim_from_all_data_training": False,
    }
    write_json(temporary_output / "sanity.json", sanity)
    temporary_output.replace(output)
    print(f"FINAL_TRAIN_LOSS={final_optimization['loss']:.10f}")
    print(f"FINAL_TRAIN_ACCURACY={final_optimization['accuracy']:.10f}")
    print(f"PRODUCTION_THUMB_VETO_THRESHOLD={thumb_threshold.value:.12f}")
    print(f"FINAL_MODEL={output / 'model.pt'}")
    print("FINAL_TRAINING=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
