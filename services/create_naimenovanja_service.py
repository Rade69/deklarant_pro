"""
ASYCUDA Pro - Kreiraj Naimenovanja Service
SERVICE ZA KREIRANJE NAIMENOVANJA IZ FAKTURE

Implementira logiku:
1. Učitaj invoice_lines iz Faktura Tab-a
2. Grupiši po (tariff, origin, PREFERENCE) ← ISPRAVLJENO!
3. Kreiraj naimenovanja u draft.items
4. Notify Naimenovanja Tab da učita podatke

Author: Radovan + Claude
Date: February 2026
"""

import uuid
import logging
from typing import List, Dict
from dataclasses import dataclass
from core.draft import DeclarationDraft, NaimenovanjeDraft, InvoiceLine

logger = logging.getLogger(__name__)


@dataclass
class GroupKey:
    """Key for grouping invoice lines
    
    DODATO EUR.1 POLJE:
    Stavke sa različitim EUR.1 brojevima idu u odvojena naimenovanja.
    """
    tariff_code: str
    origin_country: str
    preference_code: str = ""  # Povlastica (ispravka!)
    eur1_number: str = ""      # EUR.1 broj (npr. "PE1 000456/2025")

    def __hash__(self):
        return hash((self.tariff_code, self.origin_country, self.preference_code, self.eur1_number))

    def __eq__(self, other):
        return (self.tariff_code == other.tariff_code and
                self.origin_country == other.origin_country and
                self.preference_code == other.preference_code and
                self.eur1_number == other.eur1_number)


