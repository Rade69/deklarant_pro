from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


OUTPUT_DIR = Path("tools/licensing/keys")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_key = private_key.public_key()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = OUTPUT_DIR / "private_key.pem"
    public_path = OUTPUT_DIR / "public_key.pem"

    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    print(f"Private key saved to: {private_path}")
    print(f"Public key saved to: {public_path}")
    print("")
    print("VAŽNO:")
    print("- private_key.pem NE SMIJE ući u aplikaciju")
    print("- public_key.pem ide u core/licensing/public_key.py")


if __name__ == "__main__":
    main()
