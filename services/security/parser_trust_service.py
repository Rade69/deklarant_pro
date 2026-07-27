import ast
import base64
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class ParserTrustError(RuntimeError):
    pass


def validate_parser_structure(filepath: Path) -> tuple[bool, str]:
    try:
        source = filepath.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(filepath))
    except (OSError, UnicodeError, SyntaxError) as exc:
        return False, f"Parser nije moguće statički analizirati: {exc}"

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {
            base.id if isinstance(base, ast.Name)
            else base.attr if isinstance(base, ast.Attribute)
            else ""
            for base in node.bases
        }
        if "ImportStrategy" not in bases:
            continue
        methods = {
            item.name for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        missing = {"can_handle", "import_file"} - methods
        if missing:
            return False, f"Parser nema obavezne metode: {', '.join(sorted(missing))}"
        return True, f"Validna struktura parsera: {node.name}"

    return False, "Fajl ne sadrži ImportStrategy klasu"


def assert_parser_trusted(filepath: Path) -> None:
    if os.getenv("ALLOW_EXTERNAL_PARSER_PLUGINS", "").strip().lower() not in {
        "1", "true", "yes", "on",
    }:
        raise ParserTrustError("Eksterni parseri su isključeni sigurnosnom politikom")

    key_value = os.getenv("PARSER_SIGNING_PUBLIC_KEY", "").strip()
    if not key_value:
        raise ParserTrustError("Nije konfigurisan javni ključ za potpis parsera")

    key_path = Path(key_value).expanduser().resolve()
    signature_path = filepath.with_suffix(filepath.suffix + ".sig")
    if not signature_path.is_file():
        raise ParserTrustError(f"Nedostaje potpis parsera: {signature_path.name}")

    try:
        public_key = serialization.load_pem_public_key(key_path.read_bytes())
        signature = base64.b64decode(signature_path.read_bytes(), validate=True)
        public_key.verify(
            signature,
            filepath.read_bytes(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
    except (OSError, ValueError, TypeError, InvalidSignature) as exc:
        raise ParserTrustError("Potpis parsera nije važeći") from exc

