from __future__ import annotations

import hashlib
import json
import platform
import socket
import subprocess
import uuid
from dataclasses import dataclass

from .machine_id import get_machine_id


FINGERPRINT_VERSION = 2
DEFAULT_MIN_SCORE = 60  # 60% omogućava da 1 signal nedostaje bez gubitka validnosti
SIGNAL_WEIGHTS = {
    "machine_id": 30,
    "disk_id": 30,
    "mac": 15,
    "cpu": 15,
    "hostname": 10,
}


@dataclass(frozen=True)
class FingerprintMatch:
    score: int
    min_score: int
    matched: list[str]
    missing: list[str]

    @property
    def is_match(self) -> bool:
        return self.score >= self.min_score


def get_machine_fingerprint() -> dict[str, str]:
    signals = {
        "machine_id": get_machine_id(),
        "disk_id": _get_disk_id(),
        "mac": _get_mac_id(),
        "cpu": _get_cpu_id(),
        "hostname": _get_hostname(),
    }
    return {
        name: _hash_signal(name, value)
        for name, value in signals.items()
        if value
    }


def build_fingerprint_payload() -> dict:
    return {
        "fingerprint_version": FINGERPRINT_VERSION,
        "fingerprint": get_machine_fingerprint(),
        "min_score": DEFAULT_MIN_SCORE,
    }


def format_fingerprint_payload() -> str:
    return json.dumps(
        build_fingerprint_payload(),
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
    )


def calculate_fingerprint_match(
    licensed_fingerprint: dict[str, str] | None,
    min_score: int = DEFAULT_MIN_SCORE,
    current_fingerprint: dict[str, str] | None = None,
) -> FingerprintMatch:
    if not licensed_fingerprint:
        return FingerprintMatch(0, min_score, [], list(SIGNAL_WEIGHTS))

    current = current_fingerprint or get_machine_fingerprint()
    score = 0
    matched = []
    missing = []

    for name, weight in SIGNAL_WEIGHTS.items():
        expected = licensed_fingerprint.get(name)
        actual = current.get(name)
        if expected and actual and expected == actual:
            score += weight
            matched.append(name)
        else:
            missing.append(name)

    return FingerprintMatch(score, min_score, matched, missing)


def _hash_signal(name: str, value: str) -> str:
    normalized = str(value).strip().lower()
    digest = hashlib.sha256(f"{name}:{normalized}".encode("utf-8")).hexdigest()
    return digest.upper()


def _get_disk_id() -> str | None:
    system = platform.system().lower()

    if system == "linux":
        for args in (
            ["findmnt", "-no", "UUID", "/"],
            ["findmnt", "-no", "SOURCE", "/"],
        ):
            try:
                result = subprocess.run(
                    args, check=False, capture_output=True, text=True, timeout=2,
                )
                value = result.stdout.strip()
                if value:
                    return value
            except Exception:
                continue

    elif system == "windows":
        # Pokušaj 1: serijski broj fizičkog diska putem wmic
        for args in (
            ["wmic", "diskdrive", "get", "SerialNumber", "/value"],
            ["wmic", "logicaldisk", "where", "DeviceID='C:'", "get", "VolumeSerialNumber", "/value"],
        ):
            try:
                result = subprocess.run(
                    args, check=False, capture_output=True,
                    text=True, timeout=5, creationflags=0x08000000,  # CREATE_NO_WINDOW
                )
                for line in result.stdout.splitlines():
                    if "=" in line:
                        value = line.split("=", 1)[1].strip()
                        if value:
                            return value
            except Exception:
                continue

        # Pokušaj 2: PowerShell volume serial
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-Volume -DriveLetter C).UniqueId"],
                check=False, capture_output=True, text=True,
                timeout=5, creationflags=0x08000000,
            )
            value = result.stdout.strip()
            if value:
                return value
        except Exception:
            pass

    return None


def _get_mac_id() -> str | None:
    node = uuid.getnode()
    if node & (1 << 40):
        return None
    return f"{node:012x}"


def _get_cpu_id() -> str | None:
    parts = [platform.machine(), platform.processor()]
    system = platform.system().lower()

    if system == "linux":
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        parts.append(line.split(":", 1)[1].strip())
                        break
        except Exception:
            pass

    elif system == "windows":
        try:
            result = subprocess.run(
                ["wmic", "cpu", "get", "ProcessorId,Name", "/value"],
                check=False, capture_output=True, text=True,
                timeout=5, creationflags=0x08000000,
            )
            for line in result.stdout.splitlines():
                if "=" in line:
                    value = line.split("=", 1)[1].strip()
                    if value:
                        parts.append(value)
        except Exception:
            pass

    value = "|".join(p for p in parts if p)
    return value or None


def _get_hostname() -> str | None:
    return socket.gethostname().strip() or None
