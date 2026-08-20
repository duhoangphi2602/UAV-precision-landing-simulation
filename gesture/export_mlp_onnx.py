#!/usr/bin/env python3
"""Export and numerically validate only the final custom gesture classifier."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnx
import onnxruntime as ort
import torch

from gesture.contracts import GESTURE_CLASSES, PREPROCESSING_VERSION
from gesture.mlp_baseline import GestureMLP, load_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=Path("gesture/configs/mlp_v1_onnx.json")
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate final PyTorch/metadata inputs without creating ONNX",
    )
    return parser.parse_args()


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def validate_onnx_config(config: dict[str, Any]) -> None:
    if config.get("purpose") != "EXPORT_AND_NUMERICALLY_VALIDATE_FINAL_CLASSIFIER_ONLY":
        raise ValueError("ONNX gate purpose is not frozen")
    if config.get("opset_version") != 17:
        raise ValueError("ONNX gate requires opset 17")
    if config.get("media_pipe_in_onnx") is not False:
        raise ValueError("MediaPipe must remain outside the classifier ONNX")
    if config.get("input") != {
        "name": "features",
        "dtype": "float32",
        "shape": ["N", 63],
        "dynamic_batch": True,
    }:
        raise ValueError("unexpected ONNX input contract")
    if config.get("output") != {
        "name": "logits",
        "dtype": "float32",
        "shape": ["N", 7],
        "dynamic_batch": True,
    }:
        raise ValueError("unexpected ONNX output contract")
    if config["runtime"].get("provider") != "CPUExecutionProvider":
        raise ValueError("ONNX parity gate is CPU-only")


def load_gate_inputs(
    config: dict[str, Any]
) -> tuple[GestureMLP, dict[str, Any], dict[str, Any]]:
    artifacts = (
        ("checkpoint", "expected_checkpoint_sha256"),
        ("preprocessing", "expected_preprocessing_sha256"),
        ("deployment_config", "expected_deployment_config_sha256"),
    )
    for path_key, hash_key in artifacts:
        path = resolve_repo_path(config[path_key])
        if not path.is_file():
            raise FileNotFoundError(f"missing ONNX gate input: {path}")
        if sha256_file(path) != config[hash_key]:
            raise ValueError(f"ONNX gate input hash mismatch: {path_key}")

    checkpoint = torch.load(
        resolve_repo_path(config["checkpoint"]), map_location="cpu", weights_only=False
    )
    preprocessing = json.loads(resolve_repo_path(config["preprocessing"]).read_text())
    deployment = json.loads(
        resolve_repo_path(config["deployment_config"]).read_text()
    )
    if checkpoint["class_order"] != list(GESTURE_CLASSES):
        raise ValueError("checkpoint class order is not canonical")
    if deployment["class_order"] != list(GESTURE_CLASSES):
        raise ValueError("deployment class order is not canonical")
    if preprocessing["preprocessing_version"] != PREPROCESSING_VERSION:
        raise ValueError("preprocessing metadata version mismatch")
    if deployment["preprocessing_version"] != PREPROCESSING_VERSION:
        raise ValueError("deployment preprocessing version mismatch")
    if preprocessing["input_shape"] != ["N", 63]:
        raise ValueError("preprocessing input shape mismatch")
    threshold = deployment["thumb_veto"]["production_thumb_veto_threshold"]
    if not np.isfinite(threshold):
        raise ValueError("production thumb threshold is not finite")

    model = GestureMLP()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    if any(not torch.isfinite(value).all() for value in model.state_dict().values()):
        raise ValueError("final PyTorch checkpoint contains non-finite weights")
    return model, preprocessing, deployment


def main() -> int:
    args = parse_args()
    config_path = resolve_repo_path(args.config)
    config = json.loads(config_path.read_text())
    validate_onnx_config(config)
    model, preprocessing, deployment = load_gate_inputs(config)
    if args.validate_only:
        with torch.no_grad():
            logits = model(torch.zeros(2, 63, dtype=torch.float32))
        if logits.shape != (2, 7) or not torch.isfinite(logits).all():
            raise AssertionError("PyTorch model failed ONNX pre-export sanity")
        print("ONNX_INPUT=float32[N,63]")
        print("ONNX_OUTPUT=logits_float32[N,7]")
        print("DYNAMIC_BATCH=YES")
        print("READY_FOR_ONNX_EXPORT=YES")
        return 0

    onnx_path = resolve_repo_path(config["onnx_output"])
    validation_path = resolve_repo_path(config["validation_output"])
    if onnx_path.exists() or validation_path.exists():
        raise FileExistsError("ONNX output or validation report already exists")
    temporary_onnx = onnx_path.with_suffix(onnx_path.suffix + ".tmp")
    if temporary_onnx.exists():
        raise FileExistsError(f"temporary ONNX output already exists: {temporary_onnx}")

    dummy = torch.zeros(1, 63, dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy,
        temporary_onnx,
        export_params=True,
        opset_version=int(config["opset_version"]),
        do_constant_folding=True,
        input_names=[config["input"]["name"]],
        output_names=[config["output"]["name"]],
        dynamic_axes={
            config["input"]["name"]: {0: "batch"},
            config["output"]["name"]: {0: "batch"},
        },
        dynamo=False,
    )
    onnx_model = onnx.load(temporary_onnx)
    onnx.checker.check_model(onnx_model)
    metadata = {
        "class_order": json.dumps(list(GESTURE_CLASSES), separators=(",", ":")),
        "preprocessing_version": PREPROCESSING_VERSION,
        "preprocessing_sha256": config["expected_preprocessing_sha256"],
        "deployment_config_sha256": config["expected_deployment_config_sha256"],
        "production_thumb_veto_threshold": str(
            deployment["thumb_veto"]["production_thumb_veto_threshold"]
        ),
        "media_pipe_in_onnx": "false",
    }
    del onnx_model.metadata_props[:]
    for key, value in metadata.items():
        item = onnx_model.metadata_props.add()
        item.key = key
        item.value = value
    onnx.save(onnx_model, temporary_onnx)
    onnx.checker.check_model(onnx.load(temporary_onnx))

    dataset = load_manifest(resolve_repo_path(config["parity_manifest"]))
    count = min(int(config["parity_sample_count"]), len(dataset.records))
    indices = np.linspace(0, len(dataset.records) - 1, num=count, dtype=np.int64)
    mean = np.asarray(preprocessing["feature_mean"], dtype=np.float32)
    std = np.asarray(preprocessing["feature_std"], dtype=np.float32)
    parity_input = ((dataset.features[indices] - mean) / std).astype(np.float32)
    with torch.no_grad():
        pytorch_logits = model(torch.from_numpy(parity_input)).numpy()
    session = ort.InferenceSession(
        str(temporary_onnx), providers=[config["runtime"]["provider"]]
    )
    ort_logits = session.run(
        [config["output"]["name"]],
        {config["input"]["name"]: parity_input},
    )[0]
    absolute_error = np.abs(pytorch_logits - ort_logits)
    atol = float(config["runtime"]["absolute_tolerance"])
    rtol = float(config["runtime"]["relative_tolerance"])
    parity_pass = bool(np.allclose(pytorch_logits, ort_logits, atol=atol, rtol=rtol))
    if not parity_pass:
        raise AssertionError("PyTorch/ONNX Runtime numerical parity failed")

    temporary_onnx.replace(onnx_path)
    validation = {
        "verdict": "PASS",
        "scope": config["parity_scope"],
        "onnx_path": onnx_path.name,
        "onnx_sha256": sha256_file(onnx_path),
        "opset_version": int(config["opset_version"]),
        "input": config["input"],
        "output": config["output"],
        "provider": session.get_providers(),
        "parity_samples": count,
        "absolute_tolerance": atol,
        "relative_tolerance": rtol,
        "maximum_absolute_error": float(np.max(absolute_error)),
        "mean_absolute_error": float(np.mean(absolute_error)),
        "argmax_agreement": float(
            np.mean(np.argmax(pytorch_logits, axis=1) == np.argmax(ort_logits, axis=1))
        ),
        "metadata": metadata,
        "generalization_claim": False,
    }
    write_json(validation_path, validation)
    print(f"ONNX_PATH={onnx_path}")
    print(f"MAX_ABS_ERROR={validation['maximum_absolute_error']:.10g}")
    print(f"ARGMAX_AGREEMENT={validation['argmax_agreement']:.10f}")
    print("ONNX_NUMERICAL_PARITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
