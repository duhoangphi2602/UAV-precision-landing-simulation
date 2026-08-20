# Gesture subsystem

The production path is MediaPipe Hand Landmarker → frozen 63D preprocessing →
ONNX Runtime CPU → confidence and the `AUTO_LAND` thumb veto. It publishes a
typed operator request and never talks to MAVSDK/PX4 directly.

From the repository root:

```bash
make setup-gesture
make verify-assets
gesture/.venv/bin/python -m pytest gesture/tests -q
```

Run perception without ROS/UAV command publication:

```bash
gesture/.venv/bin/python -m gesture.live_onnx_webcam \
  --model gesture/models/hand_landmarker.task \
  --runtime-config gesture/configs/onnx_runtime_v1.json
```

Deployment files in `gesture/deploy/` are release assets. Datasets,
environments, checkpoints and generated experiments remain local and ignored.
Training and evaluation source/configuration is retained for reproducibility;
the final demo does not require the 2,786-frame dataset or PyTorch checkpoint.

See [`MODEL_CARD.md`](MODEL_CARD.md) for the model, evaluation and safety
evidence, and the root [`README.md`](../README.md) for the final demo.
