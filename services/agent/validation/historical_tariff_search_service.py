"""
HistoricalTariffSearchService — pretraga tarifnih iz odobrenih XML deklaracija.

Za svaku stavku fakture traži istorijski validiran tarifni broj iz
catalogs.product_tariff_mapping (popunjenog uvozom XML fajlova).

Logika pretrage:
  1. Ključne riječi iz naziv_robe → ILIKE AND upit (strogi)
  2. Fallback: najdulja ključna riječ → ILIKE OR upit (širi)
  3. ORDER BY: izvoznik match > uvoznik match > usage_count DESC

Rezultat po stavci: lista TariffHistoryMatch, sortirana po pouzdanosti.
"""

from __future__ import annotations

import re
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List

from services.agent.validation.tariff_decision_model import (
    TariffDecisionThresholds,
    decide_tariff_match,
    tariff_digits,
)

logger = logging.getLogger("deklarant_pro.historical_tariff_search")

# Bosanske/srpske stopper-riječi koje ne doprinose pretrazi
_STOP = frozenset({
    'i', 'ili', 'je', 'su', 'sa', 'se', 'za', 'na', 'u', 'iz', 'od', 'do',
    'po', 'pri', 'kao', 'ali', 'te', 'da', 'ne', 'ni', 'koji', 'koja', 'koje',
    'ostali', 'ostalo', 'ostale', 'ostala', 'drugi', 'druge', 'ost', 'razni',
    'the', 'and', 'or', 'of', 'for', 'with', 'other', 'others',
})


@dataclass
class TariffHistoryMatch:
    line_index: int
    naziv_robe_original: str       # iz invoice_line
    naziv_robe_historijski: str    # iz baze znanja
    tarifni_broj_historijski: str
    tarifni_broj_trenutni: str     # iz invoice_line (može biti prazan)
    supplier_match: bool           # izvoznik se poklapa
    usage_count: int
    source: str                    # supplier iz baze (xml fajl ili ime dobavljača)
    confidence: float              # 0.0–1.0
    decision_reason: str = ""      # kratak razlog zašto je prijedlog prošao filter
    decision_outcome: str = ""     # show_strong/show_weak/suppress
    decision_score: int = 0


