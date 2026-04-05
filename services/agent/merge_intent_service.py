"""
Merge Intent Service — pronalaženje i spajanje dupliciranih naimenovanja.

Business logika za:
- Pronalaženje naimenovanja sa istim tarifnim brojem + zemlja + povlastica
- Kreiranje prijedloga za spajanje
- Izvršenje spajanja (agregacija količina, masa, iznosa)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class NaimenovanjaSpajanje:
    """Prijedlog spajanja više naimenovanja u jedno."""
    indices: List[int]
    tariff_code: str
    merged_naziv: str
    merged_kolicina: float
    merged_bruto: float
    merged_neto: float
    merged_iznos: float


class MergeIntentService:
    """
    Service za spajanje naimenovanja — nezavisan od GUI-a.
    """

    def __init__(self, draft):
        self.draft = draft
        self.on_activity: Optional[Callable[[str], None]] = None
        self.on_agent_message: Optional[Callable[[str], None]] = None
        self.on_set_pending: Optional[Callable[[Any], None]] = None
        self.on_refresh_naim: Optional[Callable[[], None]] = None
        self.on_refresh_faktura: Optional[Callable[[], None]] = None

    # ─────────────────────────────────────────────────────
    # PRONALAŽENJE KANDIDATA
    # ─────────────────────────────────────────────────────

    def find_candidates(self) -> Optional[List[NaimenovanjaSpajanje]]:
        """
        Pronalazi naimenovanja sa istim tarifnim brojem + zemlja + povlastica
        i predlaže spajanje.
        """
        if not self.draft or not self.draft.items:
            self._msg("⚠️ Nema naimenovanja u deklaraciji.")
            return None

        self._activity("🔍 Analiziram naimenovanja...")

        from collections import defaultdict
        grupe = defaultdict(list)
        for i, item in enumerate(self.draft.items):
            kljuc = (
                item.tariff_code.strip(),
                item.origin_country_code.strip(),
                item.preference_code.strip()
            )
            grupe[kljuc].append((i, item))

        kandidati = [(k, v) for k, v in grupe.items() if len(v) >= 2]

        if not kandidati:
            self._msg("✅ Nema naimenovanja sa istim tarifnim brojem koja bi se mogla spojiti.")
            return None

        proposals = []
        linije = []

        for (tariff, zemlja, pov), stavke in kandidati:
            indices = [i for i, _ in stavke]
            items_list = [item for _, item in stavke]

            merged_kolicina = sum(it.supplementary_unit_qty or 0 for it in items_list)
            merged_bruto = sum(it.gross_mass_kg or 0 for it in items_list)
            merged_neto = sum(it.net_mass_kg or 0 for it in items_list)
            merged_iznos = sum(it.item_value or 0 for it in items_list)

            merged_naziv = max(
                (it.goods_description for it in items_list),
                key=len,
                default=""
            )

            proposals.append(NaimenovanjaSpajanje(
                indices=indices,
                tariff_code=tariff,
                merged_naziv=merged_naziv,
                merged_kolicina=merged_kolicina,
                merged_bruto=round(merged_bruto, 3),
                merged_neto=round(merged_neto, 3),
                merged_iznos=round(merged_iznos, 2)
            ))

            nazivi = " + ".join(
                (it.goods_description[:30] for it in items_list)
            )
            linije.append(
                f"&nbsp;&nbsp;• Tarifa <b>{tariff}</b> ({zemlja}) — "
                f"{len(stavke)} naim. → spoji:<br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;Kol: {merged_kolicina:.2f} | "
                f"Bruto: {merged_bruto:.3f}kg | Neto: {merged_neto:.3f}kg | "
                f"Iznos: {merged_iznos:.2f}<br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;<small>{nazivi}</small>"
            )

        # Postavi pending akciju
        if self.on_set_pending:
            from gui.tabs.agent.agent_actions import PendingAction
            self.on_set_pending(PendingAction(
                action_type="merge_naimenovanja",
                proposals=proposals,
                description=f"Spoji {sum(len(p.indices) for p in proposals)} naimenovanja u {len(proposals)}"
            ))

        self._msg(
            f"📋 Pronašao sam <b>{len(kandidati)}</b> grupu(e) za spajanje:<br><br>"
            + "<br><br>".join(linije)
            + "<br><br>🔀 <b>Spajam naimenovanja? Odgovori: Da / Ne</b>"
        )
        return proposals

    # ─────────────────────────────────────────────────────
    # IZVRŠENJE SPAJANJA
    # ─────────────────────────────────────────────────────

    def execute_merge(self, proposals: List[NaimenovanjaSpajanje]):
        """
        Spoji naimenovanja u draftu i osvježi tabove.
        """
        from PySide6.QtWidgets import QApplication

        spojeno = 0
        for merge in proposals:
            items = self.draft.items
            merged_indices = sorted(merge.indices, reverse=True)

            base_idx = min(merge.indices)
            base = items[base_idx]

            # Saberi vrijednosti
            base.gross_mass_kg = merge.merged_bruto
            base.net_mass_kg = merge.merged_neto
            base.item_value = merge.merged_iznos
            base.supplementary_unit_qty = merge.merged_kolicina

            # Obriši ostale (osim base)
            for idx in merged_indices:
                if idx != base_idx:
                    del items[idx]

            # Renumber ordinal_no
            for i, item in enumerate(items):
                item.ordinal_no = i + 1

            spojeno += len(merge.indices) - 1

        # Osvježi tabove
        QApplication.processEvents()
        if self.on_refresh_naim:
            self.on_refresh_naim()
        if self.on_refresh_faktura:
            self.on_refresh_faktura()

        self._msg(
            f"✅ <b>Spojeno {spojeno + len(proposals)} → {len(proposals)} naimenovanja.</b><br>"
            f"Količine, mase i iznosi su sabrani.<br>"
            f"Provjeri Naimenovanja tab."
        )

    # ─────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────

    def _msg(self, text: str):
        if self.on_agent_message:
            self.on_agent_message(text)

    def _activity(self, text: str):
        if self.on_activity:
            self.on_activity(text)
