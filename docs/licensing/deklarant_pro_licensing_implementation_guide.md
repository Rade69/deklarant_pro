# 🔐 DEKLARANT PRO — OFFLINE LICENSING IMPLEMENTATION GUIDE

**Datum:** 2026-04-26  
**Status:** 🧩 Implementacioni plan | Spremno za predaju coding agentu  
**Projekt:** `deklarant_pro`  
**Cilj:** Offline licenciranje bez servera, kroz Machine ID + potpisani `license.dat` + Admin Panel import.

---

## 1. SAŽETAK RJEŠENJA

Deklarant Pro treba dobiti offline licensing sistem koji ne traži server, VPS, internet konekciju ili online aktivaciju.

Predloženi sistem radi ovako:

1. Aplikacija na računaru generiše stabilan **Machine ID**
2. Korisnik iz Admin Panela kopira Machine ID
3. Korisnik šalje Machine ID vlasniku aplikacije
4. Vlasnik aplikacije generiše potpisani `license.dat`
5. Korisnik u Admin Panelu uvozi `license.dat`
6. Aplikacija na svakom startu validira:
   - digitalni potpis
   - datum važenja
   - Machine ID
   - opcionalne feature flagove

Minimalna formula sistema:

```text
Machine ID + license.dat + digitalni potpis
```

Ovo je optimalan model za desktop B2B aplikaciju bez servera.

---

## 2. ŠTA SE NE RADI U OVOJ FAZI

U ovoj fazi se NE implementira:

- online licensing server
- automatsko obnavljanje preko interneta
- centralna evidencija aktivacija
- seats kontrola preko servera
- payment integracija
- automatsko blokiranje preko udaljene baze

Razlog: trenutno bi to bilo prekomplikovano i nepotrebno skupo za održavanje.

---

## 3. PREDLOŽENA STRUKTURA FAJLOVA

U projekat dodati sljedeću strukturu:

```text
deklarant_pro/
├── core/
│   └── licensing/
│       ├── __init__.py
│       ├── machine_id.py
│       ├── license_models.py
│       ├── license_paths.py
│       ├── license_validator.py
│       ├── license_importer.py
│       └── public_key.py
│
├── tools/
│   └── licensing/
│       ├── generate_private_key.py
│       └── generate_license.py
│
└── gui/
    └── admin/
        └── license_panel.py
```

Ako projekat već ima drugačiju strukturu, ne praviti paralelni haos. U tom slučaju ove module smjestiti u postojeći `core`, `services`, `utils` ili `admin` sloj.

---

## 4. PYTHON ZAVISNOSTI

Preporučena biblioteka za digitalni potpis:

```bash
pip install cryptography
```

Dodati u `requirements.txt`:

```text
cryptography>=42.0.0
```

Ako projekat koristi Poetry:

```bash
poetry add cryptography
```

---

## 5. MACHINE ID IMPLEMENTACIJA

### 5.1 Cilj

Machine ID mora biti:

- stabilan na istom računaru
- različit na različitim računarima
- bezbjedan za slanje emailom
- hashovan, ne raw sistemski ID
- cross-platform: Windows + Linux

---

### 5.2 Izvori

#### Linux

Koristiti:

```text
/etc/machine-id
```

#### Windows

Koristiti Registry:

```text
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography\MachineGuid
```

---

### 5.3 Kod: `core/licensing/machine_id.py`

