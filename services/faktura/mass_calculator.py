"""
Mass Calculator - Kalkulacija masa
"""

from typing import List
from core.draft import InvoiceLine


class MassCalculator:
    """Raspodjeljuje mase proporcionalno na stavke"""

    @staticmethod
    def calculate_masses(
        items: List[InvoiceLine], bruto_total: float, neto_total: float
    ) -> dict:
        """
        Proporcionalno raspodijeli mase na stavke.

        Args:
            items: Lista stavki
            bruto_total: Ukupna bruto težina
            neto_total: Ukupna neto težina

        Returns:
            Dict sa statistikom: {"updated": int, "skipped": int}
        """
        if not items:
            return {"updated": 0, "skipped": 0}

        # Filtriraj stavke koje nemaju BAR JEDNU težinu
        items_to_update = [
            item
            for item in items
            if (not item.bruto_kg or item.bruto_kg == 0)
            or (not item.neto_kg or item.neto_kg == 0)
        ]

        if not items_to_update:
            return {"updated": 0, "skipped": len(items)}

        # Izračunaj odnos neto/bruto
        neto_bruto_ratio = neto_total / bruto_total if bruto_total > 0 else 0.0

        # Razdvoji stavke po scenariju
        items_without_both = []   # Nemaju ni bruto ni neto (PDF stavke)
        items_with_bruto_only = []  # Imaju bruto ALI ne neto (npr. Blagić Excel)
        items_with_neto_only = []   # Imaju neto ALI ne bruto (npr. Leburic/Pekabesko)

        for item in items_to_update:
            has_bruto = item.bruto_kg and item.bruto_kg > 0
            has_neto = item.neto_kg and item.neto_kg > 0

            if not has_bruto and not has_neto:
                items_without_both.append(item)
            elif has_bruto and not has_neto:
                items_with_bruto_only.append(item)
            elif has_neto and not has_bruto:
                items_with_neto_only.append(item)

        # SCENARIJ 1: Stavke BEZ obe težine (PDF stavke) → proporcionalna distribucija po količini
        if items_without_both:
            total_qty = sum(item.kolicina or 0.0 for item in items_without_both)

            if total_qty > 0:
                for item in items_without_both:
                    qty = item.kolicina or 0.0
                    if qty > 0:
                        proportion = qty / total_qty
                        if bruto_total > 0:
                            item.bruto_kg = bruto_total * proportion
                        if neto_total > 0:
                            item.neto_kg = neto_total * proportion

        # SCENARIJ 2: Stavke SA bruto ALI BEZ neto → izračunaj neto iz bruto
        if items_with_bruto_only and neto_bruto_ratio > 0:
            for item in items_with_bruto_only:
                item.neto_kg = item.bruto_kg * neto_bruto_ratio

        # SCENARIJ 3: Stavke SA neto ALI BEZ bruto (npr. Leburic/Pekabesko) → izračunaj bruto iz neto
        if items_with_neto_only and neto_total > 0 and bruto_total > 0:
            bruto_neto_ratio = bruto_total / neto_total
            # Provjeri da li suma neto stavki odgovara neto_total (iste stavke vs. subset)
            neto_sum = sum(item.neto_kg for item in items_with_neto_only)
            if neto_sum > 0:
                # Proporcionalni bruto: bruto_stavke = neto_stavke × (bruto_total / neto_total)
                # Ali koristimo samo udio ove grupe u ukupnom neto
                group_bruto = bruto_total * (neto_sum / neto_total)
                for item in items_with_neto_only:
                    item.bruto_kg = item.neto_kg * (group_bruto / neto_sum)

        updated_count = len(items_without_both) + len(items_with_bruto_only) + len(items_with_neto_only)
        skipped_count = len(items) - updated_count

        return {"updated": updated_count, "skipped": skipped_count}
