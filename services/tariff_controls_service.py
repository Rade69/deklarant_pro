"""
TariffControlsService — provjera da li tarifni broj podlije??e inspekcijskoj kontroli.

Koristi tabelu catalogs.tariff_controls (BiH UIO Objedinjen spisak, mart 2015).
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TariffControlResult:
    tarifni_broj: str
    naimenovanje: str = ""
    san: bool = False    # Sanitarno uvjerenje
    vet: bool = False    # Veterinarsko uvjerenje
    fit: bool = False    # Fitosanitarna kontrola
    uvk: bool = False    # Kontrola kvaliteta
    agencija: bool = False  # Agencija za lijekove
    dozvola: bool = False   # Dozvola uvoza
    napomena: str = ""

    @property
    def ima_kontrolu(self) -> bool:
        return any([self.san, self.vet, self.fit, self.uvk, self.agencija, self.dozvola])

    @property
    def opis_kontrola(self) -> list[str]:
        """Lista naziva aktivnih kontrola."""
        result = []
        if self.san:
            result.append("Sanitarno uvjerenje")
        if self.vet:
            result.append("Veterinarsko uvjerenje")
        if self.fit:
            result.append("Fitosanitarna kontrola")
        if self.uvk:
            result.append("Kontrola kvaliteta")
        if self.agencija:
            result.append("Agencija za lijekove")
        if self.dozvola:
            result.append("Dozvola uvoza/izvoza")
        return result

    @property
    def skracenice(self) -> str:
        """Kratke skracenice aktivnih kontrola, npr. 'SAN / VET'."""
        codes = []
        if self.san:
            codes.append("SAN")
        if self.vet:
            codes.append("VET")
        if self.fit:
            codes.append("FIT")
        if self.uvk:
            codes.append("UVK")
        if self.agencija:
            codes.append("AGEN")
        if self.dozvola:
            codes.append("DOZ")
        return " / ".join(codes)


def _generate_lookup_codes(tarifni_broj: str) -> list[str]:
    """
    Generiraj listu koda za provjeru: tačan broj + svi skraćeni oblici.
    Npr. "3808910000" → ["3808910000", "38089100", "380891", "380890", "3808"]
    """
    digits = re.sub(r'\D', '', tarifni_broj or "")
    if not digits:
        return []

    candidates = [digits]
    # 4-cifreni heading uvijek
    if len(digits) >= 4:
        candidates.append(digits[:4])
    # 6-cifreni
    if len(digits) >= 6:
        candidates.append(digits[:6])
    # 8-cifreni
    if len(digits) >= 8:
        candidates.append(digits[:8])

    return list(dict.fromkeys(candidates))  # deduplikacija, zadrzava redosled


def check_tariff_controls(tarifni_broj: str) -> Optional[TariffControlResult]:
    """
    Provjeri da li tarifni broj ili njegova glava (heading) podlijece kontroli.

    Prioritet pretrage:
    1. Tačan 10-cifreni broj
    2. 8-cifreni (heading level 3)
    3. 6-cifreni (heading level 2)
    4. 4-cifreni (heading/chapter)

    Vraca TariffControlResult ili None ako nema podataka za taj broj.
    """
    try:
        from database.db import get_db_connection
    except ImportError:
        logger.warning("database.db nije dostupan za provjeru kontrola")
        return None

    codes = _generate_lookup_codes(tarifni_broj)
    if not codes:
        return None

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Trazi najspecificniji match (najduzi tarifni_broj)
                placeholders = ", ".join(["%s"] * len(codes))
                cur.execute(f"""
                    SELECT tarifni_broj, naimenovanje, san, vet, fit, uvk,
                           agencija, dozvola, napomena
                    FROM catalogs.tariff_controls
                    WHERE tarifni_broj IN ({placeholders})
                      AND (san OR vet OR fit OR uvk OR agencija OR dozvola)
                    ORDER BY LENGTH(tarifni_broj) DESC
                    LIMIT 1
                """, codes)

                row = cur.fetchone()
                if not row:
                    return None

                # Podrska za RealDictCursor (dict) i obican cursor (tuple)
                if hasattr(row, "keys"):
                    return TariffControlResult(
                        tarifni_broj=row["tarifni_broj"],
                        naimenovanje=row["naimenovanje"] or "",
                        san=bool(row["san"]),
                        vet=bool(row["vet"]),
                        fit=bool(row["fit"]),
                        uvk=bool(row["uvk"]),
                        agencija=bool(row["agencija"]),
                        dozvola=bool(row["dozvola"]),
                        napomena=row["napomena"] or "",
                    )
                else:
                    return TariffControlResult(
                        tarifni_broj=row[0],
                        naimenovanje=row[1] or "",
                        san=bool(row[2]),
                        vet=bool(row[3]),
                        fit=bool(row[4]),
                        uvk=bool(row[5]),
                        agencija=bool(row[6]),
                        dozvola=bool(row[7]),
                        napomena=row[8] or "",
                    )
    except Exception as e:
        logger.warning(f"Greška pri provjeri kontrola za {tarifni_broj}: {e}")
        return None
