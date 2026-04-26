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
    parser.add_argument("--customer-name", required=True)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--machine-id", required=True)
    parser.add_argument("--valid-from", required=True)
    parser.add_argument("--valid-to", required=True)
    parser.add_argument("--features", default="full")
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    features = [item.strip() for item in args.features.split(",") if item.strip()]

    payload = {
        "customer_name": args.customer_name,
        "customer_id": args.customer_id,
        "machine_id": args.machine_id,
        "valid_from": args.valid_from,
        "valid_to": args.valid_to,
        "features": features,
        "issued_at": date.today().isoformat(),
    }

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
