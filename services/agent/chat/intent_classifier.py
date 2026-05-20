"""
IntentClassifier — Klasifikacija namjere korisnikove chat poruke.

Koristi DeepSeek (brz, veliki kontekst) da prepozna šta korisnik želi
za poruke vezane za tarifne brojeve.

Tip namjere:
  BATCH_TARIFF  — popuni tarife za SVE stavke
  SINGLE_TARIFF — predloži/provjeri tarif za jednu konkretnu stavku
  ALT_TARIFF    — korisnik nije zadovoljan, traži ALTERNATIVNI tarif za stavku
  QUERY         — informativni upit (ne treba akcija)
  OTHER         — sve ostalo (idi na standardni LLM chat)

Autor: Radovan + Claude
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """Rezultat klasifikacije namjere."""
    intent: str             # BATCH_TARIFF | SINGLE_TARIFF | ALT_TARIFF | QUERY | OTHER
    item_query: str = ""    # Naziv/opis stavke ako je pomenut
    item_ordinal: Optional[int] = None  # Redni broj stavke ako je pomenut
    confidence: float = 1.0
    raw: str = ""           # Sirovi LLM odgovor (za debug)


SYSTEM_PROMPT = """\
Si pomoćnik za klasifikaciju namjere u carinskom softveru.
Analiziraj poruku korisnika i odgovori ISKLJUČIVO validnim JSON objektom — bez ikakvog drugog teksta.

Tipovi namjere:
- BATCH_TARIFF: traži tarifne za SVE stavke / popuni sve / batch (bez specifičnog naziva robe)
- SINGLE_TARIFF: traži tarif za jednu konkretnu stavku (po imenu ili broju)
- ALT_TARIFF: nije zadovoljan postojećim tarifom, traži DRUGI/ALTERNATIVNI tarif za konkretnu stavku
- QUERY: samo pita/provjerava bez zahtjeva za akcijom
- OTHER: sve ostalo

Format odgovora (samo JSON):
{"intent": "...", "item_query": "naziv stavke ili ''", "item_ordinal": null}

Primjeri:
Poruka: "popuni sve tarifne" → {"intent":"BATCH_TARIFF","item_query":"","item_ordinal":null}
Poruka: "predloži tarif za startno uže" → {"intent":"SINGLE_TARIFF","item_query":"startno uže","item_ordinal":null}
Poruka: "73121081 nije tačan tarif za startno uže, predloži mi drugi" → {"intent":"ALT_TARIFF","item_query":"startno uže","item_ordinal":null}
Poruka: "alternativni tarifni za stavku 3" → {"intent":"ALT_TARIFF","item_query":"","item_ordinal":3}
Poruka: "koji je tarifni broj za čelik?" → {"intent":"QUERY","item_query":"čelik","item_ordinal":null}
Poruka: "predloži mi tarif" → {"intent":"BATCH_TARIFF","item_query":"","item_ordinal":null}
Poruka: "predloži mi tarif za kosilicu" → {"intent":"SINGLE_TARIFF","item_query":"kosilica","item_ordinal":null}
"""


class IntentClassifier:
    """
    Klasifikuje korisnikovu chat poruku za tarif-related zahtjeve.

    Koristi se samo za DVOSMISLENE poruke gdje keyword detekcija nije
    dovoljna — npr. "predloži mi tarif za X" vs. "predloži mi tarife".

    Zahtijeva LLMProvider (DeepSeek primarni).
    """

    def classify(self, message: str, draft_summary: str = "") -> IntentResult:
        """
        Klasificira namjeru poruke.

        Args:
            message: Korisnička poruka
            draft_summary: Kratki sažetak dostupnih stavki (opcionalno, do 300 znakova)

        Returns:
            IntentResult sa tipom namjere i extrahovanim podacima
        """
        try:
            from gui.tabs.agent.widgets.llm_provider import LLMProvider
            provider = LLMProvider()

            user_content = f'Poruka: "{message}"'
            if draft_summary:
                user_content += f"\n\nDostupne stavke (sažetak):\n{draft_summary}"

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ]

            raw = provider.complete(messages, max_tokens=80, use_small_model=False)
            raw = raw.strip()

            # Ukloni markdown blok ako postoji
            if "```" in raw:
                parts = raw.split("```")
                for part in parts:
                    p = part.strip()
                    if p.startswith("{"):
                        raw = p
                        break

            data = json.loads(raw)
            ordinal = data.get("item_ordinal")
            if ordinal is not None:
                try:
                    ordinal = int(ordinal)
                except (TypeError, ValueError):
                    ordinal = None

            return IntentResult(
                intent=data.get("intent", "OTHER"),
                item_query=(data.get("item_query") or "").strip(),
                item_ordinal=ordinal,
                raw=raw,
            )

        except Exception as e:
            logger.warning(f"[IntentClassifier] Greška: {e}")
            return IntentResult(intent="OTHER", raw=str(e))

    @staticmethod
    def build_draft_summary(draft) -> str:
        """Kratki sažetak stavki za classifier kontekst (max ~300 znakova)."""
        if not draft:
            return ""
        lines = getattr(draft, "invoice_lines", [])
        if not lines:
            naim_items = getattr(draft, "items", [])
            items = []
            for i, item in enumerate(naim_items[:20], 1):
                opis = (getattr(item, "goods_description", "") or "")[:30]
                tarifa = getattr(item, "tariff_code", "") or "?"
                items.append(f"Naim {i}. {opis} [{tarifa}]")
            summary = "; ".join(items)
            if len(naim_items) > 20:
                summary += f"; ... ({len(naim_items)} ukupno)"
            return summary[:400]
        items = []
        for i, l in enumerate(lines[:20], 1):
            naziv = (getattr(l, "naziv_robe", "") or "")[:30]
            tarifa = getattr(l, "tarifni_broj", "") or "?"
            items.append(f"{i}. {naziv} [{tarifa}]")
        summary = "; ".join(items)
        if len(lines) > 20:
            summary += f"; ... ({len(lines)} ukupno)"
        return summary[:400]
