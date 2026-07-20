#!/bin/bash
set -Eeuo pipefail

# Safely allow X11 connections without using xhost +
xhost +local:docker
