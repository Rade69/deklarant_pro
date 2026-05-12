#!/usr/bin/env python3
"""Testovi za core.licensing — Machine ID, validacija, import licence."""

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from core.licensing.machine_id import get_machine_id, _format_machine_id
from core.licensing.license_models import LicensePayload, LicenseStatus, LicenseValidationResult
from core.licensing.license_paths import get_license_dir, get_license_path
from core.licensing.license_validator import validate_license_file, _canonical_json
from core.licensing.machine_fingerprint import (
    FingerprintMatch,
    calculate_fingerprint_match,
)


# ============================================================
# MACHINE ID
# ============================================================

def test_machine_id_format():
    mid = get_machine_id()
    assert mid.startswith("DKP-")
    assert len(mid.split("-")) >= 4


def test_machine_id_stable():
    mid1 = get_machine_id()
    mid2 = get_machine_id()
    assert mid1 == mid2


def test_format_machine_id_length():
    formatted = _format_machine_id("test-raw-id")
    assert formatted.startswith("DKP-")
    parts = formatted.split("-")
    assert len(parts) >= 4
    for p in parts[1:]:
        assert len(p) == 4


# ============================================================
# LICENSE MODELS
# ============================================================

def test_license_payload_from_dict():
    data = {
        "customer_name": "Test DOO",
        "customer_id": "T001",
        "machine_id": "DKP-AAAA-BBBB-CCCC-DDDD-EEEE",
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "features": ["full"],
        "issued_at": "2026-01-01",
    }
    lp = LicensePayload.from_dict(data)
    assert lp.customer_name == "Test DOO"
    assert lp.customer_id == "T001"
    assert lp.valid_from == date(2026, 1, 1)
    assert lp.features == ["full"]


def test_license_payload_immutable():
    lp = LicensePayload("X", "1", "DKP-AAAA", date.today(), date.today(), ["full"], date.today())
    with pytest.raises(Exception):
        lp.customer_name = "Y"  # type: ignore


# ============================================================
# LICENSE PATHS
# ============================================================

def test_license_dir_exists():
    d = get_license_dir()
    assert isinstance(d, Path)


def test_license_path_ends_with_license_dat():
    p = get_license_path()
    assert p.name == "license.dat"


# ============================================================
# CANONICAL JSON
# ============================================================

def test_canonical_json_stable_order():
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert _canonical_json(a) == _canonical_json(b)


def test_canonical_json_no_whitespace():
    data = {"key": "value", "num": 123}
    result = _canonical_json(data).decode("utf-8")
    assert " " not in result
    assert "\n" not in result


# ============================================================
# VALIDACIJA — NOT FOUND
# ============================================================

def test_validate_nonexistent_license():
    result = validate_license_file(Path("/tmp/nonexistent_license.dat"))
    assert result.is_valid is False
    assert result.status == LicenseStatus.NOT_FOUND


# ============================================================
# VALIDACIJA — INVALID FORMAT
# ============================================================

def test_validate_invalid_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write("not json")
        tmp = f.name
    try:
        result = validate_license_file(Path(tmp))
        assert result.status == LicenseStatus.INVALID_FORMAT
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_validate_missing_signature():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        json.dump({"payload": {"test": 1}}, f)
        tmp = f.name
    try:
        result = validate_license_file(Path(tmp))
        assert result.status == LicenseStatus.INVALID_FORMAT
    finally:
        Path(tmp).unlink(missing_ok=True)


# ============================================================
# FINGERPRINT SCORE
# ============================================================

def test_fingerprint_score_allows_partial_match():
    licensed = {
        "machine_id": "A",
        "disk_id": "B",
        "mac": "C",
        "cpu": "D",
        "hostname": "E",
    }
    current = {
        "machine_id": "A",
        "disk_id": "B",
        "mac": "changed",
        "cpu": "D",
        "hostname": "E",
    }

    result = calculate_fingerprint_match(licensed, min_score=70, current_fingerprint=current)

    assert result.score == 85
    assert result.is_match is True
    assert "mac" in result.missing


