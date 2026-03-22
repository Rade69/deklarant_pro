"""
Tariff RAG Service - Pretraga tarifnih brojeva iz historije i zvaničnih tarifa.

Koristi RAG (Retrieval-Augmented Generation) pristup:
1. Pretražuje historiju deklaracija (PostgreSQL - catalogs shema)
2. Pretražuje zvanične tarife (PostgreSQL - catalogs.zvanicna_tarifa)
3. Kombinuje rezultate sa confidence skorom

SVE KORISTI POSTGRESQL - nema SQLite!
"""

from typing import Dict, List, Optional, Any
from database.db import get_db_connection
from services.agent.text_normalizer import TextNormalizer


class TariffRAGService:
    """
    Service za pretragu tarifnih brojeva iz historije i zvaničnih tarifa.
    Sve ide kroz PostgreSQL - catalogs shema.
    """
    
    def __init__(self):
        self.normalizer = TextNormalizer()
    
    def search_historical(self, naziv_robe: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Pretražuje historijske deklaracije (PostgreSQL catalogs.declaration_items).
        
        Args:
            naziv_robe: Naziv robe za pretragu
            limit: Maksimalan broj rezultata
            
        Returns:
            Lista rezultata sa tarifnim brojevima iz historije
        """
        results = []
        
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                
                # Ekstraktuj keywords
                keywords = self.normalizer.extract_keywords(naziv_robe)
                
                if not keywords:
                    return []
                
                # ILIKE pretraga na naziv_robe (PostgreSQL case-insensitive)
                # Koristi prvi keyword kao osnovu
                pattern = f"%{keywords[0]}%"
                
                query = """
                SELECT 
                    di.tarifni_kod,
                    di.naziv_robe,
                    di.zemlja_porijekla,
                    di.povlastica,
                    di.confidence,
                    d.invoice_number,
                    d.vendor,
                    d.buyer,
                    d.datum
                FROM catalogs.declaration_items di
                JOIN catalogs.declarations d ON di.declaration_id = d.id
                WHERE di.naziv_robe ILIKE %s
                ORDER BY di.confidence DESC, d.datum DESC
                LIMIT %s
                """
                
                cur.execute(query, (pattern, limit))
                rows = cur.fetchall()
                
                for row in rows:
                    results.append({
                        'tarifni_kod': row[0] or '',
                        'naziv_robe': row[1] or '',
                        'zemlja_porijekla': row[2] or '',
                        'povlastica': row[3] or '',
                        'confidence': float(row[4]) if row[4] else 0.5,
                        'source': 'historical',
                        'invoice_number': row[5] or '',
                        'vendor': row[6] or '',
                        'buyer': row[7] or '',
                        'datum': str(row[8]) if row[8] else ''
                    })
                
        except Exception as e:
            print(f"⚠️ Greška pri pretrazi historije: {e}")
        
        return results
    
    def search_official(self, naziv_robe: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Pretražuje zvanične tarife (PostgreSQL catalogs.zvanicna_tarifa).
        
        Args:
            naziv_robe: Naziv robe za pretragu
            limit: Maksimalan broj rezultata
            
        Returns:
            Lista rezultata sa tarifnim brojevima iz zvaničnih tarifa
        """
        results = []
        
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                
                # Ekstraktuj keywords
                keywords = self.normalizer.extract_keywords(naziv_robe)
                
                if not keywords:
                    return []
                
                # LIKE pretraga na naziv
                pattern = f"%{keywords[0]}%"
                
                query = """
                SELECT
                    tarifni_kod,
                    opis
                FROM catalogs.zvanicna_tarifa
                WHERE opis ILIKE %s
                ORDER BY tarifni_kod
                LIMIT %s
                """

                cur.execute(query, (pattern, limit))
                rows = cur.fetchall()

                for row in rows:
                    results.append({
                        'tarifni_kod': row[0],
                        'naziv_robe': row[1],
                        'source': 'official',
                        'confidence': 0.7  # Zvanična tarifa ima fiksni confidence
                    })
                
        except Exception as e:
            print(f"⚠️ Greška pri pretrazi zvaničnih tarifa: {e}")
        
        return results
    
    def search(self, naziv_robe: str, limit: int = 5) -> Dict[str, Any]:
        """
        Kombinuje pretragu historije i zvaničnih tarifa.
        
        Args:
            naziv_robe: Naziv robe za pretragu
            limit: Maksimalan broj rezultata
            
        Returns:
            Dict sa:
            - top_result: Najbolji rezultat (ili None)
            - candidates: Lista kandidata
            - needs_ai: Da li treba AI odluku (confidence < 0.80)
        """
        # Pretraži historiju
        historical_results = self.search_historical(naziv_robe, limit)
        
        # Pretraži zvanične tarife
        official_results = self.search_official(naziv_robe, limit)
        
        # Kombinuj rezultate
        all_results = historical_results + official_results
        
        if not all_results:
            return {
                'top_result': None,
                'candidates': [],
                'needs_ai': True
            }
        
        # Sortiraj po confidence
        all_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        top_result = all_results[0]
        candidates = all_results[:limit]
        
        # Da li treba AI?
        needs_ai = top_result.get('confidence', 0) < 0.80
        
        return {
            'top_result': top_result,
            'candidates': candidates,
            'needs_ai': needs_ai
        }
