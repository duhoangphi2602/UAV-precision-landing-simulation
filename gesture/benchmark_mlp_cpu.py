#!/usr/bin/env python3
"""Full parity and batch-one CPU benchmark for final PyTorch and ORT models."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch

from gesture.contracts import GESTURE_CLASSES
from gesture.mlp_baseline import GestureMLP, load_manifest
from gesture.onnx_runtime import GestureOnnxRuntime, resolve_repo_path, sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=Path("gesture/configs/mlp_v1_cpu_gate.json")
    )
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def percentile(values: list[float], quantile: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=np.float64), quantile))


def benchmark(call: Callable[[], None], warmup: int, iterations: int) -> dict[str, float]:
    for _ in range(warmup):
        call()
    latencies: list[float] = []
    cpu_started = time.process_time()
    wall_started = time.perf_counter()
    for _ in range(iterations):
        started = time.perf_counter_ns()
        call()
        latencies.append((time.perf_counter_ns() - started) / 1_000_000.0)
    wall = time.perf_counter() - wall_started
    cpu = time.process_time() - cpu_started
    mean = statistics.fmean(latencies)
    return {
        "iterations": iterations,
        "mean_ms": mean,
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "p99_ms": percentile(latencies, 0.99),
        "fps_equivalent": 1000.0 / mean,
        "process_cpu_utilization_percent": 100.0 * cpu / max(wall, 1e-12),
    }


def main() -> int:
    args = parse_args()
    config_path = resolve_repo_path(args.config)
    config = json.loads(config_path.read_text())
    output = resolve_repo_path(config["output"])
    if output.exists():
        raise FileExistsError(f"CPU deployment gate already exists: {output}")
    checkpoint_path = resolve_repo_path(config["pytorch_checkpoint"])
    if sha256_file(checkpoint_path) != config["expected_pytorch_checkpoint_sha256"]:
        raise ValueError("PyTorch checkpoint hash mismatch")
    dataset = load_manifest(resolve_repo_path(config["authoritative_manifest"]))
    if len(dataset.records) != int(config["expected_sample_count"]):
        raise ValueError("full parity sample count mismatch")
    runtime = GestureOnnxRuntime(config["runtime_config"])
    standardized = runtime.standardize(dataset.features)

    torch.set_num_threads(int(config["benchmark"]["pytorch_num_threads"]))
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if checkpoint["class_order"] != list(GESTURE_CLASSES):
        raise ValueError("PyTorch checkpoint class order mismatch")
    model = GestureMLP()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    with torch.no_grad():
        pytorch_all = model(torch.from_numpy(standardized)).numpy()
    ort_all = runtime.run_standardized(standardized)
    error = np.abs(pytorch_all - ort_all)
    argmax_agreement = float(
        np.mean(np.argmax(pytorch_all, axis=1) == np.argmax(ort_all, axis=1))
    )
    parity = config["full_parity"]
    parity_pass = bool(
        np.allclose(
            pytorch_all,
            ort_all,
            atol=float(parity["absolute_tolerance"]),
            rtol=float(parity["relative_tolerance"]),
        )
        and argmax_agreement >= float(parity["required_argmax_agreement"])
    )
    if not parity_pass:
        raise AssertionError("all-data PyTorch/ORT parity failed")

    one = standardized[:1]
    tensor = torch.from_numpy(one)

    def pytorch_call() -> None:
        with torch.no_grad():
            model(tensor)

    def ort_call() -> None:
        runtime.run_standardized(one)

    warmup = int(config["benchmark"]["warmup_iterations"])
    iterations = int(config["benchmark"]["measured_iterations"])
    pytorch_benchmark = benchmark(pytorch_call, warmup, iterations)
    ort_benchmark = benchmark(ort_call, warmup, iterations)
    pytorch_benchmark["model_size_bytes"] = checkpoint_path.stat().st_size
    onnx_path = resolve_repo_path(runtime.config["model"])
    ort_benchmark["model_size_bytes"] = onnx_path.stat().st_size

    report = {
        "verdict": "PASS",
        "metric_scope": config["metric_scope"],
        "onnx_runtime_contract": {
            "load": "PASS",
            "provider": runtime.session.get_providers(),
            "input": {
                "name": runtime.input.name,
                "shape": runtime.input.shape,
                "dtype": runtime.input.type,
            },
            "output": {
                "name": runtime.output.name,
                "shape": runtime.output.shape,
                "dtype": runtime.output.type,
            },
            "dynamic_batch": True,
            "class_order": list(runtime.class_order),
            "preprocessing_version": runtime.preprocessing["preprocessing_version"],
            "production_thumb_veto_threshold": runtime.thumb_threshold,
            "pytorch_dependency_in_production_runtime": False,
            "graph_optimization": runtime.config["graph_optimization"],
        },
        "full_parity": {
            "verdict": "PASS",
            "samples": len(dataset.records),
            "argmax_agreement": argmax_agreement,
            "maximum_absolute_logit_error": float(np.max(error)),
            "mean_absolute_logit_error": float(np.mean(error)),
            "generalization_claim": False,
        },
        "classifier_only_batch_1_benchmark": {
            "warmup_iterations": warmup,
            "pytorch_cpu": pytorch_benchmark,
            "onnx_runtime_cpu": ort_benchmark,
            "mediapipe_latency_included": False,
        },
        "host": {
            "logical_cpus": os.cpu_count(),
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
    }
    write_json(output, report)
    print(f"ARGMAX_AGREEMENT={argmax_agreement:.10f}")
    print(f"MAX_ABS_LOGIT_ERROR={report['full_parity']['maximum_absolute_logit_error']:.12g}")
    print(f"MEAN_ABS_LOGIT_ERROR={report['full_parity']['mean_absolute_logit_error']:.12g}")
    print(f"PYTORCH_P50_MS={pytorch_benchmark['p50_ms']:.6f}")
    print(f"PYTORCH_P95_MS={pytorch_benchmark['p95_ms']:.6f}")
    print(f"ORT_P50_MS={ort_benchmark['p50_ms']:.6f}")
    print(f"ORT_P95_MS={ort_benchmark['p95_ms']:.6f}")
    print(f"CPU_GATE_REPORT={output}")
    print("CPU_BENCHMARK=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
