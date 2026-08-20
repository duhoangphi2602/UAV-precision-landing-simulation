#!/usr/bin/env python3
"""Interactive webcam smoke for the frozen MediaPipe → ONNX gesture pipeline."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from gesture.collect_dataset import configure_capture, draw_hand, extract_hand
from gesture.contracts import GESTURE_POSE_DEFINITIONS
from gesture.onnx_runtime import (
    NO_COMMAND,
    GestureOnnxRuntime,
    GesturePrediction,
    no_hand_prediction,
    resolve_repo_path,
)
from gesture.thumb_veto import REJECTED_BY_THUMB_VETO


SMOKE_GESTURES = (
    "HOLD",
    "TAKEOFF",
    "FORWARD",
    "BACKWARD",
    "LEFT",
    "RIGHT",
    "AUTO_LAND",
)
TASKS = SMOKE_GESTURES + ("NO_HAND", "TRANSITION", "AMBIGUOUS_RIGHT_AUTO_LAND")


@dataclass
class LiveSmokeChecklist:
    required_consecutive: int
    task_index: int = 0
    consecutive: int = 0
    completed: list[str] = field(default_factory=list)
    transition_stage: str = "HOLD"
    ambiguous_veto_activations: int = 0
    no_hand_command_violations: int = 0

    @property
    def current_task(self) -> str | None:
        return None if self.task_index >= len(TASKS) else TASKS[self.task_index]

    @property
    def all_passed(self) -> bool:
        return self.task_index >= len(TASKS)

    def _finish_current(self) -> None:
        task = self.current_task
        if task is not None:
            self.completed.append(task)
        self.task_index += 1
        self.consecutive = 0

    def update(self, hand_present: bool, prediction: GesturePrediction) -> None:
        if not hand_present and prediction.effective_command != NO_COMMAND:
            self.no_hand_command_violations += 1
        task = self.current_task
        if task is None:
            return
        if task in SMOKE_GESTURES:
            matched = hand_present and prediction.effective_command == task
        elif task == "NO_HAND":
            matched = not hand_present and prediction.effective_command == NO_COMMAND
        elif task == "TRANSITION":
            expected = self.transition_stage
            matched = hand_present and prediction.effective_command == expected
            if matched:
                self.consecutive += 1
                if self.consecutive >= self.required_consecutive:
                    if self.transition_stage == "HOLD":
                        self.transition_stage = "FORWARD"
                        self.consecutive = 0
                    else:
                        self._finish_current()
                return
        else:
            if prediction.thumb_veto_status == REJECTED_BY_THUMB_VETO:
                self.ambiguous_veto_activations += 1
            matched = (
                hand_present
                and prediction.raw_gesture in {"RIGHT", "AUTO_LAND"}
                and prediction.effective_command != "AUTO_LAND"
            )
            if (
                matched
                and self.consecutive + 1 >= self.required_consecutive
                and self.ambiguous_veto_activations == 0
            ):
                matched = False
        self.consecutive = self.consecutive + 1 if matched else 0
        if self.consecutive >= self.required_consecutive:
            self._finish_current()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument(
        "--runtime-config", type=Path, default=Path("gesture/configs/onnx_runtime_v1.json")
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--required-consecutive", type=int, default=8)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("gesture/experiments/mlp_v1/final/live_smoke.json"),
    )
    parser.add_argument("--no-mirror-preview", action="store_true")
    return parser.parse_args()


def task_instruction(checklist: LiveSmokeChecklist) -> str:
    task = checklist.current_task
    if task is None:
        return "ALL REQUIRED LIVE TASKS PASSED"
    if task in SMOKE_GESTURES:
        return f"SHOW {task}: {GESTURE_POSE_DEFINITIONS[task]}"
    if task == "NO_HAND":
        return "REMOVE HAND COMPLETELY — must show NO_COMMAND"
    if task == "TRANSITION":
        return f"TRANSITION: show {checklist.transition_stage} steadily"
    return "AMBIGUOUS RIGHT/AUTO_LAND: folded thumb; produce a live veto safely"


def overlay(
    image: np.ndarray,
    prediction: GesturePrediction,
    checklist: LiveSmokeChecklist,
    fps: float,
    mediapipe_ms: float,
    total_ms: float,
    threshold: float,
) -> None:
    progress = f"{len(checklist.completed)}/{len(TASKS)}"
    score = (
        "N/A"
        if prediction.thumb_extension_score is None
        else f"{prediction.thumb_extension_score:.3f}/{threshold:.3f}"
    )
    lines = [
        f"TASK {progress}: {checklist.current_task or 'COMPLETE'}  stable={checklist.consecutive}/{checklist.required_consecutive}",
        task_instruction(checklist),
        f"GESTURE: {prediction.raw_gesture or 'NO_HAND'}  COMMAND: {prediction.effective_command}",
        f"CONFIDENCE: {prediction.confidence:.3f}  THUMB: {prediction.thumb_veto_status}  SCORE: {score}",
        f"FPS: {fps:.1f}  MEDIAPIPE: {mediapipe_ms:.2f} ms  ORT: {prediction.classifier_ms:.3f} ms  TOTAL: {total_ms:.2f} ms",
        "Q/Esc abort | runner auto-finishes only after every required task passes",
    ]
    for index, text in enumerate(lines):
        color = (0, 255, 0) if checklist.all_passed else (255, 255, 255)
        cv2.putText(
            image,
            text,
            (10, 26 + index * 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.51,
            color,
            2,
            cv2.LINE_AA,
        )


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    if args.required_consecutive <= 0:
        raise ValueError("required-consecutive must be positive")
    model_path = args.model.resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"Hand Landmarker model not found: {model_path}")
    output = resolve_repo_path(args.output)
    if output.exists():
        raise FileExistsError(f"live smoke report already exists: {output}")
    runtime = GestureOnnxRuntime(args.runtime_config)

    import mediapipe as mp

    capture = cv2.VideoCapture(args.camera, cv2.CAP_V4L2)
    configure_capture(capture, args.width, args.height)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"cannot open webcam index {args.camera}")
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    checklist = LiveSmokeChecklist(args.required_consecutive)
    previous_timestamp_ms = -1
    frame_count = 0
    hand_frames = 0
    mediapipe_total_ms = 0.0
    ort_total_ms = 0.0
    total_hand_pipeline_ms = 0.0
    live_veto_count = 0
    started = time.perf_counter()
    clean_completion = False
    mirror = not args.no_mirror_preview
    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("webcam returned an empty frame")
                pipeline_started = time.perf_counter()
                timestamp_ms = max(previous_timestamp_ms + 1, int(time.monotonic() * 1000))
                previous_timestamp_ms = timestamp_ms
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                media_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                landmark_started = time.perf_counter()
                result = landmarker.detect_for_video(media_image, timestamp_ms)
                landmark_ms = (time.perf_counter() - landmark_started) * 1000.0
                hand = extract_hand(result)
                if hand is None:
                    prediction = no_hand_prediction()
                else:
                    prediction = runtime.predict(hand["feature"])
                    hand_frames += 1
                    ort_total_ms += prediction.classifier_ms
                    total_hand_pipeline_ms += (time.perf_counter() - pipeline_started) * 1000.0
                    if prediction.thumb_veto_status == REJECTED_BY_THUMB_VETO:
                        live_veto_count += 1
                frame_count += 1
                mediapipe_total_ms += landmark_ms
                checklist.update(hand is not None, prediction)
                elapsed = max(time.perf_counter() - started, 1e-12)
                preview = draw_hand(
                    frame,
                    None if hand is None else hand["image_landmarks"],
                    mirror,
                )
                overlay(
                    preview,
                    prediction,
                    checklist,
                    frame_count / elapsed,
                    mediapipe_total_ms / frame_count,
                    total_hand_pipeline_ms / max(hand_frames, 1),
                    runtime.thumb_threshold,
                )
                cv2.imshow("Slice 5 ONNX Runtime Live Gesture Smoke", preview)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if checklist.all_passed:
                    clean_completion = True
                    break
    finally:
        capture.release()
        cv2.destroyAllWindows()

    elapsed = max(time.perf_counter() - started, 1e-12)
    live_pass = (
        clean_completion
        and checklist.completed == list(TASKS)
        and checklist.no_hand_command_violations == 0
    )
    thumb_pass = (
        live_pass
        and checklist.ambiguous_veto_activations > 0
        and "AUTO_LAND" in checklist.completed
    )
    report = {
        "verdict": "PASS" if live_pass and thumb_pass else "FAIL",
        "pipeline": [
            "webcam",
            "MediaPipe HandLandmarker CPU",
            "frozen canonical 63D preprocessing",
            "ONNX Runtime CPU classifier",
            "softmax confidence",
            "AUTO_LAND thumb veto",
            "final gesture prediction",
        ],
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "tasks_required": list(TASKS),
        "tasks_completed": checklist.completed,
        "required_consecutive_frames": args.required_consecutive,
        "frames": frame_count,
        "hand_frames": hand_frames,
        "live_fps": frame_count / elapsed,
        "mediapipe_ms": mediapipe_total_ms / max(frame_count, 1),
        "ort_classifier_ms": ort_total_ms / max(hand_frames, 1),
        "total_hand_pipeline_ms": total_hand_pipeline_ms / max(hand_frames, 1),
        "live_veto_activations": live_veto_count,
        "ambiguous_task_veto_activations": checklist.ambiguous_veto_activations,
        "no_hand_command_violations": checklist.no_hand_command_violations,
        "no_hand_policy": NO_COMMAND,
        "production_thumb_veto_threshold": runtime.thumb_threshold,
        "live_gesture_result": "PASS" if live_pass else "FAIL",
        "thumb_veto_runtime": "PASS" if thumb_pass else "FAIL",
        "ros_or_uav_commands_published": False,
        "concurrent_gazebo_acceptance_claim": False,
    }
    if live_pass and thumb_pass:
        write_report(output, report)
    else:
        failed = output.with_name(
            f"{output.stem}.failed-{datetime.now().strftime('%Y%m%dT%H%M%S')}{output.suffix}"
        )
        write_report(failed, report)
        print(f"LIVE_FAILURE_REPORT={failed}")
    print(f"LIVE_FPS={report['live_fps']:.3f}")
    print(f"MEDIAPIPE_MS={report['mediapipe_ms']:.3f}")
    print(f"ORT_CLASSIFIER_MS={report['ort_classifier_ms']:.6f}")
    print(f"TOTAL_PIPELINE_MS={report['total_hand_pipeline_ms']:.3f}")
    print(f"LIVE_GESTURE_RESULT={report['live_gesture_result']}")
    print(f"THUMB_VETO_RUNTIME={report['thumb_veto_runtime']}")
    if live_pass and thumb_pass:
        print(f"LIVE_SMOKE_REPORT={output}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
