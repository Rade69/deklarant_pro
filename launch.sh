#!/bin/bash
export DISPLAY=:0
export WAYLAND_DISPLAY=wayland-0
export XDG_RUNTIME_DIR=/run/user/$(id -u)
cd /home/radovan/Desktop/asycuda_pro
exec .venv/bin/python3 launcher.py
