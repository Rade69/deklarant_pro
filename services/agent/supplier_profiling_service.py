"""
Supplier Profiling Service

Proširenje supplier profiling-a:
1. Kompletan profil dobavljača (ne samo povlastice)
2. Učenje tarifnih brojeva, zemalja, proizvoda
3. Predictive analytics za nove uvoze
"""

import logging
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass
from collections import defaultdict, Counter
import json
from datetime import datetime

from database.db import get_db_connection
from services.agent.historical_learning_service_safe import HistoricalLearningServiceSafe

logger = logging.getLogger("asycuda_pro.supplier_profiling")


@dataclass
class SupplierProductProfile:
    """Profil proizvoda za suppliera."""
    product_name: str
    tariff_code: str
    usage_count: int
    countries: Dict[str, int]  # Zemlje porijekla za ovaj proizvod
    last_used: Optional[datetime]
    confidence: float  # 0.0-1.0


@dataclass
class SupplierCountryProfile:
    """Profil zemlje za suppliera."""
    country_code: str
    usage_count: int
    preferences: Dict[str, int]  # Povlastice za ovu zemlju
    products: Dict[str, int]  # Proizvodi iz ove zemlje
    last_used: Optional[datetime]


@dataclass
class SupplierCompleteProfile:
    """Kompletan profil suppliera."""
    supplier_name: str
    total_declarations: int
    total_items: int
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    
    # Detaljni profili
    product_profiles: Dict[str, SupplierProductProfile]  # product_name → profile
    country_profiles: Dict[str, SupplierCountryProfile]  # country_code → profile
    
    # Statistika
    top_products: List[Tuple[str, int]]  # (product_name, count)
    top_countries: List[Tuple[str, int]]  # (country_code, count)
    top_tariff_codes: List[Tuple[str, int]]  # (tariff_code, count)
    
    # Predictive analytics
    predicted_preferences: Dict[str, str]  # country_code → predicted_preference
    predicted_tariffs: Dict[str, List[str]]  # product_keyword → predicted_tariff_codes
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertuj u dict za JSON serializaciju."""
        return {
            'supplier_name': self.supplier_name,
            'total_declarations': self.total_declarations,
            'total_items': self.total_items,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'top_products': self.top_products,
            'top_countries': self.top_countries,
            'top_tariff_codes': self.top_tariff_codes,
            'predicted_preferences': self.predicted_preferences,
            'predicted_tariffs': self.predicted_tariffs,
            'product_count': len(self.product_profiles),
            'country_count': len(self.country_profiles)
        }


class SupplierProfilingService:
    """
    Supplier Profiling Service - kompletan profil dobavljača.
    
    Uči:
    1. Koje tarifne brojeve supplier koristi
    2. Koje zemlje porijekla
    3. Koje proizvode uvozi
    4. Koje povlastice koristi
    5. Pattern-e i trendove
    """
    
    def __init__(self):
        self.historical_service = HistoricalLearningServiceSafe()
        self.profiles_cache: Dict[str, SupplierCompleteProfile] = {}
        
        logger.info("✅ SupplierProfilingService inicijalizovan")
    
    def get_complete_profile(self, supplier_name: str) -> Optional[SupplierCompleteProfile]:
        """
        Dobavi kompletan profil suppliera.
        
        Args:
            supplier_name: Ime suppliera
        
        Returns:
            SupplierCompleteProfile ili None ako nema podataka
        """
        # Provjeri cache
        if supplier_name in self.profiles_cache:
            logger.debug(f"✅ Profile from cache: {supplier_name}")
            return self.profiles_cache[supplier_name]
        
        logger.debug(f"🔍 Building complete profile for: {supplier_name}")
        
        try:
            # Učitaj podatke iz baze
            profile = self._build_profile_from_database(supplier_name)
            
            if profile:
                # Sačuvaj u cache
                self.profiles_cache[supplier_name] = profile
                logger.info(f"✅ Built complete profile for {supplier_name}: "
                           f"{profile.total_items} items, {profile.total_declarations} declarations")
            
            return profile
            
        except Exception as e:
            logger.error(f"❌ Error building profile for {supplier_name}: {e}")
            return None
    
    def _build_profile_from_database(self, supplier_name: str) -> Optional[SupplierCompleteProfile]:
        """Izgradi profil iz baze podataka."""
        try:
            # Prvo provjeri da li supplier postoji u historiji
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Dobavi osnovne podatke o supplieru
                    cursor.execute("""
                        SELECT 
                            COUNT(DISTINCT xml_filepath) as declaration_count,
                            MIN(declaration_date) as first_seen,
                            MAX(declaration_date) as last_seen
                        FROM catalogs.exporter_xml_index
                        WHERE exporter_normalized = %s
                    """, (supplier_name,))
                    
                    row = cursor.fetchone()
                    if not row or row['declaration_count'] == 0:
                        logger.debug(f"ℹ️ No declarations found for {supplier_name}")
                        return None
                    
                    total_declarations = row['declaration_count']
                    first_seen = row['first_seen']
                    last_seen = row['last_seen']
                    
                    # Sada treba da učitaš stvarne podatke iz XML-ova
                    # Ovo je kompleksnije jer podaci nisu u bazi
                    # Za sada ćemo koristiti simplified pristup
                    
                    # Kreiraj osnovni profil
                    profile = SupplierCompleteProfile(
                        supplier_name=supplier_name,
                        total_declarations=total_declarations,
                        total_items=0,  # Ovo ćemo izračunati kasnije
                        first_seen=first_seen,
                        last_seen=last_seen,
                        product_profiles={},
                        country_profiles={},
                        top_products=[],
                        top_countries=[],
                        top_tariff_codes=[],
                        predicted_preferences={},
                        predicted_tariffs={}
                    )
                    
                    # Za sada vraćamo osnovni profil
                    # TODO: Implementirati kompletnu analizu XML-ova
                    
                    return profile
                    
        except Exception as e:
            logger.error(f"❌ Error in _build_profile_from_database: {e}")
            return None
    
    def predict_preference_for_supplier(
        self,
        supplier_name: str,
        country_code: str
    ) -> Tuple[Optional[str], float, str]:
        """
        Predvidi povlasticu za suppliera i zemlju.
        
        Args:
            supplier_name: Ime suppliera
            country_code: Kod zemlje
        
        Returns:
            Tuple: (predicted_preference, confidence, explanation)
        """
        profile = self.get_complete_profile(supplier_name)
        
        if not profile:
            # Fallback na historical learning service
            return self.historical_service.get_preference_safe(supplier_name, country_code), 0.5, "Basic historical prediction"
        
        # Provjeri da li imamo historiju za ovu zemlju
        if country_code in profile.country_profiles:
            country_profile = profile.country_profiles[country_code]
            
            if country_profile.preferences:
                # Pronađi najčešću povlasticu
                most_common = max(country_profile.preferences.items(), key=lambda x: x[1])
                preference, count = most_common
                
                confidence = min(count / country_profile.usage_count, 1.0)
                explanation = f"{supplier_name} koristi {preference} za {country_code} ({count}/{country_profile.usage_count} puta)"
                
                return preference, confidence, explanation
        
        # Ako nema historije za ovu zemlju, koristi hardcoded pravila
        from services.agent.historical_learning_service_safe import enhance_preference_logic
        preference = enhance_preference_logic(country_code, supplier_name)
        
        if preference:
            return preference, 0.3, f"Fallback na osnovna pravila za {country_code}"
        else:
            return None, 0.0, f"Nema povlastice za {country_code}"
    
    def predict_tariff_for_product(
        self,
        supplier_name: str,
        product_name: str,
        country_code: str = ""
    ) -> List[Tuple[str, float, str]]:
        """
        Predvidi tarifne brojeve za proizvod.
        
        Args:
            supplier_name: Ime suppliera
            product_name: Naziv proizvoda
            country_code: Kod zemlje (opcionalno)
        
        Returns:
            Lista (tariff_code, confidence, explanation)
        """
        profile = self.get_complete_profile(supplier_name)
        
        if not profile:
            return []
        
        predictions = []
        
        # 1. Pokušaj direktan match po nazivu
        for product_profile in profile.product_profiles.values():
            similarity = self._calculate_similarity(product_name, product_profile.product_name)
            
            if similarity > 0.7:  # Visoka sličnost
                confidence = similarity * product_profile.confidence
                explanation = f"Sličan proizvod: {product_profile.product_name[:50]}"
                
                predictions.append((
                    product_profile.tariff_code,
                    confidence,
                    explanation
                ))
        
        # 2. Pokušaj match po keyword-ima
        if not predictions:
            product_keywords = self._extract_keywords(product_name.lower())
            
            for product_profile in profile.product_profiles.values():
                profile_keywords = self._extract_keywords(product_profile.product_name.lower())
                
                # Provjeri preklapanje keyword-a
                common_keywords = set(product_keywords) & set(profile_keywords)
                if common_keywords:
                    keyword_similarity = len(common_keywords) / max(len(product_keywords), len(profile_keywords))
                    
                    if keyword_similarity > 0.5:
                        confidence = keyword_similarity * product_profile.confidence
                        explanation = f"Zajednički keyword-i: {', '.join(common_keywords)}"
                        
                        predictions.append((
                            product_profile.tariff_code,
                            confidence,
                            explanation
                        ))
        
        # Sortiraj po confidence (opadajuće)
        predictions.sort(key=lambda x: x[1], reverse=True)
        
        return predictions[:3]  # Vrati top 3 predloga
    
    def get_supplier_statistics(self, supplier_name: str) -> Dict[str, Any]:
        """Dobavi statistiku za suppliera."""
        profile = self.get_complete_profile(supplier_name)
        
        if not profile:
            return {"error": "No profile found"}
        
        return {
            "supplier_name": supplier_name,
            "total_declarations": profile.total_declarations,
            "total_items": profile.total_items,
            "product_variety": len(profile.product_profiles),
            "country_variety": len(profile.country_profiles),
            "top_products": profile.top_products[:5],
            "top_countries": profile.top_countries[:5],
            "top_tariff_codes": profile.top_tariff_codes[:5],
            "first_seen": profile.first_seen.isoformat() if profile.first_seen else None,
            "last_seen": profile.last_seen.isoformat() if profile.last_seen else None,
            "days_active": (profile.last_seen - profile.first_seen).days if profile.first_seen and profile.last_seen else 0
        }
    
    def find_similar_suppliers(
        self,
        supplier_name: str,
        max_results: int = 5
    ) -> List[Tuple[str, float, str]]:
        """
        Pronađi slične suppliere.
        
        Args:
            supplier_name: Ime suppliera
            max_results: Maksimalan broj rezultata
        
        Returns:
            Lista (similar_supplier, similarity_score, explanation)
        """
        # TODO: Implementirati advanced similarity matching
        # Za sada vraćamo praznu listu
        return []
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Izračunaj sličnost između dva teksta."""
        if not text1 or not text2:
            return 0.0
        
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Ekstraktuj ključne riječi iz teksta."""
        import re
        
        if not text:
            return []
        
        # Ukloni specijalne karaktere i brojeve
        cleaned = re.sub(r'[^a-zA-ZčćžšđČĆŽŠĐ\s]', ' ', text)
        
        # Podijeli na riječi
        words = cleaned.lower().split()
        
        # Ukloni stop riječi
        stop_words = {'i', 'ili', 'sa', 'bez', 'za', 'od', 'do', 'na', 'u', 'po', 'iz', 'kao'}
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords
    
    def clear_cache(self):
        """Očisti cache profila."""
        self.profiles_cache.clear()
        logger.info("🧹 Supplier profiles cache cleared")
    
    def preload_top_suppliers(self, limit: int = 10) -> int:
        """Preload top suppliera u cache."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT exporter_normalized, COUNT(*) as count
                        FROM catalogs.exporter_xml_index
                        GROUP BY exporter_normalized
                        ORDER BY count DESC
                        LIMIT %s
                    """, (limit,))
                    
                    loaded_count = 0
                    for row in cursor.fetchall():
                        supplier = row['exporter_normalized']
                        declaration_count = row['count']
                        
                        if supplier not in self.profiles_cache:
                            profile = self.get_complete_profile(supplier)
                            if profile:
                                loaded_count += 1
                                logger.debug(f"  ✅ Preloaded {supplier} ({declaration_count} declarations)")
                    
                    logger.info(f"✅ Preloaded {loaded_count} supplier profiles")
                    return loaded_count
                    
        except Exception as e:
            logger.error(f"❌ Error preloading suppliers: {e}")
            return 0


# Helper funkcije
def get_supplier_insights(supplier_name: str) -> Dict[str, Any]:
    """Dobavi insight-e za suppliera (high-level funkcija)."""
    service = SupplierProfilingService()
    profile = service.get_complete_profile(supplier_name)
    
    if not profile:
        return {"error": "Supplier not found"}
    
    insights = {
        "supplier_name": supplier_name,
        "declaration_frequency": "Frequent" if profile.total_declarations > 10 else "Occasional",
        "product_diversity": "High" if len(profile.product_profiles) > 20 else "Medium" if len(profile.product_profiles) > 5 else "Low",
        "country_diversity": "High" if len(profile.country_profiles) > 5 else "Low",
        "most_common_product": profile.top_products[0][0] if profile.top_products else "Unknown",
        "most_common_country": profile.top_countries[0][0] if profile.top_countries else "Unknown",
        "activity_period": f"{profile.first_seen.date() if profile.first_seen else 'Unknown'} to {profile.last_seen.date() if profile.last_seen else 'Unknown'}",
        "reliability_score": min(profile.total_declarations / 10.0, 1.0)  # 0.0-1.0
    }
    
    return insights


# Test funkcija
def test_supplier_profiling():
    """Test supplier profiling servisa."""
    print("🧪 Testiranje SupplierProfilingService...")
    
    service = SupplierProfilingService()
    
    # Test 1: Get profile for known supplier
    print("\n1. Test get complete profile:")
    supplier = "ZORKA KERAMIKA"
    profile = service.get_complete_profile(supplier)
    
    if profile:
        print(f"   ✅ Profile found for {supplier}")
        print(f"      Declarations: {profile.total_declarations}")
        print(f"      First seen: {profile.first_seen}")
        print(f"      Last seen: {profile.last_seen}")
    else:
        print(f"   ❌ No profile for {supplier}")
    
    # Test 2: Predict preference
    print("\n2. Test predict preference:")
    pref, conf, expl = service.predict_preference_for_supplier("ZORKA KERAMIKA", "RS")
    print(f"   For ZORKA KERAMIKA + RS:")
    print(f"     Preference: {pref}")
    print(f"     Confidence: {conf:.1%}")
    print(f"     Explanation: {expl}")
    
    # Test 3: Get supplier statistics
    print("\n3. Test supplier statistics:")
    stats = service.get_supplier_statistics("ZORKA KERAMIKA")
    if "error" not in stats:
        print(f"   Declarations: {stats['total_declarations']}")
        print(f"   Product variety: {stats['product_variety']}")
        print(f"   Country variety: {stats['country_variety']}")
        print(f"   Top products: {stats['top_products'][:3] if stats['top_products'] else 'None'}")
    else:
        print(f"   {stats['error']}")
    
    # Test 4: Preload top suppliers
    print("\n4. Test preload top suppliers:")
    loaded = service.preload_top_suppliers(limit=5)
    print(f"   Preloaded {loaded} suppliers")
    
    # Test 5: Clear cache
    print("\n5. Test clear cache:")
    service.clear_cache()
    print(f"   Cache cleared")
    
    print("\n✅ Supplier profiling testiran!")


if __name__ == "__main__":
    test_supplier_profiling()