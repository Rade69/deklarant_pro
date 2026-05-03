# Arhitektura: docs/architecture/TARIFF_FACADE_REFACTORING.md

"""
TariffLLMWorker — QThread worker za batch prijedlog tarifnih brojeva putem LLM-a.

Pipeline:
  Korak 1: TariffFacade.suggest_fast()   — baza znanja (bez mreže, brzo)
  Korak 2: TariffFacade.rag_candidates() — kandidati iz zvanicna_tarifa (kao kontekst)
  Korak 3: LLMProvider.complete()        — jedan batch API poziv za preostale stavke

Batch LLM poziv (Korak 3) je namjerno odvojen od HybridTariffAgent koji radi
N pojedinačnih poziva. Za 40 stavki, jedan batch poziv je 40× jeftiniji.
"""

import logging
import re
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("deklarant_pro.agent.tariff_llm")


class TariffLLMWorker(QThread):
    """
    Poziva LLM u pozadini da predloži tarifne brojeve za grupu stavki.

    Signals:
        proposals_ready(list): Lista TariffProposal objekata
        error_occurred(str):   Poruka greške
    """

    proposals_ready = Signal(list)
    error_occurred  = Signal(str)

    _BATCH_SIZE = 40

    def __init__(self, items: list, parent=None):
        super().__init__(parent)
        self.items = items  # [(idx, InvoiceLine), ...]

    def run(self):
        try:
            from .llm_provider import LLMProvider, parse_llm_error

            provider = LLMProvider()
            if provider.active_provider() == "none":
                self.error_occurred.emit(
                    "Nema AI ključa. Dodaj GROQ_API_KEY, GEMINI_API_KEY ili OPENROUTER_API_KEY u .env."
                )
                return

            all_proposals = []
            for batch_start in range(0, len(self.items), self._BATCH_SIZE):
                batch = self.items[batch_start: batch_start + self._BATCH_SIZE]
                all_proposals.extend(self._process_batch(provider, batch))

            self.proposals_ready.emit(all_proposals)

        except Exception as e:
            import traceback
            from .llm_provider import parse_llm_error
            logger.error(f"Greška: {e}\n{traceback.format_exc()}")
            self.error_occurred.emit(parse_llm_error(e))

    def _process_batch(self, provider, batch: list) -> list:
        """
        Korak 1 → 2 → 3 za jedan batch stavki.
        Korak 1 i 2 idu kroz TariffFacade — docs/architecture/TARIFF_FACADE_REFACTORING.md
        """
        from services.tariff_facade import TariffFacade
        from gui.tabs.agent.agent_actions import TariffProposal

        facade   = TariffFacade.get_instance()
        resolved = []
        remaining = []

        # Korak 1: pre-filter putem baze znanja (Level 1, bez mreže)
        for idx, line in batch:
            naziv        = (getattr(line, "naziv_robe",    "") or "").strip()
            product_code = (getattr(line, "product_code",  "") or "").strip()

            fast = facade.suggest_fast(naziv, product_code)
            if fast and fast.confidence >= 0.85:
                resolved.append(TariffProposal(
                    line_index=idx,
                    naziv_robe=naziv[:60],
                    product_code=product_code,
                    proposed_tariff=fast.tarifni_broj,
                    confidence=fast.confidence,
                    source="baza_znanja",
                ))
                logger.debug(
                    f"MAPPING idx={idx}: '{naziv[:40]}' "
                    f"→ {fast.tarifni_broj} ({fast.confidence:.0%})"
                )
            else:
                remaining.append((idx, line))

        if not remaining:
            return resolved

        # Korak 2 + 3: preostale stavke — RAG kandidati + batch LLM poziv
        product_lines = []
        for idx, line in remaining:
            naziv        = (getattr(line, "naziv_robe",      "") or "").strip()
            product_code = (getattr(line, "product_code",    "") or "").strip()
            zemlja       = (getattr(line, "zemlja_porijekla", "") or "").strip()

            desc = naziv
            if product_code:
                desc += f" [kod: {product_code}]"
            if zemlja:
                desc += f" [zemlja: {zemlja}]"

            # Korak 2: kandidati iz zvanicna_tarifa kao kontekst za LLM
            candidates_text = ""
            if naziv:
                candidates = facade.rag_candidates(naziv, zemlja, limit=5)
                if candidates:
                    c_lines = [
                        f"  {c['tarifni_kod']} — {c['naziv_robe'][:70]}"
                        for c in candidates
                    ]
                    candidates_text = "\n  Kandidati iz tarife:\n" + "\n".join(c_lines)

            product_lines.append(f"{idx}|{desc}{candidates_text}")

        # Korak 3: jedan batch LLM poziv za sve preostale stavke
        products_text = "\n".join(product_lines)

        system_msg = (
            "Ti si asistent specijalizovan za klasifikaciju robe prema "
            "Harmonizovanom sistemu (HS) i carinskoj tarifi BiH. "
            "Tarifni broj UVIJEK piši kao SAMO CIFRE bez tačaka i razmaka "
            "(npr. 84713000, NE 8471.30.00). "
            "Odgovaraj SAMO u traženom formatu IDX|TARIFNI_BROJ|POUZDANOST|OBRAZLOŽENJE. "
            "Bez uvoda, bez zaključka."
        )
        user_msg = (
            "Ti si ekspert za carinsku tarifu Bosne i Hercegovine (TARIC/HS nomeklatura).\n"
            "Za svaki proizvod predloži odgovarajući tarifni broj.\n\n"
            "PRAVILA:\n"
            "- Tarifni broj ISKLJUČIVO cifre, BEZ tačaka (npr. 84713000)\n"
            "- Ako su navedeni kandidati iz tarife — BIRAŠ između njih\n"
            "- Ako nijedan kandidat ne odgovara — možeš predložiti drugi, ali SAMO ako si siguran\n"
            "- Format: IDX|TARIFNI_BROJ|POUZDANOST|OBRAZLOŽENJE\n"
            "- Jedan red po proizvodu, bez praznih redova\n\n"
            "PRIMJER:\n"
            "5|84713000|0.9|Prijenosno računalo\n"
            "12|62034231|0.85|Muške hlače od pamuka\n\n"
            f"LISTA PROIZVODA:\n{products_text}"
        )

        try:
            raw = provider.complete(
                [{"role": "system", "content": system_msg},
                 {"role": "user",   "content": user_msg}],
                max_tokens=1200,
                use_small_model=True,
            )
            return resolved + self._parse_response(raw, remaining)
        except Exception as e:
            logger.error(f"Batch LLM greška: {e}")
            return resolved

    def _parse_response(self, raw_text: str, batch: list) -> list:
        """Parsira LLM odgovor (IDX|TARIFNI_BROJ|POUZDANOST|OBRAZLOŽENJE) u TariffProposal listu."""
        from gui.tabs.agent.agent_actions import TariffProposal

        idx_map      = {idx: line for idx, line in batch}
        proposals    = []
        seen_indices = set()

        for raw_line in raw_text.strip().split("\n"):
            raw_line = raw_line.strip()
            if not raw_line or raw_line.startswith("#"):
                continue

            parts = raw_line.split("|")
            if len(parts) < 3:
                continue

            try:
                idx = int(parts[0].strip())
            except ValueError:
                continue

            if idx not in idx_map or idx in seen_indices:
                continue

            tariff = self._normalize_tariff(parts[1].strip())
            if not tariff:
                continue

            try:
                confidence = max(0.0, min(1.0, float(parts[2].strip())))
            except (ValueError, IndexError):
                confidence = 0.5

            explanation = parts[3].strip() if len(parts) > 3 else ""
            line        = idx_map[idx]

            proposals.append(TariffProposal(
                line_index=idx,
                naziv_robe=(getattr(line, "naziv_robe", "") or "")[:60],
                product_code=getattr(line, "product_code", "") or "",
                proposed_tariff=tariff,
                confidence=confidence,
                source="llm",
            ))
            seen_indices.add(idx)

            logger.debug(
                f"idx={idx}: '{getattr(line, 'naziv_robe', '')[:40]}' "
                f"→ {tariff} ({confidence:.0%}) — {explanation[:60]}"
            )

        logger.debug(f"Parsirano {len(proposals)}/{len(batch)} prijedloga")
        return proposals

    @staticmethod
    def _normalize_tariff(raw: str) -> str:
        """Samo cifre, min 6, max 10."""
        digits = re.sub(r"\D", "", raw)
        return digits[:10] if len(digits) >= 6 else ""
