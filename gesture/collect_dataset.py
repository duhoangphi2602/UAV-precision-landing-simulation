#!/usr/bin/env python3
"""Deliberate webcam collection scaffold for the Slice 5 landmark dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from gesture.contracts import (
    CLASS_KEYS,
    CaptureDecision,
    CaptureGate,
    GESTURE_CLASSES,
    GESTURE_POSE_DEFINITIONS,
    HAND_CONNECTIONS,
    SessionMetadata,
    final_session_status,
    normalize_landmarks,
    validate_identifier,
    validate_label,
)

WEBCAM_FOURCC = "MJPG"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect session-isolated hand-landmark samples deliberately."
    )
    parser.add_argument("--model", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--preview-only",
        action="store_true",
        help="Render landmarks and metrics without creating any output",
    )
    mode.add_argument(
        "--reference-only",
        action="store_true",
        help="Allow one deliberate R-key reference capture per selected label",
    )
    parser.add_argument("--session-id")
    parser.add_argument("--subject-id")
    parser.add_argument("--hand-scope", choices=("left", "right", "both"))
    parser.add_argument("--distance", help="For example: near, medium, far")
    parser.add_argument("--view-angle", help="For example: frontal, tilted")
    parser.add_argument("--lighting")
    parser.add_argument("--background")
    parser.add_argument("--label", default=GESTURE_CLASSES[0])
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--sample-hz", type=float, default=5.0)
    parser.add_argument("--min-feature-delta", type=float, default=0.015)
    parser.add_argument(
        "--target-accepted",
        type=int,
        help="Finish the session cleanly after this many accepted samples",
    )
    parser.add_argument("--output", type=Path, default=Path("gesture/data/v1"))
    parser.add_argument(
        "--reference-output", type=Path, default=Path("gesture/references/v1")
    )
    parser.add_argument("--no-mirror-preview", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configure_capture(capture: Any, width: int, height: int) -> None:
    """Select the camera's reliable compressed stream before sizing frames."""
    capture.set(
        cv2.CAP_PROP_FOURCC,
        cv2.VideoWriter_fourcc(*WEBCAM_FOURCC),
    )
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)


def validate_target_accepted(value: int | None) -> int | None:
    if value is not None and value <= 0:
        raise ValueError("target_accepted must be positive")
    return value


def category_value(category: Any, name: str, default: Any) -> Any:
    value = getattr(category, name, default)
    return default if value is None else value


def extract_hand(result: Any) -> dict[str, Any] | None:
    if not result.hand_landmarks:
        return None

    image_landmarks = np.asarray(
        [[point.x, point.y, point.z] for point in result.hand_landmarks[0]],
        dtype=np.float32,
    )
    world_landmarks = np.asarray(
        [[point.x, point.y, point.z] for point in result.hand_world_landmarks[0]],
        dtype=np.float32,
    )
    category = result.handedness[0][0]
    handedness = str(category_value(category, "category_name", "Unknown"))
    handedness_score = float(category_value(category, "score", 0.0))
    feature = normalize_landmarks(image_landmarks, handedness)
    return {
        "image_landmarks": image_landmarks,
        "world_landmarks": world_landmarks,
        "handedness": handedness,
        "handedness_score": handedness_score,
        "feature": feature,
    }


def draw_hand(
    image: np.ndarray, landmarks: np.ndarray | None, mirror_preview: bool
) -> np.ndarray:
    preview = cv2.flip(image, 1) if mirror_preview else image.copy()
    if landmarks is None:
        return preview

    height, width = preview.shape[:2]
    points: list[tuple[int, int]] = []
    for x_value, y_value, _ in landmarks:
        x_normalized = 1.0 - float(x_value) if mirror_preview else float(x_value)
        points.append((int(x_normalized * width), int(float(y_value) * height)))

    for start, end in HAND_CONNECTIONS:
        cv2.line(preview, points[start], points[end], (80, 220, 80), 2)
    for point in points:
        cv2.circle(preview, point, 3, (40, 80, 255), -1)
    return preview


