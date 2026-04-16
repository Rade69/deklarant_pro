"""
Tariff RAG Service - Pretraga tarifnih brojeva iz istorije i zvaničnih tarifa.

Koristi RAG (Retrieval-Augmented Generation) pristup:
1. Pretražuje istoriju deklaracija (PostgreSQL - catalogs shema)
2. Pretražuje zvanične tarife (PostgreSQL - catalogs.zvanicna_tarifa)
3. Kombinuje rezultate sa confidence skorom

SVE KORISTI POSTGRESQL - nema SQLite!
"""

import re
from typing import Dict, List, Optional, Any
from database.db import get_db_connection


class TextNormalizer:
    """Normalizuje tekst za bolju pretragu tarifnih naziva."""

    STOP_WORDS = {
        'i', 'a', 'u', 'o', 'e', 'se', 'je', 'li', 'da', 'za', 'od', 'do',
        'sa', 'su', 'na', 'po', 'pri', 'pre', 'pod', 'nad', 'iz', 'bez',
        'kroz', 'k', 'ka', 'kao', 'ili', 'ali', 'jer', 'ako', 'kad', 'kada',
        'što', 'sta', 'koji', 'koja', 'koje', 'kojih', 'kojima', 'kojim',
        'ovaj', 'ova', 'ovo', 'ovi', 'ove', 'onaj', 'ona', 'ono', 'oni',
        'sam', 'si', 'je', 'smo', 'ste', 'su', 'biti', 'biće', 'bio', 'bila',
        'za', 'sve', 'svi', 'sva', 'svega', 'nego', 'već', 'još', 'samo',
        'pa', 'te', 'im', 'ih', 'mu', 'joj', 'ga', 'je', 'ju', 'mi', 'ti',
        'njega', 'nje', 'njoj', 'njim', 'njima', 'čiji', 'čija', 'čije'
    }

    def normalize(self, text: str) -> str:
        if not text:
            return ""
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\-]', '', text)
        return text.lower().strip()

    def extract_keywords(self, text: str, min_length: int = 3) -> List[str]:
        normalized = self.normalize(text)
        return [t for t in normalized.split()
                if len(t) >= min_length and t not in self.STOP_WORDS]

    def tokenize(self, text: str) -> List[str]:
        return self.normalize(text).split()

# Mapiranje ključnih riječi iz naziva robe na HS poglavlja (2 cifre)
# Ako naziv robe sadrži neku od ovih riječi, pretraga se sužava na to poglavlje
_CATEGORY_HINTS: Dict[str, str] = {
    # Farmaceutski proizvodi
    "tableta": "30", "tablete": "30", "tbl": "30", "tab": "30",
    "kapsula": "30", "kapsule": "30", "kap": "30",
    "sirup": "30", "injekcija": "30", "injekcije": "30",
    "mast": "30", "krema": "30", "gel": "30", "losion": "30",
    "supozitorij": "30", "supozitorije": "30",
    "ampula": "30", "ampule": "30",
    "vitamin": "30", "antibiotik": "30", "antibiotici": "30",
    "lijek": "30", "lijekovi": "30", "liek": "30",
    "farmaceutski": "30", "pharmaceutical": "30",
    # Kozmetika
    "šampon": "33", "sampon": "33", "pasta": "33",
    "parfem": "33", "dezodorans": "33", "sapun": "34",
    # Hrana i piće
    "mlijeko": "04", "sir": "04", "jaje": "04",
    "meso": "02", "riba": "03",
    "žitarica": "10", "pšenica": "10", "kukuruz": "10",
    "šećer": "17", "secera": "17", "čokolada": "18",
    "ulje": "15", "masnoća": "15",
    "pivo": "22", "vino": "22", "alkohol": "22",
    "kafa": "09", "čaj": "09",
    # Tekstil i odjeća
    "tkanina": "52", "pamuk": "52",
    "odjeća": "62", "odjeca": "62", "jakna": "62", "hlače": "62",
    "cipele": "64", "obuća": "64",
    # Elektronika i mašine
    "laptop": "84", "računar": "84", "racunar": "84", "kompjuter": "84",
    "motor": "84", "pumpa": "84", "kompresor": "84",
    "televizor": "85", "monitor": "85", "telefon": "85",
    "baterija": "85", "kabel": "85", "prekidač": "85",
    # Metali i proizvodi od metala
    "vijak": "73", "šraf": "73", "matica": "73",
    "čelik": "72", "gvožđe": "72", "aluminij": "76",
    # Hemikalije
    "kiseline": "28", "kiselina": "28",
    "plastika": "39", "guma": "40",
    # Papir i štampa
    "papir": "48", "karton": "48",
    "knjiga": "49", "štampani": "49", "stampani": "49",
    # Vozila
    "automobil": "87", "kamion": "87", "vozilo": "87",
    "auto": "87", "motocikl": "87",
}


