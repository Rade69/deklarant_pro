"""
Historical Learning Service

Analizira istorijske XML deklaracije i uči pattern-e za povlastice:
1. Koje povlastice se koriste za koje dobavljače
2. Koje zemlje porijekla su tipične za svakog dobavljača
3. Koje kombinacije (dobavljač + zemlja → povlastica) su najčešće

Koristi lxml za XML parsiranje. Sve javne metode imaju silent error handling
i nikad ne bacaju exception koji bi porušio ostatak aplikacije.

Javni API:
- enhance_preference_logic(country_code, exporter_name) — glavna funkcija
- get_historical_service() — singleton instanca
- HistoricalLearningServiceSafe — klasa
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("asycuda_pro.historical_learning")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SupplierProfile:
    """Profil dobavljača sa istorijskim podacima."""
    exporter_normalized: str
    total_declarations: int = 0
    total_items: int = 0
    countries: Dict[str, int] = None
    preferences: Dict[str, int] = None
    country_preference_map: Dict[str, Dict[str, int]] = None

    def __post_init__(self):
        if self.countries is None:
            self.countries = defaultdict(int)
        if self.preferences is None:
            self.preferences = defaultdict(int)
        if self.country_preference_map is None:
            self.country_preference_map = defaultdict(lambda: defaultdict(int))


@dataclass
class HistoricalPattern:
    """Istorijski pattern za kombinaciju dobavljač + zemlja."""
    exporter_normalized: str
    country_code: str
    preference_code: str
    count: int = 0
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Servis
# ---------------------------------------------------------------------------

class HistoricalLearningServiceSafe:
    """
    Servis za učenje iz istorijskih XML deklaracija.

    Sve metode su wrapped u try/except — greške su silent i ne utiču
    na ostatak aplikacije. Koristi cache da izbjegne višestruko čitanje
    iz baze i XML-ova za istog dobavljača.
    """

    def __init__(self, xml_folder: Optional[Path] = None):
        try:
            self.xml_folder = xml_folder or Path("/home/radovan/Desktop/asycuda_pro/docs/NOVA ASIKUDA")
            self.supplier_profiles: Dict[str, SupplierProfile] = {}
            self._cache_hits = 0
            self._cache_misses = 0
            self._initialized = True
            logger.debug("✅ HistoricalLearningServiceSafe inicijalizovan")
        except Exception as e:
            logger.debug(f"⚠️ Silent init error: {e}")
            self._initialized = False

    def is_available(self) -> bool:
        """Provjeri da li je servis dostupan."""
        return self._initialized

    # -----------------------------------------------------------------------
    # DB konekcija
    # -----------------------------------------------------------------------

    def get_db_connection(self):
        """Konekcija na bazu koristeći .env config."""
        import psycopg2
        env_path = Path(__file__).parent.parent.parent / ".env"
        db_config = {}
        if env_path.exists():
            for line in env_path.read_text().split('\n'):
                if '=' in line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    db_config[key.strip()] = val.strip()

        host = db_config.get('DB_HOST', '/var/run/postgresql')
        port = db_config.get('DB_PORT', '5432')
        dbname = db_config.get('DB_NAME', 'asycuda_pro')
        user = db_config.get('DB_USER', 'radovan')
        password = db_config.get('DB_PASSWORD', 'postgres')

        return psycopg2.connect(
            host=host, port=port, database=dbname, user=user, password=password
        )

    # -----------------------------------------------------------------------
    # Normalizacija
    # -----------------------------------------------------------------------

    def normalize_exporter_name(self, name: str) -> Optional[str]:
        """
        Normalizuje ime exportera za upoređivanje.

        Uklanja pravne sufikse (DOO, LTD...), višestruke razmake i
        specijalne karaktere. Vraća None ako je unos prazan.
        """
        try:
            if not name:
                return None

            name = name.upper().strip()

            prefixes_to_remove = [
                r'^TRGOVINSKA\s+DRUŠTVA?\s*',
                r'^PREDMUZEĆE\s+',
                r'^DRUŠTVO\s+SA\s+OGRANIČENOM\s+ODGOVORNOŠĆU\s*',
                r'^DOO\s*',
                r'^D\.\s*O\.\s*O\.?\s*',
                r'^D\s*O\s*O\s*',
                r'^\s*(DOO|LTD|LLC|AD|AD\s*$|A\s*D)\s*$',
                r'\s+(DOO|LTD|LLC|AD)\s*$',
            ]
            for pattern in prefixes_to_remove:
                name = re.sub(pattern, '', name, flags=re.IGNORECASE)

            name = re.sub(r'\s+\d{6,}.*$', '', name)
            name = re.sub(r'\s+', ' ', name).strip()

            return name if name else None

        except Exception:
            return None

    def _normalize_preference_code(self, pref_code: str) -> str:
        """Normalizuje kod povlastice u grupni kod (CEFTAT/CEFTAP → CEFTA)."""
        if not pref_code:
            return ""
        pref_code = pref_code.strip().upper()
        official_preferences = {
            "CEFTAT": "CEFTA",
            "CEFTAP": "CEFTA",
            "CEFTAR": "CEFTA",
            "EFTA1":  "EFTA1",   # Švajcarska+Lihtenštajn — čuvamo specifičnost
            "EFTA1R": "EFTA1",
            "EFTA2":  "EFTA2",   # Island
            "EFTA2R": "EFTA2",
            "EFTA3":  "EFTA3",   # Norveška
            "EFTA3R": "EFTA3",
            "EUP":    "EUP",
            "EUPR":   "EUP",
            "IRP":    "IRP",
            "TRP":    "TRP",
            "TRPR":   "TRP",
        }
        return official_preferences.get(pref_code, pref_code)

    def _denormalize_preference_code(self, normalized_code: str, context: str = "") -> str:
        """
        Vraća specifičan kod povlastice iz normalizovanog koda.

        Args:
            normalized_code: Normalizovani kod (npr. "CEFTA", "EUP")
            context: ISO kod zemlje (npr. "RS", "DE")
        """
        if not normalized_code:
            return ""
        normalized_code = normalized_code.strip().upper()
        preference_mapping = {
            "CEFTA":  "CEFTAR",
            "EFTA1":  "EFTA1R",
            "EFTA2":  "EFTA2R",
            "EFTA3":  "EFTA3R",
            "EUP":    "EUPR",
            "IRP":    "IRP",    # Nema revidirane verzije za Iran
            "TRP":    "TRPR",
        }
        return preference_mapping.get(normalized_code, normalized_code)

    # -----------------------------------------------------------------------
    # XML parsiranje
    # -----------------------------------------------------------------------

    def extract_items_from_xml(self, xml_path: Path) -> List[Dict]:
        """Ekstrahuje stavke (povlastica, zemlja, HS kod) iz ASYCUDA XML-a."""
        items = []
        try:
            from lxml import etree
            tree = etree.parse(str(xml_path))
            root = tree.getroot()

            for item_elem in root.xpath(".//*[local-name()='Item']"):
                item_data = {}

                pref_results = item_elem.xpath(".//*[local-name()='Preference_code']")
                if pref_results and pref_results[0].text:
                    raw_pref = pref_results[0].text.strip()
                    item_data["preference_code"] = raw_pref
                    item_data["preference_code_normalized"] = self._normalize_preference_code(raw_pref)
                else:
                    item_data["preference_code"] = ""
                    item_data["preference_code_normalized"] = ""

                country_results = item_elem.xpath(".//*[local-name()='Country_of_origin_code']")
                if country_results and country_results[0].text:
                    item_data["country_code"] = country_results[0].text.strip()
                else:
                    name_results = item_elem.xpath(".//*[local-name()='Country_of_origin_name']")
                    if name_results and name_results[0].text:
                        item_data["country_code"] = self._map_country_name_to_code(
                            name_results[0].text.strip().upper()
                        )
                    else:
                        item_data["country_code"] = ""

                hs_results = item_elem.xpath(
                    ".//*[local-name()='HScode']/*[local-name()='Commodity_code']"
                )
                item_data["hs_code"] = hs_results[0].text.strip() if (hs_results and hs_results[0].text) else ""

                if item_data["preference_code"] or item_data["country_code"]:
                    items.append(item_data)

        except Exception as e:
            logger.debug(f"Greška pri ekstrakciji stavki iz {xml_path.name}: {e}")

        return items

    def _map_country_name_to_code(self, country_name: str) -> str:
        """Mapira ime zemlje na ISO kod."""
        country_map = {
            "SRBIJA": "RS", "NEMAČKA": "DE", "ITALIJA": "IT", "KINA": "CN",
            "TURSKA": "TR", "SLOVENIJA": "SI", "HRVATSKA": "HR",
            "BOSNA I HERCEGOVINA": "BA", "CRNA GORA": "ME", "MAĐARSKA": "HU",
            "AUSTRIJA": "AT", "POLJSKA": "PL", "ČEŠKA": "CZ", "SLOVAČKA": "SK",
            "RUMUNIJA": "RO", "BUGARSKA": "BG", "GRČKA": "GR", "ŠPANLJA": "ES",
            "PORTUGAL": "PT", "FRANCUSKA": "FR", "BELGIJA": "BE", "HOLANDIJA": "NL",
            "DANSKA": "DK", "ŠVEDSKA": "SE", "FINSKA": "FI", "NORVEŠKA": "NO",
            "ŠVICARSKA": "CH", "UKRAJNA": "UA", "RUSIJA": "RU",
        }
        for name, code in country_map.items():
            if name in country_name.upper():
                return code
        return ""

    # -----------------------------------------------------------------------
    # Zvanični rječnici (povlastice i dokumenti)
    # -----------------------------------------------------------------------

    def get_official_preference_info(self, pref_code: str) -> Dict:
        """Vraća zvanične informacije o povlastici (Polje 36)."""
        pref_code = pref_code.strip().upper()
        official_info = {
            "CEFTAT": {
                "code": "CEFTAT",
                "description": "Povlastica za robu po Sporazumu CEFTA 2006 - Tranziciona pravila",
                "preference_document": "FTAT",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "CEFTAP": {
                "code": "CEFTAP",
                "description": "Povlastica za robu po Sporazumu CEFTA 2006 - PEM Konvencija",
                "preference_document": "FTAP",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "EFTA1": {
                "code": "EFTA1",
                "description": "Povlastica za robu iz Švajcarske i Lihtenštajna",
                "preference_document": "EFTA",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "EFTA2": {
                "code": "EFTA2",
                "description": "Povlastica za robu porijeklom iz Islanda",
                "preference_document": "EFTA",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "EFTA3": {
                "code": "EFTA3",
                "description": "Povlastica za robu porijeklom iz Norveške",
                "preference_document": "EFTA",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "EUP": {
                "code": "EUP",
                "description": "Povlastica za robu porijeklom iz Evropske zajednice",
                "preference_document": "EUP",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "IRP": {
                "code": "IRP",
                "description": "Povlastica za robu porijeklom iz Islamske Republike Iran",
                "preference_document": "IRP",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "TRP": {
                "code": "TRP",
                "description": "Povlastica za robu porijeklom iz Turske",
                "preference_document": "TRP",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
        }
        return official_info.get(pref_code, {
            "code": pref_code,
            "description": "Nepoznata povlastica",
            "preference_document": "",
            "origin_documents": [],
        })

    def get_origin_document_info(self, doc_code: str) -> Dict:
        """Vraća informacije o dokumentima o porijeklu (PE1, PE2, PE3...)."""
        doc_code = doc_code.strip().upper()
        origin_docs = {
            "PE1": {"code": "PE1", "description": "Uvjerenje o kretanju robe EUR.1"},
            "PE2": {"code": "PE2", "description": "Izjava o porijeklu"},
            "PE3": {"code": "PE3", "description": "Izjava o porijeklu ovlaštenog izvoznika"},
            "FTAT": {"code": "FTAT", "description": "Dokaz o porijeklu po CEFTA - Tranziciona pravila"},
            "FTAP": {"code": "FTAP", "description": "Dokaz o porijeklu po CEFTA - PEM Konvencija"},
            "EUP": {"code": "EUP", "description": "Dokaz o porijeklu iz Evropske unije"},
            "IRP": {"code": "IRP", "description": "Dokaz o porijeklu iz Irana"},
            "TRP": {"code": "TRP", "description": "Dokaz o porijeklu iz Turske"},
            "EFTA": {"code": "EFTA", "description": "Dokaz o porijeklu iz EFTA zemalja"},
        }
        return origin_docs.get(doc_code, {"code": doc_code, "description": "Nepoznati dokument"})

    # -----------------------------------------------------------------------
    # Učenje iz XML-ova
    # -----------------------------------------------------------------------

    def get_xml_files_for_exporter(self, exporter_name: str, limit: int = 20) -> List[Path]:
        """Pronalazi XML fajlove za određenog exportera iz baze."""
        xml_files = []
        try:
            from psycopg2.extras import RealDictCursor
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT xml_filepath
                        FROM catalogs.exporter_xml_index
                        WHERE exporter_normalized = %s
                        ORDER BY declaration_date DESC
                        LIMIT %s
                        """,
                        (exporter_name, limit),
                    )
                    for row in cursor.fetchall():
                        xml_path = Path(row['xml_filepath'])
                        if xml_path.exists():
                            xml_files.append(xml_path)
                        else:
                            rel_path = self.xml_folder / xml_path.name
                            if rel_path.exists():
                                xml_files.append(rel_path)
        except Exception as e:
            logger.debug(f"Greška pri dobavljanju XML fajlova za '{exporter_name}': {e}")
        return xml_files

    def learn_from_exporter(
        self, exporter_name: str, max_xml_files: int = 10
    ) -> Optional[SupplierProfile]:
        """Uči pattern-e iz XML fajlova određenog exportera."""
        logger.info(f"🔍 Učim pattern-e za exportera: {exporter_name}")

        xml_files = self.get_xml_files_for_exporter(exporter_name, limit=max_xml_files)
        if not xml_files:
            logger.warning(f"Nema XML fajlova za exportera '{exporter_name}'")
            return None

        profile = SupplierProfile(
            exporter_normalized=exporter_name,
            total_declarations=len(xml_files),
            total_items=0,
            countries=defaultdict(int),
            preferences=defaultdict(int),
            country_preference_map=defaultdict(lambda: defaultdict(int)),
        )
        profile.top_patterns = []

        for xml_path in xml_files:
            try:
                for item in self.extract_items_from_xml(xml_path):
                    profile.total_items += 1

                    country_code = item.get("country_code", "")
                    if country_code:
                        profile.countries[country_code] += 1

                    preference_code = item.get("preference_code", "")
                    if preference_code:
                        profile.preferences[preference_code] += 1

                    pref_normalized = item.get("preference_code_normalized", "")
                    if pref_normalized:
                        if not hasattr(profile, 'preferences_normalized'):
                            profile.preferences_normalized = defaultdict(int)
                        profile.preferences_normalized[pref_normalized] += 1

                    if country_code and pref_normalized:
                        profile.country_preference_map[country_code][pref_normalized] += 1

            except Exception as e:
                logger.debug(f"Greška pri analizi {xml_path.name}: {e}")

        self._calculate_top_patterns(profile)

        logger.info(
            f"✅ Naučeno {profile.total_items} stavki za '{exporter_name}': "
            f"{len(profile.countries)} zemalja, {len(profile.preferences)} povlastica"
        )
        return profile

    def _calculate_top_patterns(self, profile: SupplierProfile):
        """Izračunaj najčešće pattern-e za profil."""
        try:
            top_patterns = []
            for country_code, pref_counts in profile.country_preference_map.items():
                for pref_code, count in pref_counts.items():
                    total_for_country = sum(pref_counts.values())
                    confidence = count / total_for_country if total_for_country > 0 else 0
                    top_patterns.append({
                        'country': country_code,
                        'preference': pref_code,
                        'count': count,
                        'confidence': confidence,
                        'percentage': f"{(confidence * 100):.0f}%",
                    })
            top_patterns.sort(key=lambda x: x['count'], reverse=True)
            profile.top_patterns = top_patterns[:5]
        except Exception:
            profile.top_patterns = []

    def suggest_preference(
        self, exporter_name: str, country_code: str
    ) -> Tuple[Optional[str], float, str]:
        """
        Predlaže povlasticu za kombinaciju dobavljač + zemlja.

        Returns:
            (preference_code, confidence, explanation)
        """
        exporter_norm = self.normalize_exporter_name(exporter_name)
        if not exporter_norm:
            return None, 0.0, "Nije moguće normalizovati ime exportera"

        if exporter_norm in self.supplier_profiles:
            profile = self.supplier_profiles[exporter_norm]
        else:
            profile = self.learn_from_exporter(exporter_norm)
            if not profile:
                return None, 0.0, f"Nema istorijskih podataka za exportera '{exporter_norm}'"
            self.supplier_profiles[exporter_norm] = profile

        if country_code in profile.country_preference_map:
            pref_counts = profile.country_preference_map[country_code]
            if pref_counts:
                pref_normalized, count = max(pref_counts.items(), key=lambda x: x[1])
                pref_code = self._denormalize_preference_code(pref_normalized, country_code)
                total_for_country = sum(pref_counts.values())
                confidence = count / total_for_country
                explanation = (
                    f"Predlažem '{pref_code}' jer {exporter_norm} koristi ovu povlasticu "
                    f"{count} od {total_for_country} puta ({confidence:.0%}) za robu iz {country_code}."
                )
                return pref_code, confidence, explanation

        if hasattr(profile, 'preferences_normalized') and profile.preferences_normalized:
            pref_normalized, total_count = max(
                profile.preferences_normalized.items(), key=lambda x: x[1]
            )
            total_all = sum(profile.preferences_normalized.values())
            confidence = total_count / total_all if total_all > 0 else 0.5
            pref_code = self._denormalize_preference_code(pref_normalized, country_code)
            explanation = (
                f"Predlažem '{pref_code}' jer {exporter_norm} najčešće koristi ovu vrstu povlastice "
                f"({total_count} od {total_all} puta, {confidence:.0%}). "
                f"Nema specifičnih podataka za zemlju {country_code}."
            )
            return pref_code, confidence, explanation

        if profile.preferences:
            pref_code, total_count = max(profile.preferences.items(), key=lambda x: x[1])
            total_all = sum(profile.preferences.values())
            confidence = total_count / total_all if total_all > 0 else 0.5
            explanation = (
                f"Predlažem '{pref_code}' jer {exporter_norm} najčešće koristi ovu povlasticu "
                f"({total_count} od {total_all} puta, {confidence:.0%}). "
                f"Nema specifičnih podataka za zemlju {country_code}."
            )
            return pref_code, confidence, explanation

        return None, 0.0, f"Nema istorijskih podataka za kombinaciju {exporter_norm} + {country_code}"

    def batch_learn_top_exporters(self, limit: int = 20) -> Dict[str, SupplierProfile]:
        """Uči pattern-e za top N exportera."""
        logger.info(f"🔍 Počinjem batch učenje za top {limit} exportera")
        try:
            from psycopg2.extras import RealDictCursor
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT exporter_normalized, COUNT(*) as xml_count
                        FROM catalogs.exporter_xml_index
                        GROUP BY exporter_normalized
                        ORDER BY xml_count DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    for row in cursor.fetchall():
                        exporter_norm = row['exporter_normalized']
                        logger.info(f"  Učim {exporter_norm} ({row['xml_count']} XML-ova)")
                        profile = self.learn_from_exporter(exporter_norm, max_xml_files=10)
                        if profile:
                            self.supplier_profiles[exporter_norm] = profile
        except Exception as e:
            logger.error(f"Greška pri batch učenju: {e}")
        logger.info(f"✅ Batch učenje završeno. Naučeno {len(self.supplier_profiles)} profila.")
        return self.supplier_profiles

    # -----------------------------------------------------------------------
    # Safe (silent) API — koristi se izvana
    # -----------------------------------------------------------------------

    def get_preference_safe(self, exporter_name: str, country_code: str) -> Optional[str]:
        """
        Sigurno dobavi povlasticu iz istorije. Nikad ne baca exception.
        """
        try:
            if not self.is_available():
                return None

            exporter_norm = self.normalize_exporter_name(exporter_name)
            if not exporter_norm:
                return None

            country_code = country_code.strip().upper()
            if not country_code:
                return None

            profile = self._get_profile_safe(exporter_norm)
            if not profile:
                return None

            if country_code in profile.country_preference_map:
                pref_counts = profile.country_preference_map[country_code]
                if pref_counts:
                    pref_code, _ = max(pref_counts.items(), key=lambda x: x[1])
                    return self._denormalize_preference_code(pref_code, country_code)

            if profile.preferences:
                pref_code, _ = max(profile.preferences.items(), key=lambda x: x[1])
                return self._denormalize_preference_code(pref_code, country_code)

            return None

        except Exception:
            return None

    def _get_profile_safe(self, exporter_norm: str) -> Optional[SupplierProfile]:
        """Sigurno dobavi profil exportera sa caching-om."""
        try:
            if exporter_norm in self.supplier_profiles:
                self._cache_hits += 1
                logger.debug(f"✅ Cache hit za '{exporter_norm}'")
                return self.supplier_profiles[exporter_norm]

            self._cache_misses += 1
            logger.debug(f"🔍 Cache miss za '{exporter_norm}', učenje iz baze...")

            profile = self._learn_from_database_safe(exporter_norm)
            if profile:
                self.supplier_profiles[exporter_norm] = profile
                logger.debug(f"✅ Naučen profil za '{exporter_norm}': {profile.total_items} stavki")
            else:
                logger.debug(f"ℹ️ Nema istorijskih podataka za '{exporter_norm}'")

            return profile

        except Exception as e:
            logger.debug(f"⚠️ Silent error u _get_profile_safe za '{exporter_norm}': {e}")
            return None

    def _learn_from_database_safe(self, exporter_norm: str) -> Optional[SupplierProfile]:
        """Sigurno uči profil iz XML-ova (silent error handling)."""
        try:
            return self.learn_from_exporter(exporter_norm, max_xml_files=10)
        except Exception as e:
            logger.debug(f"⚠️ Silent error pri učenju za '{exporter_norm}': {e}")
            return None

    def enhance_existing_preference(
        self, country_code: str, exporter_name: str = ""
    ) -> str:
        """Poboljšaj logiku povlastica bez breaking changes."""
        historical_pref = self.get_preference_safe(exporter_name, country_code)
        if historical_pref:
            return historical_pref
        return self._hardcoded_preference_fallback(country_code)

    def preload_top_exporters(self, limit: int = 20) -> int:
        """Preload top exportera u cache (batch učenje)."""
        try:
            from database.db import get_db_connection
            from psycopg2.extras import RealDictCursor

            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT exporter_normalized, COUNT(*) as declaration_count
                        FROM catalogs.exporter_xml_index
                        GROUP BY exporter_normalized
                        ORDER BY declaration_count DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    rows = cursor.fetchall()
                    if not rows:
                        return 0

            loaded_count = 0
            logger.debug(f"🔍 Preloading {len(rows)} top exportera...")
            for row in rows:
                exporter_norm = row['exporter_normalized']
                if exporter_norm not in self.supplier_profiles:
                    try:
                        profile = self.learn_from_exporter(exporter_norm, max_xml_files=5)
                        if profile and profile.total_items > 0:
                            self.supplier_profiles[exporter_norm] = profile
                            loaded_count += 1
                            logger.debug(f"  ✅ Preloaded '{exporter_norm}': {profile.total_items} stavki")
                    except Exception as e:
                        logger.debug(f"  ⚠️ Error preloading '{exporter_norm}': {e}")

            logger.info(f"✅ Preloaded {loaded_count} top exportera u cache")
            return loaded_count

        except Exception as e:
            logger.debug(f"⚠️ Silent error u preload_top_exporters: {e}")
            return 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """Vrati statistiku cache-a."""
        total = self._cache_hits + self._cache_misses
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'cache_size': len(self.supplier_profiles),
            'hit_ratio': self._cache_hits / total if total > 0 else 0,
            'profiles': list(self.supplier_profiles.keys())[:10],
        }

    def _hardcoded_preference_fallback(self, country_code: str) -> str:
        """
        Hardcoded fallback — identičan postojećoj logici u EUR1QuickDialog.
        Osigurava 100% backward compatibility.
        """
        country_upper = country_code.upper()
        eu_countries = {
            'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
            'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
            'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK',
        }
        cefta_countries = {'RS', 'BA', 'ME', 'MK', 'AL', 'XK', 'MD'}

        if country_upper in eu_countries:
            return 'EUPR'
        elif country_upper in cefta_countries:
            return 'CEFTAR'
        elif country_upper == 'TR':
            return 'TRPR'
        elif country_upper == 'IR':
            return 'IRP'
        elif country_upper in {'CH', 'LI'}:
            return 'EFTA1R'
        elif country_upper == 'IS':
            return 'EFTA2R'
        elif country_upper == 'NO':
            return 'EFTA3R'
        return ''


# ---------------------------------------------------------------------------
# Globalni singleton i javne funkcije
# ---------------------------------------------------------------------------

_historical_service_instance = None


def get_historical_service() -> HistoricalLearningServiceSafe:
    """Dobavi globalnu instancu HistoricalLearningServiceSafe."""
    global _historical_service_instance
    if _historical_service_instance is None:
        _historical_service_instance = HistoricalLearningServiceSafe()
    return _historical_service_instance


def enhance_preference_logic(country_code: str, exporter_name: str = "") -> str:
    """
    Glavna funkcija za predlaganje povlastice.

    Pravila:
    1. Ako znamo exportera → koristi istorijsko učenje
    2. Ako ne znamo exportera → koristi hardcoded pravila
    3. Ako istorijsko učenje ne radi → silent fallback
    """
    try:
        service = get_historical_service()
        if exporter_name and exporter_name.strip():
            historical_pref = service.get_preference_safe(exporter_name, country_code)
            if historical_pref:
                return historical_pref
        return service._hardcoded_preference_fallback(country_code)
    except Exception:
        service = HistoricalLearningServiceSafe()
        return service._hardcoded_preference_fallback(country_code)


# Backward compatibility alias
HistoricalLearningService = HistoricalLearningServiceSafe
