"""Static contract tests for the prepared final-classifier ONNX gate."""

import json
from pathlib import Path

from gesture.export_mlp_onnx import validate_onnx_config


def test_onnx_gate_has_dynamic_classifier_only_contract():
    config = json.loads(Path("gesture/configs/mlp_v1_onnx.json").read_text())
    validate_onnx_config(config)
    assert config["input"]["shape"] == ["N", 63]
    assert config["output"]["shape"] == ["N", 7]
    assert config["input"]["dynamic_batch"] is True
    assert config["output"]["dynamic_batch"] is True
    assert config["media_pipe_in_onnx"] is False
    assert config["parity_scope"].endswith("NOT_GENERALIZATION")
