#!/usr/bin/env python3
"""Live MediaPipe/ONNX perception node publishing typed operator requests."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from precision_landing_interfaces.msg import MissionStatus, OperatorCommand
from rclpy.node import Node

from gesture.collect_dataset import configure_capture, draw_hand, extract_hand
from gesture.onnx_runtime import GestureOnnxRuntime, no_hand_prediction, resolve_repo_path
from gesture.operator_command_filter import FilterConfig, GestureCommandFilter
from gesture.thumb_veto import REJECTED_BY_THUMB_VETO


COMMAND_IDS = {
    "NO_COMMAND": OperatorCommand.COMMAND_NO_COMMAND,
    "TAKEOFF": OperatorCommand.COMMAND_TAKEOFF,
    "FORWARD": OperatorCommand.COMMAND_FORWARD,
    "BACKWARD": OperatorCommand.COMMAND_BACKWARD,
    "LEFT": OperatorCommand.COMMAND_LEFT,
    "RIGHT": OperatorCommand.COMMAND_RIGHT,
    "HOLD": OperatorCommand.COMMAND_HOLD,
    "AUTO_LAND": OperatorCommand.COMMAND_AUTO_LAND,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hand-model",
        type=Path,
        default=Path("gesture/models/hand_landmarker.task"),
    )
    parser.add_argument(
        "--runtime-config",
        type=Path,
        default=Path("gesture/configs/onnx_runtime_v1.json"),
    )
    parser.add_argument(
        "--control-config",
        type=Path,
        default=Path("gesture/configs/uav_control_v1.json"),
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--no-mirror-preview", action="store_true")
    return parser.parse_args()


def load_control_config(path: Path) -> dict[str, object]:
    resolved = resolve_repo_path(path)
    config = json.loads(resolved.read_text())
    if config.get("schema_version") != "gesture_uav_control_v1":
        raise ValueError("unexpected gesture UAV control config schema")
    return config


class GestureOperatorNode(Node):
    """Publish only operator intent; this node never owns MAVSDK or PX4."""

    def __init__(self, topic: str):
        super().__init__("gesture_operator")
        self.publisher = self.create_publisher(OperatorCommand, topic, 10)
        self.status_subscription = self.create_subscription(
            MissionStatus,
            "/precision_landing/mission_status",
            self.mission_status_callback,
            10,
        )
        self._last_logged = None
        self.flight_mode = "GESTURE MANUAL"
        self.target_status = "SEARCHING"
        self.authority = "HUMAN"

    def mission_status_callback(self, message) -> None:
        fields = {}
        for field in message.detail.split(" | "):
            if ": " in field:
                key, value = field.split(": ", 1)
                fields[key] = value
        self.target_status = fields.get("TARGET", self.target_status)
        self.authority = fields.get("AUTHORITY", self.authority)
        self.flight_mode = (
            "AUTO LAND" if self.authority == "AUTONOMOUS" else "GESTURE MANUAL"
        )

    def publish_decision(self, decision) -> None:
        message = OperatorCommand()
        message.header.stamp = self.get_clock().now().to_msg()
        message.command = COMMAND_IDS[decision.command]
        message.confidence = float(decision.confidence)
        message.valid = bool(decision.valid)
        message.stale = False
        self.publisher.publish(message)
        log_key = (decision.command, decision.reason)
        if log_key != self._last_logged:
            self.get_logger().info(
                f"operator_command={decision.command} "
                f"confidence={decision.confidence:.3f} reason={decision.reason}"
            )
            self._last_logged = log_key

    def publish_shutdown_hold(self) -> None:
        message = OperatorCommand()
        message.command = OperatorCommand.COMMAND_HOLD
        message.confidence = 0.0
        message.valid = False
        message.stale = False
        for _ in range(5):
            message.header.stamp = self.get_clock().now().to_msg()
            self.publisher.publish(message)
            time.sleep(0.04)


def draw_overlay(
    frame: np.ndarray,
    *,
    raw_command: str,
    filtered_command: str,
    reason: str,
    confidence: float,
    thumb_status: str,
    fps: float,
    landmark_ms: float,
    classifier_ms: float,
    flight_mode: str,
    target_status: str,
    authority: str,
) -> np.ndarray:
    clean_camera = cv2.resize(frame, (480, 360))
    panel = np.zeros((360, 300, 3), dtype=np.uint8)
    lines = [
        "FINAL GESTURE CONTROL",
        f"MODE: {flight_mode}",
        f"GESTURE: {raw_command}",
        f"COMMAND: {filtered_command}",
        f"CONFIDENCE: {confidence:.3f}",
        f"TARGET: {target_status}",
        f"AUTHORITY: {authority}",
        f"FILTER: {reason}",
        f"THUMB: {thumb_status}",
        f"FPS: {fps:.1f}",
        f"MEDIAPIPE: {landmark_ms:.2f} ms",
        f"ORT: {classifier_ms:.3f} ms",
        "Q/Esc: safe HOLD and exit",
    ]
    for index, text in enumerate(lines):
        if index == 0:
            color = (0, 255, 255)
        elif text.startswith("AUTHORITY"):
            color = (0, 165, 255) if authority == "AUTONOMOUS" else (0, 255, 0)
        elif text.startswith("TARGET"):
            color = (0, 255, 0) if target_status == "READY" else (180, 180, 180)
        else:
            color = (235, 235, 235)
        cv2.putText(
            panel,
            text,
            (10, 24 + index * 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
    return np.hstack((panel, clean_camera))


def main() -> int:
    args = parse_args()
    control = load_control_config(args.control_config)
    filter_config = FilterConfig(
        minimum_confidence=float(control["minimum_confidence"]),
        stable_frames=int(control["stable_frames"]),
        takeoff_stable_frames=int(control["takeoff_stable_frames"]),
        minimum_transition_interval_sec=float(
            control["minimum_transition_interval_sec"]
        ),
    )
    command_filter = GestureCommandFilter(filter_config)
    runtime = GestureOnnxRuntime(args.runtime_config)
    hand_model = resolve_repo_path(args.hand_model)
    if not hand_model.is_file():
        raise FileNotFoundError(f"Hand Landmarker model not found: {hand_model}")

    import mediapipe as mp

    rclpy.init()
    node = GestureOperatorNode(str(control["operator_command_topic"]))
    capture = cv2.VideoCapture(args.camera, cv2.CAP_V4L2)
    configure_capture(capture, args.width, args.height)
    if not capture.isOpened():
        capture.release()
        node.destroy_node()
        rclpy.shutdown()
        raise RuntimeError(f"cannot open webcam index {args.camera}")

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(hand_model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    previous_timestamp_ms = -1
    frame_count = 0
    hand_frame_count = 0
    landmark_total_ms = 0.0
    classifier_total_ms = 0.0
    started = time.perf_counter()
    last_metrics_log = started
    mirror = not args.no_mirror_preview
    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
            while rclpy.ok():
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("webcam returned an empty frame")
                timestamp_ms = max(
                    previous_timestamp_ms + 1,
                    int(time.monotonic() * 1000),
                )
                previous_timestamp_ms = timestamp_ms
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                media_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                landmark_started = time.perf_counter()
                result = landmarker.detect_for_video(media_image, timestamp_ms)
                landmark_ms = (time.perf_counter() - landmark_started) * 1000.0
                hand = extract_hand(result)
                prediction = (
                    no_hand_prediction()
                    if hand is None
                    else runtime.predict(hand["feature"])
                )
                landmark_total_ms += landmark_ms
                if hand is not None:
                    hand_frame_count += 1
                    classifier_total_ms += prediction.classifier_ms
                decision = command_filter.update(
                    prediction.effective_command,
                    prediction.confidence,
                    time.monotonic(),
                )
                node.publish_decision(decision)
                rclpy.spin_once(node, timeout_sec=0.0)

                frame_count += 1
                elapsed = max(time.perf_counter() - started, 1e-12)
                if time.perf_counter() - last_metrics_log >= 5.0:
                    node.get_logger().info(
                        "FINAL_GESTURE_METRICS "
                        f"fps={frame_count / elapsed:.2f} "
                        f"mediapipe_ms={landmark_total_ms / frame_count:.3f} "
                        f"ort_ms={classifier_total_ms / max(hand_frame_count, 1):.4f}"
                    )
                    last_metrics_log = time.perf_counter()
                preview = draw_hand(
                    frame,
                    None if hand is None else hand["image_landmarks"],
                    mirror,
                )
                dashboard = draw_overlay(
                    preview,
                    raw_command=prediction.raw_gesture or "NO_HAND",
                    filtered_command=decision.command,
                    reason=decision.reason,
                    confidence=prediction.confidence,
                    thumb_status=prediction.thumb_veto_status,
                    fps=frame_count / elapsed,
                    landmark_ms=landmark_ms,
                    classifier_ms=prediction.classifier_ms,
                    flight_mode=node.flight_mode,
                    target_status=node.target_status,
                    authority=node.authority,
                )
                if prediction.thumb_veto_status == REJECTED_BY_THUMB_VETO:
                    cv2.putText(
                        dashboard,
                        "AUTO_LAND VETOED",
                        (10, 349),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.56,
                        (0, 165, 255),
                        2,
                        cv2.LINE_AA,
                    )
                cv2.imshow("Final Gesture Operator", dashboard)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
    finally:
        if rclpy.ok():
            node.publish_shutdown_hold()
        capture.release()
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
