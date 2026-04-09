"""
HistoricalLearningService - SAFE VERSION

Ova verzija je 100% backward compatible i ne ugrožava postojeće funkcionalnosti.
Sve greške su silent - vraćaju None i ne utiču na postojeći sistem.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from collections import defaultdict
import re
from dataclasses import dataclass

logger = logging.getLogger("asycuda_pro.historical_learning")

@dataclass
class SupplierProfile:
    """Profil dobavljača sa historijskim podacima."""
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
    """Historijski pattern za kombinaciju dobavljač + zemlja."""
    exporter_normalized: str
    country_code: str
    preference_code: str
    count: int = 0
    confidence: float = 0.0


class HistoricalLearningServiceSafe:
    """
    Sigurna verzija HistoricalLearningService koja ne ugrožava postojeći sistem.
    
    Karakteristike:
    1. Svi pozivi su wrapped u try-except
    2. Sve greške su silent (ne prikazuju se korisniku)
    3. Uvijek postoji fallback na postojeću logiku
    4. Ne mijenja postojeće klase ili funkcije
    """
    
    def __init__(self, xml_folder: Optional[Path] = None):
        """
        Inicijalizacija sa silent error handling i caching-om.
        
        Karakteristike:
        1. Cache profila (ne uči iz baze svaki put)
        2. Batch učenje za top dobavljače
        3. Silent error handling
        """
        try:
            self.xml_folder = xml_folder or Path("/home/radovan/Desktop/asycuda_pro/docs/NOVA ASIKUDA")
            self.supplier_profiles: Dict[str, SupplierProfile] = {}
            self._cache_hits = 0
            self._cache_misses = 0
            self._initialized = True
            logger.debug("✅ HistoricalLearningServiceSafe inicijalizovan sa caching-om")
        except Exception as e:
            logger.debug(f"⚠️ Silent init error: {e}")
            self._initialized = False
    
    def is_available(self) -> bool:
        """Proveri da li je servis dostupan."""
        return self._initialized
    
    def normalize_exporter_name(self, exporter_name: str) -> Optional[str]:
        """
        Normalizuje ime exportera (silent version).
        
        Vraća None umesto da baci exception.
        """
        try:
            if not exporter_name:
                return None
            
            # Osnovna normalizacija
            normalized = exporter_name.strip().upper()
            
            # Ukloni nepotrebne karaktere
            normalized = re.sub(r'[^\w\s]', ' ', normalized)
            normalized = re.sub(r'\s+', ' ', normalized)
            
            return normalized if normalized else None
            
        except Exception:
            return None
    
    def get_preference_safe(self, exporter_name: str, country_code: str) -> Optional[str]:
        """
        Sigurno dobavi povlasticu iz historije.
        
        Ova funkcija:
        1. Nikada ne baca exception
        2. Uvijek vraća None ako nešto ne radi
        3. Ne utiče na postojeći sistem
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
            
            # Učitaj ili nauči profil
            profile = self._get_profile_safe(exporter_norm)
            if not profile:
                return None
            
            # Pronađi pattern za ovu zemlju
            if country_code in profile.country_preference_map:
                pref_counts = profile.country_preference_map[country_code]
                if pref_counts:
                    most_common = max(pref_counts.items(), key=lambda x: x[1])
                    pref_code, _ = most_common
                    
                    # Denormalizuj kod
                    denormalized = self._denormalize_preference_safe(pref_code, country_code)
                    return denormalized
            
            # Ako nema specifičnih podataka, probaj najčešću povlasticu
            if profile.preferences:
                most_common_overall = max(profile.preferences.items(), key=lambda x: x[1])
                pref_code, _ = most_common_overall
                return self._denormalize_preference_safe(pref_code, country_code)
            
            return None
            
        except Exception:
            # Silent error - vraćamo None
            return None
    
    def _get_profile_safe(self, exporter_norm: str) -> Optional[SupplierProfile]:
        """
        Sigurno dobavi profil exportera sa caching-om.
        
        Logika:
        1. Provjeri cache
        2. Ako nema u cache-u, uči iz baze
        3. Sačuvaj u cache-u
        """
        try:
            # Provjeri cache
            if exporter_norm in self.supplier_profiles:
                self._cache_hits += 1
                logger.debug(f"✅ Cache hit za '{exporter_norm}' (hits: {self._cache_hits}, misses: {self._cache_misses})")
                return self.supplier_profiles[exporter_norm]
            
            # Cache miss - uči iz baze
            self._cache_misses += 1
            logger.debug(f"🔍 Cache miss za '{exporter_norm}', učenje iz baze...")
            
            profile = self._learn_from_database_safe(exporter_norm)
            if profile:
                # Sačuvaj u cache-u
                self.supplier_profiles[exporter_norm] = profile
                logger.debug(f"✅ Naučen profil za '{exporter_norm}': {profile.total_items} stavki")
            else:
                logger.debug(f"ℹ️ Nema historijskih podataka za '{exporter_norm}'")
            
            return profile
            
        except Exception as e:
            logger.debug(f"⚠️ Silent error u _get_profile_safe za '{exporter_norm}': {e}")
            return None
    
    def _learn_from_database_safe(self, exporter_norm: str) -> Optional[SupplierProfile]:
        """
        Sigurno uči iz baze podataka KORISTEĆI ORIGINALNU LOGIKU.
        
        Umesto da koristi exporter_xml_index (koji nema povlastice),
        koristi originalni HistoricalLearningService koji uči direktno iz XML-ova.
        """
        try:
            # Koristi originalni HistoricalLearningService za učenje iz XML-ova
            from services.agent.historical_learning_service import HistoricalLearningService
            
            original_service = HistoricalLearningService()
            profile = original_service.learn_from_exporter(exporter_norm, max_xml_files=10)
            
            if not profile:
                return None
            
            # Konvertuj originalni profil u naš format
            our_profile = SupplierProfile(exporter_normalized=exporter_norm)
            our_profile.total_items = profile.total_items
            our_profile.total_declarations = profile.total_declarations
            
            # Kopiraj zemlje
            for country, count in profile.countries.items():
                our_profile.countries[country] = count
            
            # Kopiraj povlastice
            for pref, count in profile.preferences.items():
                our_profile.preferences[pref] = count
            
            # Kopiraj country-preference map (koristi normalizovane kodove)
            for country, pref_counts in profile.country_preference_map.items():
                for pref_normalized, count in pref_counts.items():
                    # Denormalizuj za naš format
                    pref_code = self._denormalize_preference_safe(pref_normalized, country)
                    our_profile.country_preference_map[country][pref_code] = count
            
            logger.debug(f"✅ Učeno {our_profile.total_items} stavki za '{exporter_norm}' iz XML-ova")
            
            # Izračunaj top pattern-e
            self._calculate_top_patterns(our_profile)
            
            return our_profile
                    
        except Exception as e:
            logger.debug(f"⚠️ Silent error learning from XMLs for '{exporter_norm}': {e}")
            return None
    
    def _calculate_top_patterns(self, profile: SupplierProfile):
        """Izračunaj najčešće pattern-e za profil."""
        try:
            top_patterns = []
            
            for country_code, pref_counts in profile.country_preference_map.items():
                for pref_code, count in pref_counts.items():
                    total_for_country = sum(pref_counts.values())
                    confidence = count / total_for_country if total_for_country > 0 else 0
                    
                    pattern = {
                        'country': country_code,
                        'preference': pref_code,
                        'count': count,
                        'confidence': confidence,
                        'percentage': f"{(confidence * 100):.0f}%"
                    }
                    top_patterns.append(pattern)
            
            # Sortiraj po count (opadajuće)
            top_patterns.sort(key=lambda x: x['count'], reverse=True)
            
            # Sačuvaj top 5 pattern-a
            profile.top_patterns = top_patterns[:5]
            
        except Exception:
            # Silent error
            profile.top_patterns = []
    
    def _denormalize_preference_safe(self, pref_code: str, country_code: str) -> str:
        """Sigurno denormalizuj kod povlastice."""
        try:
            if not pref_code:
                return ""
            
            pref_code = pref_code.strip().upper()
            
            # Za CEFTA povlastice, vraćamo CEFTAP kao moderniju verziju
            if pref_code in ["CEFTA", "CEFTAT", "CEFTAP"]:
                return "CEFTAP"
            
            # Za ostale, vraćamo original
            return pref_code
            
        except Exception:
            return ""
    
    def enhance_existing_preference(self, country_code: str, exporter_name: str = "") -> str:
        """
        Poboljšaj postojeću logiku bez breaking changes.
        
        Ova funkcija se koristi umesto zamjene postojeće _suggest_preference().
        """
        # 1. Prvo probaj historijsko učenje
        historical_pref = self.get_preference_safe(exporter_name, country_code)
        
        if historical_pref:
            return historical_pref
        
        # 2. Fallback na hardcoded logiku (kao u postojećem sistemu)
        return self._hardcoded_preference_fallback(country_code)
    
    def preload_top_exporters(self, limit: int = 20) -> int:
        """
        Preload top exportera u cache (batch učenje).
        
        Koristi originalni HistoricalLearningService za učenje iz XML-ova.
        """
        try:
            # Prvo dobavi top exportere iz baze
            from database.db import get_db_connection
            from psycopg2.extras import RealDictCursor
            
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Dobavi top exportere po broju deklaracija
                    query = """
                    SELECT exporter_normalized, COUNT(*) as declaration_count
                    FROM catalogs.exporter_xml_index
                    GROUP BY exporter_normalized
                    ORDER BY declaration_count DESC
                    LIMIT %s
                    """
                    cursor.execute(query, (limit,))
                    rows = cursor.fetchall()
                    
                    if not rows:
                        logger.debug("ℹ️ Nema exportera za preload")
                        return 0
                    
                    # Koristi originalni servis za batch učenje
                    from services.agent.historical_learning_service import HistoricalLearningService
                    original_service = HistoricalLearningService()
                    
                    loaded_count = 0
                    logger.debug(f"🔍 Preloading {len(rows)} top exportera...")
                    
                    for row in rows:
                        exporter_norm = row['exporter_normalized']
                        declaration_count = row['declaration_count']
                        
                        # Učitaj samo ako već nije u cache-u
                        if exporter_norm not in self.supplier_profiles:
                            try:
                                # Uči iz XML-ova
                                profile = original_service.learn_from_exporter(exporter_norm, max_xml_files=5)
                                
                                if profile and profile.total_items > 0:
                                    # Konvertuj u naš format
                                    our_profile = self._convert_original_profile(profile, exporter_norm)
                                    self.supplier_profiles[exporter_norm] = our_profile
                                    loaded_count += 1
                                    
                                    logger.debug(f"  ✅ Preloaded '{exporter_norm}': {profile.total_items} stavki iz {declaration_count} deklaracija")
                                else:
                                    logger.debug(f"  ℹ️ Nema podataka za '{exporter_norm}'")
                            except Exception as e:
                                logger.debug(f"  ⚠️ Error preloading '{exporter_norm}': {e}")
                    
                    logger.info(f"✅ Preloaded {loaded_count} top exportera u cache (total: {len(self.supplier_profiles)})")
                    return loaded_count
                    
        except Exception as e:
            logger.debug(f"⚠️ Silent error u preload_top_exporters: {e}")
            return 0
    
    def _convert_original_profile(self, original_profile, exporter_norm: str) -> SupplierProfile:
        """Konvertuj originalni profil u naš format."""
        our_profile = SupplierProfile(exporter_normalized=exporter_norm)
        our_profile.total_items = original_profile.total_items
        our_profile.total_declarations = original_profile.total_declarations
        
        # Kopiraj zemlje
        for country, count in original_profile.countries.items():
            our_profile.countries[country] = count
        
        # Kopiraj povlastice
        for pref, count in original_profile.preferences.items():
            our_profile.preferences[pref] = count
        
        # Kopiraj country-preference map
        for country, pref_counts in original_profile.country_preference_map.items():
            for pref_normalized, count in pref_counts.items():
                pref_code = self._denormalize_preference_safe(pref_normalized, country)
                our_profile.country_preference_map[country][pref_code] = count
        
        # Izračunaj top pattern-e
        self._calculate_top_patterns(our_profile)
        
        return our_profile
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Vrati statistiku cache-a."""
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'cache_size': len(self.supplier_profiles),
            'hit_ratio': self._cache_hits / (self._cache_hits + self._cache_misses) 
                if (self._cache_hits + self._cache_misses) > 0 else 0,
            'profiles': list(self.supplier_profiles.keys())[:10]  # Prvih 10
        }
    
    def _hardcoded_preference_fallback(self, country_code: str) -> str:
        """
        Hardcoded fallback - identičan postojećoj logici u EUR1QuickDialog.
        
        Ovo osigurava 100% backward compatibility.
        """
        country_upper = country_code.upper()
        
        # EU zemlje
        eu_countries = {
            'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
            'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
            'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK'
        }
        
        # CEFTA zemlje
        cefta_countries = {'RS', 'BA', 'ME', 'MK', 'AL', 'XK', 'MD'}
        
        if country_upper in eu_countries:
            return 'EUP'
        elif country_upper in cefta_countries:
            return 'CEFTAP'
        elif country_upper == 'TR':
            return 'TRP'
        elif country_upper == 'IR':
            return 'IRP'
        else:
            return ''


# Globalna instanca za jednostavno korišćenje
_historical_service_instance = None

def get_historical_service() -> HistoricalLearningServiceSafe:
    """Dobavi globalnu instancu HistoricalLearningServiceSafe."""
    global _historical_service_instance
    if _historical_service_instance is None:
        _historical_service_instance = HistoricalLearningServiceSafe()
    return _historical_service_instance


def enhance_preference_logic(country_code: str, exporter_name: str = "") -> str:
    """
    Glavna funkcija za poboljšanje logike bez breaking changes.
    
    Ova funkcija se poziva umesto direktnog korišćenja hardcoded pravila.
    
    Pravila:
    1. Ako znamo exportera → koristi historijsko učenje
    2. Ako ne znamo exportera → koristi hardcoded pravila
    3. Ako historijsko učenje ne radi → silent fallback
    """
    try:
        service = get_historical_service()
        
        # Ako imamo exportera, probaj historijsko učenje
        if exporter_name and exporter_name.strip():
            historical_pref = service.get_preference_safe(exporter_name, country_code)
            if historical_pref:
                return historical_pref
        
        # Fallback na hardcoded pravila
        return service._hardcoded_preference_fallback(country_code)
        
    except Exception:
        # Silent fallback na hardcoded logiku
        service = HistoricalLearningServiceSafe()
        return service._hardcoded_preference_fallback(country_code)