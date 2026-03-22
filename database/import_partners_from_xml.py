#!/usr/bin/env python3
"""
Import pošiljalaca (Exporter) i uvoznika (Consignee) iz ASYCUDA XML fajlova.

Parsira sve XML fajlove iz zadanog foldera i uvozi podatke u:
  - catalogs.izvoznici  (Pošiljaoci / Exporters) — bez JIB-a
  - catalogs.uvoznici   (Uvoznici  / Consignees) — sa JIB-om

Pokretanje:
    python database/import_partners_from_xml.py
    python database/import_partners_from_xml.py /putanja/do/xml/foldera
"""

import sys
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# Dodaj root projekta u path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_db_connection

XML_FOLDER = Path("/home/radovan/Downloads/NOVA ASIKUDA")

# Pravne forme koje se uklanjaju pri normalizaciji (za dedupliciranje)
_LEGAL_FORMS = re.compile(
    r'\b(D\.O\.O|DOO|D\.D\.|DD|A\.D\.|AD|S\.P\.|SP|J\.D\.O\.O\.|JDOO|LLC|LTD|GMBH|CO)\b',
    re.IGNORECASE,
)


def _normalize_naziv(naziv: str) -> str:
    """Normalizuje naziv firme za poređenje (uklanja pravne forme i interpunkciju)."""
    n = naziv.upper().strip()
    n = _LEGAL_FORMS.sub("", n)
    n = re.sub(r'[.\"\',\-]', " ", n)
    n = re.sub(r'\s+', " ", n).strip()
    return n


# ─────────────────────────────────────────────────────────────────────────────
# Parsiranje jednog XML fajla
# ─────────────────────────────────────────────────────────────────────────────

def _parse_name_field(text: str) -> tuple[str, str, str]:
    """
    Rastavlja višelinijsko polje u (naziv, grad, treći_red).
    Format u XML-u: "Naziv\nGrad\nDržava_ili_Adresa"
    """
    if not text:
        return ("", "", "")
    parts = [p.strip() for p in text.strip().split("\n")]
    naziv = parts[0] if len(parts) > 0 else ""
    grad   = parts[1] if len(parts) > 1 else ""
    treci  = parts[2] if len(parts) > 2 else ""
    return naziv, grad, treci


