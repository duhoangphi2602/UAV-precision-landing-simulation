# REPOSITORY INVENTORY

## 1. Git Baseline
- **working_tree_before_report**: CLEAN (no uncommitted changes)
- **working_tree_after_report**: 1 untracked file (`docs/evidence/REPOSITORY_INVENTORY.md`)
- **Current Branch**: `main`
- **Current Commit SHA**: `fa15a42e08511f298936b52c7dbe8911a6ca6ce6`
- **Phase A Commit**: `fa15a42e08511f298936b52c7dbe8911a6ca6ce6`
- **Tags Found**: `cpp-pid-baseline-v1`

## 2. Inventory Summary
- **Nested Repositories**: 0 (Excluding root `.git`)
- **Large Files (>20MB)**: 0
- **Cleanup Candidate Count**: 0 (All requested targets like `tmp_upstream/`, `fix_waypoint.py`, `old_inspection.sdf`, etc., are already gone)
- **ignored_output_truncated**: NO

## 3. Classification

### Cleanup Candidates
- **tmp_upstream/**: NOT FOUND -> IGNORE
- **fix_waypoint.py**: NOT FOUND -> IGNORE
- **old_inspection.sdf**: NOT FOUND -> IGNORE
- **transpose_texture.py**: NOT FOUND -> IGNORE
- **test_topics.txt**: NOT FOUND -> IGNORE
- **imu.txt**: NOT FOUND -> IGNORE
- **ps_out.txt**: NOT FOUND -> IGNORE
- **sitl_logs.txt**: NOT FOUND -> IGNORE
- **mission_logs.txt**: NOT FOUND -> IGNORE

### Generated Output & Temporary Files
- **drone_landing_ws/build/**: IGNORED -> IGNORE_GENERATED
- **drone_landing_ws/install/**: IGNORED -> IGNORE_GENERATED
- **drone_landing_ws/log/**: IGNORED -> IGNORE_GENERATED
- **.venv/**: IGNORED -> IGNORE_GENERATED
- **__pycache__/**: IGNORED -> IGNORE_GENERATED
- **drone_landing_ws/src/px4_vision_autonomy/debug_frame.png**: IGNORED -> IGNORE_GENERATED

### Evidence and Licenses
- **Root LICENSE**: NOT FOUND
- **THIRD_PARTY_NOTICES.md**: NOT FOUND
- **drone_landing_ws/src/px4_vision_autonomy/LICENSE**: TRACKED -> NEEDS_REVIEW (Risk: Losing upstream attribution if we delete the package without a root license).
- **docs/evidence/FINAL_TERMINATION_REPORT.md**: TRACKED (from Phase A) -> KEEP
- **artifacts/logs/REPORT_C2.md**: IGNORED -> MOVE_TO_EVIDENCE
- **artifacts/logs/REPORT_C3.md**: IGNORED -> MOVE_TO_EVIDENCE
- **artifacts/logs/ (Raw runtime logs)**: IGNORED -> MOVE_TO_EVIDENCE or KEEP

## 4. Needs Review Items
1. **drone_landing_ws/src/px4_vision_autonomy/LICENSE**: Is deep inside the package. Should we move it to the root or create a new attribution?
2. **artifacts/logs/REPORT_C*.md**: Need to be moved to `docs/evidence/` to become officially tracked evidence.
