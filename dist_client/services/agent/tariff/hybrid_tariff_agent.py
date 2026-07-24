"""
Hybrid Tariff Agent - Inteligentno predlaganje tarifnih brojeva.

Kombinuje tri nivoa pretrage:
1. TariffMappingService (fuzzy match, confidence > 0.85)
2. TariffRAGService (istorija + tarifa, confidence > 0.80)
3. AIDecisionService (Groq/Ollama za edge cases)

Vraća: {tarifni_broj, confidence, method, needs_review, explanation, candidates}

Performansne napomene:
- Skup validnih tarifnih kodova se učitava jednom (lazy) i kešira u memoriji.
  Provjera valjanosti broja je O(1) bez ijednog DB poziva.
- zemlja_porijekla se koristi kao boost u rankiranju — ne filtrira rezultate
  (da ne bi izgubili korisne istorijske podatke kad zemlja nije upisana).
- AI poziv (Groq/Ollama) se radi samo ako prva dva nivoa ne daju dovoljan
  confidence, čime se izbjegava kašnjenje na sporijim mašinama.
"""

import os
import re
import logging
from typing import Dict, Any, Optional, List

from services.tariff.tariff_mapping_service import TariffMappingService
from services.agent.tariff.tariff_rag_service import TariffRAGService

logger = logging.getLogger(__name__)

OLLAMA_MODEL = "qwen3.5:4b"
GROQ_MODEL   = "llama-3.1-8b-instant"

# Keš validnih tarifnih kodova — popunjava se jednom pri prvom pozivu.
# set lookup je O(1) i ne pravi nikakav DB poziv po stavki.
_valid_tariff_codes: Optional[set] = None


def _load_tariff_cache() -> set:
    """Učitava sve tarifne kodove iz DB u memoriju (jednom za cijeli process)."""
    global _valid_tariff_codes
    if _valid_tariff_codes is not None:
        return _valid_tariff_codes
    try:
        from database.db import get_db_connection
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT tarifni_kod FROM catalogs.zvanicna_tarifa")
            rows = cur.fetchall()
            # Normalizujemo: bez tačaka/razmaka, samo cifre
            _valid_tariff_codes = {
                re.sub(r'\D', '', r['tarifni_kod'])
                for r in rows
                if r['tarifni_kod']
            }
            logger.info("✅ Tariff keš učitan: %d kodova", len(_valid_tariff_codes))
    except Exception as e:
        logger.warning("⚠️ Nije moguće učitati tariff keš: %s", e)
        _valid_tariff_codes = set()
    return _valid_tariff_codes


def _validate_tariff_number(tarifni_broj: str) -> bool:
    """
    Provjerava da li tarifni broj postoji u zvaničnoj tarifi.
    Koristi in-memory keš — bez ijednog DB poziva po pozivu.
    """
    if not tarifni_broj:
        return False
    normalized = re.sub(r'\D', '', tarifni_broj)
    if len(normalized) not in (4, 6, 8, 10):
        return False
    cache = _load_tariff_cache()
    if not cache:
        return True   # Ako keš nije dostupan, ne blokiramo rad
    # Provjera: tražimo i pun kod i prefiks (4/6 cifara)
    return (
        normalized in cache
        or normalized[:8] in cache
        or normalized[:6] in cache
        or normalized[:4] in cache
    )