```python
from __future__ import annotations

import hashlib
import os
import platform
import uuid
from pathlib import Path


APP_NAME = "DeklarantPro"
MACHINE_ID_PREFIX = "DKP"


def get_machine_id() -> str:
    """
    Returns stable, formatted and hashed Machine ID.

    The raw system identifier is never returned directly.
    """
    raw_id = _get_platform_machine_id()

    if not raw_id:
        raw_id = _get_or_create_fallback_id()

    return _format_machine_id(raw_id)


def _get_platform_machine_id() -> str | None:
    system = platform.system().lower()

    if system == "linux":
        return _get_linux_machine_id()

    if system == "windows":
        return _get_windows_machine_guid()

    return None


def _get_linux_machine_id() -> str | None:
    paths = [
        Path("/etc/machine-id"),
        Path("/var/lib/dbus/machine-id"),
    ]

    for path in paths:
        try:
            if path.exists():
                value = path.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except Exception:
            continue

    return None


def _get_windows_machine_guid() -> str | None:
    try:
        import winreg

        registry_path = r"SOFTWARE\Microsoft\Cryptography"

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            if value:
                return str(value).strip()
    except Exception:
        return None

    return None


def _get_or_create_fallback_id() -> str:
    fallback_path = _get_fallback_id_path()
    fallback_path.parent.mkdir(parents=True, exist_ok=True)

    if fallback_path.exists():
        existing = fallback_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    new_id = str(uuid.uuid4())
    fallback_path.write_text(new_id, encoding="utf-8")
    return new_id


def _get_fallback_id_path() -> Path:
    system = platform.system().lower()

    if system == "windows":
        base = os.environ.get("PROGRAMDATA")
        if base:
            return Path(base) / APP_NAME / "machine_id"

    if system == "linux":
        config_home = os.environ.get("XDG_CONFIG_HOME")
        if config_home:
            return Path(config_home) / "deklarant_pro" / "machine_id"
        return Path.home() / ".config" / "deklarant_pro" / "machine_id"

    return Path.home() / ".deklarant_pro" / "machine_id"


def _format_machine_id(raw_id: str) -> str:
    digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest().upper()
    short = digest[:20]
    groups = [short[i:i + 4] for i in range(0, len(short), 4)]

    return f"{MACHINE_ID_PREFIX}-" + "-".join(groups)
```

---

## 6. LOKACIJE LICENCE

### 6.1 Cilj

Licenca se ne smije čuvati u `Program Files`, jer aplikacija često nema pravo pisanja tamo.

Koristiti:

#### Windows

```text
C:\ProgramData\DeklarantPro\license.dat
```

#### Linux

```text
~/.config/deklarant_pro/license.dat
```

---

### 6.2 Kod: `core/licensing/license_paths.py`

```python
from __future__ import annotations

import os
import platform
from pathlib import Path


APP_NAME = "DeklarantPro"


def get_license_dir() -> Path:
    system = platform.system().lower()

    if system == "windows":
        program_data = os.environ.get("PROGRAMDATA")
        if program_data:
            return Path(program_data) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME

    if system == "linux":
        config_home = os.environ.get("XDG_CONFIG_HOME")
        if config_home:
            return Path(config_home) / "deklarant_pro"
        return Path.home() / ".config" / "deklarant_pro"

    return Path.home() / ".deklarant_pro"


def get_license_path() -> Path:
    return get_license_dir() / "license.dat"


def ensure_license_dir() -> Path:
    license_dir = get_license_dir()
    license_dir.mkdir(parents=True, exist_ok=True)
    return license_dir
```

---

## 7. LICENCNI MODEL

### 7.1 Predloženi format `license.dat`

```json
{
  "payload": {
    "customer_name": "Firma DOO",
    "customer_id": "FIRMA_001",
    "machine_id": "DKP-A7F2-91KD-8821-FF09",
    "valid_from": "2026-05-01",
    "valid_to": "2027-05-01",
    "features": ["full"],
    "issued_at": "2026-04-26"
  },
  "signature": "BASE64_SIGNATURE"
}
```

Važno: potpisuje se samo `payload`, ne cijeli fajl sa `signature` poljem.

---

### 7.2 Kod: `core/licensing/license_models.py`

```python
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
```

---

## 8. PUBLIC KEY U APLIKACIJI

### 8.1 Pravilo

Aplikacija smije imati samo **PUBLIC KEY**.

Nikada ne ubacivati PRIVATE KEY u aplikaciju.

---

### 8.2 Kod: `core/licensing/public_key.py`

```python
PUBLIC_KEY_PEM = b"""
-----BEGIN PUBLIC KEY-----
OVDJE_IDE_TVOJ_PUBLIC_KEY
-----END PUBLIC KEY-----
"""
```

Ovaj fajl će se popuniti nakon generisanja private/public key para.

---

## 9. VALIDACIJA LICENCE

### 9.1 Pravila validacije

Aplikacija pri startu provjerava:

