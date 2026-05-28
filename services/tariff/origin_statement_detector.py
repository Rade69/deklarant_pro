# services/origin_statement_detector.py

"""
Origin Statement Detector

Detektuje izjave o preferencijalnom poreklu u tekstovima PDF faktura
koristeći šablone iz PostgreSQL baze.

Podržava:
- Standardne izjave (bez broja ovlašćenja)
- Izjave ovlašćenog izvoznika (sa brojem carinskog ovlašćenja)
- Više jezika: srpski, engleski, nemački, hrvatski, makedonski, turski
"""

import re
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from database.db import get_db_connection

logger = logging.getLogger("deklarant_pro.origin_statement_detector")


@dataclass
class OriginStatementMatch:
    """Rezultat detekcije izjave o poreklu."""
    jezik: str
    tip_izjave: str  # 'standard' ili 'ovlaseni_izvoznik'
    origin_country: str  # Izvučena zemlja iz [origin] placeholder-a
    authorization_number: Optional[str] = None  # Broj ovlašćenja (ako postoji)
    full_text: str = ""  # Ceo tekst izjave
    confidence: float = 1.0  # Poverenje u match (0.0-1.0)
    text_position: int = 0  # Pozicija u tekstu (za sortiranje više izjava)
    item_range: Optional[Tuple[int, int]] = None  # Raspon stavki (npr. (1, 14) za stavke 1-14)


