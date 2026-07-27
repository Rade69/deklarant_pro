from __future__ import annotations

import hmac
import json
from datetime import date
from hashlib import sha256
from pathlib import Path

from .license_paths import ensure_license_dir, get_license_dir
from .machine_id import get_machine_id


def get_license_state_path() -> Path:
    return get_license_dir() / "license_state.dat"


def check_and_update_license_state(today: date) -> tuple[bool, str | None]:
    last_seen = _read_last_seen_date()
    if last_seen and today < last_seen:
        return False, "Detektovano vraćanje sistemskog datuma."

    _write_last_seen_date(today)
    return True, None


def _read_last_seen_date() -> date | None:
    path = get_license_state_path()
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        payload = data["payload"]
        signature = data["signature"]
        if not hmac.compare_digest(signature, _sign_payload(payload)):
            return date.max
        return date.fromisoformat(str(payload["last_seen_date"]))
    except Exception:
        return date.max


def _write_last_seen_date(value: date) -> None:
    ensure_license_dir()
    payload = {"last_seen_date": value.isoformat()}
    data = {
        "payload": payload,
        "signature": _sign_payload(payload),
    }
    try:
        get_license_state_path().write_text(
            json.dumps(data, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
    except OSError:
        return


def _sign_payload(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_state_key(), raw, sha256).hexdigest()


def _state_key() -> bytes:
    return sha256(f"DeklarantPro:license-state:{get_machine_id()}".encode("utf-8")).digest()