1. Da li `license.dat` postoji
2. Da li JSON ima validan format
3. Da li digitalni potpis odgovara
4. Da li je `machine_id` isti kao trenutni računar
5. Da li je današnji datum unutar `valid_from` / `valid_to`
6. Ako je istekao, da li je u grace periodu

---

### 9.2 Kod: `core/licensing/license_validator.py`

```python
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
```

---

## 10. IMPORT LICENCE

### 10.1 Cilj

Korisnik u Admin Panelu klikne `Uvezi licencu`, izabere `.dat` ili `.json`, aplikacija ga validira i kopira na pravu lokaciju.

Ako licenca nije validna, ne smije zamijeniti postojeću validnu licencu.

---

### 10.2 Kod: `core/licensing/license_importer.py`

```python
from __future__ import annotations

import shutil
from pathlib import Path

from .license_paths import ensure_license_dir, get_license_path
from .license_validator import validate_license_file


def import_license(source_path: Path) -> tuple[bool, str]:
    if not source_path.exists():
        return False, "Izabrani licencni fajl ne postoji."

    validation = validate_license_file(source_path)

    if not validation.is_valid:
        return False, validation.message

    ensure_license_dir()
    target_path = get_license_path()

    shutil.copy2(source_path, target_path)

    return True, "Licenca je uspješno uvezena."
```

---

## 11. GENERISANJE PRIVATE/PUBLIC KEY PARA

### 11.1 Kod: `tools/licensing/generate_private_key.py`

```python
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
```

---

## 12. GENERISANJE LICENCE

### 12.1 Kod: `tools/licensing/generate_license.py`

```python
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
```

---

## 13. PRIMJER GENERISANJA LICENCE

```bash
python tools/licensing/generate_license.py \
  --customer-name "Firma DOO Bijeljina" \
  --customer-id "FIRMA_BN_001" \
  --machine-id "DKP-A7F2-91KD-8821-FF09" \
  --valid-from "2026-05-01" \
  --valid-to "2027-05-01" \
  --features "full" \
  --output "licenses/FIRMA_BN_001_license.dat"
```

---

## 14. ADMIN PANEL UI INTEGRACIJA

### 14.1 Šta dodati u Admin Panel

Dodati novu sekciju:

```text
Licenca
```

Sekcija treba da prikaže:

```text
Machine ID: DKP-A7F2-91KD-8821-FF09
Status licence: Aktivna
Firma: Firma DOO Bijeljina
Važi do: 01.05.2027
Paket: full
```

Dugmad:

```text
Kopiraj Machine ID
Uvezi licencu
Osvježi status
```

---

### 14.2 Primjer PySide6 widgeta: `gui/admin/license_panel.py`

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.licensing.license_importer import import_license
from core.licensing.license_paths import get_license_path
from core.licensing.license_validator import validate_license_file
from core.licensing.machine_id import get_machine_id


class LicensePanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.machine_id_label = QLabel()
        self.status_label = QLabel()
        self.customer_label = QLabel()
        self.valid_to_label = QLabel()
        self.features_label = QLabel()

        self.copy_machine_id_button = QPushButton("Kopiraj Machine ID")
        self.import_license_button = QPushButton("Uvezi licencu")
        self.refresh_button = QPushButton("Osvježi status")

        self._setup_ui()
        self._connect_signals()
        self.refresh_status()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Licenca")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        card = QFrame()
        card.setObjectName("LicenseCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(8)

        card_layout.addWidget(self.machine_id_label)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.customer_label)
        card_layout.addWidget(self.valid_to_label)
        card_layout.addWidget(self.features_label)

        buttons = QHBoxLayout()
        buttons.addWidget(self.copy_machine_id_button)
        buttons.addWidget(self.import_license_button)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch(1)

        card_layout.addLayout(buttons)
        root.addWidget(card)
        root.addStretch(1)

    def _connect_signals(self) -> None:
        self.copy_machine_id_button.clicked.connect(self.copy_machine_id)
        self.import_license_button.clicked.connect(self.import_license)
        self.refresh_button.clicked.connect(self.refresh_status)

    def refresh_status(self) -> None:
        machine_id = get_machine_id()
        self.machine_id_label.setText(f"Machine ID: {machine_id}")

        result = validate_license_file(get_license_path())

        if result.payload:
            self.customer_label.setText(f"Firma: {result.payload.customer_name}")
            self.valid_to_label.setText(f"Važi do: {result.payload.valid_to.isoformat()}")
            self.features_label.setText(f"Paket: {', '.join(result.payload.features)}")
        else:
            self.customer_label.setText("Firma: —")
            self.valid_to_label.setText("Važi do: —")
            self.features_label.setText("Paket: —")

        self.status_label.setText(f"Status: {result.message}")

    def copy_machine_id(self) -> None:
        machine_id = get_machine_id()
        QApplication.clipboard().setText(machine_id)
        QMessageBox.information(self, "Machine ID", "Machine ID je kopiran.")

    def import_license(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Izaberi licencni fajl",
            "",
            "License files (*.dat *.json);;All files (*.*)",
        )

        if not file_path:
            return

        success, message = import_license(Path(file_path))

        if success:
            QMessageBox.information(self, "Licenca", message)
        else:
            QMessageBox.warning(self, "Licenca", message)

        self.refresh_status()
