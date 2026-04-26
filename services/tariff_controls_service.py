"""
Deklarant Pro - Tariff Controls Service

Servis za automatsko dodavanje priloženih dokumenata u zaglavlje
na osnovu tarifnog broja (inspection rules).

Koristi tabelu catalogs.tariff_controls koja sadrži boolean kolone:
  - vet  → N853 (Veterinarsko uvjerenje)
  - san  → N852 (Sanitarno-zdravstveno uvjerenje)
  - fit  → N851 (Fitosanitarno uvjerenje)
  - uvk  → N003 (Uvjerenje o kvalitetu robe)
  - agencija → AGL (Agencija za lijekove)

Takođe koristi catalogs.inspection_rules za preciznije podatke.

Autor: Radovan + Claude
Datum: 2026-04-24
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from database.db import get_db_connection

logger = logging.getLogger(__name__)

# Mapiranje kontrole → šifra priloženog dokumenta
CONTROL_TO_DOC = {
    "vet":       {"code": "N853", "name": "Veterinarsko uvjerenje"},
    "san":       {"code": "N852", "name": "Sanitarno-zdravstveno uvjerenje"},
    "fit":       {"code": "N851", "name": "Fitosanitarno uvjerenje"},
    "uvk":       {"code": "N003", "name": "Uvjerenje o kvalitetu robe"},
    "agencija":  {"code": "AGL",  "name": "Agencija za lijekove - kontrola"},
}

# Kolone koje provjeravamo u tariff_controls (redoslijed nije bitan)
_CONTROL_COLUMNS = list(CONTROL_TO_DOC.keys())


@dataclass
class TariffControlResult:
    """Rezultat provjere inspekcijske kontrole za tarifni broj.
    
    Koristi se u _check_and_show_tariff_warning u naimenovanja_view.py
    za prikaz upozorenja o kontrolisanoj robi.
    """
    tarifni_broj: str
    naimenovanje: str = ""
    san: bool = False
    vet: bool = False
    fit: bool = False
    uvk: bool = False
    agencija: bool = False
    dozvola: bool = False
    napomena: str = ""

    @property
    def ima_kontrolu(self) -> bool:
        return any([self.san, self.vet, self.fit, self.uvk, self.agencija, self.dozvola])

    @property
    def opis_kontrola(self) -> list:
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
        """Kratke skracenice aktivnih kontrola."""
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

    def to_docs(self) -> List[Dict[str, str]]:
        """Konvertuj kontrole u listu priloženih dokumenata."""
        docs = []
        if self.san:
            docs.append({"code": "N852", "name": "Sanitarno-zdravstveno uvjerenje"})
        if self.vet:
            docs.append({"code": "N853", "name": "Veterinarsko uvjerenje"})
        if self.fit:
            docs.append({"code": "N851", "name": "Fitosanitarno uvjerenje"})
        if self.uvk:
            docs.append({"code": "N003", "name": "Uvjerenje o kvalitetu robe"})
        if self.agencija:
            docs.append({"code": "AGL", "name": "Agencija za lijekove - kontrola"})
        return docs


class TariffControlsService:
    """
    Servis za određivanje potrebnih priloženih dokumenata
    na osnovu tarifnog broja.
    """

    def __init__(self):
        self._cache: Dict[str, List[Dict[str, str]]] = {}
        self._all_rules: Optional[List[dict]] = None

    # ──────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────

    def get_required_docs(self, tariff_code: str) -> List[Dict[str, str]]:
        """
        Vrati listu priloženih dokumenata potrebnih za dati tarifni broj.

        Args:
            tariff_code: Tarifni broj (npr. "02013000", "440710", "01")

        Returns:
            Lista dict-ova: [{"code": "N853", "name": "Veterinarsko uvjerenje"}, ...]
        """
        if not tariff_code or not tariff_code.strip():
            return []

        code = tariff_code.strip().replace(" ", "").replace(".", "")

        # Cache provjera
        if code in self._cache:
            return self._cache[code]

        # Pronađi kontrole
        controls = self._find_controls(code)

        # Mapiraj u dokumente
        docs = self._controls_to_docs(controls)

        # Sačuvaj u cache
        self._cache[code] = docs
        return docs

    def get_required_docs_batch(self, tariff_codes: List[str]) -> Dict[str, List[Dict[str, str]]]:
        """
        Batch verzija — za više tarifnih brojeva odjednom.

        Args:
            tariff_codes: Lista tarifnih brojeva

        Returns:
            Dict {tariff_code: [{"code": ..., "name": ...}, ...]}
        """
        result = {}
        for code in tariff_codes:
            result[code] = self.get_required_docs(code)
        return result

    def get_docs_for_all_items(self, items: List) -> List[Dict[str, str]]:
        """
        Skupi sve potrebne dokumente za sve stavke (items) u draft-u.

        Args:
            items: Lista NaimenovanjeDraft objekata

        Returns:
            Lista jedinstvenih dokumenata (bez duplikata)
        """
        all_docs: List[Dict[str, str]] = []
        seen: set[str] = set()

        for item in items:
            tariff = getattr(item, 'tariff_code', '') or ''
            docs = self.get_required_docs(tariff)
            for doc in docs:
                if doc['code'] not in seen:
                    seen.add(doc['code'])
                    all_docs.append(doc)

        return all_docs

    def clear_cache(self) -> None:
        """Očisti cache (npr. nakon update-a baze)."""
        self._cache.clear()
        self._all_rules = None

    # ──────────────────────────────────────────────
    # MATCH LOGIKA
    # ──────────────────────────────────────────────

    def _find_controls(self, tariff_code: str) -> dict:
        """
        Pronađi kontrole za dati tarifni broj koristeći najduži match.

        Strategija:
          Generiše sve moguće dužine (10, 8, 6, 4, 2 cifre) i bira najduži match.
          Npr. "0603110000" → proba "0603110000", "06031100", "060311", "0603", "06"
        """
        rules = self._load_all_rules()
        if not rules:
            return {}

        # Normalizuj: ukloni razmake i tačke
        code = tariff_code.replace(" ", "").replace(".", "")

        # Generiši kandidate od najdužeg ka najkraćem
        candidates = _generate_lookup_codes(code)

        for candidate in candidates:
            if candidate in rules:
                return rules[candidate]

        return {}

    def _load_all_rules(self) -> Dict[str, dict]:
        """Učitaj sva pravila iz baze u cache."""
        if self._all_rules is not None:
            return self._all_rules

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cols = ", ".join(_CONTROL_COLUMNS)
                    cur.execute(f"""
                        SELECT tarifni_broj, {cols}
                        FROM catalogs.tariff_controls
                    """)
                    rows = cur.fetchall()

            rules: Dict[str, dict] = {}
            for row in rows:
                tb = row['tarifni_broj'].strip()
                controls = {}
                for col in _CONTROL_COLUMNS:
                    controls[col] = bool(row[col])
                rules[tb] = controls

            self._all_rules = rules
            logger.debug(f"  ✅ Učitano {len(rules)} pravila iz tariff_controls")
            return rules

        except Exception as e:
            logger.error(f"  ❌ Greška pri učitavanju tariff_controls: {e}")
            return {}

    def _controls_to_docs(self, controls: dict) -> List[Dict[str, str]]:
        """Mapiraj boolean kontrole u listu dokumenata."""
        docs = []
        for col, doc_info in CONTROL_TO_DOC.items():
            if controls.get(col, False):
                docs.append({
                    "code": doc_info["code"],
                    "name": doc_info["name"],
                })
        return docs


# ──────────────────────────────────────────────
# SINGLETON I HELPER FUNKCIJE
# ──────────────────────────────────────────────

_service: Optional[TariffControlsService] = None


def get_tariff_controls_service() -> TariffControlsService:
    """Dohvati singleton instancu servisa."""
    global _service
    if _service is None:
        _service = TariffControlsService()
    return _service


def get_required_docs(tariff_code: str) -> List[Dict[str, str]]:
    """Helper funkcija — brzi poziv."""
    return get_tariff_controls_service().get_required_docs(tariff_code)


# ──────────────────────────────────────────────
# STARI API — za backward compatibility
# check_tariff_controls koristi se u naimenovanja_view.py
# ──────────────────────────────────────────────


def _generate_lookup_codes(tarifni_broj: str) -> list:
    """
    Generiraj listu koda za provjeru: tačan broj + svi skraćeni oblici + dopuna na 10 cifara.
    Npr. "3808910000" → ["3808910000", "38089100", "380891", "3808", "38"]
          "06031100"  → ["06031100", "0603110000", "060311", "0603", "06"]
    
    Uključuje sve nivoe: 10 (original ili dopunjen sa 00), 8, 6, 4, 2 cifre.
    """
    digits = re.sub(r'\D', '', tarifni_broj or "")
    if not digits:
        return []

    candidates = []
    n = len(digits)
    
    # Original
    candidates.append(digits)
    
    # Ako je kraće od 10, probaj dopuniti na 10 cifara (carinski standard)
    if n < 10:
        candidates.append(digits.ljust(10, '0'))
    
    # Skraćeni oblici
    if n >= 8:
        candidates.append(digits[:8])
    if n >= 6:
        candidates.append(digits[:6])
    if n >= 4:
        candidates.append(digits[:4])
    if n >= 2:
        candidates.append(digits[:2])

    # Deduplikacija, zadržava redoslijed
    return list(dict.fromkeys(candidates))


def check_tariff_controls(tarifni_broj: str) -> Optional[TariffControlResult]:
    """
    Provjeri da li tarifni broj ili njegova glava (heading) podlijece kontroli.
    Koristi se u naimenovanja_view.py za prikaz upozorenja.

    Vraca TariffControlResult ili None ako nema podataka.
    """
    codes = _generate_lookup_codes(tarifni_broj)
    if not codes:
        return None

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
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
    except Exception as e:
        logger.warning(f"Greška pri provjeri kontrola za {tarifni_broj}: {e}")
        return None


# ──────────────────────────────────────────────
# SAMOSTALNI TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    test_cases = [
        ("02013000", "Govedina svježa"),
        ("02071000", "Piletina"),
        ("44071000", "Drvo"),
        ("84713000", "Laptop"),
        ("30023000", "Vakcine"),
        ("06031100", "Svježe cvijeće"),
        ("01", "Žive životinje (chapter)"),
        ("0101", "Živi konji (heading)"),
    ]

    svc = get_tariff_controls_service()

    print("\n=== TEST: TariffControlsService ===\n")
    for code, desc in test_cases:
        docs = svc.get_required_docs(code)
        doc_str = ", ".join(f"{d['code']} ({d['name']})" for d in docs) if docs else "(nijedan)"
        print(f"  {code:12} {desc:30} → {doc_str}")

    print("\n✅ Test završen\n")