class CreateNaimenovanjaService:
    """
    Service for creating Naimenovanja (declaration items) from invoice lines.

    Supports 3 strategies:
    1. ONE_TO_ONE: Each invoice line → 1 naimenovanje (simple)
    2. SMART_GROUP: Group by (tariff, origin, PREFERENCE) → fewer naimenovanja (recommended)
    3. MANUAL: User selects which lines go together (most control)
    """

    def __init__(self, draft: DeclarationDraft):
        self.draft = draft

    def create_one_to_one(self) -> int:
        """
        Strategy 1: ONE_TO_ONE

        Creates 1 naimenovanje for each invoice line.
        Simplest approach, but results in many items on declaration.

        Returns: Number of naimenovanja created
        """
        if not self.draft.invoice_lines:
            logger.warning("  ⚠️  No invoice lines to process!")
            return 0

        logger.debug("  🔄 Creating naimenovanja (ONE_TO_ONE)...")

        # Clear existing items
        self.draft.items.clear()

        # Create 1 naimenovanje per invoice line
        for i, line in enumerate(self.draft.invoice_lines):
            ordinal = i + 1
            naimenovanje = self._create_naimenovanje_from_line(line, ordinal_no=ordinal)
            self.draft.items.append(naimenovanje)

            # Assign back-reference: InvoiceLine -> Naimenovanje
            line.assigned_naimenovanje_id = naimenovanje.item_id
            line.assigned_naimenovanje_ordinal = ordinal

        count = len(self.draft.items)
        logger.info(f"  ✅ Created {count} naimenovanja (1:1 mapping)")

        return count

    def create_smart_group(self) -> int:
        """
        Strategy 2: SMART_GROUP (RECOMMENDED!)

        Groups invoice lines by:
        - Same tariff code
        - Same origin country
        - Same PREFERENCE code (povlastica) ← ISPRAVLJENO!

        Then creates 1 naimenovanje per group.

        Returns: Number of naimenovanja created
        """
        if not self.draft.invoice_lines:
            logger.warning("  ⚠️  No invoice lines to process!")
            return 0

        logger.debug("  🔄 Creating naimenovanja (SMART_GROUP by tariff + origin + preference)...")

        # Group lines by key
        groups: Dict[GroupKey, List[InvoiceLine]] = {}

        for line in self.draft.invoice_lines:
            key = GroupKey(
                tariff_code=line.tarifni_broj or '',
                origin_country=line.zemlja_porijekla or '',
                preference_code=line.povlastica or '',  # InvoiceLine koristi 'povlastica'!
                eur1_number=line.eur1_number or ''      # EUR.1 broj za grupisanje
            )

            if key not in groups:
                groups[key] = []

            groups[key].append(line)

        logger.debug(f"  📊 Grouped {len(self.draft.invoice_lines)} lines into {len(groups)} groups")

        # Clear existing items
        self.draft.items.clear()

        # Create 1 naimenovanje per group
        ordinal = 1
        for key, lines in groups.items():
            naimenovanje = self._create_naimenovanje_from_group(lines, ordinal_no=ordinal)
            self.draft.items.append(naimenovanje)

            # Assign back-reference: InvoiceLine -> Naimenovanje
            for line in lines:
                line.assigned_naimenovanje_id = naimenovanje.item_id
                line.assigned_naimenovanje_ordinal = ordinal

            logger.debug(f"    ✅ Group {ordinal}: Tariff {key.tariff_code}, Origin {key.origin_country}, "
                         f"Pref {key.preference_code}, EUR.1 {key.eur1_number or '(none)'}, "
                         f"{len(lines)} lines → {naimenovanje.gross_mass_kg:.2f} kg, "
                         f"{naimenovanje.item_value:.2f} {naimenovanje.currency}")

            ordinal += 1

        count = len(self.draft.items)
        logger.info(f"  ✅ Created {count} naimenovanja (grouped by tariff + origin + preference + eur1)")

        return count

    def create_from_selection(self, selected_line_indices: List[int]) -> NaimenovanjeDraft:
        """
        Strategy 3: MANUAL

        Creates 1 naimenovanje from selected invoice lines.
        User selects which lines to combine.

        Args:
            selected_line_indices: List of invoice line indices to combine

        Returns: Created NaimenovanjeDraft
        """
        if not selected_line_indices:
            raise ValueError("No lines selected!")

        # Get selected lines
        selected_lines = [self.draft.invoice_lines[i] for i in selected_line_indices]

        # Create naimenovanje
        ordinal_no = len(self.draft.items) + 1
        naimenovanje = self._create_naimenovanje_from_group(selected_lines, ordinal_no=ordinal_no)

        # Add to draft
        self.draft.items.append(naimenovanje)

        logger.info(f"  ✅ Created naimenovanje #{ordinal_no} from {len(selected_lines)} lines")

        return naimenovanje

    # ═══════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════

    def _create_naimenovanje_from_line(self, line: InvoiceLine, ordinal_no: int) -> NaimenovanjeDraft:
        """Create single naimenovanje from single invoice line"""
        # Create source reference
        source_ref = f"Faktura line {line.line_no}" if line.line_no > 0 else "Invoice line"

        naimenovanje = NaimenovanjeDraft(
            item_id=str(uuid.uuid4()),
            ordinal_no=ordinal_no,
            # Basic info (koristi InvoiceLine field names!)
            tariff_code=line.tarifni_broj or '',
            goods_description=line.naziv_robe or '',
            goods_trade_name=line.naziv_robe or '',  # Trgovački naziv (I31_12)
            origin_country_code=line.zemlja_porijekla or '',
            # Quantities
            gross_mass_kg=line.bruto_kg or 0.0,
            net_mass_kg=line.neto_kg or 0.0,
            # Values
            item_value=line.iznos or 0.0,
            statistical_value=line.iznos or 0.0,
            currency=line.valuta or 'EUR',
            # Packaging (InvoiceLine doesn't have these, use defaults)
            package_code='PK',
            package_qty=line.kolicina or 0.0,
            package_marks='X',  # Default: "X" (Oznake i broj)
            # Procedure (default to 4000 = definitive import)
            procedure_code='4000',
            # Preference (povlastica → preference_code)
            preference_code=line.povlastica or '',
            # Source tracking
            source_invoice_refs=[source_ref]
        )

        return naimenovanje

    def _create_naimenovanje_from_group(self, lines: List[InvoiceLine], ordinal_no: int) -> NaimenovanjeDraft:
        """Create single naimenovanje from multiple invoice lines (group)"""
        if not lines:
            raise ValueError("Cannot create naimenovanje from empty group!")

        # Use first line for common attributes
        first_line = lines[0]

        # Combine descriptions (all lines)
        descriptions = [line.naziv_robe for line in lines if line.naziv_robe]
        goods_description = "; ".join(descriptions[:3])  # Max 3 to avoid too long
        if len(descriptions) > 3:
            goods_description += f"; ... (+{len(descriptions)-3} more)"

        # Aggregate quantities (sum all lines - koristi InvoiceLine field names!)
        gross_mass_kg = sum(line.bruto_kg or 0.0 for line in lines)
        net_mass_kg = sum(line.neto_kg or 0.0 for line in lines)
        package_qty = sum(line.kolicina or 0.0 for line in lines)

        # Aggregate values (sum all lines)
        item_value = sum(line.iznos or 0.0 for line in lines)

        # Create source references (faktura line numbers)
        source_refs = [f"Faktura line {line.line_no}" for line in lines if line.line_no > 0]
        if not source_refs:
            source_refs = [f"Invoice lines ({len(lines)} items)"]

        # Check if all lines have same EUR.1 number
        eur1_numbers = set(line.eur1_number for line in lines if line.eur1_number)
        eur1_number = eur1_numbers.pop() if len(eur1_numbers) == 1 else ""
        
        # Determine document code based on has_origin_statement
        # PE1 = EUR.1 obrazac (nema izjave na fakturi)
        # PE2 = Izjava o poreklu na fakturi (ima izjavu)
        doc_code = ""
        if eur1_number:
            if first_line.has_origin_statement:
                doc_code = "PE2"  # Izjava na fakturi
            else:
                doc_code = "PE1"  # EUR.1 obrazac

        naimenovanje = NaimenovanjeDraft(
            item_id=str(uuid.uuid4()),
            ordinal_no=ordinal_no,
            # Basic info (from first line - koristi InvoiceLine field names!)
            tariff_code=first_line.tarifni_broj or '',
            origin_country_code=first_line.zemlja_porijekla or '',
            currency=first_line.valuta or 'EUR',
            package_code='PK',  # Default
            procedure_code='4000',  # Default
            preference_code=first_line.povlastica or '',  # Povlastica (EUP/CEFTAP/TRP)
            # Aggregated data
            goods_description=goods_description,
            goods_trade_name=first_line.naziv_robe or '',  # Trgovački naziv (I31_12) from first line
            gross_mass_kg=gross_mass_kg,
            net_mass_kg=net_mass_kg,
            package_qty=package_qty,
            item_value=item_value,
            statistical_value=item_value,
            package_marks='X',  # Default: "X" (Oznake i broj)
            # EUR.1 u Rub.44.4 (plavi border - master polje) - format: "PE1 {broj}" ili "PE2 {broj}"
            attached_document4=f"{doc_code} {eur1_number}" if doc_code and eur1_number else "",
            # Source tracking
            source_invoice_refs=source_refs
        )

        return naimenovanje


