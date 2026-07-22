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

logger = logging.getLogger("deklarant_pro.inspection")

# Mapiranje internih ključeva na čitljive nazive
INSPECTION_LABELS: dict[str, str] = {
    "sanitary":         "Inspekcija za hranu",
    "veterinary":       "Veterinarska inspekcija",
    "phytosanitary":    "Fitosanitarna inspekcija",
    "quality_control":  "Zdravstvena inspekcija",
    "market_inspection": "Tržna inspekcija",
    "medicines_agency": "Agencija za lijekove",
}

INSPECTION_ICONS: dict[str, str] = {
    "sanitary":         "🍽️",
    "veterinary":       "🐄",
    "phytosanitary":    "🌿",
    "quality_control":  "🏥",
    "market_inspection": "⛽",
    "medicines_agency": "⚕️",
}

# Mapiranje tarifnog poglavlja/broja na vrstu hrane (formular Inspekcije za hranu)
# Ključ: prefix tarifnog broja (2 ili 4 cifre), vrijednost: naziv kategorije na latinici
CHAPTER_TO_VRSTA_HRANE: dict[str, str] = {
    # Meso i prerađevine
    "02":   "Meso",
    "1601": "Mesne prerađevine",
    "1602": "Mesne prerađevine",
    # Riba
    "03":   "Riba i proizvodi od ribe",
    "1603": "Riba i proizvodi od ribe",
    "1604": "Riba i proizvodi od ribe",
    "1605": "Riba i proizvodi od ribe",
    # Mlijecni proizvodi, jaja, med
    "0401": "Mlijeko",
    "0402": "Mlijeko",
    "0403": "Mlijecni proizvodi",
    "0404": "Mlijecni proizvodi",
    "0405": "Mlijecni proizvodi",
    "0406": "Mlijecni proizvodi",
    "0407": "Jaja i proizvodi od jaja",
    "0408": "Jaja i proizvodi od jaja",
    "0409": "Med i drugi pcelinji proizvodi",
    # Povrce
    "07":   "Povrce",
    "2001": "Preradevine od povrca",
    "2002": "Preradevine od povrca",
    "2003": "Preradevine od povrca",
    "2004": "Preradevine od povrca",
    "2005": "Preradevine od povrca",
    # Voce i vocni sokovi
    "08":   "Voce",
    "0801": "Orasasti plodovi",
    "0802": "Orasasti plodovi",
    "2006": "Preradevine od voca",
    "2007": "Preradevine od voca",
    "2008": "Preradevine od voca",
    "2009": "Vocni sokovi",
    # Kafa, caj, zacini
    "0901": "Kafa i proizvodi od kafe",
    "2101": "Kafa i proizvodi od kafe",
    "0902": "Cajevi",
    "0904": "Zacini",
    "0905": "Zacini",
    "0906": "Zacini",
    "0907": "Zacini",
    "0908": "Zacini",
    "0909": "Zacini",
    "0910": "Zacini",
    "2103": "Zacini",
    "2209": "Zacini",
    # Zitarice
    "1001": "Psenica za ishranu ljudi",
    "1005": "Kukuruz za ishranu ljudi",
    "10":   "Ostale zitarice za ishranu ljudi",
    # Brasno i skrob
    "11":   "Brasno",
    # Sacme (ostaci uljarica)
    "2301": "Stocno brasno i mekinje",
    "2302": "Stocno brasno i mekinje",
    "2303": "Sacme",
    "2304": "Sacme",
    "2305": "Sacme",
    "2306": "Sacme",
    "2309": "Premiksi",
    "23":   "Stocna hrana (ostalo)",
    # Ulje i masti
    "15":   "Ulje, margarin, majoneza, mast",
    # Secer
    "17":   "Secer",
    # Kakao, konditorski
    "18":   "Konditorski proizvodi",
    # Pekarski, tjestenine, djecija hrana
    "1901": "Djecija hrana",
    "1902": "Tjestenine",
    "1904": "Konditorski proizvodi",
    "1905": "Pekarski proizvodi",
    "19":   "Pekarski proizvodi",
    # Sladoled
    "2105": "Sladoled",
    # Aditivi i ostala hrana
    "2102": "Aditivi",
    "2106": "Aditivi",
    "21":   "Ostala hrana",
    # Pica
    "2201": "Flasirana voda za pice",
    "2202": "Osvjezavajuca pica",
    "2203": "Pivo i sirovine",
    "2204": "Alkoholna pica",
    "2205": "Alkoholna pica",
    "2206": "Alkoholna pica",
    "2207": "Alkoholna pica",
    "2208": "Alkoholna pica",
    "22":   "Osvjezavajuca pica",
    # So
    "2501": "So za jelo",
}