def test_fingerprint_score_blocks_copied_machine_id_only():
    licensed = {
        "machine_id": "A",
        "disk_id": "B",
        "mac": "C",
        "cpu": "D",
        "hostname": "E",
    }
    current = {
        "machine_id": "A",
        "disk_id": "changed",
        "mac": "changed",
        "cpu": "changed",
        "hostname": "changed",
    }

    result = calculate_fingerprint_match(licensed, min_score=70, current_fingerprint=current)

    assert result.score == 30
    assert result.is_match is False


def test_validate_fingerprint_license_valid(monkeypatch, tmp_path):
    payload = {
        "customer_name": "Test DOO",
        "customer_id": "T001",
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "features": ["full"],
        "issued_at": "2026-01-01",
        "fingerprint": {"machine_id": "A", "disk_id": "B", "cpu": "C"},
        "min_score": 70,
    }
    license_path = tmp_path / "license.dat"
    license_path.write_text(json.dumps({"payload": payload, "signature": "x"}), encoding="utf-8")

    monkeypatch.setattr("core.licensing.license_validator._verify_signature", lambda *_: True)
    monkeypatch.setattr(
        "core.licensing.license_validator.calculate_fingerprint_match",
        lambda *_: FingerprintMatch(75, 70, ["machine_id", "disk_id", "cpu"], []),
    )

    result = validate_license_file(
        license_path,
        today=date(2026, 5, 4),
        update_state=False,
    )

    assert result.is_valid is True
    assert result.status == LicenseStatus.VALID
    assert result.fingerprint_score == 75
    assert result.fingerprint_min_score == 70


def test_validate_fingerprint_license_machine_mismatch(monkeypatch, tmp_path):
    payload = {
        "customer_name": "Test DOO",
        "customer_id": "T001",
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "features": ["full"],
        "issued_at": "2026-01-01",
        "fingerprint": {"machine_id": "A"},
        "min_score": 70,
    }
    license_path = tmp_path / "license.dat"
    license_path.write_text(json.dumps({"payload": payload, "signature": "x"}), encoding="utf-8")

    monkeypatch.setattr("core.licensing.license_validator._verify_signature", lambda *_: True)
    monkeypatch.setattr(
        "core.licensing.license_validator.calculate_fingerprint_match",
        lambda *_: FingerprintMatch(30, 70, ["machine_id"], ["disk_id"]),
    )

    result = validate_license_file(
        license_path,
        today=date(2026, 5, 4),
        update_state=False,
    )

    assert result.is_valid is False
    assert result.status == LicenseStatus.MACHINE_MISMATCH
    assert result.fingerprint_score == 30


def test_validate_license_clock_rollback(monkeypatch, tmp_path):
    payload = {
        "customer_name": "Test DOO",
        "customer_id": "T001",
        "machine_id": "DKP-TEST",
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "features": ["full"],
        "issued_at": "2026-01-01",
    }
    license_path = tmp_path / "license.dat"
    license_path.write_text(json.dumps({"payload": payload, "signature": "x"}), encoding="utf-8")

    monkeypatch.setattr("core.licensing.license_validator._verify_signature", lambda *_: True)
    monkeypatch.setattr("core.licensing.license_validator.get_machine_id", lambda: "DKP-TEST")
    monkeypatch.setattr(
        "core.licensing.license_validator.check_and_update_license_state",
        lambda *_: (False, "Detektovano vraćanje sistemskog datuma."),
    )

    result = validate_license_file(license_path, today=date(2026, 5, 4))

    assert result.is_valid is False
    assert result.status == LicenseStatus.CLOCK_ROLLBACK


# ============================================================
# LICENSE IMPORTER — BASIC
# ============================================================

def test_import_license_nonexistent_source():
    from core.licensing.license_importer import import_license
    ok, msg = import_license(Path("/tmp/does_not_exist.lic"))
    assert ok is False
    assert "ne postoji" in msg.lower()
