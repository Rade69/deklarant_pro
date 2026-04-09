"""
Historical Learning Service v2

Koristi postojeći exporter_xml_indexer za parsiranje XML-ova i dodaje funkcionalnost
za učenje pattern-a o povlasticama i zemljama porijekla.

Glavne funkcionalnosti:
1. Analizira XML-ove i uči pattern-e: dobavljač → zemlja → povlastica
2. Predlaže povlastice na osnovu historije
3. Sačuva naučene profile u bazu
4. Integrira se sa postojećim TariffMappingService
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Set
from collections import defaultdict
import re

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("asycuda_pro.historical_learning")


@dataclass
class HistoricalPattern:
    """Jedan pattern naučen iz historije."""
    exporter_normalized: str
    country_code: str  # ISO kod zemlje (npr. "DE", "RS", "CN")
    preference_code: str  # Povlastica (npr. "EUP", "CEFTAT", "TRP")
    count: int  # Koliko puta se pojavila ova kombinacija
    last_used: datetime  # Kada je poslednji put korištena
    confidence: float  # Pouzdanost (count / total za ovog exportera)


@dataclass
class SupplierProfile:
    """Profil dobavljača naučen iz historije."""
    exporter_normalized: str
    total_declarations: int  # Ukupno deklaracija za ovog dobavljača
    total_items: int  # Ukupno stavki
    
    # Zemlje porijekla koje koristi
    countries: Dict[str, int]  # country_code → count
    
    # Povlastice koje koristi
    preferences: Dict[str, int]  # preference_code → count
    
    # Kombinacije zemlja → povlastica
    country_preference_map: Dict[str, Dict[str, int]]  # country_code → {preference_code → count}
    
    # Najčešće kombinacije
    top_patterns: List[HistoricalPattern]


class HistoricalLearningService:
    """Servis za učenje iz historijskih XML deklaracija."""
    
    def __init__(self):
        self.xml_folder = Path(__file__).parent.parent.parent / "docs" / "NOVA ASIKUDA"
        self.supplier_profiles: Dict[str, SupplierProfile] = {}
        self.patterns: List[HistoricalPattern] = []
        
    def get_db_connection(self):
        """Konekcija na bazu koristeći .env config."""
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
        
        if host.startswith('/'):
            return psycopg2.connect(host=host, port=port, database=dbname, user=user, password=password)
        else:
            return psycopg2.connect(host=host, port=port, database=dbname, user=user, password=password)
    
    def normalize_exporter_name(self, name: str) -> str:
        """
        Normalizuje ime exportera za upoređivanje.
        Kopirano iz exporter_xml_indexer.py za konzistentnost.
        """
        if not name:
            return ""
        
        # Uppercase i strip
        name = name.upper().strip()
        
        # Ukloni prefikse koji se ponavljaju
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
        
        # Ukloni brojeve na kraju (JMBG, PIB, etc.)
        name = re.sub(r'\s+\d{6,}.*$', '', name)
        
        # Collapse whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    def extract_items_from_xml_simple(self, xml_path: Path) -> List[Dict]:
        """
        Pojednostavljena verzija za ekstrakciju stavki iz XML-a.
        Koristi iter() da pronađe sve Preference_code i Country_of_origin_code elemente.
        """
        items = []
        try:
            tree = ET.parse(str(xml_path))
            root = tree.getroot()
            
            # Pronađi sve Preference_code elemente
            pref_elements = list(root.iter("Preference_code"))
            
            for pref_elem in pref_elements:
                item_data = {}
                
                # Povlastica
                if pref_elem.text:
                    item_data["preference_code"] = pref_elem.text.strip()
                else:
                    item_data["preference_code"] = ""
                
                # Pronađi najbliži Country_of_origin_code
                country_code = ""
                country_name = ""
                
                # Traži u parent hijerarhiji
                parent = pref_elem
                for _ in range(10):  # Ograniči dubinu pretrage
                    # Pronađi Country_of_origin_code u ovom elementu
                    country_elem = parent.find(".//Country_of_origin_code")
                    if country_elem is not None and country_elem.text:
                        country_code = country_elem.text.strip()
                        break
                    
                    # Pronađi Country_of_origin_name
                    country_name_elem = parent.find(".//Country_of_origin_name")
                    if country_name_elem is not None and country_name_elem.text:
                        country_name = country_name_elem.text.strip()
                        # Pokušaj mapirati na ISO kod
                        country_code = self._map_country_name_to_code(country_name)
                        break
                    
                    # Idi na parent
                    parent = parent.getparent()
                    if parent is None:
                        break
                
                item_data["country_code"] = country_code
                item_data["country_name"] = country_name
                
                # Pronađi HS code
                hs_code = ""
                parent = pref_elem
                for _ in range(10):
                    hs_elem = parent.find(".//HScode/Code")
                    if hs_elem is not None and hs_elem.text:
                        hs_code = hs_elem.text.strip()
                        break
                    parent = parent.getparent()
                    if parent is None:
                        break
                
                item_data["hs_code"] = hs_code
                
                # Dodaj samo ako ima bar neke podatke
                if item_data["preference_code"] or item_data["country_code"]:
                    items.append(item_data)
            
            return items
            
        except Exception as e:
            logger.debug(f"Greška pri ekstrakciji stavki iz {xml_path.name}: {e}")
            return []
    
    def _map_country_name_to_code(self, country_name: str) -> str:
        """Mapira ime zemlje na ISO kod."""
        # Najčešći slučajevi
        country_map = {
            "SRBIJA": "RS",
            "NEMAČKA": "DE",
            "ITALIJA": "IT",
            "KINA": "CN",
            "TURSKA": "TR",
            "SLOVENIJA": "SI",
            "HRVATSKA": "HR",
            "BOSNA I HERCEGOVINA": "BA",
            "CRNA GORA": "ME",
            "MAĐARSKA": "HU",
            "AUSTRIJA": "AT",
            "POLJSKA": "PL",
            "ČEŠKA": "CZ",
            "SLOVAČKA": "SK",
            "RUMUNIJA": "RO",
            "BUGARSKA": "BG",
            "GRČKA": "GR",
            "ŠPANLJA": "ES",
            "PORTUGAL": "PT",
            "FRANCUSKA": "FR",
            "BELGIJA": "BE",
            "HOLANDIJA": "NL",
            "DANSKA": "DK",
            "ŠVEDSKA": "SE",
            "FINSKA": "FI",
            "NORVEŠKA": "NO",
            "ŠVICARSKA": "CH",
            "UKRAJINA": "UA",
            "RUSIJA": "RU",
        }
        
        country_name_upper = country_name.upper()
        for name, code in country_map.items():
            if name in country_name_upper:
                return code
        
        # Ako nije pronađeno, vrati prazan string
        return ""
    
    def get_xml_files_for_exporter(self, exporter_name: str, limit: int = 50) -> List[Path]:
        """
        Pronalazi XML fajlove za određenog exportera koristeći bazu exporter_xml_index.
        
        Args:
            exporter_name: Normalizovano ime exportera
            limit: Maksimalan broj XML-ova
        
        Returns:
            Lista Path objekata do XML fajlova
        """
        xml_files = []
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Pronađi XML fajlove za ovog exportera
                    query = """
                    SELECT xml_filepath 
                    FROM catalogs.exporter_xml_index 
                    WHERE exporter_normalized = %s
                    ORDER BY declaration_date DESC
                    LIMIT %s
                    """
                    cursor.execute(query, (exporter_name, limit))
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        xml_path = Path(row['xml_filepath'])
                        if xml_path.exists():
                            xml_files.append(xml_path)
                        else:
                            # Pokušaj relativnu putanju
                            rel_path = self.xml_folder / xml_path.name
                            if rel_path.exists():
                                xml_files.append(rel_path)
            
            logger.info(f"Pronađeno {len(xml_files)} XML fajlova za exportera '{exporter_name}'")
            return xml_files
            
        except Exception as e:
            logger.error(f"Greška pri dobavljanju XML fajlova za '{exporter_name}': {e}")
            return []
    
    def learn_from_exporter(self, exporter_name: str, max_xml_files: int = 20) -> Optional[SupplierProfile]:
        """
        Uči pattern-e iz XML fajlova određenog exportera.
        
        Args:
            exporter_name: Normalizovano ime exportera
            max_xml_files: Maksimalan broj XML-ova za analizu
        
        Returns:
            SupplierProfile ako je uspješno naučeno, None inače
        """
        logger.info(f"🔍 Učim pattern-e za exportera: {exporter_name}")
        
        # Pronađi XML fajlove za ovog exportera
        xml_files = self.get_xml_files_for_exporter(exporter_name, limit=max_xml_files)
        if not xml_files:
            logger.warning(f"Nema XML fajlova za exportera '{exporter_name}'")
            return None
        
        # Inicijaliziraj profil
        profile = SupplierProfile(
            exporter_normalized=exporter_name,
            total_declarations=len(xml_files),
            total_items=0,
            countries=defaultdict(int),
            preferences=defaultdict(int),
            country_preference_map=defaultdict(lambda: defaultdict(int)),
            top_patterns=[]
        )
        
        # Analiziraj svaki XML fajl
        for xml_path in xml_files:
            try:
                # Ekstrahuj stavke iz XML-a
                items = self.extract_items_from_xml_simple(xml_path)
                
                for item in items:
                    profile.total_items += 1
                    
                    # Zemlja porijekla
                    country_code = item.get("country_code", "")
                    if country_code:
                        profile.countries[country_code] += 1
                    
                    # Povlastica
                    preference_code = item.get("preference_code", "")
                    if preference_code:
                        profile.preferences[preference_code] += 1
                    
                    # Kombinacija zemlja → povlastica
                    if country_code and preference_code:
                        profile.country_preference_map[country_code][preference_code] += 1
                
            except Exception as e:
                logger.debug(f"Greška pri analizi {xml_path.name}: {e}")
                continue
        
        # Izračunaj najčešće kombinacije
        self._calculate_top_patterns(profile)
        
        logger.info(f"✅ Naučeno {profile.total_items} stavki za '{exporter_name}': "
                   f"{len(profile.countries)} zemalja, {len(profile.preferences)} povlastica")
        
        return profile
    
    def _calculate_top_patterns(self, profile: SupplierProfile):
        """Izračunava najčešće pattern-e za profil dobavljača."""
        patterns = []
        
        for country_code, pref_counts in profile.country_preference_map.items():
            for pref_code, count in pref_counts.items():
                # Izračunaj pouzdanost
                total_for_country = sum(pref_counts.values())
                confidence = count / total_for_country if total_for_country > 0 else 0
                
                pattern = HistoricalPattern(
                    exporter_normalized=profile.exporter_normalized,
                    country_code=country_code,
                    preference_code=pref_code,
                    count=count,
                    last_used=datetime.now(),
                    confidence=confidence
                )
                patterns.append(pattern)
        
        # Sortiraj po count (najčešći prvi)
        patterns.sort(key=lambda x: x.count, reverse=True)
        
        # Ograniči na top 10 pattern-a
        profile.top_patterns = patterns[:10]
    
    def suggest_preference(self, exporter_name: str, country_code: str) -> Tuple[Optional[str], float, str]:
        """
        Predlaže povlasticu za kombinaciju dobavljač + zemlja na osnovu historije.
        
        Args:
            exporter_name: Normalizovano ime exportera
            country_code: ISO kod zemlje porijekla
        
        Returns:
            Tuple (preference_code, confidence, explanation)
        """
        # Normalizuj ime exportera
        exporter_norm = self.normalize_exporter_name(exporter_name)
        if not exporter_norm:
            return None, 0.0, "Nije moguće normalizovati ime exportera"
        
        # Ako već imamo profil za ovog exportera, koristi ga
        if exporter_norm in self.supplier_profiles:
            profile = self.supplier_profiles[exporter_norm]
        else:
            # Uči pattern-e za ovog exportera
            profile = self.learn_from_exporter(exporter_norm)
            if not profile:
                return None, 0.0, f"Nema historijskih podataka za exportera '{exporter_norm}'"
            
            # Sačuvaj profil za buduće upite
            self.supplier_profiles[exporter_norm] = profile
        
        # Pronađi pattern za ovu zemlju
        if country_code in profile.country_preference_map:
            pref_counts = profile.country_preference_map[country_code]
            
            if pref_counts:
                # Pronađi najčešću povlasticu za ovu zemlju
                most_common_pref = max(pref_counts.items(), key=lambda x: x[1])
                pref_code, count = most_common_pref
                
                # Izračunaj pouzdanost
                total_for_country = sum(pref_counts.values())
                confidence = count / total_for_country
                
                # Generiši objašnjenje
                explanation = (
                    f"Predlažem '{pref_code}' jer {exporter_norm} koristi ovu povlasticu "
                    f"{count} od {total_for_country} puta ({confidence:.0%}) za robu iz {country_code}."
                )
                
                return pref_code, confidence, explanation
        
        # Ako nema specifičnog pattern-a za ovu zemlju, predloži najčešću povlasticu uopšte
        if profile.preferences:
            most_common_overall = max(profile.preferences.items(), key=lambda x: x[1])
            pref_code, total_count = most_common_overall
            
            total_all = sum(profile.preferences.values())
            confidence = total_count / total_all if total_all > 0 else 0.5
            
            explanation = (
                f"Predlažem '{pref_code}' jer {exporter_norm} najčešće koristi ovu povlasticu "
                f"({total_count} od {total_all} puta, {confidence:.0%}). "
                f"Nema specifičnih podataka za zemlju {country_code}."
            )
            
            return pref_code, confidence, explanation
        
        # Nema podataka uopšte
        return None, 0.0, f"Nema historijskih podataka za kombinaciju {exporter_norm} + {country_code}"
    
    def get_supplier_statistics(self, exporter_name: str) -> Optional[Dict]:
        """
        Vraća statistike za određenog dobavljača.
        """
        exporter_norm = self.normalize_exporter_name(exporter_name)
        if not exporter_norm:
            return None
        
        # Ako već imamo profil, vrati ga
        if exporter_norm in self.supplier_profiles:
            profile = self.supplier_profiles[exporter_norm]
        else:
            # Uči pattern-e
            profile = self.learn_from_exporter(exporter_norm)
            if not profile:
                return None
            
            self.supplier_profiles[exporter_norm] = profile
        
        # Pripremi statistike
        stats = {
            "exporter": exporter_norm,
            "total_declarations": profile.total_declarations,
            "total_items": profile.total_items,
            "countries": dict(profile.countries),
            "preferences": dict(profile.preferences),
            "top_patterns": [
                {
                    "country": p.country_code,
                    "preference": p.preference_code,
                    "count": p.count,
                    "confidence": p.confidence
                }
                for p in profile.top_patterns
            ]
        }
        
        return stats
    
    def batch_learn_top_exporters(self, limit: int = 20) -> Dict[str, SupplierProfile]:
        """
        Uči pattern-e za top N exportera (najviše XML-ova).
        """
        logger.info(f"🔍 Počinjem batch učenje za top {limit} exportera")
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Pronađi exportere sa najviše XML-ova
                    query = """
                    SELECT exporter_normalized, COUNT(*) as xml_count
                    FROM catalogs.exporter_xml_index
                    GROUP BY exporter_normalized
                    ORDER BY xml_count DESC
                    LIMIT %s
                    """
                    cursor.execute(query, (limit,))
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        exporter_norm = row['exporter_normalized']
                        xml_count = row['xml_count']
                        
                        logger.info(f"  Učim {exporter_norm} ({xml_count} XML-ova)")
                        
                        # Uči pattern-e za ovog exportera (ograniči na 10 XML-ova za brzinu)
                        profile = self.learn_from_exporter(exporter_norm, max_xml_files=10)
                        if profile:
                            self.supplier_profiles[exporter_norm] = profile
                        
            logger.info(f"✅ Batch učenje završeno. Naučeno {len(self.supplier_profiles)} profila.")
            return self.supplier_profiles
            
        except Exception as e:
            logger.error(f"Greška pri batch učenju: {e}")
            return {}
    
    def save_profiles_to_db(self):
        """
        Sačuva naučene profile u bazu za buduće korištenje.
        """
        if not self.supplier_profiles:
            logger.warning("Nema profila za čuvanje")
            return
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Kreiraj tabelu ako ne postoji
                    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS catalogs.supplier_historical_profiles (
                        id SERIAL PRIMARY KEY,
                        exporter_normalized VARCHAR(255) NOT NULL,
                        total_declarations INTEGER NOT NULL,
                        total_items INTEGER NOT NULL,
                        countries JSONB,
                        preferences JSONB,
                        country_preference_map JSONB,
                        top_patterns JSONB,
                        learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(exporter_normalized)
                    )
                    """)
                    
                    # Sačuvaj svaki profil
                    for exporter_norm, profile in self.supplier_profiles.items():
                        # Konvertuj u JSON
                        import psycopg2.extras
                        countries_json = psycopg2.extras.Json(dict(profile.countries))
                        preferences_json = psycopg2.extras.Json(dict(profile.preferences))
                        
                        # Konvertuj country_preference_map
                        cpm_json = psycopg2.extras.Json({
                            country: dict(prefs)
                            for country, prefs in profile.country_preference_map.items()
                        })
                        
                        # Konvertuj top_patterns
                        top_patterns_json = psycopg2.extras.Json([
                            {
                                "country_code": p.country_code,
                                "preference_code": p.preference_code,
                                "count": p.count,
                                "confidence": p.confidence
                            }
                            for p in profile.top_patterns
                        ])
                        
                        # Insert ili update
                        cursor.execute("""
                        INSERT INTO catalogs.supplier_historical_profiles 
                            (exporter_normalized, total_declarations, total_items, countries, 
                             preferences, country_preference_map, top_patterns)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (exporter_normalized) DO UPDATE SET
                            total_declarations = EXCLUDED.total_declarations,
                            total_items = EXCLUDED.total_items,
                            countries = EXCLUDED.countries,
                            preferences = EXCLUDED.preferences,
                            country_preference_map = EXCLUDED.country_preference_map,
                            top_patterns = EXCLUDED.top_patterns,
                            learned_at = CURRENT_TIMESTAMP
                        """, (
                            exporter_norm,
                            profile.total_declarations,
                            profile.total_items,
                            countries_json,
                            preferences_json,
                            cpm_json,
                            top_patterns_json
                        ))
                    
                    conn.commit()
                    logger.info(f"✅ Sačuvano {len(self.supplier_profiles)} profila u bazu")
                    
        except Exception as e:
            logger.error(f"Greška pri čuvanju profila u bazu: {e}")
    
    def load_profiles_from_db(self) -> Dict[str, SupplierProfile]:
        """
        Učitava prethodno naučene profile iz baze.
        """
        logger.info("🔍 Učitavam profile iz baze...")
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                    SELECT * FROM catalogs.supplier_historical_profiles
                    ORDER BY learned_at DESC
                    """)
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        try:
                            # Rekonstruiši SupplierProfile
                            profile = SupplierProfile(
                                exporter_normalized=row['exporter_normalized'],
                                total_declarations=row['total_declarations'],
                                total_items=row['total_items'],
                                countries=defaultdict(int, row['countries'] or {}),
                                preferences=defaultdict(int, row['preferences'] or {}),
                                country_preference_map=defaultdict(lambda: defaultdict(int)),
                                top_patterns=[]
                            )
                            
                            # Rekonstruiši country_preference_map
                            cpm_data = row['country_preference_map'] or {}
                            for country, prefs in cpm_data.items():
                                profile.country_preference_map[country] = defaultdict(int, prefs)
                            
                            # Rekonstruiši top_patterns
                            top_patterns_data = row['top_patterns'] or []
                            for p_data in top_patterns_data:
                                pattern = HistoricalPattern(
                                    exporter_normalized=row['exporter_normalized'],
                                    country_code=p_data.get('country_code', ''),
                                    preference_code=p_data.get('preference_code', ''),
                                    count=p_data.get('count', 0),
                                    last_used=datetime.now(),
                                    confidence=p_data.get('confidence', 0.0)
                                )
                                profile.top_patterns.append(pattern)
                            
                            self.supplier_profiles[row['exporter_normalized']] = profile
                            
                        except Exception as e:
                            logger.warning(f"Greška pri rekonstrukciji profila za {row['exporter_normalized']}: {e}")
                            continue
                    
            logger.info(f"✅ Učitano {len(self.supplier_profiles)} profila iz baze")
            return self.supplier_profiles
            
        except Exception as e:
            logger.error(f"Greška pri učitavanju profila iz baze: {e}")
            return {}


# Test funkcija
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Testiranje HistoricalLearningService v2...")
    
    service = HistoricalLearningService()
    
    # Test 1: Testiraj ekstrakciju iz jednog XML-a
    print("1. Testiram ekstrakciju iz XML-a...")
    test_xml = service.xml_folder / "001.xml"
    if test_xml.exists():
        items = service.extract_items_from_xml_simple(test_xml)
        print(f"   Pronađeno {len(items)} stavki u 001.xml")
        for i, item in enumerate(items[:3]):
            print(f"   Stavka {i+1}: pref={item.get('preference_code', 'N/A')}, "
                  f"country={item.get('country_code', 'N/A')}, hs={item.get('hs_code', 'N/A')}")
    
    # Test 2: Uči pattern-e za jednog exportera
    print("\n2. Učim pattern-e za exportera 'ZORKA KERAMIKA'...")
    profile = service.learn_from_exporter("ZORKA KERAMIKA", max_xml_files=5)
    if profile:
        print(f"   ✅ Naučeno: {profile.total_items} stavki, {len(profile.countries)} zemalja, "
              f"{len(profile.preferences)} povlastica")
        
        # Prikaži top pattern-e
        if profile.top_patterns:
            print(f"   Top pattern-i:")
            for i, pattern in enumerate(profile.top_patterns[:3]):
                print(f"     {i+1}. {pattern.country_code} → {pattern.preference_code} "
                      f"({pattern.count} puta, {pattern.confidence:.0%})")
    
    # Test 3: Predloži povlasticu
    print("\n3. Testiranje predlaganja povlastica...")
    test_cases = [
        ("ZORKA KERAMIKA", "RS"),  # Srbija
        ("ZORKA KERAMIKA", "DE"),  # Nemačka
    ]
    
    for exporter, country in test_cases:
        pref, confidence, explanation = service.suggest_preference(exporter, country)
        if pref:
            print(f"   {exporter} + {country}: {pref} (confidence: {confidence:.0%})")
            print(f"      {explanation}")
        else:
            print(f"   {exporter} + {country}: Nema predloga")
    
    # Test 4: Batch učenje
    print("\n4. Batch učenje za top 3 exportera...")
    profiles = service.batch_learn_top_exporters(limit=3)
    print(f"   ✅ Naučeno {len(profiles)} profila")
    
    # Test 5: Sačuvaj u bazu
    print("\n5. Sačuvaj profile u bazu...")
    service.save_profiles_to_db()
    
    print("\n✅ Test završen!")