# ═══════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.debug("\n" + "=" * 70)
    logger.debug("CREATE NAIMENOVANJA SERVICE - TEST")
    logger.debug("=" * 70)

    # Create test data
    draft = DeclarationDraft()

    # Add test invoice lines with different preferences (koristi InvoiceLine field names!)
    line1 = InvoiceLine()
    line1.tarifni_broj = "84713000"
    line1.naziv_robe = "Laptop HP EliteBook 840"
    line1.zemlja_porijekla = "CN"
    line1.povlastica = "100"  # Povlastica 100%
    line1.kolicina = 8.0
    line1.bruto_kg = 40.0
    line1.neto_kg = 37.6
    line1.iznos = 5800.0
    line1.valuta = "EUR"
    draft.invoice_lines.append(line1)

    line2 = InvoiceLine()
    line2.tarifni_broj = "85285200"
    line2.naziv_robe = "LED Monitor Dell 24 inch"
    line2.zemlja_porijekla = "CN"
    line2.povlastica = "300"  # Povlastica 300
    line2.kolicina = 10.0
    line2.bruto_kg = 50.0
    line2.neto_kg = 48.0
    line2.iznos = 2000.0
    line2.valuta = "EUR"
    draft.invoice_lines.append(line2)

    line3 = InvoiceLine()
    line3.tarifni_broj = "84713000"  # Same as line1!
    line3.naziv_robe = "Laptop HP EliteBook 850"
    line3.zemlja_porijekla = "CN"
    line3.povlastica = "100"  # Same preference as line1 - will group together!
    line3.kolicina = 5.0
    line3.bruto_kg = 25.0
    line3.neto_kg = 23.5
    line3.iznos = 3500.0
    line3.valuta = "EUR"
    draft.invoice_lines.append(line3)

    logger.debug(f"\n📦 Invoice has {len(draft.invoice_lines)} lines")

    # Test service
    service = CreateNaimenovanjaService(draft)

    # Test Strategy 2: SMART_GROUP (with preference)
    logger.debug("\n" + "─" * 70)
    logger.debug("TEST: SMART_GROUP Strategy (by tariff + origin + PREFERENCE)")
    logger.debug("─" * 70)
    count = service.create_smart_group()
    logger.debug(f"Result: {count} naimenovanja created (expected: 2, grouped by tariff + preference)")

    logger.debug("\n" + "─" * 70)
    logger.debug("Final naimenovanja:")
    for i, item in enumerate(draft.items):
        logger.debug(f" #{i+1}: {item.tariff_code} | Pref: {item.preference_code} | " f"{item.goods_description[:50]}... | " f"{item.gross_mass_kg:.2f} kg | {item.item_value:.2f} {item.currency}")

    logger.debug("\n" + "=" * 70)
    logger.info("✅ TEST COMPLETE!")
    logger.debug("=" * 70 + "\n")
