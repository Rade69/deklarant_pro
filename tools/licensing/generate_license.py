from __future__ import annotations

import argparse
import base64
import json
from datetime import date
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


PRIVATE_KEY_PATH = Path("tools/licensing/keys/private_key.pem")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Deklarant Pro license.dat")
    parser.add_argument("--customer-name", required=True, help="Naziv kupca/firme")
    parser.add_argument("--customer-id", required=True, help="Interni identifikator kupca")
    parser.add_argument(
        "--machine-id",
        default="",
        help="Legacy mode: machine ID (DKP-...)",
    )
    parser.add_argument(
        "--fingerprint-json",
        default="",
        help="JSON string fingerprint payload-a ili sam fingerprint objekat",
    )
    parser.add_argument(
        "--fingerprint-file",
        default="",
        help="Putanja do JSON fajla sa fingerprint payload-om",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=70,
        help="Minimalni fingerprint score (default: 70)",
    )
    parser.add_argument("--valid-from", required=True, help="Datum pocetka (YYYY-MM-DD)")
    parser.add_argument("--valid-to", required=True, help="Datum isteka (YYYY-MM-DD)")
    parser.add_argument("--features", default="full", help="CSV features, npr full,agent")
    parser.add_argument("--output", required=True, help="Izlazni license.dat path")

    args = parser.parse_args()

    features = [item.strip() for item in args.features.split(",") if item.strip()]

    fingerprint_data, min_score_from_source = _load_fingerprint_data(
        args.fingerprint_json,
        args.fingerprint_file,
    )
    if not args.machine_id and not fingerprint_data:
        raise SystemExit("Moras navesti --machine-id ili --fingerprint-json/--fingerprint-file.")
    if args.machine_id and fingerprint_data:
        raise SystemExit("Koristi ili --machine-id ili fingerprint opcije, ne oba.")

    payload: dict[str, Any] = {
        "customer_name": args.customer_name,
        "customer_id": args.customer_id,
        "machine_id": args.machine_id,
        "valid_from": args.valid_from,
        "valid_to": args.valid_to,
        "features": features,
        "issued_at": date.today().isoformat(),
    }
    if fingerprint_data:
        payload["fingerprint"] = fingerprint_data
        payload["min_score"] = int(min_score_from_source or args.min_score)

    signature = _sign_payload(payload)

    license_data = {
        "payload": payload,
        "signature": signature,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(license_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"License generated: {output_path}")


def _load_fingerprint_data(
    fingerprint_json: str,
    fingerprint_file: str,
) -> tuple[dict[str, str] | None, int | None]:
    if not fingerprint_json and not fingerprint_file:
        return None, None

    source: dict[str, Any]
    if fingerprint_json:
        source = json.loads(fingerprint_json)
    else:
        source = json.loads(Path(fingerprint_file).read_text(encoding="utf-8"))

    if "fingerprint" in source and isinstance(source["fingerprint"], dict):
        fp = source["fingerprint"]
    else:
        fp = source

    if not isinstance(fp, dict) or not fp:
        raise SystemExit("Fingerprint podaci nisu validni (ocekivan je JSON objekat).")

    cleaned: dict[str, str] = {}
    for key, value in fp.items():
        if not isinstance(key, str):
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text:
            cleaned[key] = text

    if not cleaned:
        raise SystemExit("Fingerprint je prazan.")

    min_score = source.get("min_score")
    if min_score is not None:
        try:
            min_score = int(min_score)
        except Exception as exc:
            raise SystemExit("min_score u fingerprint payload-u nije validan broj.") from exc

    return cleaned, min_score


def _sign_payload(payload: dict[str, Any]) -> str:
    private_key = serialization.load_pem_private_key(
        PRIVATE_KEY_PATH.read_bytes(),
        password=None,
    )
    payload_bytes = _canonical_json(payload)
    signature = private_key.sign(
        payload_bytes,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def _canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


if __name__ == "__main__":
    main()
