from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class LicensePayload:
    customer_name: str
    customer_id: str
    machine_id: str
    valid_from: date
    valid_to: date
    features: list[str]
    issued_at: date

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LicensePayload":
        return cls(
            customer_name=str(data["customer_name"]),
            customer_id=str(data["customer_id"]),
            machine_id=str(data["machine_id"]),
            valid_from=date.fromisoformat(str(data["valid_from"])),
            valid_to=date.fromisoformat(str(data["valid_to"])),
            features=list(data.get("features", [])),
            issued_at=date.fromisoformat(str(data["issued_at"])),
        )


@dataclass(frozen=True)
class LicenseValidationResult:
    is_valid: bool
    status: str
    message: str
    payload: LicensePayload | None = None
    days_remaining: int | None = None
    grace_days_remaining: int | None = None


class LicenseStatus:
    VALID = "valid"
    EXPIRED_GRACE = "expired_grace"
    EXPIRED = "expired"
    INVALID_SIGNATURE = "invalid_signature"
    MACHINE_MISMATCH = "machine_mismatch"
    NOT_FOUND = "not_found"
    INVALID_FORMAT = "invalid_format"
    NOT_YET_VALID = "not_yet_valid"
