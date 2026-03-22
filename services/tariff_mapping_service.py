# services/tariff_mapping_service.py

"""
Tariff Mapping Service

Automatsko mapiranje proizvoda na tarifne brojeve koristeći bazu znanja.
Omogućava:
- Auto-popunjavanje tarifnih brojeva na osnovu product_code ili naziva
- Učenje iz prošlih uvoza
- Fuzzy matching za slične proizvode
"""

import logging
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher

from database.db import get_db_connection
from core.draft.draft import InvoiceLine
from services.country_origin_validator import merge_country_origin
from services.origin_statement_detector import OriginStatementDetector

logger = logging.getLogger("asycuda_pro.tariff_mapping")


def _norm_tariff(code: str) -> str:
    """Normalizuj tarifni broj na 10 cifara (CN 8-cifreni → TARIC 10-cifreni)."""
    if code and code.isdigit() and len(code) == 8:
        return code + "00"
    return code


# ISO 3166-1 alpha-2 kodovi država članica EU
_EU_MEMBER_STATES: frozenset[str] = frozenset({
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
})

# Povlastica kodovi koji su isključivo za robu EU porijekla
_EU_ONLY_PREFERENCES: frozenset[str] = frozenset({"EUP"})


def validate_preference(zemlja: str, povlastica: str) -> str:
    """
    Vrati validnu povlasticu za datu zemlju porijekla.

    Roba iz ne-EU zemalja ne može imati EU povlasticu (EUP).
    Ako kombinacija nije validna, vraća prazan string.
    """
    if not povlastica:
        return povlastica
    zemlja_upper = (zemlja or "").strip().upper()
    povlastica_upper = povlastica.strip().upper()
    if povlastica_upper in _EU_ONLY_PREFERENCES and zemlja_upper not in _EU_MEMBER_STATES:
        logger.debug(
            f"⚠️  Nevalidna kombinacija: zemlja={zemlja!r}, povlastica={povlastica!r} → povlastica odbijena"
        )
        return ""
    return povlastica


@dataclass
class TariffMapping:
    """Predstavlja jedno mapiranje proizvod → tarif."""
    product_code: str
    naziv_robe: str
    tarifni_broj: str
    zemlja_porijekla: str
    povlastica: str
    usage_count: int
    similarity: float = 1.0  # Za fuzzy matching (0.0-1.0)

    def __post_init__(self):
        self.tarifni_broj = _norm_tariff(self.tarifni_broj)


@dataclass
class MappingResult:
    """Rezultat auto-popunjavanja tarifnih brojeva."""
    total_items: int
    matched_items: int
    unmatched_items: int
    skipped_items: int = 0  # Stavke koje već imaju tarifni broj
    matched_details: List[Tuple[int, str, str]] | None = None  # (line_no, product_code, tarifni_broj)
    unmatched_details: List[Tuple[int, str, str]] | None = None  # (line_no, product_code, naziv_robe)
    skipped_details: List[Tuple[int, str, str]] | None = None  # (line_no, product_code, tarifni_broj)

    def __post_init__(self):
        """Inicijalizuj liste ako nisu postavljene."""
        if self.matched_details is None:
            self.matched_details = []
        if self.unmatched_details is None:
            self.unmatched_details = []
        if self.skipped_details is None:
            self.skipped_details = []


def extract_meaningful_words(text: str) -> str:
    """
    Ekstraktuje samo značajne riječi iz teksta, uklanja šifre/kodove proizvoda.

    Primjeri:
    - "Mikroprekidač MS 385 A-B3-A-0" → "Mikroprekidač"
    - "Chocolate KIT-KAT 123/456" → "Chocolate KIT KAT"
    - "PREKIDAČI OSTALO 8536.50.80" → "PREKIDAČI OSTALO"

    Args:
        text: Input tekst

    Returns:
        Tekst sa samo značajnim riječima (bez kodova/brojeva)
    """
    if not text:
        return ""

    # Razdvoji po spacevima, crtama, zarezima, tačkama
    tokens = re.split(r'[\s\-,./]+', text)

    meaningful_words = []

    for token in tokens:
        token = token.strip()

        if not token:
            continue

        # Skip pure numbers
        if token.isdigit():
            continue

        # Skip tokens koji su većinom brojevi/spec karakteri (npr. "A-B3-A-0", "123/456")
        # Pravilo: Ako ima više od 50% non-alpha karaktera → skip
        alpha_chars = sum(c.isalpha() for c in token)
        total_chars = len(token)

        if total_chars > 0 and (alpha_chars / total_chars) < 0.5:
            continue

        # Skip pure special chars (npr. "-", "/", ".")
        if not any(c.isalnum() for c in token):
            continue

        # Keep this token
        meaningful_words.append(token)

    return ' '.join(meaningful_words)