class TariffRAGService:
    """
    Service za pretragu tarifnih brojeva iz istorije i zvaničnih tarifa.
    Sve ide kroz PostgreSQL - catalogs shema.
    """
    
    def __init__(self):
        self.normalizer = TextNormalizer()
    
    def search_historical(self, naziv_robe: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Pretražuje istorijske deklaracije (PostgreSQL catalogs.declaration_items).
        
        Args:
            naziv_robe: Naziv robe za pretragu
            limit: Maksimalan broj rezultata
            
        Returns:
            Lista rezultata sa tarifnim brojevima iz istorije
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
                    di.tarifni_broj,
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
            print(f"⚠️ Greška pri pretrazi istorije: {e}")
        
        return results
    
    def _detect_category_hint(self, naziv_robe: str) -> Optional[str]:
        """
        Detektuje HS poglavlje (2 cifre) na osnovu ključnih riječi iz naziva robe.
        Vraća None ako nema prepoznatljivih kategorija.
        """
        naziv_lower = naziv_robe.lower()
        for keyword, chapter in _CATEGORY_HINTS.items():
            if keyword in naziv_lower:
                return chapter
        return None

    def search_official(self, naziv_robe: str, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Pretražuje zvanične tarife (PostgreSQL catalogs.zvanicna_tarifa).

        Strategija:
        1. Ako naziv sadrži poznate kategorijske riječi → pretraži samo to HS poglavlje
        2. Ako ne → pretraži sve keywordove s OR uvjetom
        3. Vraća do `limit` kandidata sortiranih po relevantnosti
        """
        results = []

        try:
            with get_db_connection() as conn:
                cur = conn.cursor()

                keywords = self.normalizer.extract_keywords(naziv_robe)
                if not keywords:
                    return []

                chapter_hint = self._detect_category_hint(naziv_robe)

                if chapter_hint:
                    # Strategija 1: sužena pretraga po poglavlju + svi keywordovi (OR)
                    or_conditions = " OR ".join(["opis ILIKE %s"] * len(keywords))
                    params = [f"%{kw}%" for kw in keywords]
                    params.append(f"{chapter_hint}%")
                    params.append(limit)
                    query = f"""
                        SELECT tarifni_kod, opis
                        FROM catalogs.zvanicna_tarifa
                        WHERE tarifni_kod LIKE %s
                        ORDER BY
                            CASE WHEN ({or_conditions}) THEN 0 ELSE 1 END,
                            tarifni_kod
                        LIMIT %s
                    """
                    # Params: chapter_hint za LIKE, pa keywords za OR, pa limit
                    final_params = [f"{chapter_hint}%"] + [f"%{kw}%" for kw in keywords] + [limit]
                    query = f"""
                        SELECT tarifni_kod, opis
                        FROM catalogs.zvanicna_tarifa
                        WHERE tarifni_kod LIKE %s
                        ORDER BY
                            CASE WHEN {or_conditions} THEN 0 ELSE 1 END,
                            tarifni_kod
                        LIMIT %s
                    """
                    cur.execute(query, final_params)
                else:
                    # Strategija 2: globalna pretraga, OR po svim keywordovima
                    or_conditions = " OR ".join(["opis ILIKE %s"] * len(keywords))
                    params = [f"%{kw}%" for kw in keywords] + [limit]
                    query = f"""
                        SELECT tarifni_kod, opis
                        FROM catalogs.zvanicna_tarifa
                        WHERE {or_conditions}
                        ORDER BY tarifni_kod
                        LIMIT %s
                    """
                    cur.execute(query, params)

                rows = cur.fetchall()
                for row in rows:
                    results.append({
                        'tarifni_kod': row['tarifni_kod'],
                        'naziv_robe': row['opis'],
                        'source': 'official',
                        'confidence': 0.7,
                    })

        except Exception as e:
            print(f"⚠️ Greška pri pretrazi zvaničnih tarifa: {e}")

        return results
    
    def search(self, naziv_robe: str, limit: int = 5) -> Dict[str, Any]:
        """
        Kombinuje pretragu istorije i zvaničnih tarifa.
        
        Args:
            naziv_robe: Naziv robe za pretragu
            limit: Maksimalan broj rezultata
            
        Returns:
            Dict sa:
            - top_result: Najbolji rezultat (ili None)
            - candidates: Lista kandidata
            - needs_ai: Da li treba AI odluku (confidence < 0.80)
        """
        # Pretraži istoriju
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
