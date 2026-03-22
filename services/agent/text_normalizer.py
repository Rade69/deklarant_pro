"""
Text Normalizer - Normalizacija teksta za pretragu.

Koristi se za pripremu naziva robe prije pretrage u historiji i tarifama.
"""

import re
from typing import List


class TextNormalizer:
    """
    Normalizuje tekst za bolju pretragu.
    
    - Uklanja višestruke razmake
    - Uklanja specijalne karaktere
    - Konvertuje u lowercase
    - Ekstraktuje ključne riječi
    """
    
    # Stop words za srpski/hrvatski/bosanski jezik
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
    
    def __init__(self):
        pass
    
    def normalize(self, text: str) -> str:
        """
        Normalizuje tekst za pretragu.
        
        Args:
            text: Ulazni tekst
            
        Returns:
            Normalizovani tekst
        """
        if not text:
            return ""
        
        # Ukloni newlineove
        text = text.replace('\n', ' ').replace('\r', ' ')
        
        # Ukloni višestruke razmake
        text = re.sub(r'\s+', ' ', text)
        
        # Ukloni specijalne karaktere (zadrži slova, brojeve, crtice)
        text = re.sub(r'[^\w\s\-]', '', text)
        
        # Lowercase
        text = text.lower()
        
        # Trim
        text = text.strip()
        
        return text
    
    def extract_keywords(self, text: str, min_length: int = 3) -> List[str]:
        """
        Ekstraktuje ključne riječi iz teksta.
        
        Args:
            text: Ulazni tekst
            min_length: Minimalna dužina riječi
            
        Returns:
            Lista ključnih riječi
        """
        # Normalizuj
        normalized = self.normalize(text)
        
        # Tokenizuj
        tokens = normalized.split()
        
        # Filtriraj stop words i kratke riječi
        keywords = [
            token for token in tokens
            if len(token) >= min_length and token not in self.STOP_WORDS
        ]
        
        return keywords
    
    def tokenize(self, text: str) -> List[str]:
        """
        Jednostavna tokenizacija teksta.
        
        Args:
            text: Ulazni tekst
            
        Returns:
            Lista tokena
        """
        normalized = self.normalize(text)
        return normalized.split()