class TariffMappingService:
    """
    Servis za automatsko mapiranje proizvoda na tarifne brojeve.

    Matching prioritet:
    1. Tačan match po product_code (ako postoji)
    2. Fuzzy match po nazivu proizvoda (>85% sličnosti)
    3. Nije pronađen - ostaje prazan
    """

    def __init__(self):
        """Inicijalizuj servis (koristi PostgreSQL konekciju iz database.db)."""
        logger.info("✅ TariffMappingService inicijalizovan (PostgreSQL)")

    def auto_populate_tariffs(
        self,
        invoice_lines: List[InvoiceLine],
        min_similarity: float = 0.85,
        overwrite_existing: bool = False
    ) -> MappingResult:
        """
        Automatski popuni tarifne brojeve za invoice lines.

        Args:
            invoice_lines: Lista fakturnih stavki
            min_similarity: Minimalna sličnost za fuzzy match (0.0-1.0)
            overwrite_existing: Da li prepisati postojeće tarifne brojeve

        Returns:
            MappingResult sa statistikom i detaljima
        """
        logger.info(f"🎯 Auto-popunjavanje tarifnih brojeva za {len(invoice_lines)} stavki...")

        # Inicijalizuj detektor izjava (jednom za sve stavke)
        detector = OriginStatementDetector()

        matched_count = 0
        unmatched_count = 0
        matched_details = []
        unmatched_details = []

        for line in invoice_lines:
            # Skip ako već ima tarifni broj i ne želimo overwrite
            if line.tarifni_broj and not overwrite_existing:
                continue

            # Pokušaj pronaći mapping
            mapping = self.find_mapping(
                product_code=line.product_code,
                naziv_robe=line.naziv_robe,
                min_similarity=min_similarity,
                zemlja_porijekla=line.zemlja_porijekla  # Proslijedi zemlju iz PDF-a
            )

            if mapping:
                # Pronađen mapping - popuni SAMO tarifni broj
                line.tarifni_broj = mapping.tarifni_broj

                # ⚠️ NE DIRAJ povlasticu i eur1_number ako već postoje!
                # Korisnik je već uneo kroz EUR.1/PE2 dialog

                # Ako nema povlasticu, popuni iz mapping-a
                if not line.povlastica and not line.eur1_number:
                    # DETEKTUJ da li PDF sadrži izjavu o poreklu
                    has_origin_statement = line.raw.get('has_origin_statement', False)

                    # KORISTI merge_country_origin() za validaciju
                    validation_result = merge_country_origin(
                        zemlja_pdf=line.zemlja_porijekla,
                        zemlja_baza=mapping.zemlja_porijekla,
                        povlastica_baza=mapping.povlastica,
                        has_origin_statement=has_origin_statement
                    )

                    # Ažuriraj zemlju, povlasticu i confidence polja
                    line.zemlja_porijekla = validation_result.final_country
                    line.povlastica = validation_result.final_preference
                    line.country_confidence = validation_result.confidence.value
                    line.country_source = validation_result.source
                    if validation_result.conflict_details:
                        line.country_conflict_details = validation_result.conflict_details
                else:
                    # Već ima povlasticu/eur1_number - samo ažuriraj zemlju iz mapping-a ako je prazna
                    if not line.zemlja_porijekla and mapping.zemlja_porijekla:
                        line.zemlja_porijekla = mapping.zemlja_porijekla

                matched_count += 1
                matched_details.append((
                    line.line_no,
                    line.product_code or line.naziv_robe[:30],
                    mapping.tarifni_broj
                ))

                # Inkrementiraj usage_count
                self._increment_usage(mapping.tarifni_broj, mapping.product_code, mapping.naziv_robe)

                logger.debug(f"  ✅ Stavka #{line.line_no}: {line.product_code} → {mapping.tarifni_broj} "
                            f"(povlastica={line.povlastica or 'N/A'}, eur1={line.eur1_number or 'N/A'})")
            else:
                # Nije pronađen mapping
                unmatched_count += 1
                unmatched_details.append((
                    line.line_no,
                    line.product_code,
                    line.naziv_robe[:50]
                ))

                # Ako nema mappinga, ali PDF ima zemlju → postavi confidence na osnovu toga da li ima izjavu
                has_origin_statement = line.raw.get('has_origin_statement', False)
                if line.zemlja_porijekla:
                    if has_origin_statement:
                        line.country_confidence = "HIGH"
                        line.country_source = "PDF_IZJAVA"
                    else:
                        line.country_confidence = "MEDIUM"
                        line.country_source = "PDF_OZNAKA"
                        line.country_conflict_details = "PDF nema izjavu o poreklu - potrebna intervencija za povlasticu"
                else:
                    line.country_confidence = "LOW"
                    line.country_source = "NONE"
                    line.country_conflict_details = "Nema podataka o poreklu - potreban manuelni unos ili EUR1"

                logger.debug(f"  ⚠️  Stavka #{line.line_no}: {line.product_code} - nije pronađen mapping")

        result = MappingResult(
            total_items=len(invoice_lines),
            matched_items=matched_count,
            unmatched_items=unmatched_count,
            matched_details=matched_details,
            unmatched_details=unmatched_details
        )

        logger.info(f"✅ Auto-popunjavanje završeno: {matched_count}/{len(invoice_lines)} stavki popunjeno")

        return result

    def find_mapping(
        self,
        product_code: str,
        naziv_robe: str,
        min_similarity: float = 0.85,
        zemlja_porijekla: str = ""
    ) -> Optional[TariffMapping]:
        """
        Pronađi mapping za proizvod.

        Matching prioritet:
        1. Tačan match po product_code (sa prioritetom za istu zemlju)
        2. Fuzzy match po nazivu (>min_similarity, sa prioritetom za istu zemlju)

        Args:
            product_code: Šifra proizvoda
            naziv_robe: Naziv proizvoda
            min_similarity: Minimalna sličnost za fuzzy match
            zemlja_porijekla: Zemlja porijekla (za prioritizaciju matching-a)

        Returns:
            TariffMapping ili None ako nije pronađen
        """
        logger.debug(f"🔍 find_mapping: product_code='{product_code}', naziv='{naziv_robe[:40] if naziv_robe else ''}', zemlja='{zemlja_porijekla}'")

        with get_db_connection() as conn:
            with conn.cursor() as cursor:

                # 1. Pokušaj tačan match po product_code
                if product_code and product_code.strip():
                    cursor.execute("""
                        SELECT product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, usage_count
                        FROM catalogs.product_tariff_mapping
                        WHERE product_code ILIKE %s
                        ORDER BY usage_count DESC
                        LIMIT 1
                    """, (product_code.strip(),))

                    row = cursor.fetchone()
                    if row:
                        return TariffMapping(
                            product_code=row["product_code"],
                            naziv_robe=row["naziv_robe"],
                            tarifni_broj=row["tarifni_broj"],
                            zemlja_porijekla=row["zemlja_porijekla"] or "",
                            povlastica=row["povlastica"] or "",
                            usage_count=row["usage_count"],
                            similarity=1.0  # Tačan match
                        )

                # 2. Pokušaj fuzzy match po nazivu (OPTIMIZOVANO)
                if naziv_robe and naziv_robe.strip():
                    naziv_lower = naziv_robe.strip().lower()

                    # Ekstraktuj ključne riječi (prva 3 riječi, bez kratkih)
                    keywords = [w for w in naziv_lower.split()[:3] if len(w) > 2]

                    candidates = []

                    if keywords:
                        # Pretraži sa ILIKE za svaku ključnu riječ
                        like_conditions = " OR ".join(["naziv_robe ILIKE %s" for _ in keywords])
                        like_params = [f"%{kw}%" for kw in keywords]

                        cursor.execute(f"""
                            SELECT product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, usage_count
                            FROM catalogs.product_tariff_mapping
                            WHERE ({like_conditions})
                            ORDER BY usage_count DESC
                            LIMIT 500
                        """, like_params)

                        candidates = cursor.fetchall()
                        logger.debug(f"  📋 ILIKE pretraga našla {len(candidates)} kandidata")

                    # Ako ILIKE nije našao kandidate, uzmi top 500 najčešće korišćenih
                    if not candidates:
                        cursor.execute("""
                            SELECT product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, usage_count
                            FROM catalogs.product_tariff_mapping
                            WHERE naziv_robe IS NOT NULL AND naziv_robe != ''
                            ORDER BY usage_count DESC
                            LIMIT 500
                        """)
                        candidates = cursor.fetchall()
                        logger.debug(f"  📋 Fallback top 500: {len(candidates)} kandidata")

                    # Multi-strategy matching: substring + word-based + fuzzy
                    best_match = None
                    best_similarity = 0.0

                    for row in candidates:
                        candidate_lower = row["naziv_robe"].lower()

                        naziv_words = set(w for w in re.findall(r'\b\w+\b', naziv_lower) if len(w) > 2 and not w.isdigit())
                        candidate_words = set(w for w in re.findall(r'\b\w+\b', candidate_lower) if len(w) > 2 and not w.isdigit())

                        # Strategy 1: Substring match
                        if naziv_lower in candidate_lower or candidate_lower in naziv_lower:
                            similarity = 0.95

                        # Strategy 2: Word-based match
                        elif naziv_words and candidate_words:
                            common_words = naziv_words & candidate_words
                            if common_words:
                                smaller_set_size = min(len(naziv_words), len(candidate_words))
                                word_match_ratio = len(common_words) / smaller_set_size

                                if word_match_ratio >= 0.8:
                                    similarity = 0.85 + (0.15 * word_match_ratio)
                                else:
                                    similarity = 0.7 + (0.15 * word_match_ratio)
                            else:
                                similarity = SequenceMatcher(None, naziv_lower, candidate_lower).ratio()

                        # Strategy 3: Standard fuzzy match
                        else:
                            similarity = SequenceMatcher(None, naziv_lower, candidate_lower).ratio()

                        # BONUS: Ista zemlja porijekla +10%
                        candidate_zemlja = row["zemlja_porijekla"] or ""
                        country_bonus = 0.0
                        if zemlja_porijekla and candidate_zemlja and zemlja_porijekla.upper() == candidate_zemlja.upper():
                            country_bonus = 0.10

                        final_similarity = similarity + country_bonus

                        if final_similarity > best_similarity and similarity >= min_similarity:
                            best_similarity = final_similarity
                            best_match = TariffMapping(
                                product_code=row["product_code"] or "",
                                naziv_robe=row["naziv_robe"],
                                tarifni_broj=row["tarifni_broj"],
                                zemlja_porijekla=row["zemlja_porijekla"] or "",
                                povlastica=row["povlastica"] or "",
                                usage_count=row["usage_count"],
                                similarity=final_similarity
                            )
                            # Early exit ako je gotovo savršen match
                            if best_similarity >= 0.98:
                                break

                    if best_match:
                        logger.debug(f"  ✅ MATCH FOUND: '{best_match.naziv_robe[:50]}' → {best_match.tarifni_broj} (similarity: {best_similarity:.2%})")
                    else:
                        logger.debug(f"  ❌ NO MATCH: best_similarity={best_similarity:.2%} < min_similarity={min_similarity:.2%}")

                    return best_match

        logger.debug(f"  ⚠️  NO MATCH: naziv_robe je prazan ili nema product_code")
        return None

    def find_top_mappings(
        self,
        product_code: Optional[str] = None,
        naziv_robe: Optional[str] = None,
        min_similarity: float = 0.65,
        zemlja_porijekla: str = "",
        top_n: int = 3
    ) -> List[TariffMapping]:
        """
        Pronađi top N mappinga za proizvod.

        Args:
            product_code: Šifra proizvoda
            naziv_robe: Naziv proizvoda
            min_similarity: Minimalna sličnost za fuzzy match
            zemlja_porijekla: Zemlja porijekla (za prioritizaciju)
            top_n: Broj rezultata (default: 3)

        Returns:
            Lista TariffMapping objekata (max top_n)
        """
        logger.debug(f"🔍 find_top_mappings: product_code='{product_code}', "
                    f"naziv='{naziv_robe[:40] if naziv_robe else ''}', "
                    f"zemlja='{zemlja_porijekla}', top_n={top_n}")

        all_matches = []

        with get_db_connection() as conn:
            with conn.cursor() as cursor:

                # 1. Pokušaj tačan match po product_code
                if product_code and product_code.strip():
                    cursor.execute("""
                        SELECT product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, usage_count
                        FROM catalogs.product_tariff_mapping
                        WHERE product_code ILIKE %s
                        ORDER BY usage_count DESC
                        LIMIT %s
                    """, (product_code.strip(), top_n))

                    rows = cursor.fetchall()
                    for row in rows:
                        all_matches.append(TariffMapping(
                            product_code=row["product_code"],
                            naziv_robe=row["naziv_robe"],
                            tarifni_broj=row["tarifni_broj"],
                            zemlja_porijekla=row["zemlja_porijekla"] or "",
                            povlastica=row["povlastica"] or "",
                            usage_count=row["usage_count"],
                            similarity=1.0
                        ))

                    if len(all_matches) >= top_n:
                        logger.debug(f"  ✅ {len(all_matches)} exact matches found via product_code")
                        return all_matches[:top_n]

                # 2. Pokušaj fuzzy match po nazivu
                if naziv_robe and naziv_robe.strip():
                    normalized_naziv = extract_meaningful_words(naziv_robe)
                    naziv_lower = normalized_naziv.strip().lower()

                    keywords = [w for w in naziv_lower.split()[:3] if len(w) > 2]
                    candidates = []

                    if keywords:
                        like_conditions = " OR ".join(["naziv_robe ILIKE %s" for _ in keywords])
                        like_params = [f"%{kw}%" for kw in keywords]

                        cursor.execute(f"""
                            SELECT product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, usage_count
                            FROM catalogs.product_tariff_mapping
                            WHERE ({like_conditions})
                            ORDER BY usage_count DESC
                            LIMIT 500
                        """, like_params)

                        candidates = cursor.fetchall()

                    if not candidates:
                        cursor.execute("""
                            SELECT product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, usage_count
                            FROM catalogs.product_tariff_mapping
                            WHERE naziv_robe IS NOT NULL AND naziv_robe != ''
                            ORDER BY usage_count DESC
                            LIMIT 500
                        """)
                        candidates = cursor.fetchall()

                    candidate_matches = []

                    for row in candidates:
                        candidate_normalized = extract_meaningful_words(row["naziv_robe"])
                        candidate_lower = candidate_normalized.lower()

                        naziv_words = set(w for w in re.findall(r'\b\w+\b', naziv_lower) if len(w) > 2 and not w.isdigit())
                        candidate_words = set(w for w in re.findall(r'\b\w+\b', candidate_lower) if len(w) > 2 and not w.isdigit())

                        if naziv_lower in candidate_lower or candidate_lower in naziv_lower:
                            similarity = 0.95
                        elif naziv_words and candidate_words:
                            common_words = naziv_words & candidate_words
                            if common_words:
                                smaller_set_size = min(len(naziv_words), len(candidate_words))
                                word_match_ratio = len(common_words) / smaller_set_size
                                if word_match_ratio >= 0.8:
                                    similarity = 0.85 + (0.15 * word_match_ratio)
                                else:
                                    similarity = 0.7 + (0.15 * word_match_ratio)
                            else:
                                similarity = SequenceMatcher(None, naziv_lower, candidate_lower).ratio()
                        else:
                            similarity = SequenceMatcher(None, naziv_lower, candidate_lower).ratio()

                        candidate_zemlja = row["zemlja_porijekla"] or ""
                        country_bonus = 0.0
                        if zemlja_porijekla and candidate_zemlja and zemlja_porijekla.upper() == candidate_zemlja.upper():
                            country_bonus = 0.10

                        final_similarity = similarity + country_bonus

                        if similarity >= min_similarity:
                            candidate_matches.append(TariffMapping(
                                product_code=row["product_code"] or "",
                                naziv_robe=row["naziv_robe"],
                                tarifni_broj=row["tarifni_broj"],
                                zemlja_porijekla=row["zemlja_porijekla"] or "",
                                povlastica=row["povlastica"] or "",
                                usage_count=row["usage_count"],
                                similarity=final_similarity
                            ))

                    candidate_matches.sort(key=lambda m: m.similarity, reverse=True)
                    all_matches.extend(candidate_matches[:top_n])

        # Ukloni duplikate (isti tarifni broj)
        seen_tariffs = set()
        unique_matches = []
        for match in all_matches:
            if match.tarifni_broj not in seen_tariffs:
                seen_tariffs.add(match.tarifni_broj)
                unique_matches.append(match)
                if len(unique_matches) >= top_n:
                    break

        logger.debug(f"  ✅ Pronađeno {len(unique_matches)} unique match-eva")
        return unique_matches

    def save_mapping(
        self,
        product_code: str,
        naziv_robe: str,
        tarifni_broj: str,
        zemlja_porijekla: str = "",
        povlastica: str = ""
    ) -> bool:
        """
        Sačuvaj novo mapiranje u bazu znanja.

        Args:
            product_code: Šifra proizvoda
            naziv_robe: Naziv proizvoda
            tarifni_broj: Tarifni broj
            zemlja_porijekla: Zemlja porijekla
            povlastica: Povlastica

        Returns:
            True ako je uspješno sačuvano
        """
        try:
            tarifni_broj = _norm_tariff(tarifni_broj)

            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO catalogs.product_tariff_mapping
                        (product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, usage_count)
                        VALUES (%s, %s, %s, %s, %s, 1)
                        ON CONFLICT (COALESCE(product_code, ''), COALESCE(naziv_robe, '')) DO UPDATE SET
                            tarifni_broj = EXCLUDED.tarifni_broj,
                            zemlja_porijekla = EXCLUDED.zemlja_porijekla,
                            povlastica = EXCLUDED.povlastica,
                            usage_count = catalogs.product_tariff_mapping.usage_count + 1,
                            last_used = CURRENT_TIMESTAMP
                    """, (product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica))

            logger.info(f"✅ Sačuvano mapiranje: {product_code} → {tarifni_broj}")
            return True

        except Exception as e:
            logger.error(f"❌ Greška pri čuvanju mapiranja: {e}")
            return False

    def _increment_usage(self, tarifni_broj: str, product_code: Optional[str], naziv_robe: str):
        """Inkrementiraj usage_count za mapping."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE catalogs.product_tariff_mapping
                        SET usage_count = usage_count + 1,
                            last_used = CURRENT_TIMESTAMP
                        WHERE tarifni_broj = %s
                          AND product_code = %s
                          AND naziv_robe = %s
                    """, (tarifni_broj, product_code, naziv_robe))

        except Exception as e:
            logger.warning(f"⚠️  Greška pri ažuriranju usage_count: {e}")

    def learn_from_draft(self, invoice_lines: List[InvoiceLine]) -> int:
        """
        Nauči iz invoice lines sa popunjenim tarifnim brojevima.

        Args:
            invoice_lines: Lista fakturnih stavki

        Returns:
            Broj sačuvanih mappinga
        """
        saved_count = 0

        for line in invoice_lines:
            # Sačuvaj samo ako ima product_code ILI naziv_robe, I tarifni broj
            if line.tarifni_broj and (line.product_code or line.naziv_robe):
                success = self.save_mapping(
                    product_code=line.product_code or "",
                    naziv_robe=line.naziv_robe or "",
                    tarifni_broj=line.tarifni_broj,
                    zemlja_porijekla=line.zemlja_porijekla or "",
                    povlastica=line.povlastica or ""
                )

                if success:
                    saved_count += 1

        logger.info(f"📚 Naučeno {saved_count} mappinga iz draft-a")
        return saved_count

    def get_all_mappings(self) -> List[TariffMapping]:
        """Dobij sve mappinge iz baze."""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, usage_count
                    FROM catalogs.product_tariff_mapping
                    ORDER BY usage_count DESC, last_used DESC
                """)

                mappings = []
                for row in cursor.fetchall():
                    mappings.append(TariffMapping(
                        product_code=row["product_code"] or "",
                        naziv_robe=row["naziv_robe"] or "",
                        tarifni_broj=row["tarifni_broj"],
                        zemlja_porijekla=row["zemlja_porijekla"] or "",
                        povlastica=row["povlastica"] or "",
                        usage_count=row["usage_count"]
                    ))

        return mappings

    def clear_all_mappings(self) -> bool:
        """Obriši sve mappinge iz baze (za debugging)."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM catalogs.product_tariff_mapping")

            logger.info("🗑️  Svi mappinzi obrisani")
            return True

        except Exception as e:
            logger.error(f"❌ Greška pri brisanju mappinga: {e}")
            return False

    def import_from_xml_files(self, xml_paths: List[str]) -> Dict[str, int]:
        """
        Importuj mappinge iz ASYCUDA XML fajlova u bazu znanja.

        Args:
            xml_paths: Lista putanja do XML fajlova

        Returns:
            Dict sa statistikom
        """
        import xml.etree.ElementTree as ET

        logger.info(f"📚 Importujem mappinge iz {len(xml_paths)} XML fajlova...")

        stats = {
            'total_files': len(xml_paths),
            'total_items': 0,
            'imported': 0,
            'skipped': 0
        }

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                for xml_path in xml_paths:
                    try:
                        logger.debug(f"\n📁 Parsiram: {xml_path}")
                        tree = ET.parse(xml_path)
                        root = tree.getroot()
                        items = root.findall(".//Item")
                        logger.debug(f"   Pronađeno Item tagova: {len(items)}")

                        for item in items:
                            stats['total_items'] += 1

                            try:
                                tarif_elem = item.find(".//Tarification/HScode/Commodity_code")
                                tarif = tarif_elem.text.strip() if tarif_elem is not None and tarif_elem.text else ""

                                naziv_elem = item.find(".//Goods_description/Commercial_Description")
                                naziv = naziv_elem.text.strip() if naziv_elem is not None and naziv_elem.text else ""

                                zemlja_elem = item.find(".//Goods_description/Country_of_origin_code")
                                zemlja = zemlja_elem.text.strip() if zemlja_elem is not None and zemlja_elem.text else ""

                                pov_elem = item.find(".//Tarification/Preference_code")
                                povlastica = pov_elem.text.strip() if pov_elem is not None and pov_elem.text else ""

                                if not tarif or not re.match(r'^\d{8,10}$', tarif):
                                    stats['skipped'] += 1
                                    continue

                                if not naziv or len(naziv.strip()) < 3:
                                    stats['skipped'] += 1
                                    continue

                                naziv_clean = self._clean_product_name(naziv)
                                if self._is_noisy_name(naziv_clean):
                                    stats['skipped'] += 1
                                    continue

                                cursor.execute("""
                                    INSERT INTO catalogs.product_tariff_mapping
                                    (product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, usage_count)
                                    VALUES (%s, %s, %s, %s, %s, 1)
                                    ON CONFLICT (COALESCE(product_code, ''), COALESCE(naziv_robe, '')) DO NOTHING
                                """, ("", naziv_clean, tarif, zemlja or "", povlastica or ""))

                                if cursor.rowcount > 0:
                                    stats['imported'] += 1
                                else:
                                    stats['skipped'] += 1

                            except Exception as e:
                                logger.warning(f"⚠️  Greška pri parsiranju stavke: {e}")
                                stats['skipped'] += 1

                    except Exception as e:
                        logger.error(f"❌ Greška pri parsiranju {xml_path}: {e}")

        logger.info(f"✅ Import završen: {stats['imported']} mappinga uvezeno, {stats['skipped']} preskočeno")
        return stats

    def _clean_product_name(self, name: str) -> str:
        """Očisti naziv proizvoda od nepotrebnih fraza."""
        if not name:
            return ""

        clean = re.sub(r'\s+', ' ', name).strip()

        noise_patterns = [
            r'\s*po\s+fak\.?\s*$',
            r'\s*po\s+fakturi\.?\s*$',
            r'\s*-\s*po\s+fak\.?\s*$',
            r'\s*ostalo\s*$',
            r'\s*/\s*ostalo\s*/?$',
        ]

        for pattern in noise_patterns:
            clean = re.sub(pattern, '', clean, flags=re.IGNORECASE)

        return clean.strip()

    def _is_noisy_name(self, name: str) -> bool:
        """Provjeri da li je naziv previše generičan ili 'bučan'."""
        if not name or len(name) < 3:
            return True

        generic_words = ['ostalo', 'ostali', 'razno', 'drugo', '-', 'po fak']
        if name.lower() in generic_words:
            return True

        if re.match(r'^[^\w]+$', name):
            return True

        return False
