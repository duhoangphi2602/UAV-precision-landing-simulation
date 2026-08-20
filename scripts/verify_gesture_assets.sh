#!/usr/bin/env bash
set -Eeuo pipefail

verify_sha256() {
    local expected="$1"
    local path="$2"
    if [ ! -f "$path" ]; then
        echo "Missing required gesture runtime asset: $path" >&2
        return 1
    fi
    printf '%s  %s\n' "$expected" "$path" | sha256sum --check --status || {
        echo "SHA-256 mismatch: $path" >&2
        return 1
    }
}

verify_sha256 de5509bf849a6991858e95d521a0325bf711393f64668b8af9a1a129403505bf gesture/deploy/model.onnx
verify_sha256 09afa7821c0f5e719ede1848e50597e0750efc90f7b1febf82de0ea138e4428d gesture/deploy/preprocessing.json
verify_sha256 32be9fed57903aff41582eda86b7363e23cd550953b8ffa45cd1b2322f5255f9 gesture/deploy/deployment_config.json
verify_sha256 2f00b0327b36bc9a9f4bcb6aac8190bd1cf9a4f0de4139d0b62eb232a07ceaaa gesture/deploy/class_mapping.json
verify_sha256 fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1 gesture/models/hand_landmarker.task

echo "GESTURE_RUNTIME_ASSETS=PASS"
