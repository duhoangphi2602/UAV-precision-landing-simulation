#!/usr/bin/env python3
"""Create deterministic right-vs-left grouped cross-validation manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from gesture.contracts import GESTURE_CLASSES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-root", type=Path, default=Path("gesture/data/v1")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--remediation-registry",
        type=Path,
        default=Path("gesture/configs/landmark_remediation_v1.json"),
    )
    parser.add_argument("--authoritative-manifest", type=Path)
    return parser.parse_args()


def load_records(dataset_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    sessions_root = dataset_root / "sessions"
    for session_directory in sorted(path for path in sessions_root.iterdir() if path.is_dir()):
        metadata = json.loads((session_directory / "session.json").read_text())
        if metadata.get("status") != "COMPLETE":
            raise ValueError(f"session is not COMPLETE: {session_directory.name}")
        session_id = metadata["session_id"]
        if session_id != session_directory.name:
            raise ValueError(f"session directory/id mismatch: {session_directory}")
        hand_scope = metadata["hand_scope"]
        if hand_scope not in {"left", "right"}:
            raise ValueError(f"grouped CV requires one hand per session: {session_id}")

        manifest_path = session_directory / "manifest.jsonl"
        rows = [
            json.loads(line)
            for line in manifest_path.read_text().splitlines()
            if line.strip()
        ]
        if len(rows) != metadata.get("accepted_samples"):
            raise ValueError(f"manifest/session count mismatch: {session_id}")
        for line_number, row in enumerate(rows, start=1):
            if row.get("session_id") != session_id:
                raise ValueError(f"row session mismatch: {row.get('sample_id')}")
            frame_path = Path("sessions") / session_id / row["frame_path"]
            if not (dataset_root / frame_path).is_file():
                raise FileNotFoundError(frame_path)
            records.append(
                {
                    "sample_id": row["sample_id"],
                    "session_id": session_id,
                    "subject_id": row["subject_id"],
                    "label": row["label"],
                    "hand_scope": hand_scope,
                    "detected_handedness": row["handedness"],
                    "handedness_score": row["handedness_score"],
                    "capture_block_id": row.get("capture_block_id"),
                    "frame_path": frame_path.as_posix(),
                    "source_manifest_path": (
                        Path("sessions") / session_id / "manifest.jsonl"
                    ).as_posix(),
                    "source_manifest_line": line_number,
                    "normalized_feature": row["normalized_feature"],
                }
            )

    records.sort(key=lambda row: (row["session_id"], row["sample_id"]))
    sample_ids = [row["sample_id"] for row in records]
    frame_paths = [row["frame_path"] for row in records]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("duplicate sample IDs in dataset")
    if len(frame_paths) != len(set(frame_paths)):
        raise ValueError("duplicate frame paths in dataset")
    return records


def partition_summary(
    train: list[dict[str, Any]], evaluation: list[dict[str, Any]]
) -> dict[str, Any]:
    train_samples = {row["sample_id"] for row in train}
    eval_samples = {row["sample_id"] for row in evaluation}
    train_paths = {row["frame_path"] for row in train}
    eval_paths = {row["frame_path"] for row in evaluation}
    train_sessions = {row["session_id"] for row in train}
    eval_sessions = {row["session_id"] for row in evaluation}
    train_classes = {row["label"] for row in train}
    eval_classes = {row["label"] for row in evaluation}

    sample_overlap = train_samples & eval_samples
    path_overlap = train_paths & eval_paths
    session_overlap = train_sessions & eval_sessions
    expected_classes = set(GESTURE_CLASSES)
    if sample_overlap or path_overlap or session_overlap:
        raise ValueError("grouped-CV leakage detected")
    if train_classes != expected_classes or eval_classes != expected_classes:
        raise ValueError("not all gesture classes are represented on both sides")

    def side(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "samples": len(rows),
            "sessions": sorted({row["session_id"] for row in rows}),
            "classes": dict(sorted(Counter(row["label"] for row in rows).items())),
            "hands": dict(
                sorted(Counter(row["hand_scope"] for row in rows).items())
            ),
        }

    return {
        "train": side(train),
        "eval": side(evaluation),
        "sample_overlap": len(sample_overlap),
        "path_overlap": len(path_overlap),
        "session_overlap": len(session_overlap),
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> str:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in records)
    )
    temporary.replace(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    args = parse_args()
    dataset_root = args.dataset_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else dataset_root / "splits" / "grouped_2fold"
    )
    output.mkdir(parents=True, exist_ok=True)
    all_records = load_records(dataset_root)
    remediation_path = args.remediation_registry.resolve()
    remediation = json.loads(remediation_path.read_text())
    if remediation.get("metadata_corrections"):
        raise ValueError("this bounded pass does not authorize metadata corrections")
    exclusions = remediation.get("exclusions", [])
    excluded_ids = [
        row["sample_id"] for row in exclusions if row.get("decision") == "EXCLUDE"
    ]
    if len(excluded_ids) != len(set(excluded_ids)):
        raise ValueError("duplicate sample ID in remediation exclusions")
    dataset_ids = {row["sample_id"] for row in all_records}
    unknown_exclusions = set(excluded_ids) - dataset_ids
    if unknown_exclusions:
        raise ValueError(f"unknown excluded sample IDs: {sorted(unknown_exclusions)}")
    records = [row for row in all_records if row["sample_id"] not in excluded_ids]
    authoritative_path = (
        args.authoritative_manifest.resolve()
        if args.authoritative_manifest is not None
        else dataset_root / "manifests" / "authoritative_samples.jsonl"
    )
    authoritative_path.parent.mkdir(parents=True, exist_ok=True)
    authoritative_sha256 = write_jsonl(authoritative_path, records)
    right = [row for row in records if row["hand_scope"] == "right"]
    left = [row for row in records if row["hand_scope"] == "left"]
    folds = {
        "fold_a": (right, left),
        "fold_b": (left, right),
    }
    summary: dict[str, Any] = {
        "contract": "GROUPED_2_FOLD_CROSS_VALIDATION",
        "grouping_authority": "session_id",
        "independent_final_held_out_test": False,
        "original_dataset_samples": len(all_records),
        "excluded_samples": len(excluded_ids),
        "dataset_samples": len(records),
        "dataset_sessions": len({row["session_id"] for row in records}),
        "authoritative_manifest": authoritative_path.relative_to(dataset_root).as_posix(),
        "authoritative_manifest_sha256": authoritative_sha256,
        "remediation_registry": str(remediation_path),
        "remediation_registry_sha256": hashlib.sha256(
            remediation_path.read_bytes()
        ).hexdigest(),
        "folds": {},
    }
    for fold_name, (train, evaluation) in folds.items():
        fold_summary = partition_summary(train, evaluation)
        train_path = output / f"{fold_name}_train.jsonl"
        eval_path = output / f"{fold_name}_eval.jsonl"
        fold_summary["train"]["manifest"] = train_path.name
        fold_summary["train"]["sha256"] = write_jsonl(train_path, train)
        fold_summary["eval"]["manifest"] = eval_path.name
        fold_summary["eval"]["sha256"] = write_jsonl(eval_path, evaluation)
        summary["folds"][fold_name] = fold_summary

    summary_path = output / "summary.json"
    temporary = summary_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    temporary.replace(summary_path)
    for fold_name, fold in summary["folds"].items():
        print(
            f"{fold_name.upper()}_TRAIN={fold['train']['samples']} "
            f"{fold_name.upper()}_EVAL={fold['eval']['samples']}"
        )
    print(f"SPLIT_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
