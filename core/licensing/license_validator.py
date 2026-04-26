from __future__ import annotations

import base64
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .license_models import (
    LicensePayload,
    LicenseStatus,
    LicenseValidationResult,
)
from .machine_id import get_machine_id
from .public_key import PUBLIC_KEY_PEM


GRACE_DAYS = 7


def validate_license_file(license_path: Path) -> LicenseValidationResult:
    if not license_path.exists():
        return LicenseValidationResult(
            is_valid=False,
            status=LicenseStatus.NOT_FOUND,
            message="Licencni fajl nije pronađen.",
        )

    try:
        raw = license_path.read_text(encoding="utf-8")
        license_data = json.loads(raw)
        payload_dict = license_data["payload"]
        signature_b64 = license_data["signature"]
    except Exception:
        return LicenseValidationResult(
            is_valid=False,
            status=LicenseStatus.INVALID_FORMAT,
            message="Licencni fajl nema validan format.",
        )

    if not _verify_signature(payload_dict, signature_b64):
        return LicenseValidationResult(
            is_valid=False,
            status=LicenseStatus.INVALID_SIGNATURE,
            message="Digitalni potpis licence nije validan.",
        )

    try:
        payload = LicensePayload.from_dict(payload_dict)
    except Exception:
        return LicenseValidationResult(
            is_valid=False,
            status=LicenseStatus.INVALID_FORMAT,
            message="Podaci u licenci nisu validni.",
        )

    current_machine_id = get_machine_id()

    if payload.machine_id != current_machine_id:
        return LicenseValidationResult(
            is_valid=False,
            status=LicenseStatus.MACHINE_MISMATCH,
            message="Licenca ne pripada ovom računaru.",
            payload=payload,
        )

    today = date.today()

    if today < payload.valid_from:
        return LicenseValidationResult(
            is_valid=False,
            status=LicenseStatus.NOT_YET_VALID,
            message="Licenca još nije aktivna.",
            payload=payload,
        )

    if payload.valid_from <= today <= payload.valid_to:
        return LicenseValidationResult(
            is_valid=True,
            status=LicenseStatus.VALID,
            message="Licenca je validna.",
            payload=payload,
            days_remaining=(payload.valid_to - today).days,
        )

    grace_until = payload.valid_to + timedelta(days=GRACE_DAYS)

    if payload.valid_to < today <= grace_until:
        return LicenseValidationResult(
            is_valid=True,
            status=LicenseStatus.EXPIRED_GRACE,
            message="Licenca je istekla, ali je aplikacija u grace periodu.",
            payload=payload,
            grace_days_remaining=(grace_until - today).days,
        )

    return LicenseValidationResult(
        is_valid=False,
        status=LicenseStatus.EXPIRED,
        message="Licenca je istekla.",
        payload=payload,
    )


def _verify_signature(payload: dict[str, Any], signature_b64: str) -> bool:
    try:
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        signature = base64.b64decode(signature_b64.encode("utf-8"))
        payload_bytes = _canonical_json(payload)
        public_key.verify(
            signature,
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


def _canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
