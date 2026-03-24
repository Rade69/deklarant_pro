#!/bin/bash
cd /home/radovan/Desktop/asycuda_pro

# Wayland/X11 podrška
if [ -n "$WAYLAND_DISPLAY" ]; then
    export QT_QPA_PLATFORM=wayland
elif [ -n "$DISPLAY" ]; then
    export QT_QPA_PLATFORM=xcb
else
    export DISPLAY=:0
    export QT_QPA_PLATFORM=xcb
fi

exec /home/radovan/Desktop/asycuda_pro/.venv/bin/python3 run.py