# Mapiranje tarifnog poglavlja na vrstu zdravstvene robe (formular Zdravstvene inspekcije)
CHAPTER_TO_VRSTA_ZDRAVSTVENE: dict[str, str] = {
    "24":   "Duvan, duvanske preradevine i pribor za pusenje",
    "33":   "Kozmeticka sredstva",
    "34":   "Sredstva za odrzavanje cistоce",
    # Materijali u kontaktu sa hranom
    "3923": "Posude, pribor za jelo i drugi materijali koji dolaze u kontakt sa hranom",
    "3924": "Posude, pribor za jelo i drugi materijali koji dolaze u kontakt sa hranom",
    "4419": "Posude, pribor za jelo i drugi materijali koji dolaze u kontakt sa hranom",
    "6911": "Posude, pribor za jelo i drugi materijali koji dolaze u kontakt sa hranom",
    "6912": "Posude, pribor za jelo i drugi materijali koji dolaze u kontakt sa hranom",
    "7013": "Posude, pribor za jelo i drugi materijali koji dolaze u kontakt sa hranom",
    "7323": "Posude, pribor za jelo i drugi materijali koji dolaze u kontakt sa hranom",
    "7615": "Posude, pribor za jelo i drugi materijali koji dolaze u kontakt sa hranom",
    # Igracke
    "95":   "Djecje igracke",
    # Odjeca, obuca, tekstil (dodir sa kozom)
    "61":   "Sredstva koja dolaze u neposredan dodir sa kozom i sluzokoзom",
    "62":   "Sredstva koja dolaze u neposredan dodir sa kozom i sluzokozom",
    "63":   "Sredstva koja dolaze u neposredan dodir sa kozom i sluzokozom",
    "64":   "Sredstva koja dolaze u neposredan dodir sa kozom i sluzokozom",
}

# Redoslijed prikaza u dijalogu
INSPECTION_ORDER = [
    "sanitary",
    "veterinary",
    "phytosanitary",
    "quality_control",
    "market_inspection",
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
class HistoricalDocumentHint:
    """
    Istorijski (INFORMATIVNI) podatak — koliko puta je određena vrsta
    inspekcijskog dokumenta stvarno bila priložena za ovaj tarifni broj u
    prošlim ASYCUDA deklaracijama (catalogs.inspection_document_history).

    NIKAD ne zamjenjuje niti suprimira InspectionResult (pravno pravilo iz
    check()) — vidi project_rooms/2026-07-22_istorijska-napomena-inspekcije.md.
    """
    inspection_type: str
    document_name: str
    usage_count: int

    @property
    def label(self) -> str:
        return INSPECTION_LABELS.get(self.inspection_type, self.inspection_type)

    @property
    def icon(self) -> str:
        return INSPECTION_ICONS.get(self.inspection_type, "🔍")


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

    def suggest_vrsta_robe(self, tariff_code: str, inspection_type: str) -> str | None:
        """
        Predlozi vrstu robe za inspekcijski formular na osnovu tarifnog broja.

        inspection_type: 'sanitary', 'veterinary', 'phytosanitary' → CHAPTER_TO_VRSTA_HRANE
                         'quality_control'                          → CHAPTER_TO_VRSTA_ZDRAVSTVENE

        Vraca naziv kategorije (latinica) ili None ako ne moze odrediti.
        Matching ide od najspecificnijeg (4 cifre) ka poglavlju (2 cifre).
        """
        norm = self.normalize(tariff_code)
        if not norm:
            return None

        mapping = (
            CHAPTER_TO_VRSTA_ZDRAVSTVENE
            if inspection_type == "quality_control"
            else CHAPTER_TO_VRSTA_HRANE
        )

        for length in (4, 3, 2):
            prefix = norm[:length]
            if prefix in mapping:
                return mapping[prefix]

        return None

    def check_bulk(self, tariff_codes: list[str]) -> dict[str, InspectionResult]:
        """
        Provjeri više tarifnih brojeva odjednom.
        Vraća dict {tariff_code: InspectionResult}.
        """
        return {code: self.check(code) for code in tariff_codes}

    def historical_hint(self, tariff_code: str) -> list[HistoricalDocumentHint]:
        """
        Istorijski (INFORMATIVNI) podatak iz stvarnih prošlih deklaracija: koji
        je prilog (i koliko puta) zabilježen za TAČAN (8-cifreni) tarifni broj
        u catalogs.inspection_document_history (vidi database/
        migrate_inspection_document_history.py).

        NIKAD ne zamjenjuje niti suprimira check() (pravno pravilo) — ovo je
        samo dodatni kontekst. Prazna lista ako nema podatka (bez fallback
        nagađanja na prefiks/poglavlje — bolje ništa nego izmišljeno).
        """
        result: list[HistoricalDocumentHint] = []
        if not self._pg_available:
            return result

        norm = self.normalize(tariff_code)
        if not norm or len(norm) < 8:
            return result

        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT inspection_type, document_name, usage_count
                        FROM catalogs.inspection_document_history
                        WHERE tariff_code_norm = %s
                        ORDER BY usage_count DESC
                    """, (norm[:8],))
                    for row in cur.fetchall():
                        result.append(HistoricalDocumentHint(
                            inspection_type=row["inspection_type"],
                            document_name=row["document_name"] or "",
                            usage_count=row["usage_count"],
                        ))
        except Exception as e:
            logger.warning("Greška pri dohvatu istorijske napomene za %s: %s", tariff_code, e)

        return result


# Singleton za korištenje u cijeloj aplikaciji
_service_instance: InspectionService | None = None


def get_inspection_service() -> InspectionService:
    global _service_instance
    if _service_instance is None:
        _service_instance = InspectionService()
    return _service_instance