class OriginStatementDetector:
    """
    Detektor izjava o poreklu u PDF tekstovima.
    
    Usage:
        detector = OriginStatementDetector()
        result = detector.detect_in_text(pdf_text)
        
        if result:
            logger.debug(f"Zemlja: {result.origin_country}")
            logger.debug(f"Tip: {result.tip_izjave}")
            if result.authorization_number:
                logger.debug(f"Broj ovlašćenja: {result.authorization_number}")
    """
    
    # Fallback pattern-i ugrađeni u kod — aktivni uvijek, bez obzira na bazu
    _BUILTIN_PATTERNS = [
        {
            'id': 'builtin_srp_standard',
            'jezik': 'serbian',
            'tip_izjave': 'standard',
            'pattern': (
                r'\bIzvoznik\s+proizvoda\s+obuhva[ćc]enih\s+ovom\s+ispravom[\s,]*izjavljuje'
                r'\s+da\s+su,?\s+osim\s+ako\s+je\s+(?:to\s+)?druga[čc]ije\s+izri[čc]ito\s+navedeno,?'
                r'\s+ovi\s+proizvodi\s+(?P<origin>[\w\s,\/\-]+?)\s+preferencijalnog\s+porekla\.?'
            ),
        },
        {
            'id': 'builtin_eng_standard',
            'jezik': 'english',
            'tip_izjave': 'standard',
            'pattern': (
                r'\bThe\s+exporter\s+of\s+the\s+products\s+covered\s+by\s+this\s+document\s+declares\s+that,?'
                r'\s+except\s+where\s+otherwise\s+clearly\s+indicated,?\s+these\s+products\s+are\s+of'
                r'\s+(?P<origin>\w+)\s+preferential\s+origin\.?'
            ),
        },
        {
            'id': 'builtin_srp_ovlasceni',
            'jezik': 'serbian',
            'tip_izjave': 'ovlaseni_izvoznik',
            'pattern': (
                r'\bIzvoznik\s+proizvoda\s+obuhva[ćc]enih\s+ovom\s+ispravom'
                r'\s+\(Ovla[šs][ćc]eni\s+izvoznik[;,]?\s*(?:br\.?\s*(?P<broj>\S+))?\)'
                r'.*?ovi\s+proizvodi\s+(?P<origin>\w+)\s+preferencijalnog\s+porekla\.?'
            ),
        },
    ]

    # Class-level cache — DB se pita samo jednom po sesiji aplikacije
    _db_patterns_cache: Optional[List] = None
    _db_unavailable: bool = False  # True = DB nije dostupan, koristi samo builtin

    def __init__(self):
        # Učitaj iz DB samo ako još nije pokušano (ili je ranije uspjelo)
        if not OriginStatementDetector._db_unavailable and OriginStatementDetector._db_patterns_cache is None:
            OriginStatementDetector._db_patterns_cache = self._load_patterns_from_db()

        self._patterns = list(OriginStatementDetector._db_patterns_cache or [])

        # Uvijek dodaj ugrađene pattern-e (merged, bez duplikata po id)
        existing_ids = {p['id'] for p in self._patterns}
        for bp in self._BUILTIN_PATTERNS:
            if bp['id'] not in existing_ids:
                self._patterns.append(bp)
        logger.info(f"✅ OriginStatementDetector inicijalizovan sa {len(self._patterns)} pattern-a "
                    f"({'DB' if not OriginStatementDetector._db_unavailable else 'fallback'} + {len(self._BUILTIN_PATTERNS)} ugrađenih)")

    def _load_patterns_from_db(self) -> List[Dict]:
        """Učitaj regex pattern-e iz baze. Poziva se samo jednom po sesiji."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, jezik, tip_izjave, regex_pattern
                        FROM catalogs.izjave_o_poreklu
                        WHERE aktivan = TRUE
                          AND regex_pattern IS NOT NULL
                          AND regex_pattern != ''
                        ORDER BY sifra
                    """)
                    patterns = []
                    for row in cur.fetchall():
                        patterns.append({
                            'id': row['sifra'],
                            'jezik': row['jezik'],
                            'tip_izjave': row['tip_izjave'],
                            'pattern': row['regex_pattern'],
                        })
                    return patterns
        except Exception as e:
            logger.error(f"Greška pri učitavanju pattern-a iz baze: {e}")
            OriginStatementDetector._db_unavailable = True  # ne pokušavaj ponovo
            return []
    
    def detect_in_text(self, text: str) -> Optional[OriginStatementMatch]:
        """
        Detektuj izjavu o poreklu u tekstu.

        Args:
            text: Tekst PDF fakture

        Returns:
            OriginStatementMatch ako je nađena izjava, None inače
        """
        if not text:
            return None

        text = self._normalize_text(text)

        # Prvo traži izjave ovlašćenog izvoznika (specifičnije)
        approved_matches = self._try_patterns(text, 'ovlaseni_izvoznik')
        if approved_matches:
            return approved_matches[0]  # Vrati prvi match

        # Onda traži standardne izjave
        standard_matches = self._try_patterns(text, 'standard')
        if standard_matches:
            return standard_matches[0]  # Vrati prvi match

        return None

    def _normalize_text(self, text: str) -> str:
        """
        Normalizuj česte tipfelere u deklaracijama dobavljača.

        Npr. "preferncijalnog" (Srećko) → "preferencijalnog"
        """
        import re as _re
        # "preferencijalnog" ima varijante sa izostavljenim slovima
        text = _re.sub(r'\bprefer[a-z]{0,4}jalnog\b', 'preferencijalnog', text, flags=_re.IGNORECASE)
        return text

    def detect_all_in_text(self, text: str) -> List[OriginStatementMatch]:
        """
        Detektuj SVE izjave o poreklu u tekstu.

        Korisno za fakture koje imaju više izjava (npr. EU + Turska).

        Args:
            text: Tekst PDF fakture

        Returns:
            Lista OriginStatementMatch objekata (bez duplikata)
        """
        if not text:
            return []

        text = self._normalize_text(text)

        all_matches = []

        # Traži izjave ovlašćenog izvoznika
        approved_matches = self._try_patterns_all(text, 'ovlaseni_izvoznik')
        all_matches.extend(approved_matches)

        # Traži standardne izjave
        standard_matches = self._try_patterns_all(text, 'standard')
        all_matches.extend(standard_matches)

        # DEDUPLIKACIJA: Ako više pattern-a matchuje isti tekst, zadrži samo prvi
        seen_positions = set()
        unique_matches = []
        for match in all_matches:
            # Koristi text_position + origin_country kao ključ za deduplikaciju
            key = (match.text_position, match.origin_country)
            if key not in seen_positions:
                seen_positions.add(key)
                unique_matches.append(match)

        # Sortiraj po poziciji u tekstu
        unique_matches.sort(key=lambda m: m.text_position)

        logger.info(f"🔍 Detektovano {len(unique_matches)} jedinstvenih izjava o poreklu")
        for i, match in enumerate(unique_matches, 1):
            logger.info(f"   #{i}: {match.jezik} / {match.tip_izjave} / origin={match.origin_country} / range={match.item_range}")

        return unique_matches
    
    def _try_patterns(self, text: str, tip_izjave: str) -> List[OriginStatementMatch]:
        """
        Pokušaj da nađeš match za određeni tip izjave.
        
        Args:
            text: Tekst za pretragu
            tip_izjave: 'standard' ili 'ovlaseni_izvoznik'
        
        Returns:
            Lista OriginStatementMatch objekata
        """
        matches = []
        
        for pattern_data in self._patterns:
            if pattern_data['tip_izjave'] != tip_izjave:
                continue
            
            pattern = pattern_data['pattern']

            if not isinstance(pattern, str) or not pattern.strip():
                logger.warning(f"⚠️ Pattern '{pattern_data.get('id')}' nije string ili je prazan, preskačem")
                continue

            try:
                # Try with IGNORECASE, DOTALL, and MULTILINE flags
                # DOTALL: . matches newline
                # MULTILINE: ^ and $ match line boundaries
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                
                if match:
                    # Extract origin country
                    origin = match.group('origin') if 'origin' in match.groupdict() else ""
                    
                    # Extract authorization number if available
                    auth_number = None
                    if 'broj' in match.groupdict():
                        auth_number = match.group('broj')
                    elif pattern_data['tip_izjave'] == 'ovlaseni_izvoznik':
                        # Try to extract number from context
                        auth_number = self._extract_auth_number(text, match.start(), match.end())
                    
                    # Clean origin country
                    origin = self._clean_origin_country(origin)
                    
                    matches.append(OriginStatementMatch(
                        jezik=pattern_data['jezik'],
                        tip_izjave=pattern_data['tip_izjave'],
                        origin_country=origin,
                        authorization_number=auth_number,
                        full_text=match.group(0)[:200],  # Prvih 200 karaktera
                        confidence=0.95 if tip_izjave == 'ovlaseni_izvoznik' else 0.90
                    ))
                    
                    logger.debug(
                        f"✅ Nađena izjava: {pattern_data['jezik']} / {pattern_data['tip_izjave']} / "
                        f"origin={origin}"
                    )
                    
            except re.error as e:
                logger.warning(f"Greška u regex pattern-u {pattern_data['id']}: {e}")
                continue
        
        return matches

    def _try_patterns_all(self, text: str, tip_izjave: str) -> List[OriginStatementMatch]:
        """
        Pokušaj da nađeš SVE matcheve za određeni tip izjave.

        Za razliku od _try_patterns, ova metoda koristi finditer umjesto search
        da bi pronašla sve izjave u tekstu.

        Args:
            text: Tekst za pretragu
            tip_izjave: 'standard' ili 'ovlaseni_izvoznik'

        Returns:
            Lista OriginStatementMatch objekata
        """
        matches = []

        for pattern_data in self._patterns:
            if pattern_data['tip_izjave'] != tip_izjave:
                continue

            pattern = pattern_data['pattern']

            if not isinstance(pattern, str) or not pattern.strip():
                logger.warning(f"⚠️ Pattern '{pattern_data.get('id')}' nije string ili je prazan, preskačem")
                continue

            try:
                # Koristi finditer da nađe SVE matcheve
                for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE):
                    # Extract origin country
                    origin = match.group('origin') if 'origin' in match.groupdict() else ""

                    # Extract authorization number if available
                    auth_number = None
                    if 'broj' in match.groupdict():
                        auth_number = match.group('broj')
                    elif pattern_data['tip_izjave'] == 'ovlaseni_izvoznik':
                        auth_number = self._extract_auth_number(text, match.start(), match.end())

                    # Clean origin country
                    origin = self._clean_origin_country(origin)

                    # Extract item range from regex groups (start, end) ako postoje
                    item_range = None
                    if 'start' in match.groupdict() and 'end' in match.groupdict():
                        start_val = match.group('start')
                        end_val = match.group('end')
                        if start_val and end_val:
                            item_range = (int(start_val), int(end_val))
                            logger.debug(f"  📍 Item range iz regex-a: {item_range}")

                    matches.append(OriginStatementMatch(
                        jezik=pattern_data['jezik'],
                        tip_izjave=pattern_data['tip_izjave'],
                        origin_country=origin,
                        authorization_number=auth_number,
                        full_text=match.group(0)[:200],  # Prvih 200 karaktera
                        confidence=0.95 if tip_izjave == 'ovlaseni_izvoznik' else 0.90,
                        text_position=match.start(),
                        item_range=item_range
                    ))

                    logger.debug(
                        f"✅ Nađena izjava: {pattern_data['jezik']} / {pattern_data['tip_izjave']} / "
                        f"origin={origin} / pos={match.start()} / range={item_range}"
                    )

            except re.error as e:
                logger.warning(f"Greška u regex pattern-u {pattern_data['id']}: {e}")
                continue

        return matches
    
    def _extract_auth_number(self, text: str, match_start: int, match_end: int) -> Optional[str]:
        """
        Ekstraktuj broj ovlašćenja iz okoline match-a.
        
        Traži pattern-e kao:
        - "br. 12345"
        - "No 12345"
        - "Bewilligungs-Nr. 12345"
        """
        # Uzmi kontekst oko match-a (50 karaktera pre i posle)
        context_start = max(0, match_start - 50)
        context_end = min(len(text), match_end + 50)
        context = text[context_start:context_end]
        
        # Pattern-i za broj ovlašćenja
        auth_patterns = [
            r"br\.?\s*(\d+)",
            r"no\.?\s*(\d+)",
            r"nr\.?\s*(\d+)",
            r"bewilligungs[-\s]*nr\.?\s*(\d+)",
            r"ovlaš[ćc]enje\s*(\d+)",
            r"authorization\s*(\d+)",
        ]
        
        for pattern in auth_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_item_range(self, text: str, match_start: int, match_end: int) -> Optional[Tuple[int, int]]:
        """
        Ekstraktuj raspon stavki iz izjave o poreklu.

        Traži pattern-e kao:
        - "Stavke od rednog broja 1 do 14"
        - "Stavke 15 do 22"
        - "Items 1 to 14"
        - "stavka 23" (pojedinačna stavka)

        Args:
            text: Tekst fakture
            match_start: Pozicija početka izjave
            match_end: Pozicija kraja izjave

        Returns:
            Tuple(start, end) ili None ako nije pronađeno
        """
        # Uzmi kontekst oko match-a (150 karaktera prije i poslije)
        context_start = max(0, match_start - 150)
        context_end = min(len(text), match_end + 150)
        context = text[context_start:context_end]

        logger.debug(f"  📍 Context za item range: {context[:200]}...")

        # Pattern-i za raspon stavki
        range_patterns = [
            # "Stavke od rednog broja 1 do 14, kao i stavka 23"
            r"stavk[ei]\s+od\s+redn[oi]g?\s+broj[ae]?\s+(\d+)\s+(do|pa)\s+(\d+)",
            # "Stavke 15 do 22"
            r"stavk[ei]\s+(\d+)\s+(do|pa)\s+(\d+)",
            # "Items 1 to 14"
            r"items?\s+(\d+)\s+to\s+(\d+)",
            # "pozicije 1-14"
            r"pozicij[ae]\s+(\d+)\s*[-–]\s*(\d+)",
            # "stavka 23" (pojedinačna)
            r"stavk[ae]?\s+(\d+)(?!\s*(do|pa|,))",
        ]

        for pattern in range_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                start_item = int(match.group(1))
                end_item = int(match.group(3)) if match.lastindex and match.lastindex >= 3 else start_item
                logger.debug(f"  ✅ Nađen item range: ({start_item}, {end_item})")
                return (start_item, end_item)

        logger.debug(f"  ⚠️  Nije nađen item range u contextu")
        return None

    def _clean_origin_country(self, origin: str) -> str:
        """
        Očisti i normalizuj naziv zemlje.

        Primeri:
        - "Slovenian" → "SI"
        - "Serbian" → "RS"
        - "Croatian" → "HR"
        - "German" → "DE"
        - "Turskog" → "TR"
        - "TU" → "TR"
        """
        if not origin:
            return ""

        # Mapiranje naziva zemalja na ISO kodove
        country_map = {
            # English
            'serbian': 'RS',
            'slovenian': 'SI',
            'croatian': 'HR',
            'german': 'DE',
            'italian': 'IT',
            'french': 'FR',
            'spanish': 'ES',
            'portuguese': 'PT',
            'dutch': 'NL',
            'polish': 'PL',
            'czech': 'CZ',
            'slovak': 'SK',
            'hungarian': 'HU',
            'romanian': 'RO',
            'bulgarian': 'BG',
            'greek': 'GR',
            'austrian': 'AT',
            'belgian': 'BE',
            'luxembourgish': 'LU',
            'irish': 'IE',
            'danish': 'DK',
            'finnish': 'FI',
            'swedish': 'SE',
            'lithuanian': 'LT',
            'latvian': 'LV',
            'estonian': 'EE',
            'maltese': 'MT',
            'cypriot': 'CY',
            'european': 'EU',
            
            # Serbian/Croatian (nominativ i genitiv)
            'srpski': 'RS',
            'srpskog': 'RS',
            'srpske': 'RS',
            'slovenački': 'SI',
            'slovenačkog': 'SI',
            'hrvatski': 'HR',
            'hrvatskog': 'HR',
            'nemački': 'DE',
            'nemačkog': 'DE',
            'talijanski': 'IT',
            'talijanskog': 'IT',
            'francuski': 'FR',
            'francuskog': 'FR',
            'španski': 'ES',
            'španskog': 'ES',
            
            # German
            'serbisch': 'RS',
            'slowenisch': 'SI',
            'kroatisch': 'HR',
            'deutsch': 'DE',
            
            # Turkish
            'sırp': 'RS',
            'sloven': 'SI',
            'hırvat': 'HR',
            'alman': 'DE',
            'türk': 'TR',
            'turskog': 'TR',
            'turkish': 'TR',
            'tu': 'TR',
        }
        
        origin_lower = origin.lower().strip()
        origin_upper = origin.upper().strip()

        # Složeni EU zapisi (npr. "EU/ DE, DK, HR...") tretiraju se kao EU.
        if "EU/" in origin_upper or origin_upper.startswith("EU "):
            return "EU"
        
        # Direct map
        if origin_lower in country_map:
            return country_map[origin_lower]
        
        # Try to find partial match
        for key, value in country_map.items():
            if key in origin_lower or origin_lower in key:
                return value
        
        # Return as-is if not found (might be ISO code already)
        return origin.upper()[:2] if len(origin) >= 2 else ""
    
    def detect_origin_code(self, text: str) -> Optional[str]:
        """
        Brza detekcija samo zemlje porijekla (bez detalja).
        
        Args:
            text: Tekst PDF fakture
        
        Returns:
            ISO kod zemlje (npr. "SI", "DE") ili None
        """
        result = self.detect_in_text(text)
        return result.origin_country if result else None


