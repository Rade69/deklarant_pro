"""
TariffLLMWorker - QThread worker za batch prijedlog tarifnih brojeva putem LLM-a.

Koristi LLMProvider (Groq → Gemini fallback).
"""

import logging
import re
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("asycuda_pro.agent.tariff_llm")


class TariffLLMWorker(QThread):
    """
    Poziva LLM u pozadini da predloži tarifne brojeve za grupu stavki.

    Signals:
        proposals_ready(list): Lista TariffProposal objekata
        error_occurred(str):   Poruka greške
    """

    proposals_ready = Signal(list)
    error_occurred = Signal(str)

    _BATCH_SIZE = 40

    def __init__(self, items: list, parent=None):
        super().__init__(parent)
        self.items = items  # [(idx, InvoiceLine), ...]

    def run(self):
        try:
            from .llm_provider import LLMProvider, parse_llm_error

            provider = LLMProvider()
            if provider.active_provider() == "none":
                self.error_occurred.emit("Nema AI ključa. Dodaj GROQ_API_KEY ili GEMINI_API_KEY u .env.")
                return

            all_proposals = []
            for batch_start in range(0, len(self.items), self._BATCH_SIZE):
                batch = self.items[batch_start: batch_start + self._BATCH_SIZE]
                proposals = self._process_batch(provider, batch)
                all_proposals.extend(proposals)

            self.proposals_ready.emit(all_proposals)

        except Exception as e:
            import traceback
            from .llm_provider import parse_llm_error
            logger.error(f"Greška: {e}\n{traceback.format_exc()}")
            self.error_occurred.emit(parse_llm_error(e))

    def _process_batch(self, provider, batch: list) -> list:
        """Pošalje jedan batch stavki LLM-u i parsira odgovor."""
        # KORAK 1: Pre-filter putem TariffMappingService
        resolved = []
        remaining = []

        try:
            from services.tariff_mapping_service import TariffMappingService
            mapping_service = TariffMappingService()
        except Exception:
            mapping_service = None

        for idx, line in batch:
            naziv = (getattr(line, 'naziv_robe', '') or '').strip()
            product_code = (getattr(line, 'product_code', '') or '').strip()

            # Provjeri mapping samo ako imamo naziv robe
            mapping_result = None
            if mapping_service and naziv:
                try:
                    mapping_result = mapping_service.find_mapping(
                        product_code=product_code,
                        naziv_robe=naziv,
                        min_similarity=0.70
                    )
                except Exception:
                    pass

            # Ako mapping ima confidence >= 0.85, dodaj u resolved
            if mapping_result and hasattr(mapping_result, 'similarity') and mapping_result.similarity >= 0.85:
                from gui.tabs.agent.agent_actions import TariffProposal

                resolved.append(TariffProposal(
                    line_index=idx,
                    naziv_robe=naziv[:60],
                    product_code=product_code,
                    proposed_tariff=mapping_result.tarifni_broj,
                    confidence=mapping_result.similarity,
                    source="baza_znanja"
                ))
                logger.debug(
                    f"MAPPING idx={idx}: '{naziv[:40]}' "
                    f"→ {mapping_result.tarifni_broj} ({mapping_result.similarity:.0%})"
                )
            else:
                remaining.append((idx, line))

        # Ako su sve stavke riješene mappingom, vrati odmah
        if not remaining:
            return resolved

        # KORAK 2: Preostale stavke idu kroz RAG + LLM
        try:
            from services.agent.tariff_rag_service import TariffRAGService
            rag = TariffRAGService()
        except Exception:
            rag = None

        product_lines = []
        for idx, line in remaining:
            naziv = (getattr(line, 'naziv_robe', '') or '').strip()
            product_code = (getattr(line, 'product_code', '') or '').strip()
            zemlja = (getattr(line, 'zemlja_porijekla', '') or '').strip()

            desc = naziv
            if product_code:
                desc = f"{desc} [kod: {product_code}]"
            if zemlja:
                desc = f"{desc} [zemlja: {zemlja}]"

            # Dohvati kandidate iz zvanicna_tarifa
            candidates_text = ""
            if rag and naziv:
                try:
                    candidates = rag.search_official(naziv, limit=5)
                    if candidates:
                        c_lines = [
                            f"  {c['tarifni_kod']} — {c['naziv_robe'][:70]}"
                            for c in candidates
                        ]
                        candidates_text = "\n  Kandidati iz tarife:\n" + "\n".join(c_lines)
                except Exception:
                    pass

            product_lines.append(f"{idx}|{desc}{candidates_text}")

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
            "- Ako su navedeni kandidati iz tarife — BIRAŠ između njih (ne izmišljaš novi kod)\n"
            "- Ako nijedan kandidat ne odgovara — možeš predložiti drugi, ali SAMO ako si siguran\n"
            "- Format: IDX|TARIFNI_BROJ|POUZDANOST|OBRAZLOŽENJE\n"
            "- Jedan red po proizvodu, bez praznih redova\n\n"
            "PRIMJER:\n"
            "5|84713000|0.9|Prijenosno računalo\n"
            "12|62034231|0.85|Muške hlače od pamuka\n\n"
            f"LISTA PROIZVODA:\n{products_text}"
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        try:
            raw_text = provider.complete(messages, max_tokens=1200, use_small_model=True)
            llm_proposals = self._parse_response(raw_text, remaining)
            return resolved + llm_proposals
        except Exception as e:
            logger.error(f"Batch greška: {e}")
            return resolved

    def _parse_response(self, raw_text: str, batch: list) -> list:
        """Parsira LLM odgovor u listu TariffProposal objekata."""
        from gui.tabs.agent.agent_actions import TariffProposal

        idx_map = {idx: line for idx, line in batch}
        proposals = []
        seen_indices = set()

        for raw_line in raw_text.strip().split('\n'):
            raw_line = raw_line.strip()
            if not raw_line or raw_line.startswith('#'):
                continue

            parts = raw_line.split('|')
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
            line = idx_map[idx]

            proposals.append(TariffProposal(
                line_index=idx,
                naziv_robe=(getattr(line, 'naziv_robe', '') or '')[:60],
                product_code=getattr(line, 'product_code', '') or '',
                proposed_tariff=tariff,
                confidence=confidence,
                source="llm"
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
        digits = re.sub(r'\D', '', raw)
        if len(digits) < 6:
            return ''
        return digits[:10]
