"""PyTorch-free ONNX Runtime production path for gesture classification."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import onnxruntime as ort

from gesture.contracts import GESTURE_CLASSES, PREPROCESSING_VERSION
from gesture.thumb_veto import (
    ALLOWED,
    REJECTED_BY_THUMB_VETO,
    thumb_extension_score,
    thumb_veto_status,
)


NO_COMMAND = "NO_COMMAND"
REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def softmax(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float32)
    shifted = values - np.max(values, axis=-1, keepdims=True)
    exponentials = np.exp(shifted)
    return exponentials / np.sum(exponentials, axis=-1, keepdims=True)


@dataclass(frozen=True)
class GesturePrediction:
    raw_gesture: str | None
    confidence: float
    thumb_extension_score: float | None
    thumb_veto_status: str
    effective_command: str
    classifier_ms: float = 0.0

    @property
    def raw_label(self) -> str | None:
        """Compatibility alias for callers using classifier terminology."""

        return self.raw_gesture

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GestureOnnxRuntime:
    """Load the final classifier and its required deployment metadata."""

    def __init__(
        self,
        model_path: Path,
        preprocessing_path: Path | None = None,
        deployment_config_path: Path | None = None,
        *,
        expected_model_sha256: str | None = None,
        expected_preprocessing_sha256: str | None = None,
        expected_deployment_sha256: str | None = None,
    ) -> None:
        self.config: dict[str, Any]
        self.class_mapping_path: Path | None = None
        if preprocessing_path is None and deployment_config_path is None:
            config_path = resolve_repo_path(model_path)
            self.config = json.loads(config_path.read_text())
            if self.config.get("provider") != "CPUExecutionProvider":
                raise ValueError("runtime config requires CPUExecutionProvider")
            model_path = resolve_repo_path(self.config["model"])
            preprocessing_path = resolve_repo_path(self.config["preprocessing"])
            deployment_config_path = resolve_repo_path(
                self.config["deployment_config"]
            )
            expected_model_sha256 = self.config.get("expected_model_sha256")
            expected_preprocessing_sha256 = self.config.get(
                "expected_preprocessing_sha256"
            )
            expected_deployment_sha256 = self.config.get(
                "expected_deployment_config_sha256"
            )
            if "class_mapping" in self.config:
                self.class_mapping_path = resolve_repo_path(
                    self.config["class_mapping"]
                )
        else:
            if preprocessing_path is None or deployment_config_path is None:
                raise ValueError("all runtime artifact paths must be provided")
            self.config = {
                "model": str(model_path),
                "preprocessing": str(preprocessing_path),
                "deployment_config": str(deployment_config_path),
                "provider": "CPUExecutionProvider",
                "graph_optimization": "ORT_ENABLE_ALL",
            }
        self.model_path = model_path.resolve()
        self.preprocessing_path = preprocessing_path.resolve()
        self.deployment_config_path = deployment_config_path.resolve()
        for path in (
            self.model_path,
            self.preprocessing_path,
            self.deployment_config_path,
        ):
            if not path.is_file():
                raise FileNotFoundError(f"missing gesture runtime artifact: {path}")
        if (
            self.class_mapping_path is not None
            and not self.class_mapping_path.is_file()
        ):
            raise FileNotFoundError(
                f"missing gesture runtime artifact: {self.class_mapping_path}"
            )
        expected_hashes = (
            (self.model_path, expected_model_sha256),
            (self.preprocessing_path, expected_preprocessing_sha256),
            (self.deployment_config_path, expected_deployment_sha256),
        )
        for path, expected in expected_hashes:
            if expected is not None and sha256_file(path) != expected:
                raise ValueError(f"gesture runtime artifact hash mismatch: {path.name}")
        if self.class_mapping_path is not None:
            expected_mapping = self.config.get("expected_class_mapping_sha256")
            if (
                expected_mapping is not None
                and sha256_file(self.class_mapping_path) != expected_mapping
            ):
                raise ValueError(
                    "gesture runtime artifact hash mismatch: class_mapping.json"
                )

        self.preprocessing = json.loads(self.preprocessing_path.read_text())
        self.deployment = json.loads(self.deployment_config_path.read_text())
        if self.preprocessing["preprocessing_version"] != PREPROCESSING_VERSION:
            raise ValueError("preprocessing version does not match frozen contract")
        if self.deployment["preprocessing_version"] != PREPROCESSING_VERSION:
            raise ValueError("deployment preprocessing version mismatch")
        if self.deployment["class_order"] != list(GESTURE_CLASSES):
            raise ValueError("deployment class order is not canonical")
        if self.class_mapping_path is not None:
            class_mapping = json.loads(self.class_mapping_path.read_text())
            if class_mapping.get("class_order") != list(GESTURE_CLASSES):
                raise ValueError("class mapping order is not canonical")
        self.class_order = tuple(GESTURE_CLASSES)
        self.feature_mean = np.asarray(
            self.preprocessing["feature_mean"], dtype=np.float32
        )
        self.feature_std = np.asarray(
            self.preprocessing["feature_std"], dtype=np.float32
        )
        if self.feature_mean.shape != (63,) or self.feature_std.shape != (63,):
            raise ValueError("runtime standardization metadata must be 63D")
        if not np.isfinite(self.feature_mean).all() or not np.isfinite(
            self.feature_std
        ).all():
            raise ValueError("runtime standardization metadata is non-finite")
        if np.any(self.feature_std <= 0):
            raise ValueError("runtime feature standard deviations must be positive")
        self.thumb_threshold = float(
            self.deployment["thumb_veto"]["production_thumb_veto_threshold"]
        )
        if not math.isfinite(self.thumb_threshold):
            raise ValueError("production thumb threshold is non-finite")

        if "CPUExecutionProvider" not in ort.get_available_providers():
            raise RuntimeError("ONNX Runtime CPUExecutionProvider is unavailable")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(self.model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        if self.session.get_providers() != ["CPUExecutionProvider"]:
            raise RuntimeError(
                f"unexpected ONNX Runtime providers: {self.session.get_providers()}"
            )
        self._validate_model_contract()
        self.input = self.session.get_inputs()[0]
        self.output = self.session.get_outputs()[0]

    def _validate_model_contract(self) -> None:
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise ValueError("gesture ONNX must expose exactly one input and output")
        model_input = inputs[0]
        model_output = outputs[0]
        if model_input.name != "features" or model_input.type != "tensor(float)":
            raise ValueError("unexpected ONNX input name or dtype")
        if model_output.name != "logits" or model_output.type != "tensor(float)":
            raise ValueError("unexpected ONNX output name or dtype")
        if model_input.shape[1:] != [63] or model_output.shape[1:] != [7]:
            raise ValueError("unexpected ONNX classifier feature dimensions")
        if not isinstance(model_input.shape[0], str) or not isinstance(
            model_output.shape[0], str
        ):
            raise ValueError("ONNX batch dimension is not dynamic")
        metadata = self.session.get_modelmeta().custom_metadata_map
        expected_metadata = {
            "class_order": json.dumps(list(GESTURE_CLASSES), separators=(",", ":")),
            "preprocessing_version": PREPROCESSING_VERSION,
            "production_thumb_veto_threshold": str(self.thumb_threshold),
            "media_pipe_in_onnx": "false",
        }
        for key, value in expected_metadata.items():
            if metadata.get(key) != value:
                raise ValueError(f"ONNX metadata mismatch: {key}")

    def contract(self) -> dict[str, Any]:
        model_input = self.session.get_inputs()[0]
        model_output = self.session.get_outputs()[0]
        return {
            "provider": self.session.get_providers(),
            "graph_optimization": "ORT_ENABLE_ALL_STANDARD",
            "input": {
                "name": model_input.name,
                "shape": model_input.shape,
                "dtype": model_input.type,
            },
            "output": {
                "name": model_output.name,
                "shape": model_output.shape,
                "dtype": model_output.type,
            },
            "dynamic_batch": True,
            "class_order": list(GESTURE_CLASSES),
            "preprocessing_version": PREPROCESSING_VERSION,
            "production_thumb_veto_threshold": self.thumb_threshold,
            "session_creation": "PASS",
            "pytorch_required": False,
        }

    def standardize(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=np.float32)
        if values.ndim == 1:
            values = values.reshape(1, -1)
        if values.ndim != 2 or values.shape[1] != 63:
            raise ValueError("gesture runtime expects [N,63] features")
        standardized = (values - self.feature_mean) / self.feature_std
        if not np.isfinite(standardized).all():
            raise ValueError("standardized runtime feature is non-finite")
        return np.ascontiguousarray(standardized, dtype=np.float32)

    def infer_standardized(self, standardized: np.ndarray) -> np.ndarray:
        values = np.asarray(standardized, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != 63:
            raise ValueError("classifier input must be float32 [N,63]")
        logits = self.session.run(["logits"], {"features": values})[0]
        if logits.shape != (len(values), len(GESTURE_CLASSES)):
            raise ValueError(f"unexpected ONNX output shape: {logits.shape}")
        if logits.dtype != np.float32 or not np.isfinite(logits).all():
            raise ValueError("ONNX logits must be finite float32")
        return logits

    def run_standardized(self, standardized: np.ndarray) -> np.ndarray:
        """Compatibility alias used by the offline CPU deployment gate."""

        return self.infer_standardized(standardized)

    def infer_logits(self, features: np.ndarray) -> np.ndarray:
        return self.infer_standardized(self.standardize(features))

    def predict(self, feature: Sequence[float]) -> GesturePrediction:
        values = np.asarray(feature, dtype=np.float32)
        standardized = self.standardize(values)
        started = time.perf_counter()
        logits = self.infer_standardized(standardized)[0]
        classifier_ms = (time.perf_counter() - started) * 1000.0
        probabilities = softmax(logits)
        class_index = int(np.argmax(probabilities))
        raw_label = GESTURE_CLASSES[class_index]
        extension_score = thumb_extension_score(values)
        veto_status = thumb_veto_status(
            raw_label, extension_score, self.thumb_threshold
        )
        effective = (
            NO_COMMAND
            if veto_status == REJECTED_BY_THUMB_VETO
            else raw_label
        )
        return GesturePrediction(
            raw_gesture=raw_label,
            confidence=float(probabilities[class_index]),
            thumb_extension_score=extension_score,
            thumb_veto_status=veto_status,
            effective_command=effective,
            classifier_ms=classifier_ms,
        )


def no_hand_prediction() -> GesturePrediction:
    """Return a fresh safe state; never reuse a stale actionable prediction."""

    return GesturePrediction(
        raw_gesture=None,
        confidence=0.0,
        thumb_extension_score=None,
        thumb_veto_status=ALLOWED,
        effective_command=NO_COMMAND,
        classifier_ms=0.0,
    )
