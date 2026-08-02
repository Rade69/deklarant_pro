# services/declaration_assembly.py

"""
Declaration Assembly Service

Agregira podatke iz više izvora:
1. Master lista (Excel) → template sa svim stavkama (tarife, zemlje)
2. Fakture (PDF/Excel) → cijene za pojedinačne stavke

Prati kompletnost i omogućava validaciju prije kreiranja Draft-a.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from core.draft.draft import InvoiceLine, DeclarationDraft
from importers.invoice_line_utils import normalize_tariff_number
from services.tariff.product_master_list import ProductMasterList
from services.tariff.tariff_mapping_service import validate_preference

logger = logging.getLogger("deklarant_pro.services.assembly")


@dataclass
class AssemblyItem:
    """
    Stavka u procesu assembly-ja.
    Prati porijeklo podataka i kompletnost.
    """
    # Core data (from InvoiceLine)
    invoice_line: InvoiceLine

    # Metadata - porijeklo podataka
    source_master: bool = False  # Da li dolazi iz master liste
    source_invoice: Optional[str] = None  # Ime fakture koja je dodala cijenu
    manually_edited: bool = False  # Da li je ručno izmjenjen

    # Order tracking - prati originalnu poziciju stavke iz fakture
    order: int = -1  # Pozicija u fakturi (-1 = nije postavljeno)

    # Completion tracking
    missing_fields: List[str] = field(default_factory=list)
    is_complete: bool = False

    def update_from_invoice(self, invoice_line: InvoiceLine, invoice_name: str):
        """Ažuriraj podatke iz fakture"""
        # Update cijenu ako postoji
        if invoice_line.cijena_jed and invoice_line.cijena_jed > 0:
            self.invoice_line.cijena_jed = invoice_line.cijena_jed
            self.invoice_line.iznos = invoice_line.iznos or (
                invoice_line.cijena_jed * self.invoice_line.kolicina
            )
            self.source_invoice = invoice_name

        # Update količinu ako je veća
        if invoice_line.kolicina and invoice_line.kolicina > 0:
            self.invoice_line.kolicina = invoice_line.kolicina

        # Update valutu
        if invoice_line.valuta:
            self.invoice_line.valuta = invoice_line.valuta

        # Update tarifni broj ako postoji i ako nije već postavljen
        if invoice_line.tarifni_broj and not self.invoice_line.tarifni_broj:
            self.invoice_line.tarifni_broj = invoice_line.tarifni_broj

        # Update zemlju porijekla ako postoji i ako nije već postavljena
        if invoice_line.zemlja_porijekla and not self.invoice_line.zemlja_porijekla:
            self.invoice_line.zemlja_porijekla = invoice_line.zemlja_porijekla

        # Update i ostala polja ako nisu već postavljena
        if invoice_line.naziv_robe and not self.invoice_line.naziv_robe:
            self.invoice_line.naziv_robe = invoice_line.naziv_robe
        if invoice_line.bruto_kg and not self.invoice_line.bruto_kg:
            self.invoice_line.bruto_kg = invoice_line.bruto_kg
        if invoice_line.neto_kg and not self.invoice_line.neto_kg:
            self.invoice_line.neto_kg = invoice_line.neto_kg
        # Povlastica POTVRĐENA PE1/PE2/PE3 dokazom (EUR.1 dijalog nakon uvoza)
        # UVIJEK nadjačava predlog iz master liste — Excel kolona "preferential"
        # je samo pretpostavka po zemlji, bez dokaza (isto pravilo kao Agent
        # mod, koji master listu uopšte ne koristi kao izvor povlastice).
        has_confirmed_origin = bool(invoice_line.eur1_number) or invoice_line.has_origin_statement
        if has_confirmed_origin:
            if invoice_line.povlastica:
                self.invoice_line.povlastica = invoice_line.povlastica
            if invoice_line.eur1_number:
                self.invoice_line.eur1_number = invoice_line.eur1_number
            self.invoice_line.has_origin_statement = invoice_line.has_origin_statement
            self.invoice_line.is_authorized_exporter = invoice_line.is_authorized_exporter
            # BEZ ovoga ValidationService.country_confidence_style() (Faza 5
            # pravilo) vraća None za svaku Assembly stavku — vidi
            # "if not item.country_confidence: return None" — pa se ✅ NIKAD
            # ne prikazuje čak i kad je povlastica stvarno potvrđena dokazom
            # (bug prijavljen 2026-08-02, isti dan kao ovaj fajl).
            if invoice_line.country_confidence:
                self.invoice_line.country_confidence = invoice_line.country_confidence
                self.invoice_line.country_source = invoice_line.country_source
                self.invoice_line.country_conflict_details = invoice_line.country_conflict_details
        elif invoice_line.povlastica and not self.invoice_line.povlastica:
            zemlja = self.invoice_line.zemlja_porijekla or invoice_line.zemlja_porijekla
            self.invoice_line.povlastica = validate_preference(zemlja, invoice_line.povlastica)
        if invoice_line.jm and not self.invoice_line.jm:
            self.invoice_line.jm = invoice_line.jm

        self._check_completeness()

    def _check_completeness(self):
        """Provjeri kompletnost stavke"""
        self.missing_fields = []

        # Required fields
        required = {
            'naziv_robe': self.invoice_line.naziv_robe,
            'tarifni_broj': self.invoice_line.tarifni_broj,
            'zemlja_porijekla': self.invoice_line.zemlja_porijekla,
            'kolicina': self.invoice_line.kolicina,
            'cijena_jed': self.invoice_line.cijena_jed,
            'valuta': self.invoice_line.valuta,
        }

        for field_name, value in required.items():
            if not value or (isinstance(value, (int, float)) and value <= 0):
                self.missing_fields.append(field_name)

        self.is_complete = len(self.missing_fields) == 0


class DeclarationAssembly:
    """
    Declaration Assembly - agregira podatke iz više izvora.

    Workflow:
    1. load_master_list() → učita template
    2. add_invoice() → dodaj cijene iz faktura
    3. validate_completeness() → provjeri šta nedostaje
    4. create_draft() → kreiraj DeclarationDraft
    """

    def __init__(self):
        self.items: Dict[str, AssemblyItem] = {}  # code → AssemblyItem
        self.imported_invoices: List[str] = []  # Lista uvezenih faktura
        self.master_list_loaded: bool = False
        self.master_list_path: Optional[str] = None

    def load_master_list(self, excel_path: str) -> int:
        """
        Učitaj master listu kao template.

        Args:
            excel_path: Putanja do Excel fajla (Podela po poreklu.xlsx)

        Returns:
            Broj učitanih stavki
        """
        logger.info(f"Učitavanje master liste: {excel_path}")

        master_list = ProductMasterList(excel_path)

        self.items.clear()
        count = 0

        for code, record in master_list.products.items():
            # Kreiraj InvoiceLine iz master record-a
            # VAŽNO: product_code = record.code (originalna šifra, bez #2/#3 sufiksa za duplikate)
            # Dict ključ (code) može imati sufiks, ali product_code treba biti čista šifra za PDF matching
            invoice_line = InvoiceLine(
                line_no=count + 1,
                product_code=record.code,  # Originalna šifra (ne dict ključ koji može imati #2 sufiks)
                naziv_robe=record.name,
                tarifni_broj=normalize_tariff_number(record.tariff),
                zemlja_porijekla=record.origin,
                povlastica=validate_preference(record.origin, record.preferential),
                jm=record.unit,
                kolicina=record.quantity or 0.0,
                cijena_jed=0.0,  # Nema cijene u master listi
                iznos=0.0,
                valuta="EUR",  # Default
                bruto_kg=0.0,
                neto_kg=0.0,
            )

            # Kreiraj AssemblyItem
            assembly_item = AssemblyItem(
                invoice_line=invoice_line,
                source_master=True,
                order=count  # VAŽNO: Postavi originalnu poziciju
            )
            assembly_item._check_completeness()

            self.items[code] = assembly_item
            count += 1

        self.master_list_loaded = True
        self.master_list_path = excel_path

        logger.info(f"Master lista učitana: {count} stavki")
        return count

    def load_master_list_from_lines(
        self,
        invoice_lines: List[InvoiceLine],
        source_name: str
    ) -> int:
        """
        Učitaj master listu direktno iz liste InvoiceLine objekata.
        Koristi se za auto-assembly (prvi import postaje master).

        Args:
            invoice_lines: Lista InvoiceLine objekata
            source_name: Ime izvora (npr. ime fajla)

        Returns:
            Broj učitanih stavki
        """
        logger.info(f"Kreiranje master liste iz linija: {source_name} ({len(invoice_lines)} stavki)")

        self.items.clear()
        count = 0

        for idx, line in enumerate(invoice_lines):
            # Generiši kod za stavku
            # PRIORITET: koristi product_code ako postoji, inače AUTO_xxxx
            if line.product_code and line.product_code.strip():
                code = line.product_code.strip()
            else:
                code = f"AUTO_{idx+1:04d}"

            # Kreiraj AssemblyItem iz InvoiceLine
            assembly_item = AssemblyItem(
                invoice_line=line,
                source_master=True,
                order=idx  # VAŽNO: Postavi originalnu poziciju
            )
            assembly_item._check_completeness()

            self.items[code] = assembly_item
            count += 1

        self.master_list_loaded = True
        self.master_list_path = source_name

        logger.info(f"Master lista kreirana: {count} stavki")
        return count

    def add_invoice(
        self,
        invoice_lines: List[InvoiceLine],
        invoice_name: str
    ) -> Tuple[int, int, List[str]]:
        """
        Dodaj cijene iz fakture.

        Args:
            invoice_lines: Lista InvoiceLine objekata iz fakture
            invoice_name: Ime fakture (za tracking)

        Returns:
            (matched_count, unmatched_count, unmatched_names)
        """
        if not self.master_list_loaded:
            raise ValueError("Master lista nije učitana! Pozovi load_master_list() prvo.")

        logger.info(f"Dodavanje fakture: {invoice_name} ({len(invoice_lines)} stavki)")

        matched = 0
        unmatched = 0
        unmatched_names = []

        # Baza za order novih stavki = odmah iza svih postojećih
        # Svaki dodani fajl produžava listu, čuvajući redoslijed uvoza
        next_order = max((item.order for item in self.items.values() if item.order >= 0), default=-1) + 1
        new_item_idx = 0  # Relativni redoslijed unutar ovog importa

        for idx, invoice_line in enumerate(invoice_lines):
            # Pokušaj match po šifri ili nazivu
            matched_code = self._find_matching_code(invoice_line)

            if matched_code and matched_code in self.items:
                # Update postojeće stavke - ORDER SE NIKAD NE MIJENJA za matched stavke.
                # Redoslijed je određen pri prvom dodavanju stavke (Excel ili prvi import)
                # i mora ostati nepromjenjen bez obzira iz kojeg fajla dolazi cijena.
                self.items[matched_code].update_from_invoice(invoice_line, invoice_name)

                matched += 1
                logger.debug(f"Matched: {invoice_line.naziv_robe} → {matched_code}")
            else:
                # Nova stavka - dodaj JE IZA svih postojećih stavki
                # (redoslijed unutar ovog importa je očuvan, ali iza prethodnih)
                unmatched += 1
                unmatched_names.append(invoice_line.naziv_robe or "Unknown")

                unmatched_code = f"UNMATCHED-{invoice_name}-{idx:03d}"

                assembly_item = AssemblyItem(
                    invoice_line=invoice_line,
                    source_master=False,
                    source_invoice=invoice_name,
                    order=next_order + new_item_idx
                )
                assembly_item._check_completeness()

                self.items[unmatched_code] = assembly_item
                new_item_idx += 1

                logger.warning(f"Unmatched: {invoice_line.naziv_robe} - dodato kao {unmatched_code} (order={next_order + new_item_idx - 1})")

        # Track imported invoice
        if invoice_name not in self.imported_invoices:
            self.imported_invoices.append(invoice_name)

        logger.info(
            f"Faktura '{invoice_name}': {matched} matched, {unmatched} unmatched"
        )

        return matched, unmatched, unmatched_names

    def _find_matching_code(self, invoice_line: InvoiceLine) -> Optional[str]:
        """
        Pronađi odgovarajuću šifru iz master liste za stavku iz fakture.

        Strategija:
        1. Exact match po product_code (PRIORITET - najprecizniji match)
        2. Exact match po nazivu
        3. Fuzzy match po nazivu (similarity > 0.8)
        """
        from difflib import SequenceMatcher

        # STRATEGY 1: Match by product code (if available)
        # This is the most precise match - use it first for Blagić invoices
        if invoice_line.product_code and invoice_line.product_code.strip():
            product_code_lower = invoice_line.product_code.lower().strip()

            # Preferira slobodne (još neuparne) stavke sa istom šifrom.
            # Ovo podržava duplikate u master listi (ista šifra, različite količine):
            # - Prva faktura matchuje prvu slobodnu stavku
            # - Druga faktura matchuje drugu slobodnu stavku (source_invoice=None)
            first_match = None  # Fallback ako su sve stavke već uparene
            for code, item in self.items.items():
                if item.invoice_line.product_code and item.invoice_line.product_code.strip():
                    if item.invoice_line.product_code.lower().strip() == product_code_lower:
                        if item.source_invoice is None:
                            # Slobodna stavka (još nije uparena) - odmah vrati
                            logger.debug(
                                f"✓ Product code match (slobodna): '{invoice_line.product_code}' → "
                                f"'{item.invoice_line.naziv_robe}'"
                            )
                            return code
                        elif first_match is None:
                            # Zapamti prvu uparenu kao fallback
                            first_match = code

            if first_match:
                logger.debug(
                    f"✓ Product code match (fallback, već uparena): '{invoice_line.product_code}'"
                )
                return first_match

        # STRATEGY 2: Match by exact name
        if not invoice_line.naziv_robe:
            return None

        name_lower = invoice_line.naziv_robe.lower().strip()

        # Exact match
        for code, item in self.items.items():
            if item.invoice_line.naziv_robe.lower().strip() == name_lower:
                logger.debug(f"✓ Exact name match: '{invoice_line.naziv_robe}'")
                return code

        # STRATEGY 3: Fuzzy match by name
        best_match = None
        best_score = 0.8  # Threshold

        for code, item in self.items.items():
            master_name = item.invoice_line.naziv_robe.lower().strip()
            score = SequenceMatcher(None, name_lower, master_name).ratio()

            if score > best_score:
                best_score = score
                best_match = code

        if best_match:
            logger.debug(
                f"✓ Fuzzy name match: '{invoice_line.naziv_robe}' → "
                f"'{self.items[best_match].invoice_line.naziv_robe}' (score: {best_score:.2f})"
            )

        return best_match

    def get_completion_status(self) -> Dict[str, any]:
        """
        Dobavi status kompletnosti.

        Returns:
            Dict sa statistikama
        """
        total = len(self.items)
        complete = sum(1 for item in self.items.values() if item.is_complete)
        incomplete = total - complete

        # Group by missing field
        missing_by_field = {}
        for item in self.items.values():
            for field in item.missing_fields:
                if field not in missing_by_field:
                    missing_by_field[field] = 0
                missing_by_field[field] += 1

        # Stavke bez cijene
        missing_price = sum(
            1 for item in self.items.values()
            if 'cijena_jed' in item.missing_fields
        )

        return {
            'total': total,
            'complete': complete,
            'incomplete': incomplete,
            'completion_percentage': (complete / total * 100) if total > 0 else 0,
            'missing_by_field': missing_by_field,
            'missing_price_count': missing_price,
            'imported_invoices': self.imported_invoices.copy(),
            'imported_invoices_count': len(self.imported_invoices),
        }

    def get_incomplete_items(self) -> List[AssemblyItem]:
        """Dobavi listu nekompletnih stavki"""
        return [item for item in self.items.values() if not item.is_complete]

    def create_draft(self) -> DeclarationDraft:
        """
        Kreiraj DeclarationDraft snapshot iz trenutnog stanja.

        Returns:
            DeclarationDraft sa svim stavkama
        """
        if not self.master_list_loaded:
            raise ValueError("Master lista nije učitana!")

        logger.info("Kreiranje DeclarationDraft snapshot-a...")

        # Create draft
        draft = DeclarationDraft()

        # KRITIČNO: Sortiraj stavke po ORDER polju da bi održao redoslijed iz fakture!
        # Stavke koje nemaju order (-1) idu na kraj
        sorted_items = sorted(
            self.items.values(),
            key=lambda item: (item.order if item.order >= 0 else 999999, item.invoice_line.naziv_robe or "")
        )

        # Add all invoice lines (renumber them)
        invoice_lines = []
        for idx, item in enumerate(sorted_items, start=1):
            line = item.invoice_line
            line.line_no = idx
            invoice_lines.append(line)

        draft.invoice_lines = invoice_lines

        # Add metadata
        status = self.get_completion_status()
        logger.info(
            f"Draft kreiran: {len(invoice_lines)} stavki, "
            f"{status['completion_percentage']:.1f}% kompletno (sortirano po redoslijedu iz fakture)"
        )

        return draft

    def export_status_report(self) -> str:
        """Generiši tekstualni izvještaj o statusu"""
        status = self.get_completion_status()

        report = []
        report.append("=" * 60)
        report.append("DECLARATION ASSEMBLY - STATUS REPORT")
        report.append("=" * 60)
        report.append("")
        report.append(f"Master lista: {self.master_list_path or 'N/A'}")
        report.append(f"Ukupno stavki: {status['total']}")
        report.append(f"Kompletno: {status['complete']} ({status['completion_percentage']:.1f}%)")
        report.append(f"Nekompletno: {status['incomplete']}")
        report.append("")
        report.append("Uvezene fakture:")
        for inv in status['imported_invoices']:
            report.append(f"  - {inv}")
        report.append("")
        report.append("Polja koja nedostaju:")
        for field, count in status['missing_by_field'].items():
            report.append(f"  - {field}: {count} stavki")
        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    # Test assembly workflow
    assembly = DeclarationAssembly()

    # Step 1: Load master list
    assembly.load_master_list(
        "tests/data/Podela po poreklu.xlsx"
    )

    # Step 2: Simulate adding invoices
    # (In real app, this would come from PDF/Excel import)

    # Step 3: Check status
    logger.debug(assembly.export_status_report())
