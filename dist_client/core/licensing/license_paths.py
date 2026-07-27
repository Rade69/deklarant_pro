from __future__ import annotations

import os
import platform
from pathlib import Path


APP_NAME = "DeklarantPro"


def get_license_dir() -> Path:
    system = platform.system().lower()
    if system == "windows":
        program_data = os.environ.get("PROGRAMDATA")
        if program_data:
            return Path(program_data) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME
    if system == "linux":
        config_home = os.environ.get("XDG_CONFIG_HOME")
        if config_home:
            return Path(config_home) / "deklarant_pro"
        return Path.home() / ".config" / "deklarant_pro"
    return Path.home() / ".deklarant_pro"


def get_license_path() -> Path:
    return get_license_dir() / "license.dat"


def ensure_license_dir() -> Path:
    license_dir = get_license_dir()
    license_dir.mkdir(parents=True, exist_ok=True)
    return license_dir
