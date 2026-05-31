from __future__ import annotations

import hashlib
import os
import platform
import uuid
from pathlib import Path


APP_NAME = "DeklarantPro"
MACHINE_ID_PREFIX = "DKP"


def get_machine_id() -> str:
    raw_id = _get_platform_machine_id()
    if not raw_id:
        raw_id = _get_or_create_fallback_id()
    return _format_machine_id(raw_id)


def _get_platform_machine_id() -> str | None:
    system = platform.system().lower()
    if system == "linux":
        return _get_linux_machine_id()
    if system == "windows":
        return _get_windows_machine_guid()
    return None


def _get_linux_machine_id() -> str | None:
    paths = [Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")]
    for path in paths:
        try:
            if path.exists():
                value = path.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except Exception:
            continue
    return None


def _get_windows_machine_guid() -> str | None:
    try:
        import winreg
        registry_path = r"SOFTWARE\Microsoft\Cryptography"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            if value:
                return str(value).strip()
    except Exception:
        return None
    return None


def _get_or_create_fallback_id() -> str:
    fallback_path = _get_fallback_id_path()
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    if fallback_path.exists():
        existing = fallback_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    new_id = str(uuid.uuid4())
    fallback_path.write_text(new_id, encoding="utf-8")
    return new_id


def _get_fallback_id_path() -> Path:
    system = platform.system().lower()
    if system == "windows":
        base = os.environ.get("PROGRAMDATA")
        if base:
            return Path(base) / APP_NAME / "machine_id"
    if system == "linux":
        config_home = os.environ.get("XDG_CONFIG_HOME")
        if config_home:
            return Path(config_home) / "deklarant_pro" / "machine_id"
        return Path.home() / ".config" / "deklarant_pro" / "machine_id"
    return Path.home() / ".deklarant_pro" / "machine_id"


def _format_machine_id(raw_id: str) -> str:
    digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest().upper()
    short = digest[:20]
    groups = [short[i:i + 4] for i in range(0, len(short), 4)]
    return f"{MACHINE_ID_PREFIX}-" + "-".join(groups)
