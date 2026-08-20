# New Chat Import Manifest

> Purpose: minimize duplicate ChatGPT Project context while preserving implementation truth, historical rationale, evidence, unresolved gaps, and the ability to recover the later project lineage.

## 1. Import Rules

- Current Git remains the implementation evidence for the current checkout. Ordinary source and tracked configuration should not be copied into ChatGPT Project sources.
- `PROJECT_CONTINUITY.md` remains the primary project-evolution/history source.
- `MIGRATION_FILE_MANIFEST.md` remains the detailed historical artifact/provenance source.
- The four IDE audit documents reconcile those historical sources with this checkout; they do not supersede either historical source.
- `FULL / MUST RECOVER` means recover the original artifact from the old conversation or old storage and make the full artifact available to the new ChatGPT Project.
- `SUMMARY` means the historical migration sources and this manifest preserve enough information for ordinary continuation; recover the original only for a focused investigation.
- `NO` means do not consume ChatGPT Project capacity with the raw item.
- A file absent from this checkout may still have existed in another lineage.

## 2. Full Migration Table

| Item | Path/Filename | Category | Current or historical | Unique information | Already available in Git? | Import into new ChatGPT? | Import mode | Reason | Priority | Risk if omitted |
|---|---|---|---|---|---|---|---|---|---|---|
| IDE-01 | `docs/context/NEW_CHAT_BOOTSTRAP.md` | A — Must import | Current checkout reconciliation | Concise identity, truth boundaries, verdict, reading order | New untracked audit document | Yes | FULL | Canonical entry point for the new chat | CRITICAL | Agent may resume from the wrong lineage |
| IDE-02 | `docs/context/REPO_CONTEXT_GAPS.md` | A — Must import | Current checkout reconciliation | Exact unknowns and recovery blockers | New untracked audit document | Yes | FULL | Prevents guesses from becoming project history | CRITICAL | Missing lineage may be silently reimplemented |
| IDE-03 | `docs/context/IDE_REPO_SNAPSHOT.md` | A — Must import | Current checkout | Detailed Git, architecture, environment, and validation snapshot | New untracked audit document | Yes | FULL | Establishes what this checkout actually contains | HIGH | Historical claims may be mistaken for local implementation |
| IDE-04 | `docs/context/NEW_CHAT_IMPORT_MANIFEST.md` | A — Must import | Migration reconciliation | Complete import decisions and recovery priorities | New untracked audit document | Yes | FULL | Controls Project-source duplication and omissions | CRITICAL | High-value artifacts may be lost or redundant files uploaded |
| HIST-01 | `docs/context/PROJECT_CONTINUITY.md` | A — Must import | Historical project state | Primary evolution, rationale, invariants, claimed later state, workflow preferences | No; locally untracked | Yes | FULL | Core old-conversation continuity source | CRITICAL | Later decisions and intended direction are lost |
| HIST-02 | `docs/context/MIGRATION_FILE_MANIFEST.md` | A — Must import | Historical artifact provenance | Detailed role, sequence, and relationship of 31 old-chat artifacts | No; locally untracked | Yes | FULL | First-class provenance source; not replaced by this table | CRITICAL | Artifact meaning and chronology become ambiguous |
| REPO-01 | `README.md` | C — Keep in Git/local | Current checkout intent | User-facing architecture, commands, prerequisites, claimed validation | Yes | No | NO | New audit docs summarize relevant parts; Codex can inspect Git | MEDIUM | Low if Git remains accessible |
| REPO-02 | `master_plan.md` | C — Keep in Git/local | Historical/current-checkout specification | Original MVP scope, gates, ownership, fallback rules | Yes | No | NO | Useful locally but large and partially diverged from implementation | MEDIUM | Original acceptance intent is less accessible |
| REPO-03 | `docs/evidence/*.md` | D — Optional historical evidence | Historical repository evidence | Test/demo/cleanup/license/static-validation claims | Yes | No | NO | Retain in Git; import a specific report only for evidence review | MEDIUM | Historical validation details require a Git lookup |
| REPO-04 | `docs/evidence/WALKTHROUGH.md` | B — Summary sufficient | Historical repository evidence | Newer fixed-demo architecture and run summary | Yes | No | NO | Bootstrap/snapshot cover current meaning | LOW | Low |
| REPO-05 | `docs/walkthrough.md` | E — Do not import | Historically superseded | Older topic/environment-polish claims that conflict with current code/world | Yes | No | NO | Could mislead the new chat | LOW | Low; import creates confusion |
| REPO-06 | `UPSTREAM_BASELINE.md` and `THIRD_PARTY_NOTICES.md` | C — Keep in Git/local | Current checkout provenance | Upstream commit/source and MIT attribution | Yes | No | NO | Legal/provenance files remain canonical in Git | HIGH | Attribution can still be recovered from Git |
| REPO-07 | Current source, launch, Docker, scripts, YAML, tests, world/model assets | C — Keep in Git/local | Current checkout implementation | Executable implementation truth | Yes | No | NO | Do not create stale ChatGPT copies of normal source | CRITICAL | None while Git/Codex access remains available |
| LEGACY-01 | `camera_gate_report.md` | B — Summary | Historical project state | First camera transport PASS / marker detection FAIL split | No original in checkout | Summary only | SUMMARY | Provenance is already detailed in the historical manifest | MEDIUM | Early blocker rationale becomes less clear |
| LEGACY-02 | `image(58).png` | D — Optional historical evidence | Historical project state | Visual evidence of the early incorrect camera view | No | No | NO | Needed only to reconstruct the original camera failure | LOW | Minimal |
| LEGACY-03 | `camera_gate_report(1).md` | B — Summary | Historical project state | Later camera-orientation recovery checkpoint | No original in checkout | Summary only | SUMMARY | Historical manifest preserves the key distinction from #01 | MEDIUM | Camera recovery sequence may be blurred |
| LEGACY-04 | `debug_frame.png` | D — Optional historical evidence | Historical project state | Early frame used to separate image transport from perception quality | A different/current tracked debug frame exists; identity is unproven | No | NO | Filename collision must not be treated as equivalence | LOW | Minimal |
| LEGACY-05 | `snapshot_report.md` | B — Summary | Historical project state | Early runtime/repository recovery snapshot | Removed file is recoverable in older local Git history, but old-chat identity is not guaranteed | Summary only | SUMMARY | Raw copy includes obsolete state and machine-specific paths | MEDIUM | Some early debugging chronology is lost |
| LEGACY-06 | `image(59).png` | D — Optional historical evidence | Historical project state | IDE/quota interruption screenshot | No | No | NO | Workflow screenshot has no current technical authority | LOW | Minimal |
| LEGACY-07 | `image(60).png` | D — Optional historical evidence | Historical project state | Early Gazebo/baseline stabilization screenshot | No | No | NO | Keep only if reconstructing early visual history | LOW | Minimal |
| LEGACY-08 | `image(61).png` | D — Optional historical evidence | Historical project state | First successful marker-visibility visual | No | No | NO | Current code/evidence establishes the later capability | LOW | Historical visual milestone is lost |
| LEGACY-09 | `image(62).png` | D — Optional historical evidence | Historical project state | First detector overlay and near-zero error visual | No | No | NO | Useful only for visual chronology | LOW | Minimal |
| LEGACY-10 | `image(63).png` | D — Optional historical evidence | Historical project state | Gazebo plus OpenCV two-window visual | No | No | NO | Portfolio evidence can remain archived locally | LOW | Demo appearance history is reduced |
| LEGACY-11 | `REPORT_C1.md` | C — Already represented | Historical project state | C++ PID audit and ten-test result | A matching tracked report and its source/tests exist | No | NO | Repository evidence is sufficient for ordinary use | MEDIUM | Low; raw historical context remains in Git |
| LEGACY-12 | `Pasted text(3).txt` | B — Summary | Historical project state | Runtime log ordering and terminal-state debugging | No original; raw logs absent | Summary only | SUMMARY | Key termination lesson is in historical documents | MEDIUM | Detailed log chronology is unavailable |
| LEGACY-13 | `ENGINEERING_UPGRADE_READINESS_REPORT.md` | A — Must import | Historical project state | Original architecture snapshot and Python/C++/typed-interface rationale | No | Yes | FULL / MUST RECOVER | Unique bridge between fixed baseline and later slices | HIGH | Agent may redesign intentional boundaries |
| LEGACY-14 | `Screenshot From 2026-07-27 21-03-33.png` | D — Optional historical evidence | Historical project state | Slice 1 dashboard/readability visual | No | No | NO | UI history is not needed for normal continuation | LOW | Dashboard appearance rationale is weaker |
| LEGACY-15 | `walkthrough.md` | B — Summary | Historical project state | Slice 1 typed-interface/dashboard/metrics walkthrough | A different tracked file with the same name exists; equivalence is unproven | Summary only | SUMMARY | Later reports and historical sources retain the architecture summary | MEDIUM | Intermediate Slice 1 corrections are less detailed |
| LEGACY-16 | `SLICE_2_MOVING_ARUCO_ACCEPTANCE.md` | A — Must import | Historical project state | Moving-platform acceptance, safety gates, fixed regression | No | Yes | FULL / MUST RECOVER | Current checkout has no moving-mode implementation or equivalent acceptance record | CRITICAL | An accepted milestone may be reimplemented or retuned blindly |
| LEGACY-17 | `walkthrough(1).md` | B — Summary | Historical project state | Human-readable Slice 2 end-to-end flow | No | Summary only | SUMMARY | #16 and #19 are the higher-value full sources | MEDIUM | Moving-slice narrative is less approachable |
| LEGACY-18 | `pid_moving.yaml` | D — Keep local historical evidence | Historically superseded configuration | Intermediate moving PID experiment, including unsafe historical flips | No | No | NO — KEEP LOCAL AS HISTORICAL EVIDENCE | `flip_x=false` / `flip_y=false` were historically superseded; never promote automatically to current configuration | HIGH | Importing as current could reintroduce unstable sign mapping |
| LEGACY-19 | `REPORT_C2(1).md` | A — Must import | Historical project state | BODY-frame/sign diagnosis, rejected run, safe mapping, low-altitude threshold history | No | Yes | FULL / MUST RECOVER | Unique failure and decision rationale | CRITICAL | Sign errors and rejected Kalman/config choices may recur |
| LEGACY-20 | `implementation_plan.md` | B — Summary | Historical project state | Slice 3 baseline YOLO/ONNX plan and gates | No | Summary only | SUMMARY | Plan is completed/superseded; #21 preserves acceptance | MEDIUM | Baseline process provenance is thinner |
| LEGACY-21 | `SLICE_3_YOLO_ONNX_ACCEPTANCE.md` | A — Must import | Historical project state | Dataset counts, four-class baseline, training and ONNX parity evidence | No | Yes | FULL / MUST RECOVER | Establishes the reference from which Candidate A evolved | HIGH | Baseline and deployment metrics may be conflated |
| LEGACY-22 | `confusion_matrix_normalized.png` | B — Summary | Historical project state | Visual class-confusion evidence supporting class collapse | No | Summary only | SUMMARY | Key conclusion can be summarized; raw image optional for focused audit | MEDIUM | Data-centric rationale is less visually demonstrable |
| LEGACY-23 | `labels.jpg` | D — Optional historical evidence | Historical project state | Label imbalance and small-object visualization | No | No | NO | Quantitative conclusions are captured in #28 | LOW | Low |
| LEGACY-24 | `results.csv` | A — Must import | Historical project state | Raw per-epoch training metrics potentially relevant to metric provenance | No | Yes | FULL / MUST RECOVER | May be needed to investigate `0.609` versus `0.52415`; it does not itself resolve the discrepancy | CRITICAL | Metric source/curve provenance may be unrecoverable |
| LEGACY-25 | `val_batch0_labels.jpg` | D — Optional historical evidence | Historical project state | Annotation visual-sanity evidence | No | No | NO | Retain locally for dataset audit only | LOW | Minimal |
| LEGACY-26 | `val_batch0_pred.jpg` | D — Optional historical evidence | Historical project state | Baseline qualitative prediction evidence | No | No | NO | Retain locally for focused model audit | LOW | Minimal |
| LEGACY-27 | `implementation_plan(1).md` | B — Summary | Historical project state | Slice 3B single-class/960/P2/SAHI experimental plan | No | Summary only | SUMMARY | #28 and #29 preserve outcomes and rationale | MEDIUM | Experimental sequencing is less detailed |
| LEGACY-28 | `SLICE_3B_SMALL_OBJECT_OPTIMIZATION.md` | A — Must import | Historical project state | Data-centric diagnosis, Candidate A configuration/results, SAHI decision | No | Yes | FULL / MUST RECOVER | Core model-selection reasoning absent from current Git | CRITICAL | Rejected techniques or wrong task definition may be reopened |
| LEGACY-29 | `SLICE_3C_PARETO_OPTIMIZATION.md` | A — Must import | Historical project state | Candidate A/B fair comparison, final selection, distillation decision | No | Yes | FULL / MUST RECOVER | Final detector-selection record | CRITICAL | P2 may be selected without the prior Pareto evidence |
| LEGACY-30 | `implementation_plan(3).md` | A — Must import | Historical project state | TensorRT FP32/FP16/INT8 scope, gates, calibration and benchmark contract | No | Yes | FULL / MUST RECOVER | Defines the intended Slice 4 acceptance contract | CRITICAL | Deployment work may use incompatible parity criteria |
| LEGACY-31 | `implementation_plan(4).md` | A — Must import | Historical project state | Toolchain remediation, CUDA/TensorRT choices, manual-environment gate | No | Yes | FULL / MUST RECOVER | Explains why environment changes were isolated and user-controlled | CRITICAL | Old blocker may be repeated or host changed unsafely |
| GAP-01 | Later typed/moving implementation | A — Must recover locally | Historical project state / absent checkout | Typed messages, moving controller/world/config/demo and accepted source state | Not in current checkout or reachable local refs checked | No raw Chat import; recover to Git/local | NO | Executable source belongs in version control, not duplicated in ChatGPT | CRITICAL | Cannot continue or validate the claimed moving lineage |
| GAP-02 | `ml/` implementation and tracked ML metadata | A — Must recover locally | Historical project state / absent checkout | Dataset validation, training, export, evaluation, TensorRT scripts/configs | Not in current checkout | No raw Chat import; recover to Git/local | NO | Source/scripts should be restored to the correct repository lineage | CRITICAL | Claimed AI/TensorRT work cannot be reproduced |
| GAP-03 | Raw dataset and derived single-class dataset | C — Keep local only | Historical project state / absent checkout | Exact evaluation/training inputs | Not in Git by historical policy | No | NO | Licensing/size/privacy and reproducibility require controlled local storage | CRITICAL | Exact metrics and retraining cannot be reproduced |
| GAP-04 | Candidate A `.pt` and ONNX | C — Keep local only | Historical project state / absent checkout | Selected model and TensorRT input | Historically ignored; absent locally | No | NO | Binary assets should remain local with checksums/manifests | CRITICAL | Official PyTorch reference and engine rebuild are blocked |
| GAP-05 | Candidate B/P2 weights and research outputs | D — Optional historical evidence | Historical project state / absent checkout | Research comparison reproduction | Historically ignored; absent locally | No | NO | Not needed for normal deployment continuation | MEDIUM | Full Pareto reproduction is harder |
| GAP-06 | TensorRT engine and local reports | C — Keep local only | Historical project state / absent checkout | Hardware-specific engine and parity/latency evidence | Historically ignored; absent locally | No | NO | Engine is machine/version-specific; reports may be summarized | HIGH | Exact historical benchmark cannot be audited |
| GAP-07 | `ml/.venv-tensorrt` or reproducible lock/manifest | C — Keep local only | Historical project state / absent checkout | Exact toolchain needed for continuation | Not in Git; absent locally | No | NO | Do not upload an environment; recover a sanitized reproducibility manifest | HIGH | Environment may not be reproducible |
| GAP-08 | Later Git commits, branches and tags | A — Must recover/verify | Historical project state | Authoritative source lineage and merge history | Not in locally available refs/history checked | No Chat duplication | NO | Recover through Git or old storage; live origin remains unverified | CRITICAL | Source and historical claims cannot be reconciled |
| GAP-09 | `CURRENT_STATE.md` | A — Must obtain from old chat | Historical project state | Explicit user-agreed state at migration point | Missing | Yes when produced | FULL | Must be produced/reconstructed in the old conversation, not invented here | CRITICAL | The intended starting point remains ambiguous |
| GAP-10 | `DECISION_LOG.md` | A — Must obtain from old chat | Historical project state | Explicit rationale and rejected alternatives | Missing | Yes when produced | FULL | Repository structure cannot manufacture conversational rationale | CRITICAL | Future agent may repeat rejected approaches |
| LOCAL-01 | `.env`, credentials, Xauthority, private URLs/keys/tokens | E — Do not import | Local/private environment | Potential secrets and machine-specific authentication | Not tracked; no `.env` present | No | NO | Never upload raw secret-bearing files | CRITICAL | Privacy/security exposure |
| LOCAL-02 | Build/install/log/cache/runtime outputs | E — Do not import | Generated | No durable project rationale | Ignored or absent | No | NO | Regenerate locally | LOW | None |

## 3. Nine High-Value Legacy Artifacts to Recover

1. `ENGINEERING_UPGRADE_READINESS_REPORT.md`
2. `SLICE_2_MOVING_ARUCO_ACCEPTANCE.md`
3. `REPORT_C2(1).md`
4. `SLICE_3_YOLO_ONNX_ACCEPTANCE.md`
5. `results.csv`
6. `SLICE_3B_SMALL_OBJECT_OPTIMIZATION.md`
7. `SLICE_3C_PARETO_OPTIMIZATION.md`
8. `implementation_plan(3).md`
9. `implementation_plan(4).md`

## 4. Recommended ChatGPT Project Sources

Import now:

- all four IDE-generated audit documents;
- `PROJECT_CONTINUITY.md`;
- `MIGRATION_FILE_MANIFEST.md`.

Then recover and import the nine high-value legacy artifacts above. If capacity is constrained, keep the two historical migration documents and the four audit documents first; recover the nine originals before making decisions in their affected areas.

Keep current source, configs, tests, Docker/launch files, normal Git documentation, datasets, models, environments, engines, raw logs, credentials, and generated images in Git/local storage.

