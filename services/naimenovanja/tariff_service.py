import logging
logger = logging.getLogger(__name__)
"""
Tariff Service - Upravljanje tarifnim brojevima
"""

from typing import List, Optional, Dict
from services.tariff.tariff_mapping_service import TariffMappingService, TariffMapping
from services.naimenovanja.constants import NaimenovanjaConstants


class TariffService:
    """Upravlja tarifnim brojevima, cache-om i sugestijama"""

    def __init__(self, tab=None):
        # tab je opcionalan — servis je upotrebljiv i bez View-a (testabilnost)
        self.tab = tab
        # Cache za opise tarife: tariff_code → (full, short)
        # Sprijecava N+1 upite pri punjenju tabele / navigaciji.
        self.tariff_cache: Dict[str, str] = {}
        self.tariff_description_cache: Dict[str, tuple] = {}

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
        """Uklanja tehničke tarifne stope s kraja opisa.

        Premješteno iz NaimenovanjaView._clean_tariff_description (naprednija
        verzija od stare TariffService implementacije).

        Primjeri:
          '– ostalo – 15 0 0 10,' → '– ostalo'
          '– – – – punjeni – 10+1KM/kg 0 0 6+1KM/kg 0 0 0 0' → '– – – – punjeni'
          '– – od domaće svinje – 10+3,5KM/kg 10+3,5KM/kg 0 ...' → '– – od domaće svinje'
        """
        if not description:
            return ""

        import re

        # Ukloni "ex NNNN NN NN NN" i sve iza toga (podtarifni izuzetak)
        cleaned = re.sub(r"\s*\bex\s+\d[\d\s]*.*$", "", description, flags=re.IGNORECASE)
        # Ukloni KM/kg stope: npr. "10+3,5KM/kg", "0+1,5KM/kg", "10+3KM/kg"
        cleaned = re.sub(
            r"\s+\d+(?:[+/]\d+(?:[,.]\d+)?)*[A-Z/%][A-Za-z/kg%]*.*$",
            "",
            cleaned,
        )
        # Ukloni sufiks sa 4+ prostorima odvojena broja (npr. "kd 0 0 0 0 5 5 5")
        cleaned = re.sub(r"(?:\s+\w{1,3})?(?:\s+\d+){4,}[\s,]*$", "", cleaned)
        # Ukloni trailing crtice i razmake (en-dash, em-dash, hyphen)
        cleaned = cleaned.rstrip(" \u2012\u2013\u2014-").strip()

        return cleaned if cleaned else description

    def load_tariff_descriptions(self, tariff_code: str) -> tuple:
        """Učitaj (full, short) opise tarife iz SQLite (frozen-svjestan).

        Koristi services.tariff.tarifa_service.trazi_po_kodu koji već ima
        pravilan _resolve_db_path (frozen .exe fallback) i dijeljenu
        read-only konekciju — bez N+1 otvaranja konekcija.

        Premješteno iz NaimenovanjaView._load_tariff_descriptions_sqlite i
        FakturaView._get_tariff_description (objedinjuje obje implementacije).

        Args:
            tariff_code: 4-10 cifreni tarifni broj

        Returns:
            (full_description, short_description)
            full_description  → opis podbroja (8 cifara)
            short_description → opis glave (4 cifre)
        """
        if not tariff_code:
            return "", ""

        digits = "".join(filter(str.isdigit, str(tariff_code)))
        if not digits:
            return "", ""

        # Cache lookup — sprjecava N+1 upite pri punjenju tabele
        cache_key = digits[:8]
        if cache_key in self.tariff_description_cache:
            return self.tariff_description_cache[cache_key]

        try:
            from services.tariff.tarifa_service import trazi_po_kodu

            code8 = digits[:8]
            # Opis podbroja (8 cifara → lookup koji interno probava 10 cifara)
            result8 = trazi_po_kodu(code8)
            full = self._clean_tariff_description(result8["naziv"]) if result8 else ""

            # Opis glave (4 cifre) — samo ako se razlikuje od code8
            code4 = digits[:4]
            short = ""
            if code4 and code4 != code8:
                result4 = trazi_po_kodu(code4)
                short = self._clean_tariff_description(result4["naziv"]) if result4 else ""

            result = (full, short)
            self.tariff_description_cache[cache_key] = result
            return result
        except Exception as e:
            logger.debug(f"SQLite tariff lookup greška: {e}")
            return "", ""

    def load_hierarchical_label(self, tariff_code: str) -> str:
        """Vrati hijerarhijski label (poglavlje / podglava / podbroj).

        Zamjenjuje FakturaView._get_tariff_description — vraća formatiran
        string "poglavlje / podglava / podbroj" za prikaz u preview tabeli.
        """
        if not tariff_code:
            return ""
        digits = "".join(filter(str.isdigit, str(tariff_code)))
        if not digits or not digits.isdigit():
            return ""

        full, short = self.load_tariff_descriptions(tariff_code)
        labels = [l for l in (short, full) if l]
        return " / ".join(labels) if labels else tariff_code

    def load_tariff_description_from_postgres(self, tariff_code: str, nivo: str = "podbroj") -> str:
        """Učitaj opis tarife iz PostgreSQL catalogs.zvanicna_tarifa.

        Fallback kada SQLite (tarifa_2026) ne vrati ništa. Premješteno iz
        NaimenovanjaView._load_tariff_description_from_db — sa cache-om.

        nivo='podbroj' → opis podbroja (8-10 cifara)
        nivo='glava'   → opis glave (4 cifre)
        """
        if not tariff_code or not tariff_code.strip():
            return ""

        cache_key = f"pg:{nivo}:{tariff_code}"
        if cache_key in self.tariff_description_cache:
            return self.tariff_description_cache[cache_key]

        digits = "".join(filter(str.isdigit, str(tariff_code)))
        if not digits:
            return ""

        if nivo == "glava":
            lookup_code = digits[:4]
        else:
            lookup_code = digits

        try:
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    if nivo == "podbroj":
                        candidates = [lookup_code]
                        if len(lookup_code) == 8:
                            candidates.append(lookup_code + "00")
                        elif len(lookup_code) < 10:
                            candidates.append(lookup_code.ljust(10, "0"))

                        result = None
                        for candidate in candidates:
                            cursor.execute(
                                """
                                SELECT tarifni_kod, opis
                                FROM catalogs.zvanicna_tarifa
                                WHERE tarifni_kod = %s AND nivo = 'podbroj'
                                LIMIT 1
                                """,
                                (candidate,),
                            )
                            result = cursor.fetchone()
                            if result:
                                break

                        # Progressivni prefix fallback: 8→7→6 cifara
                        if not result:
                            for prefix_len in range(min(8, len(lookup_code)), 5, -1):
                                cursor.execute(
                                    """
                                    SELECT tarifni_kod, opis
                                    FROM catalogs.zvanicna_tarifa
                                    WHERE tarifni_kod LIKE %s || '%%'
                                      AND nivo = 'podbroj'
                                    ORDER BY tarifni_kod ASC
                                    LIMIT 1
                                    """,
                                    (lookup_code[:prefix_len],),
                                )
                                result = cursor.fetchone()
                                if result:
                                    break
                    else:
                        cursor.execute(
                            """
                            SELECT tarifni_kod, opis
                            FROM catalogs.zvanicna_tarifa
                            WHERE tarifni_kod = %s AND nivo = 'glava'
                            LIMIT 1
                            """,
                            (lookup_code,),
                        )
                        result = cursor.fetchone()

                        if not result:
                            subheading_code = digits[:6] if len(digits) >= 6 else digits
                            cursor.execute(
                                """
                                SELECT tarifni_kod, opis
                                FROM catalogs.zvanicna_tarifa
                                WHERE tarifni_kod = %s AND nivo = 'podglava'
                                LIMIT 1
                                """,
                                (subheading_code,),
                            )
                            result = cursor.fetchone()

                    if result:
                        raw = result["opis"] or ""
                        cleaned = self._clean_tariff_description(raw)
                        self.tariff_description_cache[cache_key] = cleaned
                        return cleaned
                    return ""
        except Exception as e:
            logger.warning(f"⚠️ PostgreSQL greška pri lookup-u tarife: {e}")
            return ""

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
                top_n=50,
            )

            return mappings
        except Exception as e:
            logger.warning(f"  ⚠️  Greška pri traženju prijedloga: {e}")
            return []

    # Nazivi previše opšti za automatsku sugestiju tarife.
    # Premješteno iz NaimenovanjaView._suggest_tariff_impl (poslovna logika u servisu).
    _STOP_WORDS = frozenset({
        "goods", "material", "materials", "item", "items",
        "parts", "product", "products", "roba", "materijal",
        "proizvod", "proizvodi", "artikal", "artikli",
        "stuff", "thing", "things", "misc", "miscellaneous",
        "other", "various",
    })

    def validate_suggestion_input(self, goods_trade_name: str) -> tuple:
        """Provjeri da li je naziv robe pogodan za automatsku sugestiju.

        Premješteno iz NaimenovanjaView._suggest_tariff_impl — poslovna
        logika (STOP_WORDS, dužina) u servisu, View samo prikazuje poruku.

        Returns:
            (is_valid: bool, reason: str)
            reason je prazan ako je validno, inače kratak opis problema.
        """
        naziv = (goods_trade_name or "").strip()
        naziv_lower = naziv.lower()

        if not naziv_lower:
            return (False, "empty")
        if naziv_lower in self._STOP_WORDS:
            return (False, "stop_word")
        if len(naziv_lower) < 5:
            return (False, "too_short")
        return (True, "")

    def validate_mappings(self, mappings: list) -> list:
        """Validira tarifne brojeve iz prijedloga protiv zvanične tarife.

        Premješteno iz NaimenovanjaView._validate_mappings — DB poziv
        (get_tarifa_opis) sada u servisu, ne u View-u.
        """
        from database.db import get_tarifa_opis
        valid = []
        for mapping in mappings:
            try:
                opis = get_tarifa_opis(mapping.tarifni_broj)
                if opis:
                    valid.append(mapping)
                    logger.info(f"      ✅ {mapping.tarifni_broj} je validan")
                else:
                    logger.warning(f" ⚠️ {mapping.tarifni_broj} ne postoji u zvaničnoj tarifi")
            except Exception as e:
                logger.error(f"      ❌ Greška pri validaciji {mapping.tarifni_broj}: {e}")
        return valid

    def validate_tariff(self, tariff_code: str) -> bool:
        """Provjeri da li tarifni broj postoji u zvaničnoj tarifi"""
        try:
            from database.db import get_tarifa_opis

            opis = get_tarifa_opis(tariff_code)
            return opis is not None
        except Exception as e:
            logger.warning(f"  ⚠️  Greška pri validaciji {tariff_code}: {e}")
            return False
