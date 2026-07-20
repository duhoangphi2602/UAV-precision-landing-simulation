#!/bin/bash
set -Eeuo pipefail

echo "Bootstrapping upstream..."
mkdir -p drone_landing_ws/src
if [ ! -d "drone_landing_ws/src/px4_vision_autonomy" ]; then
    git clone https://github.com/Tinny-Robot/px4_vision_autonomy.git tmp_upstream
    cd tmp_upstream
    git checkout 62e5b6222043c90a49ed3aca58f039c8980528e1
    cd ..
    cp -r tmp_upstream drone_landing_ws/src/px4_vision_autonomy
    rm -rf drone_landing_ws/src/px4_vision_autonomy/.git
    rm -rf tmp_upstream
    echo "Bootstrap complete."
else
    echo "Upstream already bootstrapped."
fi
