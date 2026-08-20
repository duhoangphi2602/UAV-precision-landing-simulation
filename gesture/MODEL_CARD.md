# Gesture MLP v1 model card

## Purpose and scope

This classifier recognizes seven static hand poses for a simulated UAV
operator interface: `TAKEOFF`, `FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`,
`HOLD` and `AUTO_LAND`. It is not a general-purpose gesture model and has
not been validated for real-aircraft control.

## Input and preprocessing

MediaPipe provides 21 three-dimensional hand landmarks and handedness. The
frozen `wrist-palm-canonical-v1` pipeline applies wrist centering, palm-scale
normalization, handedness canonicalization and palm rotation, then flattens the
landmarks to 63 float32 features. Standardization mean and standard deviation
were fit on all 2,786 production-training samples and are released beside the
ONNX model.

## Data and leakage prevention

Dataset v1 contains 2,786 authoritative samples across seven classes. Each
class has one right-hand and one left-hand recording session. Generalization
was measured with session-isolated grouped cross-hand 2-fold
cross-validation:

- fold A trained on right-hand sessions and evaluated on left-hand sessions;
- fold B trained on left-hand sessions and evaluated on right-hand sessions.

No frame-level random split was used. Dataset v1 has no independent held-out
test set; every number below is grouped cross-validation evidence.

## Model and training

The PyTorch training model is a 16,903-parameter MLP:

```text
63 → Linear(128) → ReLU → Dropout(0.20)
   → Linear(64)  → ReLU → Dropout(0.15)
   → Linear(7)
```

The frozen recipe uses AdamW, cross-entropy loss, deterministic seeding,
train-fold-only standardization during CV and a predetermined 80-epoch budget
without post-hoc best-epoch selection. After the architecture, recipe and
safety rule were frozen, one deployment model was trained on all 2,786
samples. Its training metrics are optimization evidence, not generalization
evidence.

## Grouped cross-hand results

| Fold | Direction | Accuracy | Macro F1 |
|---|---|---:|---:|
| A | right → left | 0.8595 | 0.8541 |
| B | left → right | 0.8920 | 0.8864 |
| Mean | grouped 2-fold CV | 0.8757 | 0.8703 |

The main observed confusion was `RIGHT` being predicted as `AUTO_LAND`.

## AUTO_LAND safety veto

A deterministic topology check is applied only when the learned class is
`AUTO_LAND`. It uses canonical-landmark thumb straightness multiplied by
palm-relative thumb-tip reach. A rejected prediction becomes `NO_COMMAND`; it
is never silently relabeled. The production threshold is
`0.753987084604339`, calibrated on all production-training `AUTO_LAND`
samples to retain at least 98%. That production calibration is not
generalization evidence.

On grouped CV predictions, the veto changed:

| Metric | Raw MLP | Safety-filtered command |
|---|---:|---:|
| `AUTO_LAND` false positives | 95 | 5 |
| `AUTO_LAND` false-positive rate | 3.98% | 0.21% |
| `AUTO_LAND` recall | 97.25% | 96.00% |
| Command macro F1 | 0.8709 | 0.8842 |

## Deployment

The custom classifier is exported as dynamic-batch float32 ONNX:

- input: `features`, `[N, 63]`;
- output: `logits`, `[N, 7]`;
- ONNX Runtime provider: `CPUExecutionProvider`;
- model size: 68,992 bytes;
- all-data PyTorch/ORT argmax agreement: 100%;
- maximum absolute logit error: approximately `9.54e-06`.

Classifier-only ORT batch-one latency was about 0.006 ms p50 on the reference
host. The accepted live webcam smoke ran at about 17.13 FPS with 20.23 ms
MediaPipe latency and 0.089 ms classifier latency; MediaPipe and camera/UI
work dominate runtime.

The live checklist passed all seven gestures, transitions, no-hand behavior,
and ambiguous `RIGHT`/`AUTO_LAND` cases. No hand produces a fresh
`NO_COMMAND`, so an old actionable prediction is never reused.

## Limitations

- One subject and only two sessions per class limit demographic and
  environmental coverage.
- Results are grouped cross-hand CV, not an independent test metric.
- Static poses do not encode motion or intent beyond the mission-state gates.
- Deployment is validated for simulation; real-flight safety certification is
  out of scope.