```

---

## 15. STARTUP VALIDACIJA APLIKACIJE

### 15.1 Gdje pozvati validaciju

Na samom startu aplikacije, prije otvaranja glavnog prozora ili odmah nakon inicijalizacije glavnog prozora.

Primjer:

```python
from PySide6.QtWidgets import QMessageBox

from core.licensing.license_paths import get_license_path
from core.licensing.license_validator import validate_license_file
from core.licensing.license_models import LicenseStatus


def check_license_or_warn(parent=None) -> bool:
    result = validate_license_file(get_license_path())

    if result.is_valid:
        if result.status == LicenseStatus.EXPIRED_GRACE:
            QMessageBox.warning(
                parent,
                "Licenca ističe",
                result.message,
            )
        return True

    QMessageBox.critical(
        parent,
        "Licenca nije validna",
        result.message,
    )

    return False
```

---

### 15.2 Ponašanje pri nevalidnoj licenci

Preporuka za prvu verziju:

- aplikacija se otvara
- dozvoljen je samo Admin Panel / Licenca
- ostale funkcije su zaključane

Ne preporučujem da aplikacija samo odmah izađe, jer korisnik mora imati način da uveze novu licencu.

---

## 16. FEATURE FLAGS

Polje `features` omogućava različite pakete.

Primjeri:

```json
"features": ["full"]
```

ili:

```json
"features": ["basic", "xml_export", "reports"]
```

---

### 16.1 Helper funkcija

```python
def has_feature(payload, feature_name: str) -> bool:
    if not payload:
        return False

    if "full" in payload.features:
        return True

    return feature_name in payload.features
```

Primjena:

```python
if not has_feature(current_license.payload, "xml_export"):
    disable_xml_export()
```

---

## 17. TESTOVI

Ako projekat ima testove, dodati:

```text
tests/test_machine_id.py
tests/test_license_validator.py
tests/test_license_importer.py
```

---

### 17.1 Test Machine ID formata

```python
from core.licensing.machine_id import get_machine_id


def test_machine_id_format():
    machine_id = get_machine_id()

    assert machine_id.startswith("DKP-")
    assert len(machine_id.split("-")) >= 4
```

---

### 17.2 Test canonical JSON stabilnosti

```python
from core.licensing.license_validator import _canonical_json


def test_canonical_json_stable_order():
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}

    assert _canonical_json(a) == _canonical_json(b)
```

---

## 18. PACKAGING NAPOMENA ZA PYINSTALLER

Ako koristiš PyInstaller, provjeriti da `cryptography` ulazi pravilno u build.

U `declarant.spec` može biti potrebno dodati:

```python
hiddenimports=[
    "cryptography",
]
```

Ako se public key čuva kao Python string u `public_key.py`, nema potrebe za dodatnim data fajlom.

Private key nikada ne smije biti dio PyInstaller builda.

---

## 19. INNO SETUP NAPOMENA

Installer ne mora unositi licencu.

Preporuka:

1. Installer samo instalira aplikaciju
2. Aplikacija pri prvom pokretanju traži licencu
3. Korisnik u Admin Panelu uvozi `license.dat`

Ovo je jednostavnije i manje sklono greškama nego custom license screen u installeru.

---

## 20. SIGURNOSNE NAPOMENE

### Obavezno

- koristiti digitalni potpis
- držati private key van aplikacije
- validirati potpis prije čitanja licence kao validne
- čuvati licencu u ProgramData / config folderu
- hashovati Machine ID

### Ne raditi

```text
❌ plain JSON bez potpisa
❌ hardcoded valid_to u aplikaciji
❌ private key u aplikaciji
❌ oslanjanje samo na šifrovanje
❌ korištenje OS/Python/Qt verzije kao identiteta računara
```

---

## 21. REALNA OGRANIČENJA

Offline licensing nije neprobojan.

Realno stanje:

```text
✔ dovoljno dobro za B2B desktop aplikaciju
✔ nema server troška
✔ jednostavno za podršku
✔ radi offline