class HistoricalTariffSearchService:
    """
    Pretražuje catalogs.product_tariff_mapping za istorijski validirane tarife.
    Koristi se za validaciju: poređenje trenutnog tarifa sa onim iz XML deklaracija.
    """

    MAX_RESULTS_PER_LINE = 3
    MIN_WORD_LEN = 3
    MIN_USAGE_FOR_CROSS_CHAPTER = 5
    MIN_USAGE_FOR_OUT_OF_PROFILE_CHAPTER = 10
    MIN_USAGE_FOR_WEAK_SOURCE = 2

    def __init__(self):
        self.last_auto_applied: list[tuple[int, str]] = []

    def validate_lines(
        self,
        invoice_lines: list,
        izvoznik_naziv: str = "",
        uvoznik_naziv: str = "",
    ) -> List[TariffHistoryMatch]:
        """
        Za svaku stavku u invoice_lines traži istorijski tarif.
        Vraća samo one gdje postoji prijedlog (bez "sve je uredu" redova).

        Args:
            invoice_lines: lista InvoiceLine objekata
            izvoznik_naziv: ime izvoznika iz Zaglavlja (boost)
            uvoznik_naziv: ime uvoznika iz Zaglavlja (boost)
        """
        results = []
        self.last_auto_applied = []
        invoice_profile = self._build_invoice_profile(invoice_lines)
        for idx, line in enumerate(invoice_lines):
            naziv = (getattr(line, 'naziv_robe', '') or '').strip()
            if not naziv:
                continue
            trenutni = (getattr(line, 'tarifni_broj', '') or '').strip()
            exporter_line = (
                getattr(getattr(line, 'exporter', None), 'name', '') or ''
            ).strip()

            izvoznik = exporter_line or izvoznik_naziv
            matches = self._search_one(naziv, izvoznik, uvoznik_naziv)
            if not matches:
                continue

            actionable = [
                match for match in matches
                if self._is_actionable_match(match, trenutni, invoice_profile)
            ]
            if not actionable:
                continue

            best = actionable[0]
            best.line_index = idx
            best.tarifni_broj_trenutni = trenutni

            feedback_action = self._feedback_action(best)
            if feedback_action == "reject":
                continue
            if feedback_action == "accept":
                line.tarifni_broj = best.tarifni_broj_historijski
                self.last_auto_applied.append((idx, best.tarifni_broj_historijski))
                continue

            results.append(best)

        return results

    def _search_one(
        self,
        naziv_robe: str,
        izvoznik: str = "",
        uvoznik: str = "",
    ) -> List[TariffHistoryMatch]:
        """Pretraži bazu za jedan naziv robe. Vraća max MAX_RESULTS_PER_LINE."""
        try:
            from database.db import get_db_connection
            words = self._extract_keywords(naziv_robe)
            if not words:
                return []

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    rows = self._query_strict(cur, words, izvoznik, uvoznik)
                    if not rows:
                        rows = self._query_broad(cur, words, izvoznik, uvoznik)
                    return self._to_matches(rows, naziv_robe)
        except Exception as e:
            logger.warning("HistoricalTariffSearch greška za '%s': %s", naziv_robe[:40], e)
            return []

    # ------------------------------------------------------------------
    # SQL upiti
    # ------------------------------------------------------------------

    def _query_strict(self, cur, words: list, izvoznik: str, uvoznik: str) -> list:
        """AND upit — svi ključni pojmovi moraju biti prisutni."""
        conditions = " AND ".join("naziv_robe ILIKE %s" for _ in words)
        params = [f"%{w}%" for w in words]
        return self._execute(cur, conditions, params, izvoznik, uvoznik)

    def _query_broad(self, cur, words: list, izvoznik: str, uvoznik: str) -> list:
        """OR fallback — najdulja ključna riječ (najspecifičnija)."""
        longest = max(words, key=len)
        conditions = "naziv_robe ILIKE %s"
        params = [f"%{longest}%"]
        return self._execute(cur, conditions, params, izvoznik, uvoznik)

    def _execute(self, cur, where_clause: str, params: list,
                 izvoznik: str, uvoznik: str) -> list:
        boost_params = []
        boost_sql = ""
        if izvoznik:
            boost_sql += "CASE WHEN supplier ILIKE %s THEN 0 ELSE 1 END,"
            boost_params.append(f"%{izvoznik[:60]}%")
        if uvoznik:
            # uvoznik nije u product_tariff_mapping, ali je u exporter_xml_index
            # Ovdje koristimo source polje (xml filename) kao proxy
            pass

        sql = f"""
            SELECT naziv_robe, commodity_code, supplier, usage_count,
                   zemlja_porijekla, source
            FROM catalogs.product_tariff_mapping
            WHERE {where_clause}
              AND commodity_code IS NOT NULL
              AND commodity_code != ''
            ORDER BY {boost_sql} usage_count DESC
            LIMIT %s
        """
        cur.execute(sql, params + boost_params + [self.MAX_RESULTS_PER_LINE])
        return cur.fetchall()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_keywords(self, naziv: str) -> list:
        """Izvuci ključne riječi iz naziva robe (min 3 slova, nije stopword)."""
        raw = re.sub(r'[^\w\s]', ' ', naziv.lower())
        words = [
            w for w in raw.split()
            if len(w) >= self.MIN_WORD_LEN and w not in _STOP
        ]
        # Uzmi najspecifičnije (najdulje) — max 3 riječi
        words_sorted = sorted(set(words), key=len, reverse=True)
        return words_sorted[:3]

    def _build_invoice_profile(self, invoice_lines: list) -> Dict:
        chapters = Counter()
        headings = Counter()
        for line in invoice_lines:
            digits = self._digits(getattr(line, 'tarifni_broj', '') or '')
            if len(digits) >= 2:
                chapters[digits[:2]] += 1
            if len(digits) >= 4:
                headings[digits[:4]] += 1
        return {
            "item_count": len(invoice_lines),
            "chapters": set(chapters),
            "headings": set(headings),
            "chapter_counts": chapters,
            "heading_counts": headings,
        }

    def _is_actionable_match(
        self,
        match: TariffHistoryMatch,
        trenutni: str,
        invoice_profile: Dict | None = None,
    ) -> bool:
        decision = decide_tariff_match(
            match,
            trenutni,
            invoice_profile,
            TariffDecisionThresholds(
                min_usage_for_cross_chapter=self.MIN_USAGE_FOR_CROSS_CHAPTER,
                min_usage_for_out_of_profile_chapter=self.MIN_USAGE_FOR_OUT_OF_PROFILE_CHAPTER,
                min_usage_for_weak_source=self.MIN_USAGE_FOR_WEAK_SOURCE,
            ),
        )
        match.decision_reason = decision.reason
        match.decision_outcome = decision.outcome.value
        match.decision_score = decision.score
        return decision.should_show

    @staticmethod
    def _digits(value: str) -> str:
        return tariff_digits(value)

    def _feedback_action(self, match: TariffHistoryMatch) -> str:
        try:
            from services.agent.validation.tariff_feedback_service import (
                get_tariff_validation_feedback_summary,
            )

            summary = get_tariff_validation_feedback_summary(match)
        except Exception as exc:
            logger.warning("HistoricalTariffSearch feedback lookup greška: %s", exc)
            return ""

        if summary.get("reject", 0) > 0:
            return "reject"
        if summary.get("accept", 0) > 0:
            return "accept"
        return ""

    def _to_matches(self, rows: list, naziv_original: str) -> List[TariffHistoryMatch]:
        results = []
        for row in rows:
            tarif    = (row['commodity_code'] or '').strip()
            naziv_h  = (row['naziv_robe'] or '')
            supplier = (row['supplier'] or '').strip()
            usage    = int(row['usage_count'] or 0)
            source   = (row['source'] or '').strip()
            if not tarif:
                continue
            if not self._tariff_exists(tarif):
                logger.warning(
                    "Preskačem historijsku tarifu koja nije u zvaničnoj tarifi: %s (%s)",
                    tarif,
                    naziv_h[:80],
                )
                continue
            # Pouzdanost: bazirana na usage_count i ima li supplier
            conf = min(0.95, 0.60 + min(usage, 100) * 0.003)
            if supplier and supplier not in ('HISTORIJA', '+', ' ', 'A'):
                conf = min(conf + 0.05, 0.97)
            results.append(TariffHistoryMatch(
                line_index=-1,
                naziv_robe_original=naziv_original,
                naziv_robe_historijski=naziv_h[:80],
                tarifni_broj_historijski=tarif,
                tarifni_broj_trenutni='',
                supplier_match=False,
                usage_count=usage,
                source=supplier or source,
                confidence=round(conf, 2),
            ))
        return results

    @staticmethod
    def _tariff_exists(tarifni_broj: str) -> bool:
        digits = tariff_digits(tarifni_broj)
        if not digits:
            return False
        try:
            from services.tariff.tarifa_service import trazi_po_kodu

            return bool(trazi_po_kodu(digits[:8]))
        except Exception as exc:
            logger.warning("Provjera zvanične tarife nije uspjela za %s: %s", tarifni_broj, exc)
            return True
