# Slice 5 Gesture Perception Freeze

Freeze date: 2026-08-20
Status: `GESTURE_PERCEPTION_DEMO_READY=YES`, `ONNX_RUNTIME_READY=YES`

## Frozen runtime

```text
webcam
→ MediaPipe Hand Landmarker CPU
→ wrist/palm canonical 63D feature
→ ONNX Runtime CPU classifier
→ softmax confidence
→ AUTO_LAND thumb-extension veto
→ gesture or NO_COMMAND
```

The class order is `TAKEOFF`, `FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `HOLD`,
`AUTO_LAND`. Perception does not publish ROS or UAV commands.

## Accepted evidence

- authoritative dataset: 2,786 unique samples, landmark QA PASS;
- grouped cross-hand 2-fold CV mean macro F1: `0.8702640419`;
- safety-filtered command macro F1: `0.8842053560`;
- `AUTO_LAND` false positives after semantic veto: `5/2386` negatives;
- full production PyTorch/ONNX parity samples: `2,786`;
- full parity argmax agreement: `1.0`;
- maximum absolute logit error: `9.5367431640625e-06`;
- live smoke: all seven gestures, no-hand, transition and ambiguous thumb-veto
  PASS;
- no-hand actionable-command violations: `0`;
- live performance: `17.128 FPS`, MediaPipe `20.232 ms`, classifier
  `0.088630 ms`, hand pipeline `20.962 ms`;
- concurrent Gazebo/PX4 performance is not claimed.

## Selective tracked freeze set

Track these maintained classes only:

- `gesture/*.py`: collection, QA, split preparation, model training,
  evaluation, export, CPU benchmark and production webcam runtime;
- `gesture/configs/*.json`: frozen data/model/safety/deployment contracts;
- `gesture/tests/*.py`: dataset, leakage, model, safety, export, runtime and live
  checklist gates;
- `gesture/requirements.lock.txt` and `gesture/README.md`;
- this manifest and the current project overview/handoff documentation;
- `.gitignore` rules protecting local data and generated assets.

The frozen source deliberately keeps one accepted offline CPU gate
(`benchmark_mlp_cpu.py`) and one accepted live gate (`live_onnx_webcam.py`).

## Local deployable artifacts

The repository policy ignores datasets, virtual environments, model binaries
and generated experiment outputs. The final artifacts are small, but they
remain local because tracking them would require explicit exceptions to the
existing `gesture/experiments/**`, `gesture/models/**`, `gesture/data/**`,
`**/*.pt` and `**/*.onnx` rules. This freeze does not silently override that
policy.

| Local artifact | SHA-256 |
|---|---|
| `gesture/data/v1/manifests/authoritative_samples.jsonl` | `52ceb56eaf40b29cc50e023f9bd34f6119512d77e0c8f9866236b0c8ce52043f` |
| `gesture/models/hand_landmarker.task` | `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` |
| `gesture/experiments/mlp_v1/final/model.pt` | `7109a1484319ea4d10432261f1758d932f796907b2cd6ebcd48371cd1657d1f1` |
| `gesture/experiments/mlp_v1/final/model.onnx` | `de5509bf849a6991858e95d521a0325bf711393f64668b8af9a1a129403505bf` |
| `gesture/experiments/mlp_v1/final/preprocessing.json` | `09afa7821c0f5e719ede1848e50597e0750efc90f7b1febf82de0ea138e4428d` |
| `gesture/experiments/mlp_v1/final/deployment_config.json` | `32be9fed57903aff41582eda86b7363e23cd550953b8ffa45cd1b2322f5255f9` |
| `gesture/experiments/mlp_v1/final/class_mapping.json` | `2f00b0327b36bc9a9f4bcb6aac8190bd1cf9a4f0de4139d0b62eb232a07ceaaa` |
| `gesture/experiments/mlp_v1/final/cpu_deployment_gate.json` | `3e3c6492e9c794de0381eca5296c9f557157d410f99638bc43abda738da46d1d` |
| `gesture/experiments/mlp_v1/final/live_smoke.json` | `298e5c8f56185b868b2d4db4c4846c13301096e736d0fe33438184cf9fb2ab61` |

Local size classes at freeze time:

- gesture dataset: approximately `374M`;
- gesture environment: approximately `1.7G`;
- gesture generated experiments: approximately `2.6M`;
- MediaPipe model directory: approximately `7.5M`.

## Integration invariants

- Mission Commander remains the sole MAVSDK/PX4 command owner;
- no hand, stale inference and vetoed `AUTO_LAND` are non-actionable;
- the gesture node must issue guarded requests, never direct flight commands;
- autonomous landing continues to use the accepted ArUco/C++ PID path;
- no model retraining is authorized by this freeze.
