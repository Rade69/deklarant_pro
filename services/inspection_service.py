"""
services/inspection_service.py

Servis za provjeru da li roba zahtijeva inspekciju na osnovu tarifnog broja.

Koristi catalogs.inspection_rules u PostgreSQL (migracija iz SQLite).
Baza se popunjava sa:
    python database/migrate_inspection_rules_to_pg.py

Primjer upotrebe:
    svc = InspectionService()
    rezultati = svc.check("1601009900")
    for r in rezultati:
        print(r.inspection_type, r.status, r.condition_text)
"""

# ============================================================
# SECTION: inspection-service-pg
# PURPOSE: Prefix-matching provjera inspekcija iz PostgreSQL
# DOC: docs/sections/inspection-rules-pg.md
# ============================================================

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("asycuda_pro.inspection")

# Mapiranje internih ključeva na čitljive nazive
INSPECTION_LABELS: dict[str, str] = {
    "veterinary":      "Veterinarska inspekcija",
    "phytosanitary":   "Fitosanitarna inspekcija",
    "sanitary":        "Sanitarna inspekcija",
    "medicines_agency": "Agencija za lijekove",
    "quality_control": "Kontrola kvaliteta",
}

INSPECTION_ICONS: dict[str, str] = {
    "veterinary":      "🐄",
    "phytosanitary":   "🌿",
    "sanitary":        "🔬",
    "medicines_agency": "⚕️",
    "quality_control": "📊",
}

# Redoslijed prikaza u dijalogu
INSPECTION_ORDER = [
    "sanitary",
    "veterinary",
    "phytosanitary",
    "quality_control",
    "medicines_agency",
]


@dataclass
class InspectionMatch:
    """Jedan pogodak inspekcijskog pravila za dati tarifni broj."""
    inspection_type:  str
    tariff_code:      str          # originalna vrijednost iz baze
    condition_text:   Optional[str]
    can_auto_decide:  bool
    match_strength:   str          # "exact", "prefix", "chapter"
    source_dataset:   Optional[str]

    @property
    def status(self) -> str:
        """Semantički status pogotka."""
        if self.condition_text:
            return "requires_inspection_if_condition_met"
        if self.can_auto_decide:
            return "requires_inspection"
        return "legal_signal_only_manual_review"

    @property
    def label(self) -> str:
        return INSPECTION_LABELS.get(self.inspection_type, self.inspection_type)

    @property
    def icon(self) -> str:
        return INSPECTION_ICONS.get(self.inspection_type, "🔍")

    @property
    def is_conditional(self) -> bool:
        return bool(self.condition_text)


@dataclass
class InspectionResult:
    """
    Rezultat provjere za jedan tarifni broj.

    Koristi se za prikaz u InspectionDialog i za generisanje inspekcijskog lista.
    """
    tariff_code:  str
    matches:      list[InspectionMatch] = field(default_factory=list)

    @property
    def requires_any_inspection(self) -> bool:
        return len(self.matches) > 0

    @property
    def has_conditional(self) -> bool:
        return any(m.is_conditional for m in self.matches)

    @property
    def inspection_types(self) -> list[str]:
        """Lista tipova inspekcija (bez duplikata, u definisanom redoslijedu)."""
        seen = set()
        result = []
        for t in INSPECTION_ORDER:
            if any(m.inspection_type == t for m in self.matches):
                if t not in seen:
                    seen.add(t)
                    result.append(t)
        return result

    def summary_text(self) -> str:
        """Kratki tekstualni opis za prikaz u tabeli."""
        if not self.matches:
            return "—"
        parts = []
        for t in self.inspection_types:
            m = next(m for m in self.matches if m.inspection_type == t)
            icon = m.icon
            if m.is_conditional:
                parts.append(f"{icon} uslovno")
            else:
                parts.append(f"{icon} da")
        return "  ".join(parts)


class InspectionService:
    """
    Servis za provjeru inspekcijskih zahtjeva po tarifnom broju.

    Koristi PostgreSQL tabelu catalogs.inspection_rules.
    Hijerarhijski prefix matching:
      "1601009900" → pokušava "1601009900" → "16010099" → "160100" → "1601" → "16"
    Vraća sve pogotke (jedan tarifni broj može zahtijevati više inspekcija).
    """

    def __init__(self):
        try:
            from database.db import get_db_connection as _get_conn
            self._get_conn = _get_conn
            self._pg_available = True
        except Exception as e:
            logger.warning(f"PostgreSQL nedostupan za inspekcije: {e}")
            self._pg_available = False

    @staticmethod
    def normalize(tariff_code: str) -> str:
        """Ukloni razmake: '1601 00 99 00' → '1601009900'."""
        return re.sub(r"\s+", "", (tariff_code or "").strip())

    def check(self, tariff_code: str) -> InspectionResult:
        """
        Provjeri da li tarifni broj zahtijeva inspekciju.

        Vraca InspectionResult sa svim pogocima (po tipu inspekcije).
        Ako PostgreSQL nije dostupan, vraca prazan rezultat.
        """
        result = InspectionResult(tariff_code=tariff_code)

        if not self._pg_available:
            return result

        norm = self.normalize(tariff_code)
        if not norm:
            return result

        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    # Prefix matching: substr(norm, 1, tariff_len) = tariff_code_norm
                    # Najspecifičniji match po tipu inspekcije (max tariff_len)
                    cur.execute("""
                        SELECT DISTINCT ON (inspection_type)
                            inspection_type,
                            tariff_code,
                            condition_text,
                            can_auto_decide,
                            match_strength,
                            source_dataset,
                            tariff_len
                        FROM catalogs.inspection_rules
                        WHERE is_active = TRUE
                          AND tariff_code_norm IS NOT NULL
                          AND tariff_code_norm != ''
                          AND tariff_code_norm = substr(%s, 1, tariff_len)
                        ORDER BY inspection_type, tariff_len DESC
                    """, (norm,))
                    rows = cur.fetchall()

                    for row in rows:
                        result.matches.append(InspectionMatch(
                            inspection_type=row["inspection_type"],
                            tariff_code=row["tariff_code"] or "",
                            condition_text=row["condition_text"],
                            can_auto_decide=bool(row["can_auto_decide"]),
                            match_strength=row["match_strength"] or "prefix",
                            source_dataset=row["source_dataset"],
                        ))

        except Exception as e:
            logger.error(f"Greška pri provjeri inspekcije za {tariff_code}: {e}")

        return result

    def check_bulk(self, tariff_codes: list[str]) -> dict[str, InspectionResult]:
        """
        Provjeri više tarifnih brojeva odjednom.
        Vraća dict {tariff_code: InspectionResult}.
        """
        return {code: self.check(code) for code in tariff_codes}


# Singleton za korištenje u cijeloj aplikaciji
_service_instance: InspectionService | None = None


def get_inspection_service() -> InspectionService:
    global _service_instance
    if _service_instance is None:
        _service_instance = InspectionService()
    return _service_instance
