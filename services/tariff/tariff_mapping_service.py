# services/tariff_mapping_service.py

"""
Tariff Mapping Service

Automatsko mapiranje proizvoda na tarifne brojeve koristeći bazu znanja.
Omogućava:
- Auto-popunjavanje tarifnih brojeva na osnovu product_code ili naziva
- Istorijska provera dobavljača (XML sa carine) pre baze znanja
- Učenje iz prošlih uvoza
- Fuzzy matching za slične proizvode

📄 Detalji: memory/project_tariff_history_prediction.md
   scripts/CHANGES_2026-04-26.md
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

logger = logging.getLogger("deklarant_pro.tariff_mapping")


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
    tarifni_broj: str       # commodity_code — uvijek 8 cifara
    precision_1: str        # Precision_1 — '000' ili '100' za lijekove
    zemlja_porijekla: str
    povlastica: str
    usage_count: int
    similarity: float = 1.0  # Za fuzzy matching (0.0-1.0)


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
        min_similarity: float = 0.70,
        overwrite_existing: bool = False,
        supplier: str = ""
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

        effective_supplier = supplier or ""

        for line in invoice_lines:
            # Skip ako već ima tarifni broj i ne želimo overwrite
            if line.tarifni_broj and not overwrite_existing:
                continue

            # Dobavi ime dobavljača za ovu liniju
            line_supplier = effective_supplier or (line.exporter.name if line.exporter.name else "")

            mapping = None

            # ── 0. Prvo istorija dobavljača (XML fajlovi sa carine — najvalidniji) ──
            if line_supplier:
                try:
                    from services.agent.tariff.tariff_suggestion_service import HybridMatchingService
                    hybrid = HybridMatchingService()
                    hist_match = hybrid.find_hybrid_mapping(
                        product_code=line.product_code,
                        naziv_robe=line.naziv_robe,
                        supplier=line_supplier,
                        country=line.zemlja_porijekla,
                        min_confidence=0.75
                    )
                    if hist_match and hist_match.confidence >= 0.82:
                        mapping = hist_match.tariff_mapping
                        logger.debug(
                            f"  📚 Istorija [{line_supplier}]: stavka #{line.line_no} "
                            f"→ {mapping.tarifni_broj} (pouzdanost: {hist_match.confidence:.0%})"
                        )
                except Exception:
                    pass  # Silent — istorijski match nije kritičan

            # ── 1. Baza znanja (ako istorija nije dala rezultat) ──
            if mapping is None:
                mapping = self.find_mapping(
                    product_code=line.product_code,
                    naziv_robe=line.naziv_robe,
                    min_similarity=min_similarity,
                    zemlja_porijekla=line.zemlja_porijekla,
                    supplier=line_supplier
                )

            if mapping:
                # Pronađen mapping - popuni tarifni broj i precision_1
                line.tarifni_broj = mapping.tarifni_broj
                line.tariff_suffix = mapping.precision_1

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
                        line.country_confidence = "HIGH"
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

    def find_batch_by_product_codes(
        self, product_codes: List[str]
    ) -> Dict[str, "TariffMapping"]:
        """
        Batch lookup po product_code — jedan SQL umjesto N.

        Vraća dict {product_code_upper: TariffMapping} samo za tačne i prefix matcheve.
        Linije bez hita trebaju proći kroz find_mapping() za fuzzy/vote matching.
        """
        codes = [c.strip() for c in product_codes if c and c.strip()]
        if not codes:
            return {}

        result: Dict[str, TariffMapping] = {}
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT DISTINCT ON (input_code)
                               input_code,
                               product_code, naziv_robe, commodity_code,
                               precision_1, zemlja_porijekla, povlastica, usage_count,
                               match_type
                        FROM (
                            SELECT
                                unnest(%s::text[]) AS input_code,
                                m.product_code, m.naziv_robe, m.commodity_code,
                                m.precision_1, m.zemlja_porijekla, m.povlastica,
                                m.usage_count,
                                CASE WHEN m.product_code ILIKE unnest(%s::text[])
                                     THEN 0 ELSE 1 END AS match_type
                            FROM catalogs.product_tariff_mapping m
                            WHERE EXISTS (
                                SELECT 1 FROM unnest(%s::text[]) AS q
                                WHERE m.product_code ILIKE q
                                   OR q ILIKE m.product_code || '%%'
                            )
                        ) sub
                        ORDER BY input_code, match_type, usage_count DESC
                    """, (codes, codes, codes))

                    for row in cursor.fetchall():
                        result[row["input_code"].upper()] = TariffMapping(
                            product_code=row["product_code"],
                            naziv_robe=row["naziv_robe"],
                            tarifni_broj=row["commodity_code"],
                            precision_1=row["precision_1"],
                            zemlja_porijekla=row["zemlja_porijekla"] or "",
                            povlastica=row["povlastica"] or "",
                            usage_count=row["usage_count"],
                            similarity=1.0,
                        )
        except Exception as e:
            logger.debug(f"⚠️ find_batch_by_product_codes greška: {e}")

        return result

    def find_mapping(
        self,
        product_code: str,
        naziv_robe: str,
        min_similarity: float = 0.70,
        zemlja_porijekla: str = "",
        supplier: str = ""
    ) -> Optional[TariffMapping]:
        """
        Pronađi mapping za proizvod.

        Matching prioritet:
        1. Tačan match po product_code (similarity=1.0)
        2. Majority vote SAMO iz supplier zapisa (ako je supplier zadan)
        3. Majority vote iz supplier + HISTORIJA zapisa
        4. Majority vote iz svih zapisa (globalno)
        5. Fuzzy match (globalno, min_similarity=0.70)

        Zemlja porijekla se mečuje posebno unutar pobjedničkog commodity_code.
        """
        logger.debug(f"🔍 find_mapping: product_code='{product_code}', naziv='{naziv_robe[:40] if naziv_robe else ''}', supplier='{supplier}'")

        with get_db_connection() as conn:
            with conn.cursor() as cursor:

                # 1. Pokušaj tačan match ili prefix match po product_code
                # Prefix match: DB kod je prefiks traženog koda (npr. "26WG0703" ↔ "26WG0703-TAUPE")
                if product_code and product_code.strip():
                    cursor.execute("""
                        SELECT product_code, naziv_robe, commodity_code, precision_1,
                               zemlja_porijekla, povlastica, usage_count
                        FROM catalogs.product_tariff_mapping
                        WHERE product_code ILIKE %s
                           OR (%s ILIKE product_code || '%%' AND product_code != '')
                        ORDER BY
                            CASE WHEN product_code ILIKE %s THEN 0 ELSE 1 END,
                            usage_count DESC
                        LIMIT 1
                    """, (product_code.strip(), product_code.strip(), product_code.strip()))

                    row = cursor.fetchone()
                    if row:
                        return TariffMapping(
                            product_code=row["product_code"],
                            naziv_robe=row["naziv_robe"],
                            tarifni_broj=row["commodity_code"],
                            precision_1=row["precision_1"],
                            zemlja_porijekla=row["zemlja_porijekla"] or "",
                            povlastica=row["povlastica"] or "",
                            usage_count=row["usage_count"],
                            similarity=1.0
                        )

                # 2. Majority vote — u tri kruga po prioritetu
                if naziv_robe and naziv_robe.strip():
                    # Krug 1: samo zapisi ovog dobavljača
                    if supplier:
                        vote_result = self._majority_vote(
                            cursor, naziv_robe, zemlja_porijekla,
                            min_votes=2, min_ratio=0.60,
                            supplier_filter=[supplier]
                        )
                        if vote_result:
                            logger.debug(f"  🗳️  VOTE [{supplier}]: '{vote_result.naziv_robe[:40]}' → {vote_result.tarifni_broj}")
                            return vote_result

                    # Krug 2: dobavljač + verifikovana istorija
                    if supplier:
                        vote_result = self._majority_vote(
                            cursor, naziv_robe, zemlja_porijekla,
                            min_votes=3, min_ratio=0.65,
                            supplier_filter=[supplier, 'HISTORIJA']
                        )
                        if vote_result:
                            logger.debug(f"  🗳️  VOTE [{supplier}+HISTORIJA]: '{vote_result.naziv_robe[:40]}' → {vote_result.tarifni_broj}")
                            return vote_result

                    # Krug 3: globalno (svi dobavljači)
                    vote_result = self._majority_vote(
                        cursor, naziv_robe, zemlja_porijekla,
                        min_votes=3, min_ratio=0.65,
                        supplier_filter=[]
                    )
                    if vote_result:
                        logger.debug(f"  🗳️  VOTE [global]: '{vote_result.naziv_robe[:40]}' → {vote_result.tarifni_broj}")
                        return vote_result

                # 3. Fuzzy match po nazivu (OPTIMIZOVANO)
                if naziv_robe and naziv_robe.strip():
                    naziv_lower = naziv_robe.strip().lower()

                    # Ekstraktuj ključne riječi (prva 3 riječi, bez kratkih)
                    keywords = [w for w in naziv_lower.split()[:3] if len(w) > 2]

                    candidates = []

                    if keywords:
                        like_conditions = " OR ".join(["naziv_robe ILIKE %s" for _ in keywords])
                        like_params = [f"%{kw}%" for kw in keywords]

                        cursor.execute(f"""
                            SELECT product_code, naziv_robe, commodity_code, precision_1,
                                   zemlja_porijekla, povlastica, usage_count
                            FROM catalogs.product_tariff_mapping
                            WHERE ({like_conditions})
                            ORDER BY usage_count DESC
                            LIMIT 500
                        """, like_params)

                        candidates = cursor.fetchall()
                        logger.debug(f"  📋 ILIKE pretraga našla {len(candidates)} kandidata")

                    if not candidates:
                        cursor.execute("""
                            SELECT product_code, naziv_robe, commodity_code, precision_1,
                                   zemlja_porijekla, povlastica, usage_count
                            FROM catalogs.product_tariff_mapping
                            WHERE naziv_robe IS NOT NULL AND naziv_robe != ''
                            ORDER BY usage_count DESC
                            LIMIT 500
                        """)
                        candidates = cursor.fetchall()
                        logger.debug(f"  📋 Fallback top 500: {len(candidates)} kandidata")

                    best_match = None
                    best_similarity = 0.0

                    for row in candidates:
                        candidate_lower = row["naziv_robe"].lower()

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

                        if final_similarity > best_similarity and similarity >= min_similarity:
                            best_similarity = final_similarity
                            best_match = TariffMapping(
                                product_code=row["product_code"] or "",
                                naziv_robe=row["naziv_robe"],
                                tarifni_broj=row["commodity_code"],
                                precision_1=row["precision_1"],
                                zemlja_porijekla=row["zemlja_porijekla"] or "",
                                povlastica=row["povlastica"] or "",
                                usage_count=row["usage_count"],
                                similarity=final_similarity
                            )
                            if best_similarity >= 0.98:
                                break

                    if best_match:
                        logger.debug(f"  ✅ MATCH FOUND: '{best_match.naziv_robe[:50]}' → {best_match.tarifni_broj}/{best_match.precision_1} (similarity: {best_similarity:.2%})")
                    else:
                        logger.debug(f"  ❌ NO MATCH: best_similarity={best_similarity:.2%} < min_similarity={min_similarity:.2%}")

                    return best_match

        logger.debug(f"  ⚠️  NO MATCH: naziv_robe je prazan ili nema product_code")
        return None

    def _majority_vote(
        self,
        cursor,
        naziv_robe: str,
        zemlja_porijekla: str = "",
        min_votes: int = 3,
        min_ratio: float = 0.65,
        supplier_filter: List[str] = []
    ) -> Optional[TariffMapping]:
        """
        Majority vote matching — određuje commodity_code glasanjem po ključnim riječima.

        supplier_filter: lista suppliara koji se pretražuju ([] = svi)
        Zemlja porijekla se mečuje POSEBNO unutar pobjedničkog commodity_code.
        """
        from collections import Counter

        # Izvuci ključne riječi — prvih 2 značajne (bez kratkih, bez brojeva, bez generičkih)
        _generic = {'set', 'the', 'and', 'for', 'super', 'extra', 'plus', 'new',
                    'ostalo', 'ostali', 'drugi', 'druge', 'type', 'per'}
        words = [
            w.lower() for w in re.findall(r'\b[a-zA-ZšđčćžŠĐČĆŽ]{3,}\b', naziv_robe)
            if not w.isdigit() and w.lower() not in _generic
        ][:2]

        if not words:
            return None

        # Pretraži bazu sa ILIKE za svaku ključnu riječ
        like_conditions = " OR ".join(["naziv_robe ILIKE %s" for _ in words])
        like_params = [f"%{w}%" for w in words]

        # Dodaj supplier filter ako je zadan
        if supplier_filter:
            placeholders = ", ".join(["%s"] * len(supplier_filter))
            supplier_clause = f" AND supplier IN ({placeholders})"
            params = like_params + supplier_filter
        else:
            supplier_clause = ""
            params = like_params

        cursor.execute(f"""
            SELECT commodity_code, precision_1, zemlja_porijekla, povlastica, usage_count, naziv_robe
            FROM catalogs.product_tariff_mapping
            WHERE {like_conditions}{supplier_clause}
            ORDER BY usage_count DESC
            LIMIT 300
        """, params)

        rows = cursor.fetchall()
        if not rows:
            return None

        # Glasaj po commodity_code (ponderirano sa usage_count)
        # Zapisi koji sadrže direktni substring ulaza dobijaju 10× veći ponder
        naziv_lower = naziv_robe.strip().lower()
        input_words_set = set(w.lower() for w in words)

        votes: Counter = Counter()
        for row in rows:
            candidate_lower = row["naziv_robe"].lower()
            base_weight = max(1, row["usage_count"])

            # Substring boost: ako kandidat sadrži sve ulazne ključne riječi
            candidate_word_set = set(re.findall(r'\b\w+\b', candidate_lower))
            matching_words = input_words_set & candidate_word_set
            if len(matching_words) == len(input_words_set):
                # Svi ulazni keywords pronađeni u kandidatu → 10× boost
                weight = base_weight * 10
            elif len(matching_words) >= 2:
                # Barem 2 zajednička keyword → 3× boost
                weight = base_weight * 3
            else:
                weight = base_weight

            votes[row["commodity_code"]] += weight

        total_votes = sum(votes.values())
        dominant_code, dominant_count = votes.most_common(1)[0]
        ratio = dominant_count / total_votes

        logger.debug(f"  🗳️  Vote: '{' '.join(words)}' → {dominant_code} ({dominant_count}/{total_votes} = {ratio:.0%}), min_votes={min_votes}, min_ratio={min_ratio}")

        if dominant_count < min_votes or ratio < min_ratio:
            return None

        # Pobjednički kod je određen — sad mečuj zemlju posebno
        same_code = [r for r in rows if r["commodity_code"] == dominant_code]

        # Pronađi precision_1 — koristi najčešće korišćen
        best_record = max(same_code, key=lambda r: r["usage_count"])
        precision = best_record["precision_1"]

        # Mečuj zemlju porijekla posebno
        matched_zemlja = ""
        matched_povlastica = ""

        if zemlja_porijekla:
            zemlja_upper = zemlja_porijekla.upper()
            country_matches = [
                r for r in same_code
                if (r["zemlja_porijekla"] or "").upper() == zemlja_upper
            ]
            if country_matches:
                best_country = max(country_matches, key=lambda r: r["usage_count"])
                matched_zemlja = best_country["zemlja_porijekla"]
                matched_povlastica = best_country["povlastica"] or ""
                logger.debug(f"  🌍  Zemlja match: {matched_zemlja} → povlastica={matched_povlastica or 'N/A'}")
            else:
                # Ista tarifa, ali zemlja nije u bazi — zadrži iz PDF-a, bez povlastice
                matched_zemlja = zemlja_porijekla
                logger.debug(f"  🌍  Zemlja {zemlja_porijekla} nije u bazi za {dominant_code} — zadržana iz PDF-a")

        return TariffMapping(
            product_code="",
            naziv_robe=best_record["naziv_robe"],
            tarifni_broj=dominant_code,
            precision_1=precision,
            zemlja_porijekla=matched_zemlja,
            povlastica=matched_povlastica,
            usage_count=dominant_count,
            similarity=ratio
        )

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
                        SELECT product_code, naziv_robe, commodity_code, precision_1,
                               zemlja_porijekla, povlastica, usage_count
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
                            tarifni_broj=row["commodity_code"],
                            precision_1=row["precision_1"],
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
                            SELECT product_code, naziv_robe, commodity_code, precision_1,
                                   zemlja_porijekla, povlastica, usage_count
                            FROM catalogs.product_tariff_mapping
                            WHERE ({like_conditions})
                            ORDER BY usage_count DESC
                            LIMIT 500
                        """, like_params)

                        candidates = cursor.fetchall()

                    if not candidates:
                        cursor.execute("""
                            SELECT product_code, naziv_robe, commodity_code, precision_1,
                                   zemlja_porijekla, povlastica, usage_count
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
                                tarifni_broj=row["commodity_code"],
                                precision_1=row["precision_1"],
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
        povlastica: str = "",
        precision_1: str = "000"
    ) -> bool:
        """
        Sačuvaj novo mapiranje u bazu znanja.

        Args:
            product_code: Šifra proizvoda
            naziv_robe: Naziv proizvoda
            tarifni_broj: Commodity_code — 8 cifara
            zemlja_porijekla: Zemlja porijekla
            povlastica: Povlastica
            precision_1: Precision_1 (default '000', '100' za lijekove)

        Returns:
            True ako je uspješno sačuvano
        """
        try:
            # Commodity_code u mapping tabeli je uvijek 8-cifreni CN kod (baza za matching).
            # "Ex" TARIC kodovi (10 cifara, zadnje 2 ≠ 00) se čuvaju kao 8-cifreni CN
            # jer mapping služi za preporuku — finalni "ex" unos radi korisnik ručno.
            commodity = re.sub(r"\D", "", tarifni_broj.strip())[:8] if tarifni_broj else ""
            if not commodity or not commodity.isdigit() or len(commodity) != 8:
                logger.warning(f"⚠️  Nevalidan commodity_code: '{tarifni_broj}' — preskočeno")
                return False

            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO catalogs.product_tariff_mapping
                        (product_code, naziv_robe, commodity_code, precision_1, zemlja_porijekla, povlastica, usage_count)
                        VALUES (%s, %s, %s, %s, %s, %s, 1)
                        ON CONFLICT (product_code, naziv_robe, commodity_code) DO UPDATE SET
                            precision_1 = CASE
                                WHEN EXCLUDED.precision_1 != '000' THEN EXCLUDED.precision_1
                                ELSE catalogs.product_tariff_mapping.precision_1
                            END,
                            zemlja_porijekla = EXCLUDED.zemlja_porijekla,
                            povlastica = EXCLUDED.povlastica,
                            usage_count = catalogs.product_tariff_mapping.usage_count + 1,
                            last_used = CURRENT_TIMESTAMP
                    """, (product_code or "", naziv_robe or "", commodity, precision_1, zemlja_porijekla, povlastica))

            logger.info(f"✅ Sačuvano mapiranje: {product_code} → {commodity}/{precision_1}")
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
                        WHERE commodity_code = %s
                          AND product_code = %s
                          AND naziv_robe = %s
                    """, (tarifni_broj, product_code or "", naziv_robe))

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
                    SELECT product_code, naziv_robe, commodity_code, precision_1,
                           zemlja_porijekla, povlastica, usage_count
                    FROM catalogs.product_tariff_mapping
                    ORDER BY usage_count DESC, last_used DESC
                """)

                mappings = []
                for row in cursor.fetchall():
                    mappings.append(TariffMapping(
                        product_code=row["product_code"] or "",
                        naziv_robe=row["naziv_robe"] or "",
                        tarifni_broj=row["commodity_code"],
                        precision_1=row["precision_1"],
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
                        import os as _os
                        source_name = _os.path.basename(xml_path)
                        logger.debug(f"\n📁 Parsiram: {xml_path}")
                        tree = ET.parse(xml_path)
                        root = tree.getroot()
                        items = root.findall(".//Item")

                        # Izvuci ime izvoznika iz XML zaglavlja (prva linija)
                        exp_el = root.find(".//Traders/Exporter/Exporter_name")
                        exporter_name = ""
                        if exp_el is not None and exp_el.text:
                            exporter_name = exp_el.text.strip().split('\n')[0].strip()
                        logger.debug(f"   Pronađeno Item tagova: {len(items)}")

                        for item in items:
                            stats['total_items'] += 1

                            try:
                                tarif_elem = item.find(".//Tarification/HScode/Commodity_code")
                                tarif = tarif_elem.text.strip() if tarif_elem is not None and tarif_elem.text else ""

                                prec_elem = item.find(".//Tarification/HScode/Precision_1")
                                precision = prec_elem.text.strip() if prec_elem is not None and prec_elem.text else "000"

                                naziv_elem = item.find(".//Goods_description/Commercial_Description")
                                naziv = naziv_elem.text.strip() if naziv_elem is not None and naziv_elem.text else ""

                                zemlja_elem = item.find(".//Goods_description/Country_of_origin_code")
                                zemlja = zemlja_elem.text.strip() if zemlja_elem is not None and zemlja_elem.text else ""

                                pov_elem = item.find(".//Tarification/Preference_code")
                                povlastica = pov_elem.text.strip() if pov_elem is not None and pov_elem.text else ""

                                if not tarif or not re.match(r'^\d{8}$', tarif):
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
                                    (product_code, naziv_robe, commodity_code, precision_1, zemlja_porijekla, povlastica, usage_count, source, supplier)
                                    VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s)
                                    ON CONFLICT (product_code, naziv_robe, commodity_code) DO UPDATE SET
                                        precision_1 = CASE
                                            WHEN EXCLUDED.precision_1 != '000' THEN EXCLUDED.precision_1
                                            ELSE catalogs.product_tariff_mapping.precision_1
                                        END,
                                        source = CASE
                                            WHEN catalogs.product_tariff_mapping.source = '' THEN EXCLUDED.source
                                            ELSE catalogs.product_tariff_mapping.source
                                        END,
                                        supplier = CASE
                                            WHEN catalogs.product_tariff_mapping.supplier IS NULL
                                              OR catalogs.product_tariff_mapping.supplier = '' THEN EXCLUDED.supplier
                                            ELSE catalogs.product_tariff_mapping.supplier
                                        END,
                                        usage_count = catalogs.product_tariff_mapping.usage_count + 1,
                                        last_used = CURRENT_TIMESTAMP
                                """, ("", naziv_clean, tarif, precision, zemlja or "", povlastica or "", source_name, exporter_name))

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
