from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


OUTPUT_DIR = Path(__file__).parent / "keys"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_path = OUTPUT_DIR / "parser_signing_private.pem"
    public_path = OUTPUT_DIR / "parser_signing_public.pem"
    private_path.write_bytes(private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public_path.write_bytes(private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    print(f"Javni ključ: {public_path}")
    print("Privatni ključ čuvati offline i nikad ga ne kopirati na klijentski računar.")


if __name__ == "__main__":
    main()