def overlay_status(
    preview: np.ndarray,
    mode: str,
    label: str,
    recording: bool,
    accepted: int,
    rejected_duplicate: int,
    hand: dict[str, Any] | None,
    preview_fps: float,
    inference_ms: float,
    target_accepted: int | None = None,
) -> None:
    state = "RECORDING" if recording else mode
    color = (0, 0, 255) if recording else (0, 220, 255)
    if mode == "COLLECT":
        controls = "SPACE record/pause | 1-7 label while paused | Q quit"
    elif mode == "REFERENCE":
        controls = "R save one reference | 1-7 label | Q quit"
    else:
        controls = "Non-recording zero-write preview | Q quit"
    sample_progress = (
        str(accepted)
        if target_accepted is None
        else f"{accepted}/{target_accepted}"
    )
    lines = [
        f"LABEL: {label}",
        f"STATE: {state}",
        f"SAMPLES: {sample_progress}  NEAR-DUP SKIPS: {rejected_duplicate}",
        f"PREVIEW FPS: {preview_fps:.1f}  LANDMARK: {inference_ms:.1f} ms",
        controls,
    ]
    if hand is None:
        lines.append("HAND: NONE")
    else:
        lines.append(
            f"HAND: {hand['handedness']} ({hand['handedness_score']:.2f})"
        )
    for index, text in enumerate(lines):
        cv2.putText(
            preview,
            text,
            (12, 28 + index * 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            color if index == 1 else (255, 255, 255),
            2,
            cv2.LINE_AA,
        )


def write_session_metadata(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def append_sample(
    session_directory: Path,
    manifest_path: Path,
    frame: np.ndarray,
    record: dict[str, Any],
) -> None:
    frame_path = session_directory / record["frame_path"]
    if not cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise RuntimeError(f"failed to write frame: {frame_path}")
    with manifest_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, separators=(",", ":")) + "\n")


def save_reference(
    output_directory: Path,
    label: str,
    subject_id: str,
    frame: np.ndarray,
    hand: dict[str, Any],
    model_path: Path,
    model_sha256: str,
    backend: str,
) -> Path:
    """Write exactly one non-training guidance reference for a gesture label."""

    output_directory.mkdir(parents=True, exist_ok=True)
    stem = label.lower()
    image_path = output_directory / f"{stem}.jpg"
    metadata_path = output_directory / f"{stem}.json"
    if image_path.exists() or metadata_path.exists():
        raise FileExistsError(
            f"reference for {label} already exists and will not be overwritten"
        )
    if not cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise RuntimeError(f"failed to write reference image: {image_path}")
    payload = {
        "usage": "collection_guidance_only_not_training",
        "label": label,
        "pose_definition": GESTURE_POSE_DEFINITIONS[label],
        "subject_id": subject_id,
        "captured_utc": utc_now(),
        "landmark_backend": backend,
        "landmark_model_path": str(model_path),
        "landmark_model_sha256": model_sha256,
        "handedness": hand["handedness"],
        "handedness_score": hand["handedness_score"],
        "image_landmarks": hand["image_landmarks"].tolist(),
        "world_landmarks": hand["world_landmarks"].tolist(),
        "normalized_feature": hand["feature"].tolist(),
    }
    write_session_metadata(metadata_path, payload)
    return metadata_path


