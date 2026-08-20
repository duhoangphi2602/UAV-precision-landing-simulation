# Third-Party Notices

This project uses open-source software and model assets under their respective
licenses. Installing or running the project does not change those upstream
terms.

## px4_vision_autonomy-derived package

- Upstream: <https://github.com/Tinny-Robot/px4_vision_autonomy>
- Pinned source revision used for the original import:
  `62e5b6222043c90a49ed3aca58f039c8980528e1`
- License: MIT
- Local derived package: `drone_landing_ws/src/px4_vision_autonomy`

The upstream MIT notice remains in
`drone_landing_ws/src/px4_vision_autonomy/LICENSE`.

## MediaPipe Hand Landmarker

The repository does not redistribute `hand_landmarker.task`. The maintained
download helper retrieves the versioned Google-hosted asset:

<https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task>

Expected SHA-256:
`fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`.
The asset and MediaPipe runtime remain subject to Google's upstream terms.

## Runtime platforms and libraries

PX4 Autopilot, ROS 2, Gazebo Harmonic, MAVSDK, OpenCV, MediaPipe, PyTorch,
ONNX, ONNX Runtime and their transitive dependencies retain their own
copyright and license terms. Refer to their upstream distributions for the
complete notices shipped with each installed version.
