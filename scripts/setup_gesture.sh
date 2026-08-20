#!/usr/bin/env bash
set -Eeuo pipefail

command -v uv >/dev/null 2>&1 || {
    echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
}

echo "Creating the Python 3.10 gesture environment..."
if [ -x gesture/.venv/bin/python ]; then
    gesture/.venv/bin/python -c \
        'import sys; assert sys.version_info[:2] == (3, 10), "gesture/.venv must use Python 3.10"'
    echo "Reusing the existing Python 3.10 environment."
else
    UV_LINK_MODE=copy uv venv --python 3.10 gesture/.venv
fi

echo "Installing the frozen CPU dependency set..."
UV_LINK_MODE=copy uv pip install \
    --python gesture/.venv/bin/python \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --requirements gesture/requirements.lock.txt

./scripts/download_hand_landmarker.sh
./scripts/verify_gesture_assets.sh

echo "GESTURE_SETUP=PASS"
