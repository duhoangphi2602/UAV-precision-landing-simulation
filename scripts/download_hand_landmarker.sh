#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODEL_URL="https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
readonly EXPECTED_SHA256="fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
readonly DESTINATION="gesture/models/hand_landmarker.task"

if [ -f "$DESTINATION" ] &&
    printf '%s  %s\n' "$EXPECTED_SHA256" "$DESTINATION" | sha256sum --check --status; then
    echo "MediaPipe Hand Landmarker is already present and verified."
    exit 0
fi

command -v curl >/dev/null 2>&1 || {
    echo "curl is required to download the MediaPipe Hand Landmarker." >&2
    exit 1
}

mkdir -p "$(dirname "$DESTINATION")"
temporary_file="$(mktemp)"
trap 'rm -f "$temporary_file"' EXIT

echo "Downloading pinned MediaPipe Hand Landmarker..."
curl --fail --location --retry 3 --output "$temporary_file" "$MODEL_URL"
printf '%s  %s\n' "$EXPECTED_SHA256" "$temporary_file" | sha256sum --check --status || {
    echo "Downloaded Hand Landmarker SHA-256 mismatch." >&2
    exit 1
}
install -m 0644 "$temporary_file" "$DESTINATION"
echo "MEDIAPIPE_MODEL=PASS"
