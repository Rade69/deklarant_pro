# importers/vendors/leburic/leburic_pekabesko_xml_parser.py
"""
ASYCUDA Pro - Leburic/Pekabesko XML Parser

Parsira Pekabesko AD fakture u XML formatu.

Format:
    <Faktura>
        <Zaglavlje>
            <BrojFakture>, <Datum>, <Prodavac>, <Kupac>, ...
        </Zaglavlje>
        <Stavke>
            <Stavka br="N">
                <Opis>, <BarKod>, <JedinicaMere>,
                <NetoKgr>, <Kolicina>, <CenaPoJedinici>, <UkupnoEUR>
            </Stavka>
        </Stavke>
        <Sumarno>
            <UkupnoNetoKg>, <UkupnoBrutoKg>, <UkupnoEUR>, <Poreklo>
        </Sumarno>
    </Faktura>

Napomene:
- XML nema tarifne šifre (CustomID) — tarife se mogu auto-popuniti
  preko TariffMappingService po nazivu/bar-kodu
- Zemlja porijekla se čita iz <Poreklo> (default: MK)
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
    Parsira Pekabesko faktura XML fajl.

    Args:
        filepath: Putanja do XML fajla

    Returns:
        ImportResult sa stavkama, težinama i metapodacima
    """
    logger.info(f"Leburic/Pekabesko XML parsiranje: {Path(filepath).name}")

    tree = ET.parse(filepath)
    root = tree.getroot()

    # ── Zaglavlje ──────────────────────────────────────────────────
    zaglavlje = root.find("Zaglavlje")
    invoice_number = ""
    zemlja = "MK"

    if zaglavlje is not None:
        invoice_number = (
            _txt(zaglavlje.find("NalogBroj"))
            or _txt(zaglavlje.find("BrojFakture"))
        )

    # ── Sumarno ────────────────────────────────────────────────────
    sumarno = root.find("Sumarno")
    bruto_kg = 0.0
    neto_kg = 0.0

    if sumarno is not None:
        bruto_kg = _num(sumarno.find("UkupnoBrutoKg"))
        neto_kg  = _num(sumarno.find("UkupnoNetoKg"))
        poreklo  = _txt(sumarno.find("Poreklo")).upper()
        if poreklo:
            zemlja = poreklo

    logger.info(
        f"  Header: faktura={invoice_number!r}, "
        f"bruto={bruto_kg:.3f}kg, neto={neto_kg:.3f}kg, zemlja={zemlja}"
    )

    # ── Stavke ─────────────────────────────────────────────────────
    stavke_el = root.find("Stavke")
    invoice_lines: list[InvoiceLine] = []

    if stavke_el is not None:
        for stavka in stavke_el.findall("Stavka"):
            line_no = int(stavka.get("br", len(invoice_lines) + 1))

            naziv     = _txt(stavka.find("Opis"))
            barcode   = _txt(stavka.find("BarKod"))
            jm_raw    = _txt(stavka.find("JedinicaMere"))
            neto_item = _num(stavka.find("NetoKgr"))
            kolicina  = _num(stavka.find("Kolicina"))
            cijena    = _num(stavka.find("CenaPoJedinici"))
            iznos     = _num(stavka.find("UkupnoEUR"))

            # Normalizuj JM: Kgr/Par/Kom → kg/par/kom
            jm = _normalize_jm(jm_raw)

            # product_code: koristimo bar kod kao privremeni identifikator
            # (XML nema Pekabesko item šifru; tarifa se popunjava naknadno)
            product_code = barcode if barcode else str(line_no)

            line = InvoiceLine(
                line_no=line_no,
                product_code=product_code,
                naziv_robe=naziv,
                tarifni_broj="",          # XML nema tarifne šifre
                zemlja_porijekla=zemlja,
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

    logger.info(
        f"  ✅ Parsed {len(invoice_lines)} stavki, "
        f"bruto={bruto_kg:.3f}kg, neto={neto_kg:.3f}kg"
    )

    return ImportResult(
        items=invoice_lines,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency="EUR",
        import_type="leburic_pekabesko",
        exporter=Party(name="PEKABESKO AD"),
    )


_JM_MAP = {
    "kgr": "kg", "kg": "kg",
    "par": "par", "kom": "kom",
    "kos": "kos", "l": "L", "ml": "ml",
}


def _normalize_jm(raw: str) -> str:
    return _JM_MAP.get(raw.strip().lower(), raw.strip())
