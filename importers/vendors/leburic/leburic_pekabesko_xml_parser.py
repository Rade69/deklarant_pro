# importers/vendors/leburic/leburic_pekabesko_xml_parser.py
"""
ASYCUDA Pro - Faktura XML Parser (Pekabesko / Medicopharm / slični)

Parsira fakture u XML formatu od različitih dobavljača.

Format (zajednička struktura):
    <Faktura>
        <Zaglavlje>
            <BrojFakture>, <Datum>, <Prodavac>, <Kupac>, ...
        </Zaglavlje>
        <Stavke>
            <Stavka br="N">
                <Opis>, <BarKod>, <JedinicaMere>, <Sifra>,
                <NetoKgr>, <Kolicina>, <CenaPoJedinici>/<CenaEUR>, <UkupnoEUR>,
                <ZemljaPorekla> ili <Porijeklo>  ← opciono, po stavci
            </Stavka>
        </Stavke>
        <Sumarno>  ← opciono
            <UkupnoNetoKg>, <UkupnoBrutoKg>, <UkupnoEUR>, <Poreklo>
        </Sumarno>
    </Faktura>

Napomene:
- XML nema tarifne šifre (CustomID) — tarife se mogu auto-popuniti
  preko TariffMappingService po nazivu/bar-kodu
- Zemlja porijekla: prvo <ZemljaPorekla> po stavci → <Porijeklo> po stavci
  → <Sumarno><Poreklo> → default "MK"
- Prodavac se čita iz <Zaglavlje><Prodavac><Naziv>
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult

logger = logging.getLogger("asycuda_pro.import.leburic_pekabesko_xml")


def detect_leburic_pekabesko_xml(filepath: str) -> bool:
    """
    Detektuj Pekabesko faktura XML format.

    Kriteriji:
    - .xml ekstenzija
    - Root tag = "Faktura"
    - Ima <Stavke> child element
    """
    try:
        if not str(filepath).lower().endswith(".xml"):
            return False
        tree = ET.parse(filepath)
        root = tree.getroot()
        if root.tag != "Faktura":
            return False
        if root.find("Stavke") is None:
            return False
        return True
    except Exception:
        return False


def _txt(element: ET.Element | None, default: str = "") -> str:
    """Sigurno čitanje teksta XML elementa (bez citation markera '[cite: N]')."""
    if element is None or element.text is None:
        return default
    # Ukloni citation markere koje mogu biti u tekstu dokumenta
    text = element.text.strip()
    text = re.sub(r"\s*\[cite:[^\]]*\]", "", text).strip()
    return text


def _num(element: ET.Element | None, default: float = 0.0) -> float:
    """Sigurno čitanje numeričke vrijednosti XML elementa."""
    s = _txt(element).replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def parse_leburic_pekabesko_xml(filepath: str) -> ImportResult:
    """
    Parsira faktura XML fajl (Pekabesko, Medicopharm, slični).

    Args:
        filepath: Putanja do XML fajla

    Returns:
        ImportResult sa stavkama, težinama i metapodacima
    """
    logger.info(f"Faktura XML parsiranje: {Path(filepath).name}")

    tree = ET.parse(filepath)
    root = tree.getroot()

    # ── Zaglavlje ──────────────────────────────────────────────────
    zaglavlje = root.find("Zaglavlje")
    invoice_number = ""
    exporter_name  = ""
    exporter_jib   = ""
    importer_name  = ""
    importer_jib   = ""

    if zaglavlje is not None:
        invoice_number = (
            _txt(zaglavlje.find("NalogBroj"))
            or _txt(zaglavlje.find("BrojFakture"))
        )
        # Prodavac (Exporter — strani dobavljač)
        prodavac = zaglavlje.find("Prodavac")
        if prodavac is not None:
            exporter_name = _txt(prodavac.find("Naziv"))
            exporter_jib  = _txt(prodavac.find("PoreskiBroj")) or _txt(prodavac.find("JIB"))

        # Kupac (Importer — domaća BiH firma)
        kupac = zaglavlje.find("Kupac")
        importer_name = ""
        importer_jib  = ""
        if kupac is not None:
            importer_name = _txt(kupac.find("Naziv"))
            importer_jib  = _txt(kupac.find("JIB")) or _txt(kupac.find("PoreskiBroj")) or _txt(kupac.find("MatBroj"))

    # ── Sumarno ────────────────────────────────────────────────────
    sumarno = root.find("Sumarno")
    bruto_kg = 0.0
    neto_kg = 0.0
    default_zemlja = "MK"

    if sumarno is not None:
        bruto_kg = _num(sumarno.find("UkupnoBrutoKg"))
        neto_kg  = _num(sumarno.find("UkupnoNetoKg"))
        poreklo  = _txt(sumarno.find("Poreklo")).upper()
        if poreklo:
            default_zemlja = poreklo

    logger.info(
        f"  Header: faktura={invoice_number!r}, "
        f"bruto={bruto_kg:.3f}kg, neto={neto_kg:.3f}kg, default_zemlja={default_zemlja}"
    )

    # ── Stavke ─────────────────────────────────────────────────────
    stavke_el = root.find("Stavke")
    invoice_lines: list[InvoiceLine] = []

    if stavke_el is not None:
        for stavka in stavke_el.findall("Stavka"):
            line_no = int(stavka.get("br", len(invoice_lines) + 1))

            naziv     = _txt(stavka.find("Opis"))
            tarifa    = _txt(stavka.find("TarifniBroj"))
            barcode   = _txt(stavka.find("BarKod"))
            sifra     = _txt(stavka.find("Sifra"))
            jm_raw    = _txt(stavka.find("JedinicaMere"))
            neto_item = _num(stavka.find("NetoKgr"))
            kolicina  = _num(stavka.find("Kolicina"))

            # Cena: CenaPoJedinici ili CenaEUR
            cijena = _num(stavka.find("CenaPoJedinici")) or _num(stavka.find("CenaEUR"))
            iznos     = _num(stavka.find("UkupnoEUR"))

            # Porijeklo po stavci → fallback na default zemlju
            stavka_poreklo = _txt(stavka.find("ZemljaPorekla")).upper()
            if not stavka_poreklo:
                stavka_poreklo = _txt(stavka.find("Porijeklo")).upper()
            zemlja_stavke = stavka_poreklo if stavka_poreklo else default_zemlja

            # Normalizuj JM: Kgr/Par/Kom → kg/par/kom
            jm = _normalize_jm(jm_raw) if jm_raw else "kg"

            # product_code: šifra > bar kod > line number
            product_code = sifra if sifra else (barcode if barcode else str(line_no))

            line = InvoiceLine(
                line_no=line_no,
                product_code=product_code,
                naziv_robe=naziv,
                tarifni_broj=tarifa,
                zemlja_porijekla=zemlja_stavke,
                povlastica="",
                jm=jm,
                kolicina=kolicina,
                cijena_jed=cijena,
                iznos=iznos,
                valuta="EUR",
                bruto_kg=0.0,
                neto_kg=neto_item,
            )
            invoice_lines.append(line)

    exporter = Party(name=exporter_name, vat_or_id=exporter_jib) if exporter_name else None
    importer = Party(name=importer_name, vat_or_id=importer_jib) if importer_name else None

    for line in invoice_lines:
        line.exporter = exporter
        line.importer = importer

    logger.info(
        f"  ✅ Parsed {len(invoice_lines)} stavki, "
        f"bruto={bruto_kg:.3f}kg, neto={neto_kg:.3f}kg, "
        f"exporter={exporter_name!r}, importer={importer_name!r}"
    )

    return ImportResult(
        items=invoice_lines,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency="EUR",
        import_type="leburic_pekabesko",
        exporter=exporter,
        importer=importer,
    )


_JM_MAP = {
    "kgr": "kg", "kg": "kg",
    "par": "par", "kom": "kom",
    "kos": "kos", "l": "L", "ml": "ml",
}


def _normalize_jm(raw: str) -> str:
    return _JM_MAP.get(raw.strip().lower(), raw.strip())
