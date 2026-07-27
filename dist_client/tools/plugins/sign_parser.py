import argparse
import base64
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("parser_file", type=Path)
    parser.add_argument("--private-key", required=True, type=Path)
    args = parser.parse_args()

    private_key = serialization.load_pem_private_key(
        args.private_key.read_bytes(),
        password=None,
    )
    signature = private_key.sign(
        args.parser_file.read_bytes(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    output = args.parser_file.with_suffix(args.parser_file.suffix + ".sig")
    output.write_bytes(base64.b64encode(signature))
    print(f"Potpis kreiran: {output}")


if __name__ == "__main__":
    main()
