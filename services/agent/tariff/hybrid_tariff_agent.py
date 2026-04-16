"""
Hybrid Tariff Agent - Inteligentno predlaganje tarifnih brojeva.

Kombinuje tri nivoa pretrage:
1. TariffMappingService (fuzzy match, confidence > 0.85)
2. TariffRAGService (istorija + tarifa, confidence > 0.80)
3. AIDecisionService (Groq/Ollama za edge cases)

Vraća: {tarifni_broj, confidence, method, needs_review}
"""

import os
import re
from typing import Dict, Any, Optional, List
from services.tariff_mapping_service import TariffMappingService
from services.agent.tariff.tariff_rag_service import TariffRAGService

OLLAMA_MODEL = "qwen3.5:4b"
GROQ_MODEL = "llama-3.1-8b-instant"


class AIDecisionService:
    """AI odluke o tarifnim brojevima (Groq ili Ollama backend)."""

    def __init__(self, use_ollama: bool = True):
        self.backend = None
        self.groq_client = None
        self.ollama_client = None
        self.model = None
        self._init_groq()
        if not self.groq_client and use_ollama:
            self._init_ollama()

    def _init_groq(self):
        try:
            from groq import Groq
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return
            self.groq_client = Groq(api_key=api_key)
            self.backend = 'groq'
            self.model = GROQ_MODEL
            print(f"✅ Groq: {GROQ_MODEL} spreman")
        except ImportError:
            print("⚠️ groq paket nije instaliran.")
        except Exception as e:
            print(f"⚠️ Groq inicijalizacija neuspješna: {e}")

    def _init_ollama(self):
        try:
            import ollama
            client = ollama.Client(host="http://localhost:11434")
            models = client.list()
            available = [m.model for m in models.models]
            if not any(OLLAMA_MODEL in m for m in available):
                return
            self.ollama_client = client
            self.backend = 'ollama'
            self.model = OLLAMA_MODEL
            print(f"✅ Ollama: {OLLAMA_MODEL} spreman")
        except Exception as e:
            print(f"⚠️ Ollama nije dostupna: {e}")

    def decide_tariff(self, naziv_robe: str, rag_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.backend:
            return self._fallback_decision(naziv_robe, rag_context)
        try:
            if rag_context:
                return self._decide_multiple_choice(naziv_robe, rag_context)
            else:
                return self._decide_free(naziv_robe)
        except Exception as e:
            print(f"⚠️ Greška pri AI odluci ({self.backend}): {e}")
            return self._fallback_decision(naziv_robe, rag_context)

    def _chat(self, prompt: str, max_tokens: int = 50) -> str:
        if self.backend == 'groq':
            response = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        elif self.backend == 'ollama':
            response = self.ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1, "num_predict": max_tokens * 4,
                         "num_thread": 2, "num_ctx": 512, "think": False, "keep_alive": 0}
            )
            raw = response.message.content
            return re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        return ""

    def _decide_multiple_choice(self, naziv_robe: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        choices = "\n".join([
            f"{i+1}. {c.get('tarifni_broj') or c.get('kod', '')} — {(c.get('naziv_robe') or c.get('opis', ''))[:70]}"
            for i, c in enumerate(candidates[:5])
        ])
        prompt = f"Roba: {naziv_robe}\n\nMogući tarifni brojevi:\n{choices}\n\nOdgovori SAMO brojem (1-{len(candidates[:5])}) koji najbolje odgovara. Ništa drugo."
        answer = self._chat(prompt, max_tokens=10)
        match = re.search(r'\b([1-5])\b', answer)
        if match:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(candidates):
                chosen = candidates[idx]
                tb = chosen.get('tarifni_broj') or chosen.get('kod', '')
                return {'tarifni_broj': tb, 'confidence': round(0.82 - (idx * 0.05), 2),
                        'explanation': f"AI ({self.backend}) odabrao: {chosen.get('naziv_robe', '')[:60]}",
                        'source': f'ai_{self.backend}'}
        return self._fallback_decision(naziv_robe, candidates)

    def _decide_free(self, naziv_robe: str) -> Dict[str, Any]:
        prompt = f"Ti si ekspert za carinske tarife (HS nomenklatura, BiH/EU).\n\nOdredi tarifni broj za: {naziv_robe}\n\nOdgovori u formatu:\nTARIFNI_BROJ: [8 cifara]\nRAZLOG: [jedna rečenica]"
        answer = self._chat(prompt, max_tokens=100)
        tarifni_broj = self._extract_tariff_number(answer)
        if not tarifni_broj:
            return {'tarifni_broj': '', 'confidence': 0.0,
                    'explanation': 'AI nije uspio odrediti tarifni broj', 'source': 'ai_failed'}
        return {'tarifni_broj': tarifni_broj, 'confidence': 0.72,
                'explanation': self._extract_razlog(answer), 'source': f'ai_{self.backend}_free'}

    def _extract_tariff_number(self, text: str) -> Optional[str]:
        match = re.search(r'TARIFNI_BROJ:\s*(\d{4,10})', text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'\b(\d{8})\b', text)
        return match.group(1) if match else None

    def _extract_razlog(self, text: str) -> str:
        match = re.search(r'RAZLOG:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        return match.group(1).strip() if match else text.strip()[:200]

    def _fallback_decision(self, naziv_robe: str, rag_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        if rag_context:
            top = rag_context[0]
            return {'tarifni_broj': top.get('tarifni_broj', ''),
                    'confidence': round(top.get('confidence', 0.5) * 0.8, 2),
                    'explanation': 'Preuzeto iz istorije (AI nije dostupan)', 'source': 'historical_fallback'}
        return {'tarifni_broj': '', 'confidence': 0.0,
                'explanation': 'Nema rezultata i AI nije dostupan', 'source': 'none'}

    def is_available(self) -> bool:
        return self.backend is not None

    def get_backend_info(self) -> str:
        if self.backend == 'groq':
            return f"Groq ({GROQ_MODEL})"
        elif self.backend == 'ollama':
            return f"Ollama ({OLLAMA_MODEL})"
        return "Nije dostupan"


class HybridTariffAgent:
    """
    Hibridni agent za predlaganje tarifnih brojeva.
    
    Tri nivoa:
    1. Fuzzy match iz postojećih mapiranja (najbrži)
    2. RAG pretraga istorije i zvaničnih tarifa
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
        
        # NIVO 2: TariffRAGService (istorija + tarifa)
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