def main() -> int:
    args = parse_args()
    mode = "PREVIEW" if args.preview_only else "REFERENCE" if args.reference_only else "COLLECT"
    args.target_accepted = validate_target_accepted(args.target_accepted)
    if mode != "COLLECT" and args.target_accepted is not None:
        raise ValueError("target_accepted is a collection-mode option")
    gate = CaptureGate(
        sample_hz=args.sample_hz,
        min_feature_delta=args.min_feature_delta,
        label=validate_label(args.label),
    )
    if mode == "COLLECT":
        required = {
            "session-id": args.session_id,
            "subject-id": args.subject_id,
            "hand-scope": args.hand_scope,
            "distance": args.distance,
            "view-angle": args.view_angle,
            "lighting": args.lighting,
            "background": args.background,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                "collection mode requires: " + ", ".join(sorted(missing))
            )
        args.session_id = validate_identifier(args.session_id, "session_id")
        args.subject_id = validate_identifier(args.subject_id, "subject_id")
    elif mode == "REFERENCE":
        if not args.subject_id:
            raise ValueError("reference mode requires --subject-id")
        args.subject_id = validate_identifier(args.subject_id, "subject_id")
    model_path = args.model.resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"Hand Landmarker model not found: {model_path}")

    # Import lazily: MediaPipe 1.0 initializes optional host audio support during
    # import, which is unavailable in some headless test/sandbox contexts.
    import mediapipe as mp

    capture = cv2.VideoCapture(args.camera, cv2.CAP_V4L2)
    configure_capture(capture, args.width, args.height)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"cannot open webcam index {args.camera}")

    base_options = mp.tasks.BaseOptions(model_asset_path=str(model_path))
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    backend = f"MediaPipe Tasks HandLandmarker {mp.__version__}"
    model_sha256 = sha256_file(model_path)
    session_directory: Path | None = None
    manifest_path: Path | None = None
    session_path: Path | None = None
    metadata: dict[str, Any] | None = None
    if mode == "COLLECT":
        session_directory = args.output.resolve() / "sessions" / args.session_id
        if session_directory.exists():
            capture.release()
            raise FileExistsError(
                f"session already exists and will not be overwritten: {session_directory}"
            )
        (session_directory / "frames").mkdir(parents=True)
        manifest_path = session_directory / "manifest.jsonl"
        session_path = session_directory / "session.json"
        metadata = SessionMetadata(
            session_id=args.session_id,
            subject_id=args.subject_id,
            hand_scope=args.hand_scope,
            distance=args.distance,
            view_angle=args.view_angle,
            lighting=args.lighting,
            background=args.background,
            camera_index=args.camera,
            frame_width=actual_width,
            frame_height=actual_height,
            landmark_backend=backend,
            landmark_model_path=str(model_path),
            landmark_model_sha256=model_sha256,
        ).to_dict()
        metadata.update(
            {
                "started_utc": utc_now(),
                "status": "IN_PROGRESS",
                "target_accepted_samples": args.target_accepted,
            }
        )
        write_session_metadata(session_path, metadata)

    counters: Counter[str] = Counter()
    previous_timestamp_ms = -1
    mirror_preview = not args.no_mirror_preview
    clean_exit = False
    frame_count = 0
    hand_frame_count = 0
    inference_total_ms = 0.0
    loop_started = time.perf_counter()

    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("webcam returned an empty frame")

                timestamp_ms = max(
                    previous_timestamp_ms + 1, int(time.monotonic() * 1000)
                )
                previous_timestamp_ms = timestamp_ms
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                media_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                inference_started = time.perf_counter()
                result = landmarker.detect_for_video(media_image, timestamp_ms)
                inference_ms = (time.perf_counter() - inference_started) * 1000.0
                inference_total_ms += inference_ms
                frame_count += 1
                hand = extract_hand(result)
                if hand is not None:
                    hand_frame_count += 1

                now = time.monotonic()
                if mode == "COLLECT":
                    feature = None if hand is None else hand["feature"]
                    decision = gate.evaluate(now, feature)
                    if decision == CaptureDecision.NEAR_DUPLICATE:
                        counters["near_duplicate"] += 1
                    elif decision == CaptureDecision.ACCEPT:
                        assert hand is not None
                        assert session_directory is not None
                        assert manifest_path is not None
                        assert metadata is not None
                        sample_number = counters["accepted"] + 1
                        sample_id = f"{args.session_id}-{sample_number:06d}"
                        relative_frame = f"frames/{sample_id}.jpg"
                        record = {
                            "schema_version": metadata["schema_version"],
                            "sample_id": sample_id,
                            "session_id": args.session_id,
                            "subject_id": args.subject_id,
                            "label": gate.label,
                            "captured_utc": utc_now(),
                            "monotonic_timestamp_ms": timestamp_ms,
                            "frame_path": relative_frame,
                            "handedness": hand["handedness"],
                            "handedness_score": hand["handedness_score"],
                            "image_landmarks": hand["image_landmarks"].tolist(),
                            "world_landmarks": hand["world_landmarks"].tolist(),
                            "normalized_feature": feature.tolist(),
                            "preprocessing_version": metadata["preprocessing_version"],
                            "capture_block_id": (
                                f"block-{gate.capture_block_index:03d}"
                            ),
                        }
                        append_sample(session_directory, manifest_path, frame, record)
                        counters["accepted"] += 1
                        counters[f"label:{gate.label}"] += 1
                        if (
                            args.target_accepted is not None
                            and counters["accepted"] >= args.target_accepted
                        ):
                            print(f"TARGET_REACHED={args.target_accepted}")
                            clean_exit = True
                            break

                image_landmarks = None if hand is None else hand["image_landmarks"]
                preview = draw_hand(frame, image_landmarks, mirror_preview)
                elapsed = max(time.perf_counter() - loop_started, 1e-9)
                overlay_status(
                    preview,
                    mode,
                    gate.label,
                    gate.recording,
                    counters["accepted"],
                    counters["near_duplicate"],
                    hand,
                    frame_count / elapsed,
                    inference_total_ms / frame_count,
                    args.target_accepted,
                )
                cv2.imshow("Slice 5 Gesture Dataset Collector", preview)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    clean_exit = True
                    break
                if mode == "COLLECT" and key == ord(" "):
                    recording = gate.toggle_recording()
                    if recording:
                        print(f"CAPTURE_BLOCK=block-{gate.capture_block_index:03d}")
                elif chr(key) in CLASS_KEYS:
                    gate.select_label(CLASS_KEYS[chr(key)])
                elif mode == "REFERENCE" and key == ord("r") and hand is not None:
                    saved = save_reference(
                        args.reference_output.resolve(),
                        gate.label,
                        args.subject_id,
                        frame,
                        hand,
                        model_path,
                        model_sha256,
                        backend,
                    )
                    print(f"REFERENCE_SAVED={saved}")
    finally:
        capture.release()
        cv2.destroyAllWindows()
        if metadata is not None and session_path is not None:
            metadata.update(
                {
                    "ended_utc": utc_now(),
                    "status": final_session_status(clean_exit),
                    "accepted_samples": counters["accepted"],
                    "near_duplicate_skips": counters["near_duplicate"],
                    "capture_blocks": gate.capture_block_index,
                    "samples_by_label": {
                        label: counters[f"label:{label}"] for label in GESTURE_CLASSES
                    },
                }
            )
            write_session_metadata(session_path, metadata)

    elapsed = max(time.perf_counter() - loop_started, 1e-9)
    print(f"PREVIEW_FRAMES={frame_count}")
    print(f"HAND_DETECTED_FRAMES={hand_frame_count}")
    print(f"PREVIEW_FPS={frame_count / elapsed:.3f}")
    print(f"LANDMARK_INFERENCE_MS={inference_total_ms / max(frame_count, 1):.3f}")
    print(f"CLEAN_EXIT={'YES' if clean_exit else 'NO'}")
    if session_directory is not None:
        print(f"SESSION_SAVED={session_directory}")
        print(f"ACCEPTED_SAMPLES={counters['accepted']}")
    if mode == "PREVIEW" and hand_frame_count == 0:
        return 2
    return 0 if clean_exit else 3


if __name__ == "__main__":
    raise SystemExit(main())