# ---------------------------------------------------------------------------
# AI Decision Service
# ---------------------------------------------------------------------------

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
            logger.info("✅ Groq: %s spreman", GROQ_MODEL)
        except ImportError:
            logger.warning("⚠️ groq paket nije instaliran.")
        except Exception as e:
            logger.warning("⚠️ Groq inicijalizacija neuspješna: %s", e)

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
            logger.info("✅ Ollama: %s spreman", OLLAMA_MODEL)
        except Exception as e:
            logger.warning("⚠️ Ollama nije dostupna: %s", e)

    def decide_tariff(self, naziv_robe: str, rag_context: List[Dict[str, Any]],
                      zemlja_porijekla: str = "") -> Dict[str, Any]:
        if not self.backend:
            return self._fallback_decision(naziv_robe, rag_context)
        try:
            if rag_context:
                return self._decide_multiple_choice(naziv_robe, rag_context, zemlja_porijekla)
            else:
                return self._decide_free(naziv_robe, zemlja_porijekla)
        except Exception as e:
            logger.warning("⚠️ Greška pri AI odluci (%s): %s", self.backend, e)
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

    def _decide_multiple_choice(self, naziv_robe: str,
                                candidates: List[Dict[str, Any]],
                                zemlja_porijekla: str = "") -> Dict[str, Any]:
        choices = "\n".join([
            f"{i+1}. {c.get('tarifni_broj') or c.get('tarifni_kod', '')} — "
            f"{(c.get('naziv_robe') or c.get('opis', ''))[:70]}"
            for i, c in enumerate(candidates[:5])
        ])
        zemlja_info = f"\nZemlja porijekla: {zemlja_porijekla}" if zemlja_porijekla else ""
        prompt = (
            f"Roba: {naziv_robe}{zemlja_info}\n\n"
            f"Mogući tarifni brojevi:\n{choices}\n\n"
            f"Odgovori SAMO brojem (1-{len(candidates[:5])}) koji najbolje odgovara. Ništa drugo."
        )
        answer = self._chat(prompt, max_tokens=10)
        match = re.search(r'\b([1-5])\b', answer)
        if match:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(candidates):
                chosen = candidates[idx]
                tb = chosen.get('tarifni_broj') or chosen.get('tarifni_kod', '')
                return {
                    'tarifni_broj': tb,
                    'confidence': round(0.82 - (idx * 0.05), 2),
                    'explanation': f"AI ({self.backend}) odabrao: {chosen.get('naziv_robe', '')[:60]}",
                    'source': f'ai_{self.backend}',
                }
        return self._fallback_decision(naziv_robe, candidates)

    def _decide_free(self, naziv_robe: str, zemlja_porijekla: str = "") -> Dict[str, Any]:
        zemlja_info = f"\nZemlja porijekla: {zemlja_porijekla}" if zemlja_porijekla else ""
        prompt = (
            f"Ti si ekspert za carinske tarife (HS nomenklatura, BiH/EU).\n\n"
            f"Odredi tarifni broj za: {naziv_robe}{zemlja_info}\n\n"
            f"Odgovori u formatu:\n"
            f"TARIFNI_BROJ: [8 cifara]\n"
            f"RAZLOG: [jedna rečenica]"
        )
        answer = self._chat(prompt, max_tokens=100)
        tarifni_broj = self._extract_tariff_number(answer)
        if not tarifni_broj:
            return {'tarifni_broj': '', 'confidence': 0.0,
                    'explanation': 'AI nije uspio odrediti tarifni broj', 'source': 'ai_failed'}
        # Niži confidence kad nema RAG konteksta
        confidence = 0.65 if not zemlja_porijekla else 0.68
        return {
            'tarifni_broj': tarifni_broj,
            'confidence': confidence,
            'explanation': self._extract_razlog(answer),
            'source': f'ai_{self.backend}_free',
        }

    def _extract_tariff_number(self, text: str) -> Optional[str]:
        match = re.search(r'TARIFNI_BROJ:\s*(\d{4,10})', text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'\b(\d{8})\b', text)
        return match.group(1) if match else None

    def _extract_razlog(self, text: str) -> str:
        match = re.search(r'RAZLOG:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        return match.group(1).strip() if match else text.strip()[:200]

    def _fallback_decision(self, naziv_robe: str,
                           rag_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        if rag_context:
            top = rag_context[0]
            return {
                'tarifni_broj': top.get('tarifni_broj', ''),
                'confidence': round(top.get('confidence', 0.5) * 0.8, 2),
                'explanation': 'Preuzeto iz istorije (AI nije dostupan)',
                'source': 'historical_fallback',
            }
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


# ---------------------------------------------------------------------------
# Hybrid Tariff Agent
# ---------------------------------------------------------------------------

class HybridTariffAgent:
    """
    Hibridni agent za predlaganje tarifnih brojeva.

    Tri nivoa (svaki sljedeći se poziva samo ako prethodni ne da dovoljno):
    1. TariffMappingService — fuzzy match iz naučenih mapiranja (najbrži)
    2. TariffRAGService     — PostgreSQL pretraga istorije + zvaničnih tarifa
    3. AIDecisionService    — Groq/Ollama za edge-case (sporost ovisi o mreži/hardware)

    Sve metode primaju zemlja_porijekla, ali ga koriste kao boost — ne kao
    filter — da ne blokiraju korisne rezultate kad zemlja nije upisana.

    Validacija tarifnog broja koristi in-memory keš (O(1), bez DB poziva).
    """

    THRESHOLD_DIRECT = 0.85   # Direktno prihvati, bez review-a
    THRESHOLD_REVIEW = 0.60   # Predloži, ali označi za pregled

    def __init__(self):
        self.mapping_service = TariffMappingService()
        self.rag_service     = TariffRAGService()
        self.ai_service      = AIDecisionService(use_ollama=True)
        # Zagrijemo keš pri inicijalizaciji (ne blokiramo — greška = prazan set)
        _load_tariff_cache()

    def decide_tariff(self, naziv_robe: str,
                      zemlja_porijekla: str = "") -> Dict[str, Any]:
        """
        Donosi odluku o tarifnom broju koristeći hibridni pristup.

        Args:
            naziv_robe:      Naziv robe iz deklaracije / fakture
            zemlja_porijekla: ISO-2 ili puni naziv (npr. "DE", "Njemačka").
                              Koristi se za boost u rankiranju i AI promptu.

        Returns:
            {
              tarifni_broj: str,
              confidence:   float (0.0–1.0),
              method:       'mapping' | 'rag' | 'ai' | 'rag_low_confidence' | 'none',
              needs_review: bool,
              valid_in_db:  bool,   # da li tarifni_broj postoji u zvanicna_tarifa
              explanation:  str,
              candidates:   list[dict],
            }
        """
        result: Dict[str, Any] = {
            'tarifni_broj': '',
            'confidence':   0.0,
            'method':       'none',
            'needs_review': True,
            'valid_in_db':  False,
            'explanation':  '',
            'candidates':   [],
        }

        # ── Nivo 1: TariffMappingService ──────────────────────────────
        mapping = self._try_mapping(naziv_robe, zemlja_porijekla)
        if mapping and mapping['confidence'] >= self.THRESHOLD_DIRECT:
            result.update(mapping)
            result['method']       = 'mapping'
            result['needs_review'] = False
            return self._finalize(result)

        # ── Nivo 2: TariffRAGService ──────────────────────────────────
        rag = self._try_rag(naziv_robe, zemlja_porijekla)
        if rag and rag['confidence'] >= self.THRESHOLD_DIRECT:
            result.update(rag)
            result['method']       = 'rag'
            result['needs_review'] = False
            return self._finalize(result)

        # ── Nivo 3: AIDecisionService ─────────────────────────────────
        rag_context = rag.get('candidates', []) if rag else []
        # Uključi i mapping rezultat u kontekst za AI ako postoji
        if mapping and mapping.get('tarifni_broj'):
            rag_context = [mapping] + rag_context

        ai = self._try_ai(naziv_robe, rag_context, zemlja_porijekla)
        if ai and ai['tarifni_broj']:
            result.update(ai)
            result['method'] = 'ai'
            return self._finalize(result)

        # ── Fallback: RAG s niskim confidence ────────────────────────
        if rag and rag['tarifni_broj']:
            result.update(rag)
            result['method']       = 'rag_low_confidence'
            result['needs_review'] = True
            return self._finalize(result)

        result['explanation'] = "Nema rezultata iz bilo kog izvora. Potreban ručni unos."
        return result

    def _finalize(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Završna obrada: validacija tarifnog broja i postavljanje needs_review
        na osnovu oba praga (THRESHOLD_DIRECT i THRESHOLD_REVIEW).
        """
        tb = result.get('tarifni_broj', '')
        valid = _validate_tariff_number(tb)
        result['valid_in_db'] = valid

        if tb and not valid:
            # Broj ne postoji u tarifi — smanji confidence i označi za pregled
            result['confidence']   = min(result['confidence'], 0.45)
            result['needs_review'] = True
            result['explanation']  += " ⚠️ Tarifni broj nije pronađen u zvaničnoj tarifi."

        # Postavi needs_review prema pragovima
        conf = result['confidence']
        if conf >= self.THRESHOLD_DIRECT and valid:
            result['needs_review'] = False
        elif conf >= self.THRESHOLD_REVIEW:
            result['needs_review'] = True   # predloži ali označi
        else:
            result['needs_review'] = True   # niska pouzdanost

        return result

    # ── Privatne metode ────────────────────────────────────────────────

    def _try_mapping(self, naziv_robe: str,
                     zemlja_porijekla: str = "") -> Optional[Dict[str, Any]]:
        """Fuzzy match iz TariffMappingService."""
        try:
            res = self.mapping_service.find_mapping(
                product_code=None,
                naziv_robe=naziv_robe,
                min_similarity=0.70,
            )
            if res and hasattr(res, 'tarifni_broj') and res.tarifni_broj:
                return {
                    'tarifni_broj': res.tarifni_broj,
                    'confidence':   getattr(res, 'similarity', 0.5),
                    'explanation':  f"Fuzzy match: {getattr(res, 'naziv_robe', 'N/A')}",
                    'candidates':   [],
                }
        except Exception as e:
            logger.warning("⚠️ Greška pri mapping pretrazi: %s", e)
        return None

    def _try_rag(self, naziv_robe: str,
                 zemlja_porijekla: str = "") -> Optional[Dict[str, Any]]:
        """RAG pretraga iz TariffRAGService, sa boost-om po zemlji porijekla."""
        try:
            rag_result = self.rag_service.search(
                naziv_robe,
                limit=5,
                zemlja_porijekla=zemlja_porijekla,
            )
            if rag_result and rag_result.get('top_result'):
                top        = rag_result['top_result']
                candidates = rag_result.get('candidates', [])
                return {
                    'tarifni_broj': top.get('tarifni_broj') or top.get('tarifni_kod', ''),
                    'confidence':   top.get('confidence', 0.5),
                    'explanation':  f"Preuzeto iz {top.get('source', 'nepoznato')}",
                    'candidates':   candidates,
                }
        except Exception as e:
            logger.warning("⚠️ Greška pri RAG pretrazi: %s", e)
        return None

    def _try_ai(self, naziv_robe: str,
                rag_context: List[Dict[str, Any]],
                zemlja_porijekla: str = "") -> Optional[Dict[str, Any]]:
        """AI odluka, s kontekstom iz RAG-a i zemljom porijekla u promptu."""
        try:
            ai_result = self.ai_service.decide_tariff(
                naziv_robe, rag_context, zemlja_porijekla
            )
            if ai_result and ai_result.get('tarifni_broj'):
                return {
                    'tarifni_broj': ai_result['tarifni_broj'],
                    'confidence':   ai_result.get('confidence', 0.5),
                    'explanation':  ai_result.get('explanation', 'AI odluka'),
                    'candidates':   [],
                }
        except Exception as e:
            logger.warning("⚠️ Greška pri AI odluci: %s", e)
        return None

    # ── Batch i statistika ─────────────────────────────────────────────

    def batch_decide(self, items: List[Dict[str, str]],
                     max_workers: int = 4) -> List[Dict[str, Any]]:
        """
        Batch procesiranje više stavki.

        Koristi ThreadPoolExecutor samo za Nivo 1+2 (DB) jer su I/O bound.
        AI poziv (Nivo 3) ostaje sekvencijalan — ne preopterećujemo API.

        Args:
            items:       Lista dict-ova sa 'naziv_robe' i opciono 'zemlja_porijekla'
            max_workers: Broj paralelnih niti (default 4, snizi na sporoj mašini)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = [None] * len(items)

        def _process(idx_item):
            idx, item = idx_item
            naziv  = item.get('naziv_robe', '')
            zemlja = item.get('zemlja_porijekla', '')
            res = self.decide_tariff(naziv, zemlja)
            res['original_name'] = naziv
            res['index']         = idx
            return idx, res

        with ThreadPoolExecutor(max_workers=max_workers) as exe:
            futures = {exe.submit(_process, (i, item)): i
                       for i, item in enumerate(items)}
            for future in as_completed(futures):
                try:
                    idx, res = future.result()
                    results[idx] = res
                except Exception as e:
                    i = futures[future]
                    logger.warning("⚠️ batch_decide[%d] greška: %s", i, e)
                    results[i] = {
                        'tarifni_broj': '', 'confidence': 0.0,
                        'method': 'error', 'needs_review': True,
                        'valid_in_db': False,
                        'explanation': str(e), 'candidates': [],
                        'original_name': items[i].get('naziv_robe', ''),
                        'index': i,
                    }

        return results

    def get_statistics(self) -> Dict[str, Any]:
        cache = _load_tariff_cache()
        return {
            'threshold_direct':    self.THRESHOLD_DIRECT,
            'threshold_review':    self.THRESHOLD_REVIEW,
            'tariff_cache_size':   len(cache),
            'services': {
                'mapping':       'TariffMappingService',
                'rag':           'TariffRAGService',
                'ai':            self.ai_service.get_backend_info(),
                'ai_available':  self.ai_service.is_available(),
            },
        }