# ============================================================
# USAGE EXAMPLE / TEST
# ============================================================

if __name__ == "__main__":
    detector = OriginStatementDetector()
    
    test_texts = [
        # Serbian standard
        "Izvoznik proizvoda obuhvaćenih ovom ispravom izjavljuje da su, "
        "osim ako je to drugačije izričito navedeno, ovi proizvodi Slovenian "
        "preferencijalnog porekla.",
        
        # English standard
        "The exporter of the products covered by this document declares that, "
        "except where otherwise clearly indicated, these products are of "
        "Serbian preferential origin.",
        
        # German approved exporter
        "Der Ausführer (Ermächtigter Ausführer; Bewilligungs-Nr. 12345) der Waren, "
        "auf die sich dieses Handelspapier bezieht, erklärt, dass diese Waren, "
        "soweit nicht anders angegeben, Croatian Präferenzursprungswaren sind.",
        
        # No statement
        "Faktura broj 123/2025. Roba: Termostati. Cena: 1000 EUR.",
    ]
    
    logger.debug("=" * 70)
    logger.debug("ORIGIN STATEMENT DETECTOR - TEST")
    logger.debug("=" * 70)
    
    for i, text in enumerate(test_texts, 1):
        logger.debug(f"\nTest {i}:")
        logger.debug(f"Text: {text[:80]}...")
        
        result = detector.detect_in_text(text)
        
        if result:
            logger.info(f"✅ MATCH: {result.jezik} / {result.tip_izjave}")
            logger.debug(f"   Origin: {result.origin_country}")
            if result.authorization_number:
                logger.debug(f"   Auth Number: {result.authorization_number}")
            logger.debug(f"   Confidence: {result.confidence:.2f}")
        else:
            logger.error("❌ NO MATCH")
