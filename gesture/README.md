# Slice 5 — Gesture Perception Engineering

This directory is isolated from the frozen autonomous-landing runtime. Slice 5
does not publish ROS 2 commands and does not control PX4 or MAVSDK.

## Frozen perception architecture

```text
OpenCV webcam
→ MediaPipe Tasks Hand Landmarker (CPU)
→ 21 xyz landmarks and handedness
→ wrist translation, palm scaling, palm rotation, handedness canonicalization
→ 63-value feature vector
→ ONNX Runtime MLP 63→128→64→7
→ softmax confidence
→ AUTO_LAND thumb-extension veto
→ gesture or NO_COMMAND
```

Collection and the accepted webcam runtime use synchronous MediaPipe `VIDEO`
mode with a single hand.

The frozen class order is:

1. `TAKEOFF`
2. `FORWARD`
3. `BACKWARD`
4. `LEFT`
5. `RIGHT`
6. `HOLD`
7. `AUTO_LAND`

The visual contract is based on finger topology, not screen-pointing direction:

| Command | Frozen static pose |
|---|---|
| `HOLD` | Open palm: thumb, index, middle, ring, and pinky extended |
| `TAKEOFF` | Index, middle, ring, and pinky extended; thumb folded |
| `AUTO_LAND` | Thumb and pinky extended; middle three folded (shaka) |
| `FORWARD` | Index extended; thumb and other fingers folded |
| `BACKWARD` | Index and middle extended; ring/pinky folded; thumb relaxed/folded |
| `LEFT` | Thumb extended; index, middle, ring, and pinky folded |
| `RIGHT` | Pinky extended; thumb, index, middle, and ring folded |

These definitions are mirrored-hand invariant after handedness canonicalization.
They must not change after dataset collection starts unless measured class
separability reveals a serious defect.

No hand and stale predictions are not dataset classes. No hand produces a fresh
`NO_COMMAND` state and never reuses an actionable gesture.

## Dataset v1 contract

The unit of isolation is a recording session, never an adjacent frame. Dataset
v1 contains exactly one right-hand and one left-hand session per class. Its
authoritative evaluation uses grouped cross-hand 2-fold CV: right→left and
left→right. There is no independent held-out test set in dataset v1.

Each session records:

- pseudonymous subject and immutable session identifiers;
- hand scope, distance, view angle, lighting, background, and camera settings;
- landmark backend version and model SHA-256;
- preprocessing/schema versions;
- original unmirrored JPEG frame;
- raw image and world landmarks;
- handedness and confidence;
- normalized 63-value feature;
- label and capture timestamps.

The collector accepts frames only while the operator has explicitly enabled
recording. It rate-limits accepted samples and rejects adjacent landmark
features below the configured RMS-distance threshold.

Before collecting data, capture canonical reference images for all seven frozen
pose definitions. In particular, `TAKEOFF` and `AUTO_LAND` must be visually
unambiguous because their false activations are safety-sensitive.

## Zero-write live preview

This mode opens the real webcam, renders all 21 landmarks and handedness, and
prints measured preview FPS and mean Hand Landmarker inference time after a
clean `Q`/`Esc` exit. It creates no session, frame, manifest, or reference.

```bash
gesture/.venv/bin/python -m gesture.collect_dataset \
  --model gesture/models/hand_landmarker.task \
  --preview-only
```

## Canonical guidance references

Reference mode is separate from dataset collection. Select a label with `1`–`7`
and press `R` once to save one canonical image, raw landmarks, normalized
feature, model path/hash, and pose definition. Existing references are never
overwritten. These local files are collection guidance and are excluded from
training.

```bash
gesture/.venv/bin/python -m gesture.collect_dataset \
  --model gesture/models/hand_landmarker.task \
  --reference-only \
  --subject-id subject01
```

## Collector

The model file is intentionally a required argument; the tool never downloads
models or packages. Local dataset frames and model assets are Git-ignored.

```bash
gesture/.venv/bin/python -m gesture.collect_dataset \
  --model gesture/models/hand_landmarker.task \
  --session-id subject01-session01 \
  --subject-id subject01 \
  --hand-scope right \
  --distance medium \
  --view-angle frontal \
  --lighting indoor-day \
  --background office \
  --label TAKEOFF
```

Controls:

