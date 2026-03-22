"""
Auto Fill Service - Automatsko popunjavanje tarifnih brojeva
"""

from typing import List, Dict, Any
from core.draft import InvoiceLine


class AutoFillService:
    """Automatsko popunjavanje osnovnih polja i tarifnih brojeva"""

    @staticmethod
    def fill_basic_fields(items: List[InvoiceLine]) -> int:
        """
        Popuni osnovna polja (valuta, jm, iznos).

        Args:
            items: Lista stavki

        Returns:
            Broj ažuriranih stavki
        """
        filled_count = 0

        for item in items:
            item_updated = False

            # Auto-fill valuta (default EUR if missing)
            if not item.valuta or item.valuta.strip() == "":
                item.valuta = "EUR"
                item_updated = True

            # Auto-fill jm (default kom if missing)
            if not item.jm or item.jm.strip() == "":
                item.jm = "kom"
                item_updated = True

            # Auto-calculate iznos if missing but qty and price exist
            if (
                (not item.iznos or item.iznos == 0)
                and item.kolicina
                and item.cijena_jed
            ):
                item.iznos = item.kolicina * item.cijena_jed
                item_updated = True

            if item_updated:
                filled_count += 1

        return filled_count

    @staticmethod
    def fill_tariff_numbers(
        items: List[InvoiceLine], min_similarity: float = 0.70
    ) -> Dict[str, Any]:
        """
        Popuni tarifne brojeve iz baze znanja.

        Args:
            items: Lista stavki
            min_similarity: Minimalna sličnost za match (default 0.70)

        Returns:
            Dict sa rezultatima:
            {
                "matched": int,
                "unmatched": int,
                "skipped": int,
                "matched_details": List[tuple],
                "unmatched_details": List[tuple],
                "skipped_details": List[tuple]
            }
        """
        from services.tariff_mapping_service import TariffMappingService
        from services.country_origin_validator import merge_country_origin

        service = TariffMappingService()

        matched_count = 0
        unmatched_count = 0
        skipped_count = 0
        matched_details = []
        unmatched_details = []
        skipped_details = []

        for line in items:
            # Skip ako već ima tarifni broj
            if line.tarifni_broj:
                skipped_count += 1
                skipped_details.append(
                    (
                        line.line_no,
                        line.product_code or line.naziv_robe[:30],
                        line.tarifni_broj,
                    )
                )
                continue

            # Pokušaj pronaći mapping
            mapping = service.find_mapping(
                product_code=line.product_code,
                naziv_robe=line.naziv_robe,
                min_similarity=min_similarity,
                zemlja_porijekla=line.zemlja_porijekla,
            )

            if mapping:
                # Pronađen mapping
                line.tarifni_broj = mapping.tarifni_broj
                
                # KORISTI merge_country_origin() za validaciju
                validation_result = merge_country_origin(
                    zemlja_pdf=line.zemlja_porijekla,
                    zemlja_baza=mapping.zemlja_porijekla,
                    povlastica_baza=mapping.povlastica
                )
                
                # Ažuriraj zemlju, povlasticu i confidence polja
                line.zemlja_porijekla = validation_result.final_country
                line.povlastica = validation_result.final_preference
                line.country_confidence = validation_result.confidence.value
                line.country_source = validation_result.source
                if validation_result.conflict_details:
                    line.country_conflict_details = validation_result.conflict_details

                matched_count += 1
                matched_details.append(
                    (
                        line.line_no,
                        line.product_code or line.naziv_robe[:30],
                        mapping.tarifni_broj,
                    )
                )

                # Inkrementiraj usage_count
                service._increment_usage(
                    mapping.tarifni_broj, mapping.product_code, mapping.naziv_robe
                )
            else:
                # Nije pronađen
                unmatched_count += 1
                unmatched_details.append(
                    (line.line_no, line.product_code, line.naziv_robe[:50])
                )
                
                # Ako nema mappinga, ali PDF ima zemlju → postavi HIGH confidence
                if line.zemlja_porijekla:
                    line.country_confidence = "HIGH"
                    line.country_source = "PDF"
                else:
                    line.country_confidence = "LOW"
                    line.country_source = "NONE"

        return {
            "matched": matched_count,
            "unmatched": unmatched_count,
            "skipped": skipped_count,
            "matched_details": matched_details,
            "unmatched_details": unmatched_details,
            "skipped_details": skipped_details,
        }
