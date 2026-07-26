#!/usr/bin/env python3
"""
Sync root .py fajlove u dist_client/ (bez BOM, bez suvišnih trailing whitespace).

Faza -1.B Agent V2 plana §10 — dist_client strategija.

Preskače namjerno različite fajlove (frozen-build patch-evi, .pyd shim-ovi)
i upozorava na fajlove koji postoje samo u jednoj strani.

Korištenje:
    python scripts/sync_dist_client.py          # dry-run
    python scripts/sync_dist_client.py --apply   # primijeni promjene
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist_client"

# Fajlovi koji su NAMJERNO različiti ili ne trebaju sync
SKIP_FILES = {
    "app/run.py",                       # frozen-build MCP start
    "config/settings.py",               # frozen-build path logika
    "services/tarifa_service.py",       # frozen-build patch
    "services/tariff/tariff_mapping_service.py",  # .pyd shim
    "exporters/asycuda_xml_builder.py", # poznat drift, dvosmjeran
}

# Folderi koji se potpuno preskaču
SKIP_DIRS = {".venv", "__pycache__", ".git", "dist_client", "dist", "build", ".worktrees"}


def collect_py_files(root: Path) -> set[Path]:
    """Skupi sve .py fajlove (relativne putanje)."""
    result = set()
    for f in root.rglob("*.py"):
        rel = f.relative_to(root)
        parts = rel.parts
        if parts[0] in SKIP_DIRS:
            continue
        if any(p == "__pycache__" for p in parts):
            continue
        if str(rel).replace("\\", "/") in SKIP_FILES:
            continue
        result.add(rel)
    return result


def normalize(content: bytes) -> bytes:
    """Normalizuj BOM i trailing whitespace."""
    return content.lstrip(b"\xef\xbb\xbf").rstrip()


def check():
    """Provjeri da li su root i dist_client sinhronizovani. Vraća listu razlika."""
    root_files = collect_py_files(ROOT)
    dist_files = collect_py_files(DIST)

    only_root = root_files - dist_files
    only_dist = dist_files - root_files
    different = []

    for rel in sorted(root_files & dist_files):
        root_path = ROOT / rel
        dist_path = DIST / rel
        c1 = normalize(root_path.read_bytes())
        c2 = normalize(dist_path.read_bytes())
        if c1 != c2:
            different.append(rel)

    return sorted(only_root), sorted(only_dist), sorted(different)


def apply():
    """Primijeni sync — kopiraj root u dist_client."""
    root_files = collect_py_files(ROOT)
    synced = 0
    for rel in sorted(root_files):
        root_path = ROOT / rel
        dist_path = DIST / rel
        dist_path.parent.mkdir(parents=True, exist_ok=True)
        content = root_path.read_text(encoding="utf-8-sig")
        dist_path.write_text(content, encoding="utf-8")
        synced += 1
    print(f"Sync: {synced} fajlova kopirano (root → dist_client)")


if __name__ == "__main__":
    dry_run = "--apply" not in sys.argv

    only_root, only_dist, different = check()

    if only_root:
        print(f"\n⚠️  Samo u root ({len(only_root)}):")
        for f in only_root:
            print(f"  + {f}")

    if only_dist:
        print(f"\n⚠️  Samo u dist_client ({len(only_dist)}):")
        for f in only_dist:
            print(f"  - {f}")

    if different:
        print(f"\n❌ STVARNE RAZLIKE ({len(different)}):")
        for f in different:
            print(f"  ~ {f}")
    else:
        print("\n✅ Nema stvarnih razlika (nakon normalizacije).")

    if dry_run:
        print("\n[Dry run — koristi --apply za primjenu]")
        if different and not only_root and not only_dist:
            print("Za sync pokreni: python scripts/sync_dist_client.py --apply")
    else:
        apply()
