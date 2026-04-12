"""
Hybrid Matching Service

Kombinacija više metoda za bolje mapiranje tarifnih brojeva:
1. Historijsko učenje (supplier profiling)
2. Semantic matching (LLM embedding)
3. Keyword matching (tradicionalni)
4. Confidence scoring
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from database.db import get_db_connection
from services.tariff_mapping_service import TariffMapping
from services.agent.learning.historical_learning_service_safe import HistoricalLearningServiceSafe

logger = logging.getLogger("asycuda_pro.hybrid_matching")


@dataclass
class HybridMatch:
    """Rezultat hybrid matching-a."""
    tariff_mapping: TariffMapping
    confidence: float  # 0.0-1.0
    method: str  # 'historical', 'semantic', 'keyword', 'rules'
    explanation: str  # Objašnjenje zašto je ovaj predlog


@dataclass
class HybridMatchingResult:
    """Rezultat hybrid matching-a za više stavki."""
    matches: List[HybridMatch]
    avg_confidence: float
    method_distribution: Dict[str, int]  # Koliko puta je koja metoda korištena


class HybridMatchingService:
    """
    Hybrid Matching Service koji kombinira više metoda.
    
    Weight distribucija:
    - Historijsko: 40% (šta je ovaj dobavljač ranije koristio)
    - Semantic: 30% (LLM embedding sličnost)
    - Keyword: 20% (tradicionalni matching)
    - Rules: 10% (carinska pravila)
    """
    
    def __init__(self):
        self.historical_service = HistoricalLearningServiceSafe()
        self.keyword_service = None  # Postojeći TariffMappingService
        self.semantic_service = None  # LLM embedding service (treba implementirati)
        self.rules_service = None  # Customs rules service (treba implementirati)
        
        # Weight distribucija
        self.weights = {
            'historical': 0.40,
            'semantic': 0.30,
            'keyword': 0.20,
            'rules': 0.10
        }
        
        logger.info("✅ HybridMatchingService inicijalizovan")
    
    def find_hybrid_mapping(
        self,
        product_code: str,
        naziv_robe: str,
        supplier: str = "",
        country: str = "",
        min_confidence: float = 0.60
    ) -> Optional[HybridMatch]:
        """
        Pronađi najbolji mapping koristeći hybrid pristup.
        
        Args:
            product_code: Šifra proizvoda
            naziv_robe: Naziv proizvoda
            supplier: Ime dobavljača (za historijsko učenje)
            country: Zemlja porijekla (za pravila)
            min_confidence: Minimalna pouzdanost za prihvat
        
        Returns:
            HybridMatch sa najvećim confidence-om ili None
        """
        logger.debug(f"🔍 Hybrid mapping za: '{product_code}', '{naziv_robe[:40]}', supplier='{supplier}'")
        
        # Dobavi sve kandidate iz različitih metoda
        all_candidates = self._get_all_candidates(product_code, naziv_robe, supplier, country)
        
        if not all_candidates:
            logger.debug(f"ℹ️ Nema kandidata za '{naziv_robe[:40]}'")
            return None
        
        # Kombinuj kandidate i izračunaj finalne confidence
        best_match = self._combine_candidates(all_candidates)
        
        if best_match and best_match.confidence >= min_confidence:
            logger.debug(f"✅ Hybrid match: {best_match.tariff_mapping.tarifni_broj} "
                        f"(confidence: {best_match.confidence:.1%}, method: {best_match.method})")
            return best_match
        else:
            logger.debug(f"⚠️ Hybrid match below threshold: {best_match.confidence if best_match else 0:.1%} "
                        f"(min: {min_confidence:.1%})")
            return None
    
    def _get_all_candidates(
        self,
        product_code: str,
        naziv_robe: str,
        supplier: str,
        country: str
    ) -> List[HybridMatch]:
        """Dobavi kandidate iz svih metoda."""
        candidates = []
        
        # 1. Historijsko učenje (ako imamo suppliera)
        if supplier and supplier.strip():
            historical_candidates = self._get_historical_candidates(supplier, product_code, naziv_robe)
            candidates.extend(historical_candidates)
        
        # 2. Keyword matching (uvijek dostupno)
        keyword_candidates = self._get_keyword_candidates(product_code, naziv_robe)
        candidates.extend(keyword_candidates)
        
        # 3. Semantic matching (ako je dostupno)
        semantic_candidates = self._get_semantic_candidates(naziv_robe)
        candidates.extend(semantic_candidates)
        
        # 4. Rules-based matching (ako imamo zemlju)
        if country and country.strip():
            rules_candidates = self._get_rules_candidates(country, product_code, naziv_robe)
            candidates.extend(rules_candidates)
        
        return candidates
    
    def _get_historical_candidates(
        self,
        supplier: str,
        product_code: str,
        naziv_robe: str
    ) -> List[HybridMatch]:
        """Dobavi kandidate iz historijskog učenja."""
        candidates = []
        
        try:
            # Učitaj historijske podatke za ovog suppliera
            profile = self.historical_service._get_profile_safe(supplier)
            
            if not profile:
                return candidates
            
            # Pretraži bazu za tarifne brojeve koje je ovaj supplier ranije koristio
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Prvo po product_code (ako postoji)
                    if product_code and product_code.strip():
                        cursor.execute("""
                            SELECT DISTINCT ON (commodity_code) 
                                   product_code, naziv_robe, commodity_code, precision_1,
                                   zemlja_porijekla, povlastica, usage_count
                            FROM catalogs.product_tariff_mapping
                            WHERE product_code ILIKE %s
                            AND EXISTS (
                                SELECT 1 FROM catalogs.exporter_xml_index
                                WHERE exporter_normalized = %s
                                AND commodity_code = catalogs.product_tariff_mapping.commodity_code
                            )
                            ORDER BY commodity_code, usage_count DESC
                            LIMIT 5
                        """, (product_code.strip(), supplier))
                        
                        rows = cursor.fetchall()
                        
                        for row in rows:
                            mapping = TariffMapping(
                                product_code=row["product_code"],
                                naziv_robe=row["naziv_robe"],
                                tarifni_broj=row["commodity_code"],
                                precision_1=row["precision_1"],
                                zemlja_porijekla=row["zemlja_porijekla"] or "",
                                povlastica=row["povlastica"] or "",
                                usage_count=row["usage_count"],
                                similarity=1.0
                            )
                            
                            # Izračunaj confidence na osnovu usage_count
                            confidence = min(row["usage_count"] / 100.0, 1.0) * self.weights['historical']
                            
                            candidate = HybridMatch(
                                tariff_mapping=mapping,
                                confidence=confidence,
                                method='historical',
                                explanation=f"Supplier {supplier} ranije koristio ovaj tarifni broj ({row['usage_count']} puta)"
                            )
                            candidates.append(candidate)
                    
                    # Ako nema po product_code, pokušaj po nazivu
                    if not candidates and naziv_robe:
                        # Ekstraktuj ključne riječi iz naziva
                        keywords = self._extract_keywords(naziv_robe)
                        
                        if keywords:
                            query = f"%{'%'.join(keywords[:3])}%"
                            cursor.execute("""
                                SELECT DISTINCT ON (commodity_code) 
                                       product_code, naziv_robe, commodity_code, precision_1,
                                       zemlja_porijekla, povlastica, usage_count
                                FROM catalogs.product_tariff_mapping
                                WHERE naziv_robe ILIKE %s
                                AND EXISTS (
                                    SELECT 1 FROM catalogs.exporter_xml_index
                                    WHERE exporter_normalized = %s
                                    AND commodity_code = catalogs.product_tariff_mapping.commodity_code
                                )
                                ORDER BY commodity_code, usage_count DESC
                                LIMIT 5
                            """, (query, supplier))
                            
                            rows = cursor.fetchall()
                            
                            for row in rows:
                                mapping = TariffMapping(
                                    product_code=row["product_code"],
                                    naziv_robe=row["naziv_robe"],
                                    tarifni_broj=row["commodity_code"],
                                    precision_1=row["precision_1"],
                                    zemlja_porijekla=row["zemlja_porijekla"] or "",
                                    povlastica=row["povlastica"] or "",
                                    usage_count=row["usage_count"],
                                    similarity=1.0
                                )
                                
                                # Izračunaj confidence
                                similarity = self._calculate_similarity(naziv_robe, row["naziv_robe"])
                                confidence = similarity * self.weights['historical']
                                
                                candidate = HybridMatch(
                                    tariff_mapping=mapping,
                                    confidence=confidence,
                                    method='historical',
                                    explanation=f"Supplier {supplier} koristio sličan proizvod: {row['naziv_robe'][:50]}"
                                )
                                candidates.append(candidate)
        
        except Exception as e:
            logger.debug(f"⚠️ Error u historijskom matching-u za {supplier}: {e}")
        
        return candidates
    
    def _get_keyword_candidates(
        self,
        product_code: str,
        naziv_robe: str
    ) -> List[HybridMatch]:
        """Dobavi kandidate iz keyword matching-a (postojeći servis)."""
        candidates = []
        
        try:
            # Koristi postojeći TariffMappingService
            from services.tariff_mapping_service import TariffMappingService
            
            keyword_service = TariffMappingService()
            mapping = keyword_service.find_mapping(
                product_code=product_code,
                naziv_robe=naziv_robe,
                min_similarity=0.70
            )
            
            if mapping:
                # Izračunaj confidence na osnovu similarity
                confidence = mapping.similarity * self.weights['keyword']
                
                candidate = HybridMatch(
                    tariff_mapping=mapping,
                    confidence=confidence,
                    method='keyword',
                    explanation=f"Keyword match: similarity={mapping.similarity:.1%}"
                )
                candidates.append(candidate)
        
        except Exception as e:
            logger.debug(f"⚠️ Error u keyword matching-u: {e}")
        
        return candidates
    
    def _get_semantic_candidates(self, naziv_robe: str) -> List[HybridMatch]:
        """Dobavi kandidate iz semantic matching-a (placeholder za sada)."""
        # TODO: Implementirati LLM embedding matching
        # Za sada vraćamo praznu listu
        return []
    
    def _get_rules_candidates(
        self,
        country: str,
        product_code: str,
        naziv_robe: str
    ) -> List[HybridMatch]:
        """Dobavi kandidate na osnovu carinskih pravila."""
        candidates = []
        
        try:
            # Pravilo: Određeni proizvodi imaju specifične tarifne brojeve za određene zemlje
            # Na primjer: "vino" iz EU → tarifni broj za vino
            
            # Ekstraktuj ključne riječi
            keywords = self._extract_keywords(naziv_robe.lower())
            
            # Pravila baza (može se proširiti)
            rules = {
                ('vino', 'RS'): '22042110',  # Vino iz Srbije
                ('vino', 'DE'): '22042110',  # Vino iz Nemačke
                ('sir', 'RS'): '04061010',   # Sir iz Srbije
                ('sir', 'DE'): '04061010',   # Sir iz Nemačke
                ('meso', 'RS'): '02013000',  # Meso iz Srbije
                ('meso', 'DE'): '02013000',  # Meso iz Nemačke
            }
            
            for (product_keyword, rule_country), tariff_code in rules.items():
                if country.upper() == rule_country and any(product_keyword in kw for kw in keywords):
                    # Pronađi mapping za ovaj tarifni broj
                    with get_db_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                SELECT product_code, naziv_robe, commodity_code, precision_1,
                                       zemlja_porijekla, povlastica, usage_count
                                FROM catalogs.product_tariff_mapping
                                WHERE commodity_code = %s
                                ORDER BY usage_count DESC
                                LIMIT 1
                            """, (tariff_code,))
                            
                            row = cursor.fetchone()
                            if row:
                                mapping = TariffMapping(
                                    product_code=row["product_code"],
                                    naziv_robe=row["naziv_robe"],
                                    tarifni_broj=row["commodity_code"],
                                    precision_1=row["precision_1"],
                                    zemlja_porijekla=row["zemlja_porijekla"] or "",
                                    povlastica=row["povlastica"] or "",
                                    usage_count=row["usage_count"],
                                    similarity=1.0
                                )
                                
                                candidate = HybridMatch(
                                    tariff_mapping=mapping,
                                    confidence=self.weights['rules'],
                                    method='rules',
                                    explanation=f"Carinsko pravilo: {product_keyword} iz {country} → {tariff_code}"
                                )
                                candidates.append(candidate)
        
        except Exception as e:
            logger.debug(f"⚠️ Error u rules matching-u: {e}")
        
        return candidates
    
    def _combine_candidates(self, candidates: List[HybridMatch]) -> Optional[HybridMatch]:
        """Kombinuj kandidate i izaberi najbolji."""
        if not candidates:
            return None
        
        # Grupiši kandidate po tarifnom broju
        tariff_groups: Dict[str, List[HybridMatch]] = {}
        
        for candidate in candidates:
            tariff_code = candidate.tariff_mapping.tarifni_broj
            if tariff_code not in tariff_groups:
                tariff_groups[tariff_code] = []
            tariff_groups[tariff_code].append(candidate)
        
        # Za svaku grupu izračunaj kombinovani confidence
        best_match = None
        best_confidence = 0.0
        
        for tariff_code, group in tariff_groups.items():
            # Kombinuj confidence iz različitih metoda
            combined_confidence = 0.0
            methods_used = set()
            
            for candidate in group:
                combined_confidence += candidate.confidence
                methods_used.add(candidate.method)
            
            # Bonus za više metoda koje se slažu
            method_bonus = len(methods_used) * 0.05  # 5% bonus po metodi
            final_confidence = min(combined_confidence + method_bonus, 1.0)
            
            if final_confidence > best_confidence:
                best_confidence = final_confidence
                best_match = group[0]  # Uzmi prvi match iz grupe
                best_match.confidence = final_confidence
                
                # Kreiraj kombinovano objašnjenje
                methods_str = ", ".join(sorted(methods_used))
                best_match.explanation = f"Kombinovani match ({methods_str}): confidence={final_confidence:.1%}"
        
        return best_match
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Ekstraktuj ključne riječi iz teksta."""
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
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Izračunaj sličnost između dva teksta."""
        if not text1 or not text2:
            return 0.0
        
        # Koristi SequenceMatcher za string similarity
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def batch_hybrid_mapping(
        self,
        items: List[Dict[str, Any]],
        supplier: str = "",
        min_confidence: float = 0.60
    ) -> HybridMatchingResult:
        """
        Batch hybrid mapping za više stavki.
        
        Args:
            items: Lista stavki sa product_code i naziv_robe
            supplier: Ime dobavljača (opcionalno)
            min_confidence: Minimalna pouzdanost
        
        Returns:
            HybridMatchingResult sa svim match-evima
        """
        matches = []
        method_counts = {'historical': 0, 'semantic': 0, 'keyword': 0, 'rules': 0}
        
        for i, item in enumerate(items):
            product_code = item.get('product_code', '')
            naziv_robe = item.get('naziv_robe', '')
            country = item.get('zemlja_porijekla', '')
            
            match = self.find_hybrid_mapping(
                product_code=product_code,
                naziv_robe=naziv_robe,
                supplier=supplier,
                country=country,
                min_confidence=min_confidence
            )
            
            if match:
                matches.append(match)
                method_counts[match.method] += 1
                
                logger.debug(f"  [{i+1}] {naziv_robe[:40]}: {match.tariff_mapping.tarifni_broj} "
                            f"({match.confidence:.1%}, {match.method})")
            else:
                logger.debug(f"  [{i+1}] {naziv_robe[:40]}: NO MATCH")
        
        # Izračunaj prosječni confidence
        avg_confidence = sum(m.confidence for m in matches) / len(matches) if matches else 0.0
        
        result = HybridMatchingResult(
            matches=matches,
            avg_confidence=avg_confidence,
            method_distribution=method_counts
        )
        
        logger.info(f"✅ Batch hybrid mapping: {len(matches)}/{len(items)} match-eva "
                   f"(avg confidence: {avg_confidence:.1%})")
        
        return result
    
    def get_matching_stats(self) -> Dict[str, any]:
        """Vrati statistiku matching-a."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Ukupno mapiranja u bazi
                    cursor.execute("SELECT COUNT(*) as total FROM catalogs.product_tariff_mapping")
                    total_mappings = cursor.fetchone()['total']
                    
                    # Broj različitih suppliera u historiji
                    cursor.execute("SELECT COUNT(DISTINCT exporter_normalized) as suppliers FROM catalogs.exporter_xml_index")
                    total_suppliers = cursor.fetchone()['suppliers']
                    
                    # Prosječan usage_count
                    cursor.execute("SELECT AVG(usage_count) as avg_usage FROM catalogs.product_tariff_mapping")
                    avg_usage = cursor.fetchone()['avg_usage'] or 0
                    
            return {
                'total_mappings': total_mappings,
                'total_suppliers': total_suppliers,
                'avg_usage': round(avg_usage, 1),
                'weights': self.weights,
                'historical_service_available': self.historical_service.is_available()
            }
        
        except Exception as e:
            logger.debug(f"⚠️ Error getting matching stats: {e}")
            return {}


# Helper funkcija za brzo testiranje
def test_hybrid_matching():
    """Test hybrid matching servisa."""
    print("🧪 Testiranje HybridMatchingService...")
    
    service = HybridMatchingService()
    
    # Test 1: Historijski match (ZORKA KERAMIKA)
    print("\n1. Test za ZORKA KERAMIKA (historijski):")
    match1 = service.find_hybrid_mapping(
        product_code="",
        naziv_robe="Keramičke pločice",
        supplier="ZORKA KERAMIKA",
        country="RS",
        min_confidence=0.50
    )
    
    if match1:
        print(f"   ✅ Match: {match1.tariff_mapping.tarifni_broj}")
        print(f"      Confidence: {match1.confidence:.1%}")
        print(f"      Method: {match1.method}")
        print(f"      Explanation: {match1.explanation}")
    else:
        print("   ❌ No match")
    
    # Test 2: Keyword match (bez suppliera)
    print("\n2. Test keyword match (bez suppliera):")
    match2 = service.find_hybrid_mapping(
        product_code="",
        naziv_robe="Vino crno",
        supplier="",
        country="RS",
        min_confidence=0.50
    )
    
    if match2:
        print(f"   ✅ Match: {match2.tariff_mapping.tarifni_broj}")
        print(f"      Confidence: {match2.confidence:.1%}")
        print(f"      Method: {match2.method}")
        print(f"      Explanation: {match2.explanation}")
    else:
        print("   ❌ No match")
    
    # Test 3: Rules match
    print("\n3. Test rules match (vino iz Srbije):")
    match3 = service.find_hybrid_mapping(
        product_code="",
        naziv_robe="Crno vino",
        supplier="",
        country="RS",
        min_confidence=0.50
    )
    
    if match3:
        print(f"   ✅ Match: {match3.tariff_mapping.tarifni_broj}")
        print(f"      Confidence: {match3.confidence:.1%}")
        print(f"      Method: {match3.method}")
        print(f"      Explanation: {match3.explanation}")
    else:
        print("   ❌ No match")
    
    # Test 4: Statistika
    print("\n4. Matching statistika:")
    stats = service.get_matching_stats()
    if stats:
        print(f"   Total mappings: {stats['total_mappings']}")
        print(f"   Total suppliers: {stats['total_suppliers']}")
        print(f"   Avg usage: {stats['avg_usage']}")
        print(f"   Historical service available: {stats['historical_service_available']}")
    
    print("\n✅ Hybrid matching testiran!")


if __name__ == "__main__":
    test_hybrid_matching()
