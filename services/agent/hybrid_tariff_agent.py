"""
Hybrid Tariff Agent - Inteligentno predlaganje tarifnih brojeva.

Kombinuje tri nivoa pretrage:
1. TariffMappingService (fuzzy match, confidence > 0.85)
2. TariffRAGService (historija + tarifa, confidence > 0.80)
3. AIDecisionService (Ollama za edge cases)

Vraća: {tarifni_broj, confidence, method, needs_review}
"""

from typing import Dict, Any, Optional, List
from services.tariff_mapping_service import TariffMappingService
from services.agent.tariff_rag_service import TariffRAGService
from services.agent.ai_decision_service import AIDecisionService


class HybridTariffAgent:
    """
    Hibridni agent za predlaganje tarifnih brojeva.
    
    Tri nivoa:
    1. Fuzzy match iz postojećih mapiranja (najbrži)
    2. RAG pretraga historije i zvaničnih tarifa
    3. AI odluka za edge cases
    """
    
    # Pragovi za confidence
    THRESHOLD_DIRECT = 0.85   # Direktno prihvati
    THRESHOLD_REVIEW = 0.60   # Pregledaj ali predloži
    
    def __init__(self):
        """Inicijalizuje sve servise."""
        self.mapping_service = TariffMappingService()
        self.rag_service = TariffRAGService()
        self.ai_service = AIDecisionService(use_ollama=True)
    
    def decide_tariff(self, naziv_robe: str, zemlja_porijekla: str = "") -> Dict[str, Any]:
        """
        Donosi odluku o tarifnom broju koristeći hibridni pristup.
        
        Args:
            naziv_robe: Naziv robe
            zemlja_porijekla: Zemlja porijekla (opciono)
            
        Returns:
            Dict sa:
            - tarifni_broj: Predloženi tarifni broj
            - confidence: Confidence skor (0.0-1.0)
            - method: Korištena metoda ('mapping', 'rag', 'ai')
            - needs_review: Da li treba pregled (confidence < THRESHOLD_DIRECT)
            - explanation: Objašnjenje odluke
            - candidates: Lista alternativnih kandidata
        """
        result = {
            'tarifni_broj': '',
            'confidence': 0.0,
            'method': 'none',
            'needs_review': True,
            'explanation': '',
            'candidates': []
        }
        
        # NIVO 1: TariffMappingService (fuzzy match)
        mapping_result = self._try_mapping(naziv_robe)
        
        if mapping_result and mapping_result['confidence'] >= self.THRESHOLD_DIRECT:
            result.update(mapping_result)
            result['method'] = 'mapping'
            result['needs_review'] = False
            return result
        
        # NIVO 2: TariffRAGService (historija + tarifa)
        rag_result = self._try_rag(naziv_robe)
        
        if rag_result and rag_result['confidence'] >= self.THRESHOLD_DIRECT:
            result.update(rag_result)
            result['method'] = 'rag'
            result['needs_review'] = False
            return result
        
        # NIVO 3: AIDecisionService (AI odluka)
        # Koristi RAG kandidate kao kontekst
        rag_context = rag_result.get('candidates', []) if rag_result else []
        ai_result = self._try_ai(naziv_robe, rag_context)
        
        if ai_result and ai_result['tarifni_broj']:
            result.update(ai_result)
            result['method'] = 'ai'
            result['needs_review'] = ai_result['confidence'] < self.THRESHOLD_DIRECT
            return result
        
        # Fallback: Vrati najbolji RAG rezultat čak i sa nižim confidence
        if rag_result and rag_result['tarifni_broj']:
            result.update(rag_result)
            result['method'] = 'rag_low_confidence'
            result['needs_review'] = True
            return result
        
        # Nema rezultata
        result['explanation'] = "Nema rezultata iz bilo kog izvora. Potreban ručni unos."
        return result
    
    def _try_mapping(self, naziv_robe: str) -> Optional[Dict[str, Any]]:
        """
        Pokušaj sa TariffMappingService.
        
        Args:
            naziv_robe: Naziv robe
            
        Returns:
            Rezultat ili None
        """
        try:
            mapping_result = self.mapping_service.find_mapping(
                product_code=None,
                naziv_robe=naziv_robe,
                min_similarity=0.70
            )
            
            # TariffMapping je object, ne dict!
            if mapping_result and hasattr(mapping_result, 'tarifni_broj') and mapping_result.tarifni_broj:
                return {
                    'tarifni_broj': mapping_result.tarifni_broj,
                    'confidence': mapping_result.similarity if hasattr(mapping_result, 'similarity') else 0.5,
                    'explanation': f"Fuzzy match: {mapping_result.naziv_robe if hasattr(mapping_result, 'naziv_robe') else 'N/A'}",
                    'candidates': []
                }
        except Exception as e:
            print(f"⚠️ Greška pri mapping pretrazi: {e}")
        
        return None
    
    def _try_rag(self, naziv_robe: str) -> Optional[Dict[str, Any]]:
        """
        Pokušaj sa TariffRAGService.
        
        Args:
            naziv_robe: Naziv robe
            
        Returns:
            Rezultat ili None
        """
        try:
            rag_result = self.rag_service.search(naziv_robe, limit=5)
            
            if rag_result and rag_result.get('top_result'):
                top = rag_result['top_result']
                candidates = rag_result.get('candidates', [])
                
                return {
                    'tarifni_broj': top['tarifni_broj'],
                    'confidence': top.get('confidence', 0.5),
                    'explanation': f"Preuzeto iz {top.get('source', 'nepoznato')}",
                    'candidates': candidates
                }
        except Exception as e:
            print(f"⚠️ Greška pri RAG pretrazi: {e}")
        
        return None
    
    def _try_ai(self, naziv_robe: str, rag_context: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Pokušaj sa AIDecisionService.
        
        Args:
            naziv_robe: Naziv robe
            rag_context: Kontekst iz RAG pretrage
            
        Returns:
            Rezultat ili None
        """
        try:
            ai_result = self.ai_service.decide_tariff(naziv_robe, rag_context)
            
            if ai_result and ai_result.get('tarifni_broj'):
                return {
                    'tarifni_broj': ai_result['tarifni_broj'],
                    'confidence': ai_result.get('confidence', 0.5),
                    'explanation': ai_result.get('explanation', 'AI odluka'),
                    'candidates': []
                }
        except Exception as e:
            print(f"⚠️ Greška pri AI odluci: {e}")
        
        return None
    
    def batch_decide(self, items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Batch procesiranje više stavki.
        
        Args:
            items: Lista stavki sa 'naziv_robe' i opciono 'zemlja_porijekla'
            
        Returns:
            Lista rezultata
        """
        results = []
        
        for i, item in enumerate(items):
            naziv = item.get('naziv_robe', '')
            zemlja = item.get('zemlja_porijekla', '')
            
            result = self.decide_tariff(naziv, zemlja)
            result['original_name'] = naziv
            result['index'] = i
            
            results.append(result)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Vraća statistiku o agentu.
        
        Returns:
            Dict sa statistikom
        """
        return {
            'threshold_direct': self.THRESHOLD_DIRECT,
            'threshold_review': self.THRESHOLD_REVIEW,
            'services': {
                'mapping': 'TariffMappingService',
                'rag': 'TariffRAGService',
                'ai': f'AIDecisionService (Ollama {self.ai_service.model})',
                'ai_available': self.ai_service.is_available()
            }
        }
