# importers/faktura_xml_parser.py
"""
Deklarant Pro - Univerzalni Faktura XML Parser

Parsira bilo koji XML sa strukturom <Faktura>/<Stavke>.
Radi sa Pekabesko, Medicopharm, Blagić, SumaProm, i bilo kojim drugim
dobavljačem koji koristi sličnu XML strukturu.

Princip: za svaki koncept (opis, tarifa, cijena...) imamo listu mogućih
XML tagova — parser uzima prvi koji postoji u fajlu.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from services.security.safe_xml import safe_parse

logger = logging.getLogger("deklarant_pro.import.faktura_xml")

# ── Mapping: koncept → mogući XML tagovi (redoslijed prioriteta) ──

_HEADER_TAGS = {
    "invoice_number": ["BrojFakture", "NalogBroj", "InvoiceNumber", "FakturaBroj", "Broj"],
    "date": ["Datum", "DatumFakture", "InvoiceDate", "Date"],
    "seller_name": ["Prodavac/Naziv", "Seller/Name", "Izdavalac/Naziv", "ProdavacNaziv"],
    "buyer_name": ["Kupac/Naziv", "Buyer/Name", "KupacNaziv", "Primalac/Naziv"],
}

_SUMMARY_TAGS = {
    "bruto_kg": ["UkupnoBrutoKg", "BrutoUkupno", "TotalGrossKg", "GrossWeight"],
    "neto_kg": ["UkupnoNetoKg", "NetoUkupno", "TotalNetKg", "NetWeight"],
    "total_amount": ["UkupnoEUR", "Ukupno", "TotalEUR", "TotalAmount"],
    "origin": ["Poreklo", "Porijeklo", "ZemljaPorekla", "CountryOfOrigin"],
}

_ITEM_TAGS = {
    "description": ["Opis", "NazivRobe", "Description", "OpisRobe", "Naziv"],
    "tariff": ["TarifniBroj", "TariffCode", "HSCode", "HSCodeNumber", "Tarifa"],
    "barcode": ["BarKod", "Barcode", "EAN", "GTIN", "BarKodBroj"],
    "product_code": ["Sifra", "ProductCode", "Code", "Artikal", "ItemCode"],
    "unit": ["JedinicaMere", "Unit", "JM", "MjernaJedinica", "UnitMeasure"],
    "net_weight": ["NetoKgr", "NetoKg", "NetWeight", "NetoKilograms", "NetWeightItem"],
    "quantity": ["Kolicina", "Quantity", "Qty", "KolicinaKom"],
    "unit_price": ["CenaPoJedinici", "CenaEUR", "UnitPrice", "CijenaJed", "PricePerUnit", "Cena"],
    "total_price": ["UkupnoEUR", "Ukupno", "TotalEUR", "TotalPrice", "Iznos"],
    "origin": ["ZemljaPorekla", "Porijeklo", "CountryOfOrigin", "OriginCountry", "ZemljaPorijekla", "Poreklo"],
}


def detect_faktura_xml(filepath: str) -> bool:
    """
    Detektuj da li je XML faktura format.

    Kriteriji:
    - .xml ekstenzija
    - Root tag = "Faktura" (case-insensitive)
    - Ima <Stavke> child element
    """
    try:
        if not str(filepath).lower().endswith(".xml"):
            return False
        tree = safe_parse(filepath)
        root = tree.getroot()
        tag = root.tag.lower()
        # Ukloni namespace ako postoji
        if '}' in tag:
            tag = tag.split('}', 1)[1]
        if tag != "faktura":
            return False
        if root.find("Stavke") is None:
            return False
        return True
    except Exception:
        return False


# ── Helperi ─────────────────────────────────────────────────────────

def _txt(element: ET.Element | None, default: str = "") -> str:
    """Sigurno čitanje teksta XML elementa."""
    if element is None or element.text is None:
        return default
    text = element.text.strip()
    # Ukloni citation markere [cite: N]
    text = re.sub(r"\s*\[cite:[^\]]*\]", "", text).strip()
    return text


def _num(element: ET.Element | None, default: float = 0.0) -> float:
    """Sigurno čitanje numeričke vrijednosti."""
    s = _txt(element).replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def _normalize_tariff(raw: str) -> str:
    """Normalizuj tarifni broj na 8-10 cifara (HS/TARIC standard).
    
    Pravila:
    - Uzmi samo cifre (ukloni slash, razmake, tačke, slova)
    - Ako je > 10 cifara → skrati na 10 (TARIC max)
    - Ako je < 8 i >= 4 cifara → ostavi (korisnik dopunjava)
    - Ako je prazno → vrati prazan string
    """
    s = re.sub(r"[^\d]", "", raw.strip())
    if not s:
        return ""
    # ASYCUDA max: 10 cifara (TARIC)
    if len(s) > 10:
        s = s[:10]
    return s


def _find_any(parent: ET.Element | None, candidates: Sequence[str]) -> ET.Element | None:
    """Nađi prvi postojeći element iz liste kandidata.
    
    Podržava i direktne tagove i putanje sa / (npr. 'Prodavac/Naziv').
    """
    if parent is None:
        return None
    for tag in candidates:
        elem = parent.find(tag)
        if elem is not None:
            return elem
    return None


_JM_MAP = {
    "kgr": "kg", "kg": "kg",
    "par": "par", "kom": "kom", "kos": "kos",
    "l": "L", "ml": "ml", "tab": "tab",
}


def _normalize_jm(raw: str) -> str:
    return _JM_MAP.get(raw.strip().lower(), raw.strip())


# ── Glavni parser ──────────────────────────────────────────────────

def parse_faktura_xml(filepath: str) -> ImportResult:
    """
    Univerzalni parser za bilo koji <Faktura>/<Stavke> XML.

    Args:
        filepath: Putanja do XML fajla

    Returns:
        ImportResult sa stavkama, težinama i metapodacima
    """
    logger.info(f"Univerzalni Faktura XML parsiranje: {Path(filepath).name}")

    tree = safe_parse(filepath)
    root = tree.getroot()

    # ── Zaglavlje ──────────────────────────────────────────────────
    zaglavlje = root.find("Zaglavlje")

    invoice_number = _txt(_find_any(zaglavlje, _HEADER_TAGS["invoice_number"]))
    invoice_date   = _txt(_find_any(zaglavlje, _HEADER_TAGS["date"]))
    seller_name    = _txt(_find_any(zaglavlje, _HEADER_TAGS["seller_name"]))
    buyer_name     = _txt(_find_any(zaglavlje, _HEADER_TAGS["buyer_name"]))

    logger.info(
        f"  Zaglavlje: faktura={invoice_number!r}, datum={invoice_date!r}, "
        f"prodavac={seller_name!r}, kupac={buyer_name!r}"
    )

    # ── Sumarno (opciono) ─────────────────────────────────────────
    sumarno = root.find("Sumarno")
    bruto_kg    = _num(_find_any(sumarno, _SUMMARY_TAGS["bruto_kg"]))
    neto_kg     = _num(_find_any(sumarno, _SUMMARY_TAGS["neto_kg"]))
    total_eur   = _num(_find_any(sumarno, _SUMMARY_TAGS["total_amount"]))
    default_zemlja = _txt(_find_any(sumarno, _SUMMARY_TAGS["origin"])).upper() or "MK"

    logger.info(
        f"  Sumarno: bruto={bruto_kg:.3f}kg, neto={neto_kg:.3f}kg, "
        f"total={total_eur:.2f}EUR, default_zemlja={default_zemlja}"
    )

    # ── Stavke ─────────────────────────────────────────────────────
    stavke_el = root.find("Stavke")
    invoice_lines: list[InvoiceLine] = []

    if stavke_el is not None:
        for stavka in stavke_el.findall("Stavka"):
            line_no = int(stavka.get("br", len(invoice_lines) + 1))

            desc   = _txt(_find_any(stavka, _ITEM_TAGS["description"]))
            tariff_raw = _txt(_find_any(stavka, _ITEM_TAGS["tariff"]))
            tariff = _normalize_tariff(tariff_raw)
            barcode = _txt(_find_any(stavka, _ITEM_TAGS["barcode"]))
            sifra  = _txt(_find_any(stavka, _ITEM_TAGS["product_code"]))
            jm_raw = _txt(_find_any(stavka, _ITEM_TAGS["unit"]))
            neto_item = _num(_find_any(stavka, _ITEM_TAGS["net_weight"]))
            qty    = _num(_find_any(stavka, _ITEM_TAGS["quantity"]))
            price  = _num(_find_any(stavka, _ITEM_TAGS["unit_price"]))
            amount = _num(_find_any(stavka, _ITEM_TAGS["total_price"]))

            # Porijeklo po stavci → fallback na Sumarno → default "MK"
            origin_elem = _find_any(stavka, _ITEM_TAGS["origin"])
            zemlja = _txt(origin_elem).upper() if origin_elem is not None else default_zemlja

            jm = _normalize_jm(jm_raw) if jm_raw else "kg"

            # product_code: šifra > bar kod > line number
            product_code = sifra if sifra else (barcode if barcode else str(line_no))

            line = InvoiceLine(
                line_no=line_no,
                product_code=product_code,
                naziv_robe=desc,
                tarifni_broj=tariff,
                zemlja_porijekla=zemlja,
                povlastica="",
                jm=jm,
                kolicina=qty,
                cijena_jed=price,
                iznos=amount,
                valuta="EUR",
                bruto_kg=0.0,
                neto_kg=neto_item,
            )
            invoice_lines.append(line)

    exporter = Party(name=seller_name) if seller_name else None
    importer_party = Party(name=buyer_name) if buyer_name else None

    logger.info(
        f"  ✅ Parsed {len(invoice_lines)} stavki, "
        f"bruto={bruto_kg:.3f}kg, neto={neto_kg:.3f}kg, exporter={seller_name!r}"
    )

    result = ImportResult(
        items=invoice_lines,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency="EUR",
        import_type="faktura_xml",
        exporter=exporter,
    )

    # Dodaj buyer info u result
    if importer_party:
        result.buyer = importer_party  # type: ignore[attr-defined]

    return result
