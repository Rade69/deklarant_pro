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