- `Space`: start or pause deliberate recording;
- `1`–`7`: change class while paused;
- `Q` or `Esc`: finish the session.

Output structure:

```text
gesture/data/v1/sessions/<session_id>/
├── session.json
├── manifest.jsonl
└── frames/
    └── <sample_id>.jpg
```

Use two consistently named sessions per pose: `s01-right-mixed` and
`s02-left-mixed`. Collect approximately 200 accepted samples in each session;
the split is assigned later.

Pause recording before changing distance, angle, hand position, or lighting,
then press `Space` to start a new capture block. Every accepted sample records
its `capture_block_id`; grouped CV still keeps each complete session on only
one side of a fold.

Example right-hand session:

```bash
QT_QPA_PLATFORM=xcb gesture/.venv/bin/python -m gesture.collect_dataset \
  --model gesture/models/hand_landmarker.task \
  --session-id subject01-forward-s01-right-mixed \
  --subject-id subject01 \
  --hand-scope right \
  --distance mixed \
  --view-angle mixed \
  --lighting mixed \
  --background office \
  --label FORWARD \
  --target-accepted 200
```

Use at least five deliberate capture blocks per session and vary conditions
between blocks. The collector starts paused and exits cleanly at 200 accepted
samples.

## PyTorch MLP v1 grouped cross-hand baseline

The first baseline is fixed at `63→128→64→7` with ReLU and dropout. It uses
AdamW, CrossEntropyLoss, CPU execution, train-fold-only standardization, 80
predetermined epochs, and the final epoch checkpoint. Cross-hand evaluation is
diagnostic and never selects a checkpoint.

Validate all contracts without creating an experiment:

```bash
gesture/.venv/bin/python -m gesture.train_mlp_cv \
  --config gesture/configs/mlp_v1.json \
  --validate-only
```

The foreground training command omits `--validate-only`. Generated models,
plots, predictions, and metrics are written under `gesture/experiments/mlp_v1/`
and are Git-ignored.

## Deterministic AUTO_LAND thumb veto

The bounded post-baseline safety experiment keeps the learned prediction
visible and applies a semantic topology check only when the raw class is
`AUTO_LAND`. It never relabels a rejected prediction as `RIGHT`:

```text
raw learned classifier
→ canonical thumb straightness × palm-relative thumb-tip reach
→ ALLOWED or REJECTED_BY_THUMB_VETO
→ safety-filtered command
```

Each cross-hand direction derives its numerical threshold only from that
fold's training `AUTO_LAND` features. The evaluator reuses the saved MLP
predictions and performs no retraining:

```bash
gesture/.venv/bin/python -m gesture.evaluate_thumb_veto \
  --config gesture/configs/thumb_veto_v1.json
```

## Final all-data model and prepared ONNX gate

The production model uses all authoritative samples only after grouped
cross-hand CV and the thumb-veto recipe are frozen. Its training accuracy is
optimization evidence, not a new generalization metric. The final checkpoint,
standardization, class mapping, provenance, and production thumb threshold are
written together under `gesture/experiments/mlp_v1/final/`.

The prepared ONNX gate exports only the `63→128→64→7` classifier with dynamic
batch input `float32[N,63]` and output logits `float32[N,7]`. MediaPipe and the
thumb veto remain outside the graph, accompanied by deployment metadata.

```bash
gesture/.venv/bin/python -m gesture.export_mlp_onnx \
  --config gesture/configs/mlp_v1_onnx.json
```

Offline full parity and batch-1 classifier benchmarks are separate from the
PyTorch-free production runner:

```bash
gesture/.venv/bin/python -m gesture.benchmark_mlp_cpu \
  --config gesture/configs/mlp_v1_cpu_gate.json
```

The CPU deployment gate runs all-data numerical parity and separate batch-one
classifier benchmarks for PyTorch and ONNX Runtime. The production runtime
module itself has no PyTorch dependency. The subsequent webcam smoke never
publishes ROS or UAV commands and requires all seven gestures, no-hand safety,
a pose transition, and a live ambiguous `RIGHT`/`AUTO_LAND` veto before it can
write a passing report.

```bash
gesture/.venv/bin/python -m gesture.live_onnx_webcam \
  --model gesture/models/hand_landmarker.task \
  --runtime-config gesture/configs/onnx_runtime_v1.json
```
