"""Unit/static gates for the PyTorch-free ONNX Runtime path."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from gesture.onnx_runtime import (
    GestureOnnxRuntime,
    NO_COMMAND,
    no_hand_prediction,
    softmax,
)


def test_runtime_module_import_does_not_import_pytorch():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import gesture.onnx_runtime; "
            "assert 'torch' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_no_hand_is_fresh_no_command_state():
    state = no_hand_prediction()
    assert state.effective_command == NO_COMMAND
    assert state.raw_gesture is None
    assert state.confidence == 0.0


def test_softmax_is_normalized_and_stable():
    values = softmax(np.asarray([[1000.0, 1001.0, 999.0]], dtype=np.float32))
    np.testing.assert_allclose(values.sum(axis=1), 1.0, atol=1e-6)
    assert int(np.argmax(values)) == 1


def test_ort_gate_config_requires_all_data_and_stable_benchmark():
    config = json.loads(Path("gesture/configs/mlp_v1_cpu_gate.json").read_text())
    assert config["expected_sample_count"] == 2786
    assert config["benchmark"]["batch_size"] == 1
    assert config["benchmark"]["warmup_iterations"] >= 100
    assert config["benchmark"]["measured_iterations"] >= 1000


def test_tracked_release_bundle_loads_without_pytorch():
    runtime = GestureOnnxRuntime(Path("gesture/configs/onnx_runtime_v1.json"))
    contract = runtime.contract()
    assert contract["provider"] == ["CPUExecutionProvider"]
    assert contract["input"]["shape"][1:] == [63]
    assert contract["output"]["shape"][1:] == [7]
    assert contract["pytorch_required"] is False