❌ nema centralne kontrole
❌ nema automatskog renewal-a
❌ napredan korisnik može pokušati patchovati aplikaciju
```

To je prihvatljiv kompromis za trenutnu fazu projekta.

---

## 22. IMPLEMENTACIONI REDOSLIJED

### FAZA 1 — Machine ID

- [ ] dodati `machine_id.py`
- [ ] prikazati Machine ID u Admin Panelu
- [ ] dodati dugme Kopiraj Machine ID
- [ ] testirati Windows + Linux

---

### FAZA 2 — License validator

- [ ] dodati modele
- [ ] dodati public key
- [ ] dodati validator
- [ ] dodati import licence
- [ ] dodati lokacije licence

---

### FAZA 3 — License generator

- [ ] dodati key generator
- [ ] generisati private/public key
- [ ] public key ubaciti u aplikaciju
- [ ] private key čuvati samo kod vlasnika
- [ ] dodati CLI generator licence

---

### FAZA 4 — UI integracija

- [ ] dodati Licenca panel
- [ ] prikaz statusa
- [ ] import licence
- [ ] poruke korisniku
- [ ] zaključavanje funkcija ako licenca nije validna

---

### FAZA 5 — Packaging

- [ ] provjeriti PyInstaller build
- [ ] provjeriti Inno Setup installer
- [ ] testirati na čistoj Windows mašini bez Python-a

---

## 23. PROMPT ZA CODING AGENTA

```text
Implementiraj offline licensing sistem za PySide6 aplikaciju deklarant_pro.

Cilj:
- bez servera
- bez interneta
- Machine ID + license.dat + digitalni potpis
- Admin Panel integracija

Dodaj module:
core/licensing/machine_id.py
core/licensing/license_paths.py
core/licensing/license_models.py
core/licensing/public_key.py
core/licensing/license_validator.py
core/licensing/license_importer.py

Dodaj tools:
tools/licensing/generate_private_key.py
tools/licensing/generate_license.py

Machine ID:
- Linux: /etc/machine-id
- Windows: HKLM SOFTWARE Microsoft Cryptography MachineGuid
- uvijek hashovati SHA256
- format DKP-XXXX-XXXX-XXXX-XXXX-XXXX
- fallback UUID ako sistemski ID nije dostupan

Licenca:
- JSON sa payload + signature
- potpisuje se canonical JSON payload
- aplikacija validira public key-em
- private key ne smije biti u aplikaciji

Admin Panel:
- dodaj sekciju Licenca
- prikaži Machine ID
- dugme Kopiraj Machine ID
- dugme Uvezi licencu
- prikaz statusa, firme, valid_to i features

Startup:
- na startu validirati license.dat
- ako nije validna, aplikacija ne smije crashovati
- dozvoliti korisniku da uveze novu licencu

Ne implementirati server.
Ne implementirati online aktivaciju.
Ne uvoditi nepotrebnu arhitekturu.
Poštovati postojeću strukturu projekta.
```

---

## 24. ZAKLJUČAK

Najbolje rješenje za trenutnu fazu Deklarant Pro aplikacije je:

```text
Offline license.dat + Machine ID + digitalni potpis
```

Ovaj sistem:

- uklapa se u postojeći Admin Panel
- ne traži server
- ne traži internet
- omogućava godišnje produženje
- daje dovoljno sigurnosti za B2B desktop aplikaciju

Kasnije, ako broj korisnika poraste, sistem se može nadograditi na online licensing server bez bacanja ovog rada.
