"""Pytest konfiguracija i shared fixtures."""

import sys
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Dodaj root direktorijum u path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
