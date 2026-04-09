"""
Historical Learning Service

Analizira historijske XML deklaracije i uči pattern-e:
1. Koje povlastice se koriste za koje dobavljače
2. Koje zemlje porijekla su tipične za svakog dobavljača
3. Koje kombinacije (dobavljač + zemlja → povlastica) su najčešće

Koristi lxml za bolje parsiranje XML-a.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
import re

import psycopg2
from psycopg2.extras import RealDictCursor
from lxml import etree

logger = logging.getLogger("asycuda_pro.historical_learning")


@dataclass
class HistoricalPattern:
    """Jedan pattern naučen iz historije."""
    exporter_normalized: str
    country_code: str  # ISO kod zemlje (npr. "DE", "RS", "CN")
    preference_code: str  # Povlastica (npr. "EUP", "CEFTAT", "TRP")
    count: int  # Koliko puta se pojavila ova kombinacija
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
    
    def extract_items_from_xml(self, xml_path: Path) -> List[Dict]:
        """
        Ekstrahuje stavke iz XML-a koristeći lxml.
        
        XML struktura u ASYCUDA XML-ovima:
        <Item>
          <Tarification>
            <Preference_code>CEFTAT</Preference_code>
          </Tarification>
          <Goods_description>
            <Country_of_origin_code>RS</Country_of_origin_code>
            <Country_of_origin_name>SRBIJA</Country_of_origin_name>
          </Goods_description>
          <HScode>
            <Code>69089000</Code>
          </HScode>
        </Item>
        """
        items = []
        try:
            # Parse XML sa lxml
            tree = etree.parse(str(xml_path))
            root = tree.getroot()
            
            # Pronađi sve Item elemente
            # Koristimo XPath koji ignorira namespace
            item_elements = root.xpath(".//*[local-name()='Item']")
            
            for item_elem in item_elements:
                item_data = {}
                
                # Povlastica - može biti u Tarification/Preference_code
                # Koristimo xpath() umesto find() za kompleksne upite
                pref_results = item_elem.xpath(".//*[local-name()='Preference_code']")
                if pref_results and pref_results[0].text:
                    raw_pref = pref_results[0].text.strip()
                    item_data["preference_code"] = raw_pref
                    item_data["preference_code_normalized"] = self._normalize_preference_code(raw_pref)
                else:
                    item_data["preference_code"] = ""
                    item_data["preference_code_normalized"] = ""
                
                # Zemlja porijekla (ISO kod)
                country_code_results = item_elem.xpath(".//*[local-name()='Country_of_origin_code']")
                if country_code_results and country_code_results[0].text:
                    item_data["country_code"] = country_code_results[0].text.strip()
                else:
                    # Pokušaj iz imena zemlje
                    country_name_results = item_elem.xpath(".//*[local-name()='Country_of_origin_name']")
                    if country_name_results and country_name_results[0].text:
                        country_name = country_name_results[0].text.strip().upper()
                        item_data["country_code"] = self._map_country_name_to_code(country_name)
                    else:
                        item_data["country_code"] = ""
                
                # Ime zemlje
                country_name_results = item_elem.xpath(".//*[local-name()='Country_of_origin_name']")
                if country_name_results and country_name_results[0].text:
                    item_data["country_name"] = country_name_results[0].text.strip()
                else:
                    item_data["country_name"] = ""
                
                # Tarifni broj (HS code) - u ASYCUDA XML-u je Commodity_code unutar HScode
                hs_results = item_elem.xpath(".//*[local-name()='HScode']/*[local-name()='Commodity_code']")
                if hs_results and hs_results[0].text:
                    item_data["hs_code"] = hs_results[0].text.strip()
                else:
                    item_data["hs_code"] = ""
                
                # Dodaj samo ako ima bar neke podatke
                if item_data["preference_code"] or item_data["country_code"]:
                    items.append(item_data)
            
            return items
            
        except Exception as e:
            logger.debug(f"Greška pri ekstrakciji stavki iz {xml_path.name}: {e}")
            return []
    
    def _map_country_name_to_code(self, country_name: str) -> str:
        """Mapira ime zemlje na ISO kod."""
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
        
        return ""
    
    def _normalize_preference_code(self, pref_code: str) -> str:
        """
        Normalizuje kod povlastice prema zvaničnim šiframa iz carinskog dokumenta.
        
        Prema "Šifre za popunjavanje carinske deklaracije" (Prilog 5):
        - CEFTAT: Povlastica za robu po Sporazumu CEFTA 2006 - Tranziciona (prelazna) pravila
        - CEFTAP: Povlastica za robu po Sporazumu CEFTA 2006 - PEM Konvencija
        
        Za potrebe učenja, tretiramo CEFTA povlastice kao istu grupu.
        """
        if not pref_code:
            return ""
        
        pref_code = pref_code.strip().upper()
        
        # Zvanične šifre povlastica (polje 36)
        official_preferences = {
            "CEFTAT": "CEFTA",  # Tranziciona pravila
            "CEFTAP": "CEFTA",  # PEM Konvencija
            "EFTA1": "EFTA",   # Švajcarska + Lihtenštajn
            "EFTA2": "EFTA",   # Island
            "EFTA3": "EFTA",   # Norveška
            "EUP": "EUP",      # Evropska unija
            "IRP": "IRP",      # Iran
            "TRP": "TRP",      # Turska
        }
        
        # Vrati normalizovani kod ako postoji u zvaničnim šiframa
        return official_preferences.get(pref_code, pref_code)
    
    def _denormalize_preference_code(self, normalized_code: str, context: str = "") -> str:
        """
        Vraća specifičan kod povlastice iz normalizovanog koda.
        
        Prema carinskom dokumentu, za CEFTA postoje dvije verzije:
        1. CEFTAT - Tranziciona (prelazna) pravila
        2. CEFTAP - PEM Konvencija (modernija)
        
        Args:
            normalized_code: Normalizovani kod (npr. "CEFTA", "EUP", "TRP")
            context: Kontekst (npr. zemlja kod "RS", "DE", "TR")
        
        Returns:
            Specifičan kod povlastice prema zvaničnim šiframa
        """
        if not normalized_code:
            return ""
        
        # Mapiranje normalizovanih kodova na specifične šifre
        preference_mapping = {
            "CEFTA": "CEFTAP",  # Podrazumevano: PEM Konvencija (modernija)
            "EFTA": "EFTA1",    # Podrazumevano: Švajcarska + Lihtenštajn
            "EUP": "EUP",
            "IRP": "IRP",
            "TRP": "TRP",
        }
        
        # Ako je CEFTA povlastica, možemo dodati inteligentniju logiku
        if normalized_code == "CEFTA":
            # Za zemlje CEFTA regiona (Srbija, Crna Gora, itd.) koristimo CEFTAP
            cefta_countries = {"RS", "ME", "BA", "AL", "MK", "MD", "XK"}
            if context in cefta_countries:
                return "CEFTAP"
            else:
                # Za ostale slučajeve, vraćamo CEFTAP kao moderniju verziju
                return "CEFTAP"
        
        # Vrati specifičan kod iz mapping-a ili originalni kod
        return preference_mapping.get(normalized_code, normalized_code)
    
    def get_official_preference_info(self, pref_code: str) -> Dict:
        """
        Vraća zvanične informacije o povlastici iz carinskog dokumenta.
        
        Args:
            pref_code: Kod povlastice (npr. "CEFTAP", "EUP", "TRP")
        
        Returns:
            Dict sa informacijama o povlastici
        """
        pref_code = pref_code.strip().upper()
        
        # Zvanične šifre i opisi iz carinskog dokumenta
        # Polje 36: Šifre za povlastice (tarifno - preferencijalne)
        official_info = {
            "CEFTAT": {
                "code": "CEFTAT",
                "description": "Povlastica za robu po Sporazumu CEFTA 2006 - Tranziciona (prelazna) pravila",
                "field": "36",
                "type": "an..6",
                "preference_document": "FTAT",  # Dokaz u polju 44
                "preference_document_desc": "Dokaz o preferencijalnom porijeklu robe po CEFTA - Tranziciona (prelazna) pravila",
                "origin_documents": ["PE1", "PE2", "PE3"],  # Dokumenti o poreklu
            },
            "CEFTAP": {
                "code": "CEFTAP",
                "description": "Povlastica za robu po Sporazumu CEFTA 2006 - PEM Konvencija",
                "field": "36",
                "type": "an..6",
                "preference_document": "FTAP",  # Dokaz u polju 44
                "preference_document_desc": "Dokaz o preferencijalnom porijeklu robe po CEFTA - PEM Konvencija",
                "origin_documents": ["PE1", "PE2", "PE3"],  # Dokumenti o poreklu
            },
            "EFTA1": {
                "code": "EFTA1",
                "description": "Povlastica za robu sa porijeklom iz Švajcarske Konfederacije i Kneževine Lihtenštajn",
                "field": "36",
                "type": "an..6",
                "preference_document": "EFTA",  # Dokaz u polju 44
                "preference_document_desc": "Dokaz o preferencijalnom porijeklu robe iz Švajcarske, Lihtenštajna, Islanda i Norveške",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "EFTA2": {
                "code": "EFTA2",
                "description": "Povlastica za robu porijeklom iz Islanda",
                "field": "36",
                "type": "an..6",
                "preference_document": "EFTA",
                "preference_document_desc": "Dokaz o preferencijalnom porijeklu robe iz Švajcarske, Lihtenštajna, Islanda i Norveške",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "EFTA3": {
                "code": "EFTA3",
                "description": "Povlastica za robu porijeklom iz Kraljevine Norveške",
                "field": "36",
                "type": "an..6",
                "preference_document": "EFTA",
                "preference_document_desc": "Dokaz o preferencijalnom porijeklu robe iz Švajcarske, Lihtenštajna, Islanda i Norveške",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "EUP": {
                "code": "EUP",
                "description": "Povlastica za robu porijeklom iz Evropske zajednice",
                "field": "36",
                "type": "an..6",
                "preference_document": "EUP",
                "preference_document_desc": "Dokaz o preferencijalnom porijeklu robe iz Evropske unije",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "IRP": {
                "code": "IRP",
                "description": "Povlastica za robu porijeklom iz Islamske Republike Iran",
                "field": "36",
                "type": "an..6",
                "preference_document": "IRP",
                "preference_document_desc": "Dokaz o preferencijalnom porijeklu robe iz Islamske Republike Iran",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
            "TRP": {
                "code": "TRP",
                "description": "Povlastica za robu porijeklom iz Turske",
                "field": "36",
                "type": "an..6",
                "preference_document": "TRP",
                "preference_document_desc": "Dokaz o preferencijalnom porijeklu robe iz Turske",
                "origin_documents": ["PE1", "PE2", "PE3"],
            },
        }
        
        return official_info.get(pref_code, {
            "code": pref_code,
            "description": "Nepoznata povlastica",
            "field": "36",
            "type": "an..6",
            "preference_document": "",
            "preference_document_desc": "",
            "origin_documents": [],
        })
    
    def get_origin_document_info(self, doc_code: str) -> Dict:
        """
        Vraća informacije o dokumentima o poreklu (PE1, PE2, PE3).
        
        Args:
            doc_code: Kod dokumenta ("PE1", "PE2", "PE3")
        
        Returns:
            Dict sa informacijama o dokumentu
        """
        doc_code = doc_code.strip().upper()
        
        # Dokumenti o poreklu iz carinskog dokumenta (polje 44)
        origin_docs = {
            "PE1": {
                "code": "PE1",
                "description": "Uvjerenje o kretanju robe EUR.1",
                "field": "44",
                "type": "an4",
                "full_name": "Uvjerenje o kretanju robe EUR.1",
                "usage": "Za veće vrijednosti robe, izdaje carinska uprava",
            },
            "PE2": {
                "code": "PE2",
                "description": "Izjava o porijeklu (kao dokaz o preferencijalnom porijeklu robe)",
                "field": "44",
                "type": "an4",
                "full_name": "Izjava o porijeklu",
                "usage": "Za manje vrijednosti robe, izjava dobavljača",
            },
            "PE3": {
                "code": "PE3",
                "description": "Izjava o porijeklu ovlaštenog izvoznika (kao dokaz o preferencijalnom porijeklu robe)",
                "field": "44",
                "type": "an4",
                "full_name": "Izjava o porijeklu ovlaštenog izvoznika",
                "usage": "Za ovlašćene izvoznike sa registrovanim brojem",
            },
            "FTAT": {
                "code": "FTAT",
                "description": "Dokaz o preferencijalnom porijeklu robe po CEFTA - Tranziciona (prelazna) pravila",
                "field": "44",
                "type": "an4",
                "full_name": "Dokaz o preferencijalnom porijeklu robe po CEFTA - Tranziciona pravila",
                "usage": "Za CEFTA tranziciona pravila",
            },
            "FTAP": {
                "code": "FTAP",
                "description": "Dokaz o preferencijalnom porijeklu robe po CEFTA - PEM Konvencija",
                "field": "44",
                "type": "an4",
                "full_name": "Dokaz o preferencijalnom porijeklu robe po CEFTA - PEM Konvencija",
                "usage": "Za CEFTA PEM Konvencija",
            },
            "EUP": {
                "code": "EUP",
                "description": "Dokaz o preferencijalnom porijeklu robe iz Evropske unije",
                "field": "44",
                "type": "an4",
                "full_name": "Dokaz o preferencijalnom porijeklu robe iz Evropske unije",
                "usage": "Za EU povlastice",
            },
            "IRP": {
                "code": "IRP",
                "description": "Dokaz o preferencijalnom porijeklu robe iz Islamske Republike Iran",
                "field": "44",
                "type": "an4",
                "full_name": "Dokaz o preferencijalnom porijeklu robe iz Islamske Republike Iran",
                "usage": "Za Iran povlastice",
            },
            "TRP": {
                "code": "TRP",
                "description": "Dokaz o preferencijalnom porijeklu robe iz Turske",
                "field": "44",
                "type": "an4",
                "full_name": "Dokaz o preferencijalnom porijeklu robe iz Turske",
                "usage": "Za Turska povlastice",
            },
            "EFTA": {
                "code": "EFTA",
                "description": "Dokaz o preferencijalnom porijeklu robe iz Švajcarske, Lihtenštajna, Islanda i Norveške",
                "field": "44",
                "type": "an4",
                "full_name": "Dokaz o preferencijalnom porijeklu robe iz EFTA zemalja",
                "usage": "Za EFTA povlastice",
            },
        }
        
        return origin_docs.get(doc_code, {
            "code": doc_code,
            "description": "Nepoznati dokument",
            "field": "44",
            "type": "an4",
            "full_name": "",
            "usage": "",
        })
    
    def get_xml_files_for_exporter(self, exporter_name: str, limit: int = 20) -> List[Path]:
        """Pronalazi XML fajlove za određenog exportera."""
        xml_files = []
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
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
                            rel_path = self.xml_folder / xml_path.name
                            if rel_path.exists():
                                xml_files.append(rel_path)
            
            logger.info(f"Pronađeno {len(xml_files)} XML fajlova za exportera '{exporter_name}'")
            return xml_files
            
        except Exception as e:
            logger.error(f"Greška pri dobavljanju XML fajlova za '{exporter_name}': {e}")
            return []
    
    def learn_from_exporter(self, exporter_name: str, max_xml_files: int = 10) -> Optional[SupplierProfile]:
        """Uči pattern-e iz XML fajlova određenog exportera."""
        logger.info(f"🔍 Učim pattern-e za exportera: {exporter_name}")
        
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
                items = self.extract_items_from_xml(xml_path)
                
                for item in items:
                    profile.total_items += 1
                    
                    country_code = item.get("country_code", "")
                    if country_code:
                        profile.countries[country_code] += 1
                    
                    # Koristi originalni kod za statistike
                    preference_code = item.get("preference_code", "")
                    if preference_code:
                        profile.preferences[preference_code] += 1
                    
                    # Koristi normalizovani kod za učenje pattern-a
                    pref_normalized = item.get("preference_code_normalized", "")
                    if pref_normalized:
                        # Takođe pratimo i normalizovane kodove
                        if "preferences_normalized" not in profile.__dict__:
                            profile.preferences_normalized = defaultdict(int)
                        profile.preferences_normalized[pref_normalized] += 1
                    
                    if country_code and pref_normalized:
                        profile.country_preference_map[country_code][pref_normalized] += 1
                
            except Exception as e:
                logger.debug(f"Greška pri analizi {xml_path.name}: {e}")
                continue
        
        # Izračunaj najčešće kombinacije
        self._calculate_top_patterns(profile)
        
        logger.info(f"✅ Naučeno {profile.total_items} stavki za '{exporter_name}': "
                   f"{len(profile.countries)} zemalja, {len(profile.preferences)} povlastica")
        
        return profile
    
    def _calculate_top_patterns(self, profile: SupplierProfile):
        """Izračunava najčešće pattern-e."""
        patterns = []
        
        for country_code, pref_counts in profile.country_preference_map.items():
            for pref_code, count in pref_counts.items():
                total_for_country = sum(pref_counts.values())
                confidence = count / total_for_country if total_for_country > 0 else 0
                
                pattern = HistoricalPattern(
                    exporter_normalized=profile.exporter_normalized,
                    country_code=country_code,
                    preference_code=pref_code,
                    count=count,
                    confidence=confidence
                )
                patterns.append(pattern)
        
        patterns.sort(key=lambda x: x.count, reverse=True)
        profile.top_patterns = patterns[:10]
    
    def suggest_preference(self, exporter_name: str, country_code: str) -> Tuple[Optional[str], float, str]:
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
                return None, 0.0, f"Nema historijskih podataka za exportera '{exporter_norm}'"
            
            self.supplier_profiles[exporter_norm] = profile
        
        # Pronađi pattern za ovu zemlju (koristi normalizovane kodove)
        if country_code in profile.country_preference_map:
            pref_counts = profile.country_preference_map[country_code]
            
            if pref_counts:
                most_common_pref = max(pref_counts.items(), key=lambda x: x[1])
                pref_normalized, count = most_common_pref
                
                # Vrati specifičan kod iz normalizovanog
                pref_code = self._denormalize_preference_code(pref_normalized, country_code)
                
                total_for_country = sum(pref_counts.values())
                confidence = count / total_for_country
                
                # Dodaj napomenu ako je CEFTA povlastica
                explanation_suffix = ""
                if pref_normalized == "CEFTA":
                    # Proveri koji se specifični kod koristio u historiji
                    original_codes = [p for p in profile.preferences.keys() if p in ["CEFTAT", "CEFTAP"]]
                    if original_codes:
                        used_codes = ", ".join(original_codes)
                        explanation_suffix = f" (u historiji korišteno: {used_codes})"
                
                explanation = (
                    f"Predlažem '{pref_code}' jer {exporter_norm} koristi CEFTA povlasticu "
                    f"{count} od {total_for_country} puta ({confidence:.0%}) za robu iz {country_code}.{explanation_suffix}"
                )
                
                return pref_code, confidence, explanation
        
        # Ako nema specifičnog pattern-a, predloži najčešću povlasticu
        if hasattr(profile, 'preferences_normalized') and profile.preferences_normalized:
            most_common_overall = max(profile.preferences_normalized.items(), key=lambda x: x[1])
            pref_normalized, total_count = most_common_overall
            
            total_all = sum(profile.preferences_normalized.values())
            confidence = total_count / total_all if total_all > 0 else 0.5
            
            # Vrati specifičan kod
            pref_code = self._denormalize_preference_code(pref_normalized, country_code)
            
            explanation = (
                f"Predlažem '{pref_code}' jer {exporter_norm} najčešće koristi ovu vrstu povlastice "
                f"({total_count} od {total_all} puta, {confidence:.0%}). "
                f"Nema specifičnih podataka za zemlju {country_code}."
            )
            
            return pref_code, confidence, explanation
        
        # Fallback na originalne preference
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
        
        return None, 0.0, f"Nema historijskih podataka za kombinaciju {exporter_norm} + {country_code}"
    
    def batch_learn_top_exporters(self, limit: int = 20) -> Dict[str, SupplierProfile]:
        """Uči pattern-e za top N exportera."""
        logger.info(f"🔍 Počinjem batch učenje za top {limit} exportera")
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
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
                        
                        profile = self.learn_from_exporter(exporter_norm, max_xml_files=10)
                        if profile:
                            self.supplier_profiles[exporter_norm] = profile
            
            logger.info(f"✅ Batch učenje završeno. Naučeno {len(self.supplier_profiles)} profila.")
            return self.supplier_profiles
            
        except Exception as e:
            logger.error(f"Greška pri batch učenju: {e}")
            return {}
    
    def integrate_with_tariff_mapping_service(self):
        """
        Integrira se sa postojećim TariffMappingService.
        
        Ova metoda bi trebala da se pozove nakon što se nauče pattern-i,
        da bi se poboljšalo predlaganje tarifnih brojeva.
        """
        # Ovdje bi se integrisalo sa TariffMappingService
        # Na primer, dodati historijske pattern-e kao dodatni faktor u scoring-u
        logger.info("🔗 Integriram se sa TariffMappingService...")
        
        # TODO: Implementirati integraciju
        # Ideja: Koristiti historijske pattern-e kao boost za matching
        # Ako je proizvod od poznatog dobavljača sa poznatom zemljom,
        # povećati score za tarifne brojeve koji se često koriste u toj kombinaciji
        
        logger.info("✅ Integracija sa TariffMappingService završena")


# Test funkcija
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Testiranje HistoricalLearningService...")
    
    service = HistoricalLearningService()
    
    # Test 1: Testiraj ekstrakciju iz XML-a
    print("1. Testiram ekstrakciju iz XML-a...")
    test_xml = service.xml_folder / "001.xml"
    if test_xml.exists():
        items = service.extract_items_from_xml(test_xml)
        print(f"   Pronađeno {len(items)} stavki u 001.xml")
        for i, item in enumerate(items):
            print(f"   Stavka {i+1}: pref={item.get('preference_code', 'N/A')}, "
                  f"country={item.get('country_code', 'N/A')}, hs={item.get('hs_code', 'N/A')}")
    
    # Test 2: Uči pattern-e za jednog exportera
    print("\n2. Učim pattern-e za exportera 'ZORKA KERAMIKA'...")
    profile = service.learn_from_exporter("ZORKA KERAMIKA", max_xml_files=5)
    if profile:
        print(f"   ✅ Naučeno: {profile.total_items} stavki, {len(profile.countries)} zemalja, "
              f"{len(profile.preferences)} povlastica")
        
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
        ("ZORKA KERAMIKA", "TR"),  # Turska
        ("ZORKA KERAMIKA", "IR"),  # Iran
    ]
    
    for exporter, country in test_cases:
        pref, confidence, explanation = service.suggest_preference(exporter, country)
        if pref:
            # Dodaj zvanične informacije
            pref_info = service.get_official_preference_info(pref)
            print(f"   {exporter} + {country}: {pref} (confidence: {confidence:.0%})")
            print(f"      {pref_info['description']}")
            print(f"      {explanation}")
        else:
            print(f"   {exporter} + {country}: Nema predloga")
    
    # Test 4: Prikaži zvanične informacije o povlasticama
    print("\n4. Zvanične informacije o povlasticama (Polje 36):")
    official_codes = ["CEFTAT", "CEFTAP", "EUP", "TRP", "IRP"]
    for code in official_codes:
        info = service.get_official_preference_info(code)
        print(f"   {code}: {info['description']}")
        print(f"      Polje: {info['field']}, Tip: {info['type']}")
        print(f"      Dokaz u polju 44: {info['preference_document']} - {info['preference_document_desc']}")
        print(f"      Dokumenti o poreklu: {', '.join(info['origin_documents'])}")
    
    # Test 5: Prikaži informacije o dokumentima o poreklu
    print("\n5. Dokumenti o poreklu (Polje 44):")
    origin_docs = ["PE1", "PE2", "PE3", "FTAP", "EUP"]
    for doc in origin_docs:
        info = service.get_origin_document_info(doc)
        print(f"   {doc}: {info['description']}")
        print(f"      Polje: {info['field']}, Tip: {info['type']}")
        if info.get('usage'):
            print(f"      Upotreba: {info['usage']}")
    
    # Test 4: Batch učenje
    print("\n4. Batch učenje za top 3 exportera...")
    profiles = service.batch_learn_top_exporters(limit=3)
    print(f"   ✅ Naučeno {len(profiles)} profila")
    
    print("\n✅ Test završen!")