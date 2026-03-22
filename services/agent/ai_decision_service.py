"""
AI Decision Service - AI odluke za tarifne brojeve.

Podržava dva backend-a:
1. Groq API (llama-3.1-8b-instant) - brz, besplatan, aktivan
2. Ollama (lokalni model) - kad bude dostupno više RAM-a

Automatski bira dostupni backend: Groq → Ollama → fallback
"""

import os
import re
from typing import Dict, List, Optional, Any

OLLAMA_MODEL = "qwen3.5:4b"
GROQ_MODEL = "llama-3.1-8b-instant"


class AIDecisionService:
    """
    Service za AI odluke o tarifnim brojevima.

    Multiple-choice pristup: model bira između RAG kandidata.
    Slobodna klasifikacija za nepoznate proizvode.
    """

    def __init__(self, use_ollama: bool = True):
        self.backend = None  # 'groq' | 'ollama' | None
        self.groq_client = None
        self.ollama_client = None
        self.model = None

        # Probaj Groq prvo (brži, ne opterećuje CPU)
        self._init_groq()

        # Ako Groq nije dostupan, probaj Ollamu
        if not self.groq_client and use_ollama:
            self._init_ollama()

    def _init_groq(self):
        """Inicijalizuje Groq klijent iz GROQ_API_KEY env varijable."""
        try:
            from groq import Groq
            from dotenv import load_dotenv
            load_dotenv()

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                print("ℹ️ GROQ_API_KEY nije postavljen, preskačem Groq.")
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
        """Inicijalizuje Ollama klijent."""
        try:
            import ollama
            client = ollama.Client(host="http://localhost:11434")
            models = client.list()
            available = [m.model for m in models.models]
            if not any(OLLAMA_MODEL in m for m in available):
                print(f"⚠️ Ollama model {OLLAMA_MODEL} nije dostupan.")
                return
            self.ollama_client = client
            self.backend = 'ollama'
            self.model = OLLAMA_MODEL
            print(f"✅ Ollama: {OLLAMA_MODEL} spreman")
        except Exception as e:
            print(f"⚠️ Ollama nije dostupna: {e}")

    def decide_tariff(self, naziv_robe: str, rag_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Donosi AI odluku o tarifnom broju.

        Sa RAG kandidatima → multiple-choice (brzo)
        Bez kandidata → slobodna klasifikacija
        """
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
        """Unified chat metoda za oba backend-a."""
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
                options={
                    "temperature": 0.1,
                    "num_predict": max_tokens * 4,
                    "num_thread": 2,
                    "num_ctx": 512,
                    "think": False,
                    "keep_alive": 0,
                }
            )
            raw = response.message.content
            return re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

        return ""

    def _decide_multiple_choice(self, naziv_robe: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Brza odluka: AI bira između RAG kandidata."""
        choices = "\n".join([
            f"{i+1}. {c.get('tarifni_broj') or c.get('kod', '')} — {(c.get('naziv_robe') or c.get('opis', ''))[:70]}"
            for i, c in enumerate(candidates[:5])
        ])

        prompt = f"""Roba: {naziv_robe}

Mogući tarifni brojevi:
{choices}

Odgovori SAMO brojem (1-{len(candidates[:5])}) koji najbolje odgovara. Ništa drugo."""

        answer = self._chat(prompt, max_tokens=10)

        match = re.search(r'\b([1-5])\b', answer)
        if match:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(candidates):
                chosen = candidates[idx]
                tb = chosen.get('tarifni_broj') or chosen.get('kod', '')
                confidence = round(0.82 - (idx * 0.05), 2)
                return {
                    'tarifni_broj': tb,
                    'confidence': confidence,
                    'explanation': f"AI ({self.backend}) odabrao: {chosen.get('naziv_robe', '')[:60]}",
                    'source': f'ai_{self.backend}'
                }

        return self._fallback_decision(naziv_robe, candidates)

    def _decide_free(self, naziv_robe: str) -> Dict[str, Any]:
        """Slobodna klasifikacija bez RAG kandidata."""
        prompt = f"""Ti si ekspert za carinske tarife (HS nomenklatura, BiH/EU).

Odredi tarifni broj za: {naziv_robe}

Odgovori u formatu:
TARIFNI_BROJ: [8 cifara]
RAZLOG: [jedna rečenica]"""

        answer = self._chat(prompt, max_tokens=100)
        tarifni_broj = self._extract_tariff_number(answer)

        if not tarifni_broj:
            return {'tarifni_broj': '', 'confidence': 0.0,
                    'explanation': 'AI nije uspio odrediti tarifni broj', 'source': 'ai_failed'}

        return {
            'tarifni_broj': tarifni_broj,
            'confidence': 0.72,
            'explanation': self._extract_razlog(answer),
            'source': f'ai_{self.backend}_free'
        }

    def _extract_tariff_number(self, text: str) -> Optional[str]:
        match = re.search(r'TARIFNI_BROJ:\s*(\d{4,10})', text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'\b(\d{8})\b', text)
        if match:
            return match.group(1)
        return None

    def _extract_razlog(self, text: str) -> str:
        match = re.search(r'RAZLOG:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text.strip()[:200]

    def _fallback_decision(self, naziv_robe: str, rag_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback kada AI ne radi — vrati prvog RAG kandidata."""
        if rag_context:
            top = rag_context[0]
            return {
                'tarifni_broj': top.get('tarifni_broj', ''),
                'confidence': round(top.get('confidence', 0.5) * 0.8, 2),
                'explanation': 'Preuzeto iz historije (AI nije dostupan)',
                'source': 'historical_fallback'
            }
        return {
            'tarifni_broj': '',
            'confidence': 0.0,
            'explanation': 'Nema rezultata i AI nije dostupan',
            'source': 'none'
        }

    def is_available(self) -> bool:
        return self.backend is not None

    def get_backend_info(self) -> str:
        if self.backend == 'groq':
            return f"Groq ({GROQ_MODEL})"
        elif self.backend == 'ollama':
            return f"Ollama ({OLLAMA_MODEL})"
        return "Nije dostupan"
