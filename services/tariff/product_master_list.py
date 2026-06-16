# services/product_master_list.py

"""
Product Master List Service

Upravlja master listom proizvoda koja sadrži:
- Tarifne brojeve
- Zemlje porijekla
- Preferencijalne oznake
- Standardizovane šifre

Koristi se za obogaćivanje importovanih faktura sa dodatnim podacima.
"""

import logging
import openpyxl
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher

from core.draft.draft import InvoiceLine
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("deklarant_pro.services.product_master")


@dataclass
class ProductMasterRecord:
    """Jedan proizvod iz master liste"""
    code: str              # Šifra proizvoda
    name: str              # Naziv dobra/usluge
    unit: str              # Jedinica mjere
    tariff: str            # Tarifni broj
    origin: str            # Zemlja porijekla (ISO kod)
    preferential: str      # Preferencijal (P ili prazno)
    quantity: float = 0.0  # Default količina (ako je u master listi)


class ProductMasterList:
    """
    Upravlja master listom proizvoda.

    Omogućava:
    - Učitavanje iz Excel fajla
    - Pretragu po šifri ili nazivu
    - Fuzzy matching proizvoda
    - Obogaćivanje faktura podacima iz master liste
    """

    def __init__(self, excel_path: Optional[str] = None):
        """
        Args:
            excel_path: Putanja do Excel fajla sa master listom
        """
        self.products: Dict[str, ProductMasterRecord] = {}  # code → record
        self.products_by_name: Dict[str, ProductMasterRecord] = {}  # name → record

        if excel_path:
            self.load_from_excel(excel_path)

    def load_from_excel(self, excel_path: str) -> int:
        """
        Učita master listu iz Excel fajla.

        Expected columns:
        - Rbr, Šifra, Naziv dobra / usluge, JM, Kol.,
          Tarifni br, Zemlja porekla, Preferencijal, Faktura

        Returns:
            Broj učitanih proizvoda
        """
        logger.info(f"Učitavam master listu: {excel_path}")

        wb = openpyxl.load_workbook(excel_path, data_only=True)

        try:
            ws = wb.active

            # Find column indices
            header_map = {}
            for col_idx in range(1, ws.max_column + 1):
                header = ws.cell(1, col_idx).value
                if header:
                    header_map[str(header).strip().lower()] = col_idx

            # Helper to get column index
            def get_col(name: str) -> Optional[int]:
                return header_map.get(name.lower())

            code_col = get_col("šifra") or get_col("sifra") or 2
            name_col = get_col("naziv dobra / usluge") or get_col("naziv") or 3
            unit_col = get_col("jm") or 4
            qty_col = get_col("kol.") or get_col("kolicina") or 5
            tariff_col = get_col("tarifni br") or get_col("tarifni broj") or 6
            origin_col = get_col("zemlja porekla") or get_col("zemlja") or 7
            pref_col = get_col("preferencijal") or get_col("povlastica") or 8

            # Parse rows
            count = 0
            # Prati duplikate šifri da se ne gube stavke
            code_occurrence: Dict[str, int] = {}

            for row_idx in range(2, ws.max_row + 1):
                code = str(ws.cell(row_idx, code_col).value or "").strip()
                name = str(ws.cell(row_idx, name_col).value or "").strip()

                if not code and not name:
                    continue

                unit = str(ws.cell(row_idx, unit_col).value or "").strip()
                qty = float(ws.cell(row_idx, qty_col).value or 0)
                tariff = str(ws.cell(row_idx, tariff_col).value or "").strip()
                # Normalizuj na 10 cifara: CN kod (8 cifara) dobija sufiks "00"
                if tariff.isdigit() and len(tariff) == 8:
                    tariff = tariff + "00"
                origin_raw = str(ws.cell(row_idx, origin_col).value or "").strip()
                pref_raw = str(ws.cell(row_idx, pref_col).value or "").strip()

                # Normalize origin to ISO code
                origin = normalize_country_name(origin_raw)

                # Normalize preferential (DA/YES → EUP for EU preferences, else empty)
                pref_upper = pref_raw.upper()
                preferential = "EUP" if pref_upper in {"DA", "YES", "Y", "P", "EUP", "1", "TRUE"} else ""

                # Odredi dict ključ:
                # - stavke bez šifre dobijaju auto-generisanu šifru
                # - duplikati dobijaju sufiks (#2, #3...) da se ne prepisuju
                if not code:
                    dict_key = f"NOCODE_{row_idx:04d}"
                else:
                    code_upper = code.upper()
                    occurrence = code_occurrence.get(code_upper, 0) + 1
                    code_occurrence[code_upper] = occurrence
                    dict_key = code_upper if occurrence == 1 else f"{code_upper}#{occurrence}"

                record = ProductMasterRecord(
                    code=code,  # Originalna šifra (bez sufiksa) za PDF matching
                    name=name,
                    unit=unit,
                    tariff=tariff,
                    origin=origin,
                    preferential=preferential,
                    quantity=qty
                )

                # Uvijek sačuvaj u products (sa jedinstvenim ključem)
                self.products[dict_key] = record

                # Store by name (for fuzzy matching)
                if name:
                    self.products_by_name[name.lower()] = record

                count += 1
        finally:
            # Ensure workbook is always closed
            wb.close()

        logger.info(f"Učitano {count} proizvoda iz master liste")
        return count

    def find_by_code(self, code: str) -> Optional[ProductMasterRecord]:
        """Pronađi proizvod po šifri (exact match)"""
        if not code:
            return None
        return self.products.get(code.upper())

    def find_by_name(self, name: str, threshold: float = 0.8) -> Optional[ProductMasterRecord]:
        """
        Pronađi proizvod po nazivu (fuzzy match).

        Args:
            name: Naziv proizvoda
            threshold: Minimum similarity score (0.0-1.0)

        Returns:
            ProductMasterRecord ako je pronađen dobar match
        """
        if not name:
            return None

        name_lower = name.lower().strip()

        # Exact match
        if name_lower in self.products_by_name:
            return self.products_by_name[name_lower]

        # Fuzzy match
        best_match = None
        best_score = threshold

        for master_name, record in self.products_by_name.items():
            score = SequenceMatcher(None, name_lower, master_name).ratio()
            if score > best_score:
                best_score = score
                best_match = record

        if best_match:
            logger.debug(f"Fuzzy match: '{name}' → '{best_match.name}' (score: {best_score:.2f})")

        return best_match

    def enrich_invoice_line(
        self,
        invoice_line: InvoiceLine,
        override_price: bool = False
    ) -> InvoiceLine:
        """
        Obogati InvoiceLine podacima iz master liste.

        Args:
            invoice_line: InvoiceLine iz fakture
            override_price: Ako False, ne mijenja cijenu iz fakture

        Returns:
            Obogaćeni InvoiceLine
        """
        # Try to find product by name
        master_record = self.find_by_name(invoice_line.naziv_robe)

        if not master_record:
            logger.debug(f"Proizvod nije pronađen u master listi: {invoice_line.naziv_robe}")
            return invoice_line

        # Enrich data from master list
        if not invoice_line.tarifni_broj and master_record.tariff:
            invoice_line.tarifni_broj = master_record.tariff

        if not invoice_line.zemlja_porijekla and master_record.origin:
            invoice_line.zemlja_porijekla = master_record.origin

        if not invoice_line.jm and master_record.unit:
            invoice_line.jm = master_record.unit

        logger.debug(
            f"Obogaćen proizvod: {invoice_line.naziv_robe} → "
            f"tariff={master_record.tariff}, origin={master_record.origin}"
        )

        return invoice_line

    def enrich_invoice_lines(
        self,
        invoice_lines: List[InvoiceLine]
    ) -> List[InvoiceLine]:
        """
        Obogati sve InvoiceLine stavke podacima iz master liste.

        Args:
            invoice_lines: Lista InvoiceLine objekata iz fakture

        Returns:
            Lista obogaćenih InvoiceLine objekata
        """
        enriched_lines = []
        matched_count = 0

        for line in invoice_lines:
            enriched = self.enrich_invoice_line(line)
            enriched_lines.append(enriched)

            # Check if enrichment happened
            master_record = self.find_by_name(line.naziv_robe)
            if master_record:
                matched_count += 1

        logger.info(
            f"Obogaćeno {matched_count}/{len(invoice_lines)} stavki iz master liste"
        )

        return enriched_lines


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    # Test master list loading
    master_list = ProductMasterList(
        "/home/radovan/Desktop/PythonProjects/deklarant_pro/tests/data/Podela po poreklu.xlsx"
    )

    logger.info(f"\n✅ Loaded {len(master_list.products)} products")

    # Test fuzzy matching
    test_names = [
        "ISPARIVAC RCS-3250608ED",
        "KUGLASTI VENTIL CA-1/4",
        "AGREGAT (LBP)",
    ]

    logger.debug("\n🔍 Testing fuzzy matching:")
    for name in test_names:
        match = master_list.find_by_name(name)
        if match:
            logger.debug(f"  '{name}' → {match.tariff} ({match.origin})")
        else:
            logger.debug(f"  '{name}' → NOT FOUND")
