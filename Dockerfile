FROM osrf/ros:humble-desktop

# Install basic dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    git \
    python3-pip \
    python3-venv \
    sudo \
    lsb-release \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Gazebo Harmonic
RUN wget https://packages.osrfoundation.org/gazebo.gpg -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null \
    && apt-get update \
    && apt-get install -y gz-harmonic \
    && rm -rf /var/lib/apt/lists/*

# Install ROS 2 Gazebo Harmonic bridge and OpenCV
RUN apt-get update && apt-get install -y \
    ros-humble-ros-gzharmonic \
    ros-humble-cv-bridge \
    ros-humble-vision-opencv \
    libopencv-dev \
    libopencv-contrib-dev \
    python3-opencv \
    cmake \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages (MAVSDK)
RUN pip3 install --no-cache-dir \
    mavsdk \
    aioconsole \
    pytest \
    "numpy<2"

# Install PX4 dependencies
RUN apt-get update && apt-get install -y \
    ninja-build \
    exiftool \
    astyle \
    && pip3 install --no-cache-dir \
    kconfiglib \
    jinja2 \
    empy \
    jsonschema \
    pyros-genmsg \
    packaging \
    toml \
    "numpy<2" \
    future \
    && rm -rf /var/lib/apt/lists/*

# Setup user
ARG USERNAME=devuser
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME
WORKDIR /home/$USERNAME

# Clone and build PX4
# Wait, downloading PX4 inside docker makes the image large, but it ensures we have it pre-built.
# Or we can let it be a volume? The user says:
# "Không commit toàn bộ PX4 source vào repository chính."
# "PX4 có thể đặt tại: /opt/PX4-Autopilot"
USER root
RUN mkdir -p /opt/PX4-Autopilot && chown -R $USERNAME:$USERNAME /opt/PX4-Autopilot
USER $USERNAME

# We will clone and build PX4
ARG PX4_VERSION
RUN echo "PX4_VERSION ARG: ${PX4_VERSION}" \
    && git clone https://github.com/PX4/PX4-Autopilot.git /opt/PX4-Autopilot \
    && cd /opt/PX4-Autopilot \
    && git checkout ${PX4_VERSION} \
    && git submodule update --init --recursive \
    && bash ./Tools/setup/ubuntu.sh --no-nuttx --no-sim-tools \
    && python3 -m pip install --user --no-cache-dir --force-reinstall "numpy==1.26.4" \
    && python3 -c "import numpy; print('NumPy version:', numpy.__version__); print('NumPy path:', numpy.__file__); assert numpy.__version__ == '1.26.4'" \
    && python3 -c "import cv2; assert hasattr(cv2, 'aruco')" \
    && bash -c "source /opt/ros/humble/setup.bash && python3 -c 'from cv_bridge import CvBridge'"

# Pre-build PX4 SITL Gazebo (Compile only)
RUN cd /opt/PX4-Autopilot \
    && make px4_sitl_default

# Add Entrypoint
COPY docker/entrypoint.sh /home/$USERNAME/entrypoint.sh
USER root
RUN chmod +x /home/$USERNAME/entrypoint.sh
USER $USERNAME

ENTRYPOINT ["/home/devuser/entrypoint.sh"]
CMD ["/bin/bash"]
