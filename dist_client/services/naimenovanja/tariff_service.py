import logging
logger = logging.getLogger(__name__)
"""
Tariff Service - Upravljanje tarifnim brojevima
"""

from typing import List, Optional, Dict
from services.tariff_mapping_service import TariffMappingService, TariffMapping
from services.naimenovanja.constants import NaimenovanjaConstants


class TariffService:
    """Upravlja tarifnim brojevima, cache-om i sugestijama"""

    def __init__(self, tab):
        self.tab = tab
        self.tariff_cache: Dict[str, str] = {}

    def load_tariff_description(self, tariff_code: str) -> str:
        """
        Load tariff description from PostgreSQL database.
        Also tries prefix matching if exact match not found.
        Returns empty string if not found.
        """
        if not tariff_code or len(tariff_code.strip()) == 0:
            return ""

        # Helper function to generate fallback codes
        def generate_fallback_codes(code):
            codes = []
            digits = "".join(filter(str.isdigit, str(code)))

            if digits:
                codes.append(digits)

            for i in range(len(digits), 5, -1):
                prefix = digits[:i]
                if prefix not in codes:
                    codes.append(prefix)

            return codes

        # Use get_db_connection context manager
        try:
            from database.db import get_db_connection
            
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Try exact match first
                    cursor.execute(
                        """
                        SELECT tarifni_kod, opis
                        FROM catalogs.zvanicna_tarifa
                        WHERE tarifni_kod = %s
                        LIMIT 1
                    """,
                        (tariff_code.strip(),),
                    )

                    result = cursor.fetchone()

                    # If no exact match, try prefix matching
                    if not result:
                        fallback_codes = generate_fallback_codes(tariff_code)
                        for code in fallback_codes:
                            cursor.execute(
                                """
                                SELECT tarifni_kod, opis
                                FROM catalogs.zvanicna_tarifa
                                WHERE tarifni_kod LIKE %s || '%%'
                                ORDER BY LENGTH(tarifni_kod) DESC
                                LIMIT 1
                            """,
                                (code,),
                            )

                            result = cursor.fetchone()
                            if result:
                                break

                    if result:
                        raw_description = result[1] or ""
                        cleaned_description = self._clean_tariff_description(raw_description)
                        return cleaned_description
                    else:
                        return ""

        except Exception as e:
            logger.warning(f"  ⚠️  PostgreSQL error loading tariff description: {e}")
            return ""

    def _clean_tariff_description(self, description: str) -> str:
        """Clean tariff description by removing technical data"""
        if not description:
            return ""

        import re

        # Remove sequences of numbers that appear to be technical codes
        cleaned = re.sub(r"\b\d+\s+\d+\s+\d+\s+\d+(\s+\d+)*\s*$", "", description)

        # Remove trailing sequences of numbers separated by spaces
        cleaned = re.sub(
            r"\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s*$", "", cleaned
        )

        # Remove any remaining trailing numeric sequences
        cleaned = re.sub(r"\s+\d+\s+\d+\s+\d+\s+\d+\s*$", "", cleaned)

        # Clean up any trailing whitespace
        cleaned = cleaned.rstrip()

        # If cleaning resulted in empty string, return original
        if not cleaned.strip():
            return description

        return cleaned

    def extract_short_code(self, tariff_code: str) -> str:
        """Extract 4-6 digit code from tariff code for higher level classification"""
        if not tariff_code:
            return ""

        digits = "".join(filter(str.isdigit, tariff_code))

        if len(digits) >= 6:
            return digits[:6]
        elif len(digits) >= 4:
            return digits[:4]
        else:
            return digits

    def suggest_tariff(
        self, goods_trade_name: str, origin_country_code: str
    ) -> List[TariffMapping]:
        """
        Sugeriši tarifni broj za trenutno selektovano naimenovanje.

        Args:
            goods_trade_name: Trgovački naziv robe
            origin_country_code: Šifra zemlje porijekla

        Returns:
            Lista top 3 prijedloga
        """
        try:
            service = TariffMappingService()

            mappings = service.find_top_mappings(
                product_code=None,
                naziv_robe=goods_trade_name,
                min_similarity=NaimenovanjaConstants.MIN_SIMILARITY_THRESHOLD,
                zemlja_porijekla=origin_country_code or "",
                top_n=3,
            )

            return mappings
        except Exception as e:
            logger.warning(f"  ⚠️  Greška pri traženju prijedloga: {e}")
            return []

    def validate_tariff(self, tariff_code: str) -> bool:
        """Provjeri da li tarifni broj postoji u zvaničnoj tarifi"""
        try:
            from database.db import get_tarifa_opis

            opis = get_tarifa_opis(tariff_code)
            return opis is not None
        except Exception as e:
            logger.warning(f"  ⚠️  Greška pri validaciji {tariff_code}: {e}")
            return False