def parse_xml(file_path: Path) -> dict:
    """
    Parsira jedan ASYCUDA XML fajl.
    Vraća {'exporter': {...}, 'consignee': {...}} ili None polja ako ne postoje.
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError:
        return None

    traders = root.find("Traders")
    if traders is None:
        return None

    result = {"exporter": None, "consignee": None}

    # ── Exporter (Pošiljalac) ────────────────────────────────────────────────
    exp = traders.find("Exporter")
    if exp is not None:
        raw = (exp.findtext("Exporter_name") or "").strip()
        if raw:
            naziv, grad, drzava = _parse_name_field(raw)
            if naziv:
                result["exporter"] = {
                    "naziv": naziv,
                    "grad":  grad,
                    "drzava": drzava,
                    "adresa": "",   # nije posebno u XML-u
                }

    # ── Consignee (Uvoznik) ──────────────────────────────────────────────────
    con = traders.find("Consignee")
    if con is not None:
        jib  = (con.findtext("Consignee_code") or "").strip()
        raw  = (con.findtext("Consignee_name") or "").strip()
        if raw:
            naziv, grad, adresa = _parse_name_field(raw)
            if naziv:
                result["consignee"] = {
                    "jib":    jib,
                    "naziv":  naziv,
                    "grad":   grad,
                    "adresa": adresa,
                    "drzava": "BIH" if jib else "",
                }

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Skeniranje svih XML fajlova
# ─────────────────────────────────────────────────────────────────────────────

def scan_xml_folder(folder: Path) -> tuple[dict, dict]:
    """
    Prolazi kroz sve XML fajlove i skuplja unikatne pošiljaaoce i uvoznike.

    Vraća:
        exporters: {naziv -> {naziv, grad, drzava, adresa}}
        consignees: {jib -> {jib, naziv, grad, adresa, drzava}}
    """
    exporters  = {}   # ključ: normalizovani naziv → čuva najpotpuniji zapis
    consignees = {}   # ključ: jib (ili naziv ako nema JIB)

    xml_files = list(folder.glob("*.xml"))
    total = len(xml_files)
    print(f"📂 Pronađeno {total} XML fajlova u {folder}")

    errors = 0
    for i, f in enumerate(xml_files, 1):
        if i % 500 == 0:
            print(f"  ⏳ {i}/{total} obrađeno...")

        data = parse_xml(f)
        if data is None:
            errors += 1
            continue

        # Pošiljalac — ključ je normalizovani naziv, čuva najpotpuniji
        exp = data.get("exporter")
        if exp and exp["naziv"]:
            key = _normalize_naziv(exp["naziv"])
            if key not in exporters:
                exporters[key] = exp
            else:
                # Zadrži zapis sa dužim nazivom (vjerovatno potpuniji)
                if len(exp["naziv"]) > len(exporters[key]["naziv"]):
                    exporters[key] = exp

        # Uvoznik — ključ je JIB (ako ga ima), inače naziv
        con = data.get("consignee")
        if con and con["naziv"]:
            key = con["jib"] if con["jib"] else con["naziv"]
            if key not in consignees:
                consignees[key] = con

    print(f"✅ Skeniranje završeno. Greške parsiranja: {errors}")
    print(f"   Unikatnih pošiljalaca: {len(exporters)}")
    print(f"   Unikatnih uvoznika:    {len(consignees)}")
    return exporters, consignees


# ─────────────────────────────────────────────────────────────────────────────
# Uvoz u PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

def import_exporters(exporters: dict, conn):
    """Uvozi pošiljaaoce u catalogs.izvoznici (bez JIB-a)."""
    cur = conn.cursor()

    # Dohvati postojeće nazive da ne dupliramo
    cur.execute("SELECT naziv FROM catalogs.izvoznici")
    existing = {r["naziv"] for r in cur.fetchall()}

    novi = 0
    for naziv, data in exporters.items():
        if naziv in existing:
            continue
        cur.execute(
            """INSERT INTO catalogs.izvoznici (jib, naziv, adresa, grad, drzava)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT DO NOTHING""",
            ("", data["naziv"], data["adresa"], data["grad"], data["drzava"]),
        )
        novi += 1

    conn.commit()
    print(f"✅ Pošiljaoci: {novi} novih uvezeno, {len(exporters) - novi} već postojalo.")


def import_consignees(consignees: dict, conn):
    """Uvozi uvoznike u catalogs.uvoznici (sa JIB-om gdje postoji)."""
    cur = conn.cursor()

    # Dohvati postojeće JIB-ove i nazive
    cur.execute("SELECT jib, naziv FROM catalogs.uvoznici")
    existing_jibs    = {r["jib"] for r in cur.fetchall() if r["jib"]}
    cur.execute("SELECT naziv FROM catalogs.uvoznici")
    existing_nazivi  = {r["naziv"] for r in cur.fetchall()}

    novi = 0
    azurirani = 0

    for key, data in consignees.items():
        jib   = data["jib"]
        naziv = data["naziv"]

        if jib and jib in existing_jibs:
            # Ažuriraj grad/adresu/drzavu ako JIB već postoji ali podaci mogu biti bolji
            cur.execute(
                """UPDATE catalogs.uvoznici
                   SET grad   = COALESCE(NULLIF(grad,''),   %s),
                       adresa = COALESCE(NULLIF(adresa,''), %s),
                       drzava = COALESCE(NULLIF(drzava,''), %s)
                   WHERE jib = %s""",
                (data["grad"], data["adresa"], data["drzava"], jib),
            )
            azurirani += 1
        elif naziv not in existing_nazivi:
            cur.execute(
                """INSERT INTO catalogs.uvoznici (jib, naziv, adresa, grad, drzava)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (jib, naziv, data["adresa"], data["grad"], data["drzava"]),
            )
            novi += 1

    conn.commit()
    print(f"✅ Uvoznici: {novi} novih uvezeno, {azurirani} ažurirano, "
          f"{len(consignees) - novi - azurirani} duplikata preskočeno.")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else XML_FOLDER

    if not folder.exists():
        print(f"❌ Folder ne postoji: {folder}")
        sys.exit(1)

    print(f"🚀 Import partnera iz XML fajlova")
    print(f"   Folder: {folder}")
    print()

    # 1. Skeniraj XML fajlove
    exporters, consignees = scan_xml_folder(folder)
    print()

    # 2. Uvezi u bazu
    with get_db_connection() as conn:
        print("📥 Uvoz pošiljalaca...")
        import_exporters(exporters, conn)

        print("📥 Uvoz uvoznika...")
        import_consignees(consignees, conn)

    print()
    print("🎉 Import završen!")


if __name__ == "__main__":
    main()
