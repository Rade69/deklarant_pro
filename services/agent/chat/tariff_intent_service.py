ï»¿"""
Tariff Intent Service Ã¢â‚¬â€ predlog, provjera i brisanje tarifnih brojeva.

Business logika za:
- Batch predlog tarifnih brojeva (istorija dobavljaÃ„Âa + lokalna baza + LLM fallback)
- Predlog po filter keyword-u
- Provjera tarifnog za konkretan naziv robe (HybridTariffAgent)
- Brisanje svih tarifnih brojeva
- IzvrÃ…Â¡enje popune tarifnih nakon potvrde

Ã°Å¸â€œâ€ž Detalji: memory/project_tariff_history_prediction.md
   scripts/CHANGES_2026-04-26.md
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class TariffProposal:
    """Predlog tarifnog broja za jednu stavku."""
    line_index: int
    naziv_robe: str
    product_code: str
    proposed_tariff: str
    confidence: float
    source: str  # "istorija" | "baza_znanja" | "rag" | "llm"
    source_detail: str = ""  # npr. ime dobavljaÃ„Âa, broj prethodnih upotreba


class TariffIntentService:
    """
    Service za tarifne operacije Ã¢â‚¬â€ nezavisan od GUI-a.
    Prima callbacks za UI interakcije.
    """

    def __init__(self, draft):
        self.draft = draft
        # Callback-i koje postavlja Controller
        self.on_activity: Optional[Callable[[str], None]] = None
        self.on_agent_message: Optional[Callable[[str], None]] = None
        self.on_set_pending: Optional[Callable[[Any], None]] = None
        self.on_refresh_faktura: Optional[Callable[[], None]] = None

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # BATCH PRIJEDLOG
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def propose_all(self) -> Optional[List[TariffProposal]]:
        """
        Analizira stavke bez tarifnog broja.
        Redosled: 1) istorija dobavljaÃ„Âa  2) lokalna baza znanja  3) LLM
        VraÃ„â€¡a predloge ili None ako su sve veÃ„â€¡ popunjene.
        """
        if not self.draft or not self.draft.invoice_lines:
            self._msg("Ã¢Å¡Â Ã¯Â¸Â Nema uÃ„Âitanih stavki u Faktura tabu.")
            return None

        bez_tarife = [
            (i, line) for i, line in enumerate(self.draft.invoice_lines)
            if not line.tarifni_broj or not line.tarifni_broj.strip()
        ]

        if not bez_tarife:
            self._msg("Ã¢Å“â€¦ Sve stavke veÃ„â€¡ imaju upisane tarifne brojeve.")
            return None

        # Ã¢â€â‚¬Ã¢â€â‚¬ 0. Dobavi ime dobavljaÃ„Âa za istorijsku proveru Ã¢â€â‚¬Ã¢â€â‚¬
        exporter_name = self._get_exporter_name()

        self._activity(f"Ã°Å¸â€Â TraÃ…Â¾im tarifne brojeve za {len(bez_tarife)} stavki...")

        from services.tariff_mapping_service import TariffMappingService
        from services.agent.tariff.tariff_suggestion_service import HybridMatchingService
        svc = TariffMappingService()
        hybrid = HybridMatchingService() if exporter_name else None
        proposals: List[TariffProposal] = []
        bez_lokalne: List[Tuple[int, Any]] = []

        # Ã¢â€â‚¬Ã¢â€â‚¬ Batch lookup po product_code (1 SQL umjesto N) Ã¢â€â‚¬Ã¢â€â‚¬
        all_codes = [getattr(l, 'product_code', '') or '' for _, l in bez_tarife]
        batch_hits = svc.find_batch_by_product_codes(all_codes)

        istorijskih = 0

        for idx, line in bez_tarife:
            # Ã¢â€â‚¬Ã¢â€â‚¬ 1. Prvo proveri istoriju dobavljaÃ„Âa Ã¢â€â‚¬Ã¢â€â‚¬
            if exporter_name and hybrid:
                hist_match = self._try_history_match(
                    hybrid, exporter_name, line.product_code, line.naziv_robe,
                    getattr(line, 'zemlja_porijekla', '')
                )
                if hist_match:
                    hist_match.line_index = idx
                    proposals.append(hist_match)
                    istorijskih += 1
                    continue

            # Ã¢â€â‚¬Ã¢â€â‚¬ 2. Batch hit po product_code Ã¢â€â‚¬Ã¢â€â‚¬
            code_key = (line.product_code or '').strip().upper()
            batch_mapping = batch_hits.get(code_key)
            if batch_mapping:
                proposals.append(TariffProposal(
                    line_index=idx,
                    naziv_robe=line.naziv_robe[:60],
                    product_code=line.product_code,
                    proposed_tariff=batch_mapping.tarifni_broj,
                    confidence=1.0,
                    source="baza_znanja"
                ))
                continue

            # Ã¢â€â‚¬Ã¢â€â‚¬ 3. Lokalna baza Ã¢â‚¬â€ fuzzy/vote za linije bez product_code hita Ã¢â€â‚¬Ã¢â€â‚¬
            mapping = svc.find_mapping(
                product_code=line.product_code,
                naziv_robe=line.naziv_robe,
                min_similarity=0.92
            )
            if mapping:
                proposals.append(TariffProposal(
                    line_index=idx,
                    naziv_robe=line.naziv_robe[:60],
                    product_code=line.product_code,
                    proposed_tariff=mapping.tarifni_broj,
                    confidence=mapping.similarity if hasattr(mapping, 'similarity') else 1.0,
                    source="baza_znanja"
                ))
            else:
                bez_lokalne.append((idx, line))

        if istorijskih:
            self._activity(
                f"Ã°Å¸â€œÅ¡ Istorija ({exporter_name}): {istorijskih} stavki reÃ…Â¡eno iz ranijih deklaracija"
            )

        return self._handle_llm_fallback(proposals, bez_lokalne, len(bez_tarife))

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # PRIJEDLOG PO FILTERU
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def propose_by_keyword(self, keyword: str) -> Optional[List[TariffProposal]]:
        """
        PredlaÃ…Â¾e tarifne brojeve za stavke Ã„Âiji naziv_robe sadrÃ…Â¾i keyword.
        Redosled: 1) istorija dobavljaÃ„Âa  2) lokalna baza  3) LLM
        """
        if not self.draft or not self.draft.invoice_lines:
            self._msg("Ã¢Å¡Â Ã¯Â¸Â Nema uÃ„Âitanih stavki u Faktura tabu.")
            return None

        kw = keyword.lower().strip()

        filtrirane = [
            (i, line) for i, line in enumerate(self.draft.invoice_lines)
            if kw in (getattr(line, 'naziv_robe', '') or '').lower()
        ]

        if not filtrirane:
            self._msg(f"Ã¢Å¡Â Ã¯Â¸Â Nema stavki Ã„Âiji naziv sadrÃ…Â¾i '{keyword}'.")
            return None

        # Ã¢â€â‚¬Ã¢â€â‚¬ 0. Dobavi ime dobavljaÃ„Âa Ã¢â€â‚¬Ã¢â€â‚¬
        exporter_name = self._get_exporter_name()

        self._activity(f"Ã°Å¸â€Â NaÃ„â€˜eno {len(filtrirane)} stavki s '{keyword}', traÃ…Â¾im tarifne...")

        from services.tariff_mapping_service import TariffMappingService
        from services.agent.tariff.tariff_suggestion_service import HybridMatchingService
        svc = TariffMappingService()
        hybrid = HybridMatchingService() if exporter_name else None
        proposals: List[TariffProposal] = []
        bez_lokalne: List[Tuple[int, Any]] = []

        # Ã¢â€â‚¬Ã¢â€â‚¬ Batch lookup po product_code (1 SQL umjesto N) Ã¢â€â‚¬Ã¢â€â‚¬
        all_codes = [getattr(l, 'product_code', '') or '' for _, l in filtrirane]
        batch_hits = svc.find_batch_by_product_codes(all_codes)

        istorijskih = 0

        for idx, line in filtrirane:
            naziv = (getattr(line, 'naziv_robe', '') or '').strip()
            product_code = (getattr(line, 'product_code', '') or '').strip()
            country = getattr(line, 'zemlja_porijekla', '') or ''

            # Ã¢â€â‚¬Ã¢â€â‚¬ 1. Prvo istorija dobavljaÃ„Âa Ã¢â€â‚¬Ã¢â€â‚¬
            if exporter_name and hybrid:
                hist_match = self._try_history_match(
                    hybrid, exporter_name, product_code, naziv, country
                )
                if hist_match:
                    hist_match.line_index = idx
                    proposals.append(hist_match)
                    istorijskih += 1
                    continue

            # Ã¢â€â‚¬Ã¢â€â‚¬ 2. Batch hit po product_code Ã¢â€â‚¬Ã¢â€â‚¬
            batch_mapping = batch_hits.get(product_code.upper())
            if batch_mapping:
                proposals.append(TariffProposal(
                    line_index=idx,
                    naziv_robe=naziv[:60],
                    product_code=product_code,
                    proposed_tariff=batch_mapping.tarifni_broj,
                    confidence=1.0,
                    source="baza_znanja"
                ))
                continue

            # Ã¢â€â‚¬Ã¢â€â‚¬ 3. Lokalna baza Ã¢â‚¬â€ fuzzy/vote za linije bez product_code hita Ã¢â€â‚¬Ã¢â€â‚¬
            mapping = svc.find_mapping(
                product_code=product_code,
                naziv_robe=naziv,
                min_similarity=0.92
            )
            if mapping:
                proposals.append(TariffProposal(
                    line_index=idx,
                    naziv_robe=naziv[:60],
                    product_code=product_code,
                    proposed_tariff=mapping.tarifni_broj,
                    confidence=mapping.similarity if hasattr(mapping, 'similarity') else 1.0,
                    source="baza_znanja"
                ))
            else:
                bez_lokalne.append((idx, line))

        if istorijskih:
            self._activity(
                f"Ã°Å¸â€œÅ¡ Istorija ({exporter_name}): {istorijskih} stavki reÃ…Â¡eno iz ranijih deklaracija"
            )

        return self._handle_llm_fallback(proposals, bez_lokalne, len(filtrirane))

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # ISTORIJSKI MATCHING (dobavljaÃ„Â Ã¢â€ â€™ tarifni broj)
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def _get_exporter_name(self) -> str:
        """IzvlaÃ„Âi ime dobavljaÃ„Âa (exporter) iz drafta."""
        if self.draft and hasattr(self.draft, 'exporter') and self.draft.exporter:
            name = getattr(self.draft.exporter, 'name', '') or ''
            if name.strip():
                return name.strip()
        if self.draft and self.draft.invoice_lines:
            for line in self.draft.invoice_lines:
                if hasattr(line, 'exporter') and line.exporter:
                    name = getattr(line.exporter, 'name', '') or ''
                    if name.strip():
                        return name.strip()
        return ""

    def _try_history_match(
        self, hybrid, exporter_name: str, product_code: str, naziv_robe: str, country: str
    ) -> Optional[TariffProposal]:
        """
        PokuÃ…Â¡aj da naÃ„â€˜eÃ…Â¡ tarifni broj iz istorije dobavljaÃ„Âa.
        Koristi HybridMatchingService sa teÃ…Â¾inom na istorijskom match-u.
        """
        try:
            match = hybrid.find_hybrid_mapping(
                product_code=product_code,
                naziv_robe=naziv_robe,
                supplier=exporter_name,
                country=country,
                min_confidence=0.75
            )
            if match and match.confidence >= 0.82:
                detail = f"{exporter_name}, {match.explanation}"
                return TariffProposal(
                    line_index=-1,  # postaviÃ„â€¡e se u pozivaocu
                    naziv_robe=naziv_robe[:60],
                    product_code=product_code,
                    proposed_tariff=match.tariff_mapping.tarifni_broj,
                    confidence=match.confidence,
                    source="istorija",
                    source_detail=detail
                )
        except Exception:
            pass  # Silent Ã¢â‚¬â€ istorijski match nije kritiÃ„Âan
        return None

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # LLM FALLBACK
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def _handle_llm_fallback(self, local_proposals, bez_lokalne, ukupno_bez):
        """PokuÃ…Â¡aj LLM za preostale stavke."""
        if not bez_lokalne:
            return self._show_proposals(local_proposals, [], ukupno_bez)

        self._activity(
            f"Ã¢Å“â€¦ Lokalna baza: {len(local_proposals)} prijedloga. "
            f"Ã°Å¸Â¤â€“ Pitam AI za preostalih {len(bez_lokalne)} stavki..."
        )

        # Pokreni LLM worker Ã¢â‚¬â€ callback Ã„â€¡e show_results
        from gui.tabs.agent.widgets.tariff_llm_worker import TariffLLMWorker
        worker = TariffLLMWorker(bez_lokalne, parent=self._view_ref())
        worker.proposals_ready.connect(
            lambda llm_p: self._show_proposals(local_proposals, llm_p, ukupno_bez)
        )
        worker.error_occurred.connect(
            lambda _: self._show_proposals(local_proposals, [], ukupno_bez)
        )
        worker.finished.connect(worker.deleteLater)

        # SaÃ„Âuvaj referencu na controller-u da GC ne ubije
        ctrl = getattr(self, '_controller_ref', None)
        if ctrl:
            if not hasattr(ctrl, '_tariff_workers'):
                ctrl._tariff_workers = []
            ctrl._tariff_workers.append(worker)
            worker.finished.connect(
                lambda: ctrl._tariff_workers.remove(worker) if worker in ctrl._tariff_workers else None
            )
        worker.start()
        return None  # LLM je async Ã¢â‚¬â€ rezultat ide kroz callback

    def _show_proposals(self, local_proposals, llm_proposals, ukupno_bez):
        """PrikaÃ…Â¾i kombinirane prijedloge korisniku."""
        svi = local_proposals + llm_proposals

        if not svi:
            self._msg(
                f"Ã¢Å¡Â Ã¯Â¸Â Nisam uspio naÃ„â€¡i prijedloge za <b>{ukupno_bez}</b> stavki "
                f"ni u lokalnoj bazi ni putem AI-a.<br>"
                f"PokuÃ…Â¡aj pretraÃ…Â¾ivanjem tarifne tarife ili ruÃ„Ânim unosom."
            )
            return svi

        linije = []
        for p in svi:
            pct = int(p.confidence * 100)
            if p.source == "istorija":
                izvor = "Ã°Å¸â€œÅ¡ istorija"
                detail = f" Ã¢â‚¬â€ {p.source_detail}" if p.source_detail else ""
            elif p.source == "baza_znanja":
                izvor = "Ã°Å¸â€œÅ¡ baza"
                detail = ""
            else:
                izvor = "Ã°Å¸Â¤â€“ AI"
                detail = ""
            linije.append(
                f"&nbsp;&nbsp;Ã¢â‚¬Â¢ <b>{p.proposed_tariff}</b> Ã¢â‚¬â€ {p.naziv_robe} "
                f"<small>({izvor}, {pct}% pouzdanost{detail})</small>"
            )

        nema = ukupno_bez - len(svi)
        napomena = f"<br><small>Ã¢Å¡Â Ã¯Â¸Â Za {nema} stavki nije naÃ„â€˜en prijedlog.</small>" if nema else ""

        # Postavi pending akciju
        if self.on_set_pending:
            from gui.tabs.agent.agent_actions import PendingAction
            self.on_set_pending(PendingAction(
                action_type="fill_tariff",
                proposals=svi,
                description=f"UpiÃ…Â¡i {len(svi)} tarifnih brojeva"
            ))

        self._msg(
            f"Ã°Å¸â€œâ€¹ Prijedlozi za <b>{len(svi)}</b> od {ukupno_bez} stavki:<br><br>"
            + "<br>".join(linije)
            + napomena
            + "<br><br>Ã¢Å“ÂÃ¯Â¸Â <b>Upisujem u tabelu? Odgovori: Da / Ne</b>"
        )
        return svi

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # IZVRÃ…Â ENJE POPUNE
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def execute_fill(self, proposals, chat=None):
        """UpiÃ…Â¡i predloÃ…Â¾ene tarifne brojeve u draft i osvjeÃ…Â¾i Faktura tab."""
        from PySide6.QtWidgets import QApplication

        upisano = 0
        for p in proposals:
            line = self.draft.invoice_lines[p.line_index]
            line.tarifni_broj = p.proposed_tariff
            upisano += 1

        if self.on_refresh_faktura:
            QApplication.processEvents()
            self.on_refresh_faktura()

        self._msg(
            f"Ã¢Å“â€¦ <b>Upisano {upisano} tarifnih brojeva</b> u Faktura tab.<br>"
            f"Provjeri tabelu i korigiÃ…Â¡i ako je potrebno."
        )

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # BRISANJE
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def delete_all(self):
        """ObriÃ…Â¡i sve tarifne brojeve iz draft.invoice_lines."""
        from PySide6.QtWidgets import QApplication

        if not self.draft or not self.draft.invoice_lines:
            self._msg("Ã¢Å¡Â Ã¯Â¸Â Nema uÃ„Âitanih stavki.")
            return

        obrisano = 0
        for line in self.draft.invoice_lines:
            if getattr(line, 'tarifni_broj', None):
                line.tarifni_broj = ''
                obrisano += 1

        if self.on_refresh_faktura:
            QApplication.processEvents()
            self.on_refresh_faktura()

        self._msg(f"Ã¢Å“â€¦ Obrisano <b>{obrisano}</b> tarifnih brojeva iz Faktura taba.")

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # PRIJEDLOG TARIFNOG ZA KONKRETAN NAZIV (DeepSeek)
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def check_tariff_for_name(self, naziv_robe: str):
        """
        PredlaÃ…Â¾i tarifni broj za naziv robe.

        Tok:
        1. Lokalna baza znanja (TariffMappingService fuzzy match)
        2. RAG pretraga zvanicna_tarifa.db
        3. DeepSeek direktni poziv sa HS kontekstom iz RAG-a
        """
        self._activity(f"Ã°Å¸â€Â TraÃ…Â¾im tarifni za: {naziv_robe}")

        from PySide6.QtCore import QThread, Signal

        svc_ref = self

        class _Worker(QThread):
            done = Signal(str)
            error = Signal(str)

            def __init__(self_, naziv):
                super().__init__()
                self_._naziv = naziv

            def run(self_):
                try:
                    naziv = self_._naziv

                    # DeepSeek direktno Ã¢â‚¬â€ bez RAG, bez baze kao konteksta
                    # RAG i baza znanja sidre model na pogreÃ…Â¡an tarif.
                    # DeepSeek poznaje HS nomenklaturu Ã¢â‚¬â€ pustiti ga da klasificira slobodno.
                    from gui.tabs.agent.widgets.llm_provider import LLMProvider
                    provider = LLMProvider()

                    system_msg = (
                        "Si ekspert za carinsku tarifu (Harmonizovani sistem Ã¢â‚¬â€ HS/TARIC). "
                        "Odgovaraj na srpskom jeziku, kratko i precizno.\n"
                        "PRAVILA:\n"
                        "1. Uvijek razmotri materijal (plastika, sintetiÃ„Âka vlakna, Ã„Âelik, guma...), "
                        "funkciju i upotrebu Ã¢â‚¬â€ ne samo doslovan prijevod naziva.\n"
                        "2. PredloÃ…Â¾i opcije iz RAZLIÃ„Å’ITIH poglavlja HS-a. "
                        "Npr. isti predmet moÃ…Â¾e biti klasificiran u poglavlju 39 (plastika), "
                        "56 (sintetiÃ„Âka vlakna/konopci), 73 (Ã„Âelik) Ã¢â‚¬â€ sve ovisi o materijalu.\n"
                        "3. Nikada ne predlaÃ…Â¾aj samo jedno poglavlje. "
                        "Ako si nesiguran, navedite opcije za razliÃ„Âite materijale.\n"
                        "4. Format odgovora (svaka opcija u novom redu):\n"
                        "**XXXXXXXX** Ã¢â‚¬â€ [naziv iz HS tarife] Ã¢â‚¬â€ [materijal i zaÃ…Â¡to odgovara]\n"
                        "5. Tarifni broj = 8 cifara bez taÃ„Âaka. Bez uvoda, bez zakljuÃ„Âka."
                    )

                    user_msg = (
                        f'PredloÃ…Â¾i tarifni HS broj za robu: "{naziv}"\n'
                        f'Daj 4-5 opcija iz RAZLIÃ„Å’ITIH poglavlja: '
                        f'razmisli o sintetiÃ„Âkim vlaknima, plastici, gumi, metalu, '
                        f'dijelovima maÃ…Â¡ina Ã¢â‚¬â€ i objasni za koji materijal/upotrebu odgovara svaki.'
                    )

                    messages = [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ]
                    result = provider.complete(messages, max_tokens=350, use_small_model=False)
                    self_.done.emit(result.strip())

                except Exception as e:
                    self_.error.emit(str(e))

        worker = _Worker(naziv_robe)

        def _on_done(text):
            svc_ref._msg(
                f"<b>Ã°Å¸â€œÅ’ Prijedlog tarifnog za: {naziv_robe}</b><br><br>"
                f"{text}<br><br>"
                f"Ã°Å¸â€™Â¾ Da saÃ„ÂuvaÃ…Â¡ u bazu znanja, reci npr.:<br>"
                f"<i>Zapamti 84713000 za {naziv_robe}</i>"
            )
            svc_ref._activity(f"Ã¢Å“â€¦ Prijedlog tarifnog za '{naziv_robe}' gotov")

        def _on_error(err):
            svc_ref._msg(f"Ã¢ÂÅ’ GreÃ…Â¡ka pri traÃ…Â¾enju tarifnog: {err}")

        worker.done.connect(_on_done)
        worker.error.connect(_on_error)
        worker.finished.connect(worker.deleteLater)

        ctrl = getattr(self, '_controller_ref', None)
        if ctrl:
            if not hasattr(ctrl, '_tariff_check_workers'):
                ctrl._tariff_check_workers = []
            ctrl._tariff_check_workers.append(worker)
        worker.start()

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # SNIMANJE U BAZU ZNANJA
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def learn_tariff(self, naziv_robe: str, tarifni_broj: str):
        """
        SaÃ„Âuvaj mapiranje naziv_robe Ã¢â€ â€™ tarifni_broj u bazu znanja.
        Korisnik eksplicitno kaÃ…Â¾e da je tarifni taÃ„Âan.
        """
        import re
        # Normalizuj Ã¢â‚¬â€ samo cifre, 8 znakova
        digits = re.sub(r'\D', '', tarifni_broj)[:8]
        if len(digits) != 8:
            self._msg(
                f"Ã¢Å¡Â Ã¯Â¸Â Tarifni broj mora imati 8 cifara (upisano: <b>{tarifni_broj}</b>).<br>"
                f"Primjer: <i>Zapamti 84713000 za laptop</i>"
            )
            return

        # PronaÃ„â€˜i product_code ako roba postoji u draft.invoice_lines
        product_code = ""
        if self.draft and self.draft.invoice_lines:
            kw = naziv_robe.lower().strip()
            for line in self.draft.invoice_lines:
                if kw in (getattr(line, 'naziv_robe', '') or '').lower():
                    product_code = getattr(line, 'product_code', '') or ''
                    break

        try:
            from services.tariff_mapping_service import TariffMappingService
            svc = TariffMappingService()

            # ObriÃ…Â¡i sve stare zapise za ovaj naziv/product_code Ã¢â‚¬â€ korisnik potvrÃ„â€˜uje taÃ„Âan tarif.
            # Bez brisanja, stari pogreÃ…Â¡ni zapis (sa visokim usage_count) pobijedi pri auto-popuni.
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM catalogs.product_tariff_mapping
                        WHERE naziv_robe ILIKE %s
                           OR (product_code = %s AND product_code != '')
                    """, (f"%{naziv_robe}%", product_code or "__NONE__"))

            ok = svc.save_mapping(
                product_code=product_code,
                naziv_robe=naziv_robe,
                tarifni_broj=digits,
            )
            if ok:
                self._msg(
                    f"Ã¢Å“â€¦ <b>ZapamÃ„â€¡eno!</b> <code>{digits}</code> Ã¢â€ â€™ <b>{naziv_robe}</b><br>"
                    f"<small>SaÃ„Âuvano u bazu znanja Ã¢â‚¬â€ koristiÃ„â€¡e se automatski pri sljedeÃ„â€¡em uvozu.</small>"
                )
            else:
                self._msg(f"Ã¢Å¡Â Ã¯Â¸Â Nije saÃ„Âuvano Ã¢â‚¬â€ provjeri tarifni broj <b>{digits}</b>.")
        except Exception as e:
            self._msg(f"Ã¢ÂÅ’ GreÃ…Â¡ka pri snimanju: {e}")

    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # HELPERS
    # Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def _msg(self, text: str):
        if self.on_agent_message:
            self.on_agent_message(text)

    def _activity(self, text: str):
        if self.on_activity:
            self.on_activity(text)

    def _view_ref(self):
        """VraÃ„â€¡a view referencu za parent widget."""
        ctrl = getattr(self, '_controller_ref', None)
        if ctrl and hasattr(ctrl, 'view'):
            return ctrl.view
        return None


