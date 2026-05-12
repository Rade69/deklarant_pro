"""
Mass Calculator - Kalkulacija masa
"""

from typing import List
from core.draft import InvoiceLine


class MassCalculator:
    """Raspodjeljuje mase proporcionalno na stavke"""

    MASS_DECIMALS = 2

    @staticmethod
    def _round_mass(value: float) -> float:
        return round(value, MassCalculator.MASS_DECIMALS)

    @staticmethod
    def _fix_rounding_remainder(
        all_items: List[InvoiceLine],
        updated_items: List[InvoiceLine],
        field_name: str,
        expected_total: float,
    ) -> None:
        if expected_total <= 0 or len(updated_items) != len(all_items):
            return

        current_total = sum(
            getattr(item, field_name, 0.0) or 0.0 for item in all_items
        )
        diff = MassCalculator._round_mass(expected_total - current_total)
        max_rounding_diff = max(0.05, len(all_items) * 0.01 + 0.01)
        if diff == 0 or abs(diff) > max_rounding_diff:
            return

        target = next(
            (
                item
                for item in reversed(updated_items)
                if (getattr(item, field_name, 0.0) or 0.0) > 0
            ),
            updated_items[-1],
        )
        current_value = getattr(target, field_name, 0.0) or 0.0
        target_value = MassCalculator._round_mass(current_value + diff)
        if target_value >= 0:
            setattr(target, field_name, target_value)

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

        # Izračunaj odnos neto/bruto (default 0.95 ako neto nije poznat)
        neto_bruto_ratio = neto_total / bruto_total if (bruto_total > 0 and neto_total > 0) else 0.95

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
            n = len(items_without_both)

            if total_qty > 0:
                for item in items_without_both:
                    qty = item.kolicina or 0.0
                    if qty > 0:
                        proportion = qty / total_qty
                        if bruto_total > 0:
                            item.bruto_kg = MassCalculator._round_mass(
                                bruto_total * proportion
                            )
                        if neto_total > 0:
                            item.neto_kg = MassCalculator._round_mass(
                                neto_total * proportion
                            )
                        elif item.bruto_kg:
                            item.neto_kg = MassCalculator._round_mass(
                                item.bruto_kg * neto_bruto_ratio
                            )
                        # Ako imamo neto ali ne bruto (samo neto unesen), izračunaj bruto
                        if item.neto_kg and item.neto_kg > 0 and (not item.bruto_kg or item.bruto_kg <= 0):
                            item.bruto_kg = MassCalculator._round_mass(
                                item.neto_kg / neto_bruto_ratio
                            )
                    else:
                        # Stavka nema količinu unutar grupe — ravnomjerna raspodjela
                        item.bruto_kg = (
                            MassCalculator._round_mass(bruto_total / n)
                            if bruto_total > 0
                            else 0.0
                        )
                        item.neto_kg = (
                            MassCalculator._round_mass(neto_total / n)
                            if neto_total > 0
                            else MassCalculator._round_mass(
                                item.bruto_kg * neto_bruto_ratio
                            )
                        )
            else:
                # Nijedna stavka nema količinu — ravnomjerna raspodjela na sve
                avg_bruto = (
                    MassCalculator._round_mass(bruto_total / n)
                    if bruto_total > 0
                    else 0.0
                )
                avg_neto = (
                    MassCalculator._round_mass(neto_total / n)
                    if neto_total > 0
                    else MassCalculator._round_mass(avg_bruto * neto_bruto_ratio)
                )
                for item in items_without_both:
                    item.bruto_kg = avg_bruto
                    item.neto_kg = avg_neto

        # SCENARIJ 2: Stavke SA bruto ALI BEZ neto → izračunaj neto iz bruto
        if items_with_bruto_only and neto_bruto_ratio > 0:
            for item in items_with_bruto_only:
                item.neto_kg = MassCalculator._round_mass(
                    item.bruto_kg * neto_bruto_ratio
                )

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
                    item.bruto_kg = MassCalculator._round_mass(
                        item.neto_kg * (group_bruto / neto_sum)
                    )
        elif items_with_neto_only and bruto_total <= 0:
            # Fallback: nema ukupnog bruta → procijeni bruto iz neta (neto = bruto × 0.95)
            for item in items_with_neto_only:
                if item.neto_kg and item.neto_kg > 0:
                    item.bruto_kg = MassCalculator._round_mass(
                        item.neto_kg / neto_bruto_ratio
                    )

        MassCalculator._fix_rounding_remainder(
            items, items_to_update, "bruto_kg", bruto_total
        )
        MassCalculator._fix_rounding_remainder(
            items, items_to_update, "neto_kg", neto_total
        )

        updated_count = len(items_without_both) + len(items_with_bruto_only) + len(items_with_neto_only)
        skipped_count = len(items) - updated_count

        return {"updated": updated_count, "skipped": skipped_count}
