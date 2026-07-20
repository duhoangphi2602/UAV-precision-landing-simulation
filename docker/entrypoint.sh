#!/bin/bash
set -e

# Setup ROS 2 environment
source /opt/ros/humble/setup.bash

# Setup PX4 environment variables for Gazebo Harmonic
export GZ_VERSION=harmonic

# If workspace exists, source it
if [ -f "/home/devuser/drone_landing_ws/install/setup.bash" ]; then
    source /home/devuser/drone_landing_ws/install/setup.bash
fi

exec "$@"
