"""
Deklarant Pro - Kreiraj Naimenovanja Service
SERVICE ZA KREIRANJE NAIMENOVANJA IZ FAKTURE

Implementira logiku:
1. Učitaj invoice_lines iz Faktura Tab-a
2. Grupiši po (tariff, origin, PREFERENCE) ← ISPRAVLJENO!
3. Kreiraj naimenovanja u draft.items
4. Notify Naimenovanja Tab da učita podatke

Autor: Radovan + Claude
Datum: Februar 2026
"""

import uuid
import logging
from typing import List, Dict
from dataclasses import dataclass
from core.draft import DeclarationDraft, NaimenovanjeDraft, InvoiceLine

logger = logging.getLogger(__name__)


@dataclass
class GroupKey:
    """Ključ za grupisanje faktura linija
    
    DODATO EUR.1 POLJE:
    Stavke sa različitim EUR.1 brojevima idu u odvojena naimenovanja.
    """
    tariff_code: str
    origin_country: str
    preference_code: str = ""  # Povlastica (ispravka!)
    eur1_number: str = ""      # EUR.1 broj (npr. "PE1 000456/2025")

    def __hash__(self):
        return hash((self.tariff_code, self.origin_country, self.preference_code, self.eur1_number))

    def __eq__(self, other):
        return (self.tariff_code == other.tariff_code and
                self.origin_country == other.origin_country and
                self.preference_code == other.preference_code and
                self.eur1_number == other.eur1_number)


class CreateNaimenovanjaService:
    """
    Service za kreiranje Naimenovanja (stavki deklaracije) iz faktura linija.

    Podržava 3 strategije:
    1. ONE_TO_ONE: Svaka faktura linija → 1 naimenovanje (jednostavno)
    2. SMART_GROUP: Grupiši po (tariff, origin, PREFERENCE) → manje naimenovanja (preporučeno)
    3. MANUAL: Korisnik bira koje linije idu zajedno (najviše kontrole)
    """

    def __init__(self, draft: DeclarationDraft):
        self.draft = draft

    def create_one_to_one(self) -> int:
        """
        Strategija 1: ONE_TO_ONE

        Kreira 1 naimenovanje za svaku faktura liniju.
        Najjednostavniji pristup, ali rezultira mnogo stavki na deklaraciji.

        Returns: Broj kreiranih naimenovanja
        """
        if not self.draft.invoice_lines:
            logger.warning("  ⚠️  Nema faktura linija za procesiranje!")
            return 0

        logger.debug("  🔄 Kreiranje naimenovanja (ONE_TO_ONE)...")

        # Očisti postojeće stavke
        self.draft.items.clear()

        # Kreiraj 1 naimenovanje po faktura liniji
        for i, line in enumerate(self.draft.invoice_lines):
            ordinal = i + 1
            naimenovanje = self._create_naimenovanje_from_line(line, ordinal_no=ordinal)
            self.draft.items.append(naimenovanje)

            # Dodeli povratnu referencu: InvoiceLine -> Naimenovanje
            line.assigned_naimenovanje_id = naimenovanje.item_id
            line.assigned_naimenovanje_ordinal = ordinal

        count = len(self.draft.items)
        logger.info(f"  ✅ Kreirano {count} naimenovanja (1:1 mapiranje)")

        return count

    def create_smart_group(self) -> int:
        """
        Strategija 2: SMART_GROUP (PREPORUČENO!)

        Grupiše faktura linije po:
        - Isti tarifni broj
        - Ista zemlja porekla
        - Isti PREFERENCE kod (povlastica) ← ISPRAVLJENO!

        Zatim kreira 1 naimenovanje po grupi.

        Returns: Broj kreiranih naimenovanja
        """
        if not self.draft.invoice_lines:
            logger.warning("  ⚠️  Nema faktura linija za procesiranje!")
            return 0

        logger.debug("  🔄 Kreiranje naimenovanja (SMART_GROUP po tarifa + poreklo + povlastica)...")

        # Grupiši linije po ključu
        groups: Dict[GroupKey, List[InvoiceLine]] = {}

        for line in self.draft.invoice_lines:
            key = GroupKey(
                tariff_code=line.tarifni_broj or '',
                origin_country=line.zemlja_porijekla or '',
                preference_code=line.povlastica or '',  # InvoiceLine koristi 'povlastica'!
                eur1_number=line.eur1_number or ''      # EUR.1 broj za grupisanje
            )

            if key not in groups:
                groups[key] = []

            groups[key].append(line)

        logger.debug(f"  📊 Grupisano {len(self.draft.invoice_lines)} linija u {len(groups)} grupa")
        # DEBUG: upiši svaku grupu u fajl da vidimo zašto se nešto grupišalo zajedno
        import pathlib
        _log = pathlib.Path.home() / "naim_debug.log"
        with open(_log, "w", encoding="utf-8") as _f:
            _f.write(f"Ukupno linija: {len(self.draft.invoice_lines)}, grupa: {len(groups)}\n\n")
            for gkey, glines in groups.items():
                _f.write(f"GRUPA key=({gkey.tariff_code!r}, {gkey.origin_country!r}, {gkey.preference_code!r}, {gkey.eur1_number!r}) → {len(glines)} linija\n")
                for gl in glines:
                    _f.write(f"  - {(gl.naziv_robe or '')[:55]} | tarifa={gl.tarifni_broj!r} | zemlja={gl.zemlja_porijekla!r} | povl={gl.povlastica!r}\n")
                _f.write("\n")

        # Očisti postojeće stavke
        self.draft.items.clear()

        # Kreiraj 1 naimenovanje po grupi
        ordinal = 1
        for key, lines in groups.items():
            naimenovanje = self._create_naimenovanje_from_group(lines, ordinal_no=ordinal)
            self.draft.items.append(naimenovanje)

            # Dodeli povratnu referencu: InvoiceLine -> Naimenovanje
            for line in lines:
                line.assigned_naimenovanje_id = naimenovanje.item_id
                line.assigned_naimenovanje_ordinal = ordinal

            logger.debug(f"    ✅ Grupa {ordinal}: Tarifa {key.tariff_code}, Poreklo {key.origin_country}, "
                         f"Povl {key.preference_code}, EUR.1 {key.eur1_number or '(nema)'}, "
                         f"{len(lines)} linija → {naimenovanje.gross_mass_kg:.2f} kg, "
                         f"{naimenovanje.item_value:.2f} {naimenovanje.currency}")

            ordinal += 1

        count = len(self.draft.items)
        logger.info(f"  ✅ Kreirano {count} naimenovanja (grupisano po tarifa + poreklo + povlastica + eur1)")

        return count

    def create_from_selection(self, selected_line_indices: List[int]) -> NaimenovanjeDraft:
        """
        Strategija 3: MANUAL

        Kreira 1 naimenovanje od izabranih faktura linija.
        Korisnik bira koje linije da kombinuje.

        Args:
            selected_line_indices: Lista indeksa faktura linija za kombinovanje

        Returns: Kreirano NaimenovanjeDraft
        """
        if not selected_line_indices:
            raise ValueError("Nema izabranih linija!")

        # Uzmi izabrane linije
        selected_lines = [self.draft.invoice_lines[i] for i in selected_line_indices]

        # Kreiraj naimenovanje
        ordinal_no = len(self.draft.items) + 1
        naimenovanje = self._create_naimenovanje_from_group(selected_lines, ordinal_no=ordinal_no)

        # Dodaj u draft
        self.draft.items.append(naimenovanje)

        logger.info(f"  ✅ Kreirano naimenovanje #{ordinal_no} od {len(selected_lines)} linija")

        return naimenovanje

    # ═══════════════════════════════════════════════════════════
    # POMOĆNE METODE
    # ═══════════════════════════════════════════════════════════

    def _create_naimenovanje_from_line(self, line: InvoiceLine, ordinal_no: int) -> NaimenovanjeDraft:
        """Kreiraj jedno naimenovanje od jedne faktura linije"""
        # Kreiraj referencu izvora
        source_ref = f"Faktura linija {line.line_no}" if line.line_no > 0 else "Faktura linija"

        # Rb.44 dokument porijekla na osnovu povlastice i has_origin_statement
        pov = line.povlastica or ''
        eur1 = (getattr(line, 'eur1_number', '') or '').strip()
        has_stmt = getattr(line, 'has_origin_statement', False)
        doc44 = ""
        if pov:
            if has_stmt:
                is_auth = getattr(line, 'is_authorized_exporter', False)
                pe_code = "PE3" if is_auth else "PE2"
                doc44 = f"{pe_code} {eur1}".strip() if eur1 else pe_code
            else:
                doc44 = f"PE1 {eur1}".strip() if eur1 else "PE1"

        naimenovanje = NaimenovanjeDraft(
            item_id=str(uuid.uuid4()),
            ordinal_no=ordinal_no,
            # Osnovne informacije (koristi InvoiceLine field names!)
            tariff_code=line.tarifni_broj or '',
            tariff_suffix=line.tariff_suffix or '000',
            goods_description=line.naziv_robe or '',
            goods_trade_name=line.naziv_robe or '',  # Trgovački naziv (I31_12)
            origin_country_code=line.zemlja_porijekla or '',
            # Količine
            gross_mass_kg=line.bruto_kg or 0.0,
            net_mass_kg=line.neto_kg or 0.0,
            # Vrednosti
            item_value=line.iznos or 0.0,
            statistical_value=line.iznos or 0.0,
            currency=line.valuta or 'EUR',
            # Pakovanje (InvoiceLine nema ove, koristi podrazumevane)
            package_code='PK',
            package_qty=line.kolicina or 0.0,
            package_marks='X',  # Podrazumevano: "X" (Oznake i broj)
            # Procedura (podrazumevano 4000 = definitivni uvoz)
            procedure_code='4000',
            procedure_prev_code='000',
            # Povlastica (povlastica → preference_code)
            preference_code=pov,
            # Rb.44 – dokument porijekla (PE1=EUR.1, PE2=izjava na fakturi)
            attached_document4=doc44,
            # Praćenje izvora
            source_invoice_refs=[source_ref]
        )

        apply_supplementary_unit(naimenovanje)
        return naimenovanje

    def _create_naimenovanje_from_group(self, lines: List[InvoiceLine], ordinal_no: int) -> NaimenovanjeDraft:
        """Kreiraj jedno naimenovanje od više faktura linija (grupa)"""
        if not lines:
            raise ValueError("Ne može se kreirati naimenovanje iz prazne grupe!")

        # Koristi prvu liniju za zajedničke atribute
        first_line = lines[0]

        # Kombinuj opise (sve linije)
        descriptions = [line.naziv_robe for line in lines if line.naziv_robe]
        goods_description = "; ".join(descriptions[:3])  # Maks 3 da ne bude predugačko
        if len(descriptions) > 3:
            goods_description += f"; ... (+{len(descriptions)-3} više)"

        # Agregiraj količine (zbir svih linija - koristi InvoiceLine field names!)
        gross_mass_kg = sum(line.bruto_kg or 0.0 for line in lines)
        net_mass_kg = sum(line.neto_kg or 0.0 for line in lines)
        package_qty = sum(line.kolicina or 0.0 for line in lines)

        # Agregiraj vrednosti (zbir svih linija)
        item_value = sum(line.iznos or 0.0 for line in lines)

        # Kreiraj reference izvora (brojevi faktura linija)
        source_refs = [f"Faktura linija {line.line_no}" for line in lines if line.line_no > 0]
        if not source_refs:
            source_refs = [f"Faktura linije ({len(lines)} stavki)"]

        # Proveri da li sve linije imaju isti EUR.1 broj
        eur1_numbers = set(line.eur1_number for line in lines if line.eur1_number)
        eur1_number = eur1_numbers.pop() if len(eur1_numbers) == 1 else ""

        # Odredi kod dokumenta porijekla
        # PE1 = EUR.1 obrazac (nema izjave na fakturi)
        # PE2 = Izjava o porijeklu na fakturi
        # PE3 = Izjava ovlaštenog izvoznika
        pov_group = first_line.povlastica or ''
        has_stmt_group = getattr(first_line, 'has_origin_statement', False)
        is_auth_group = getattr(first_line, 'is_authorized_exporter', False)
        doc_code = ""
        if pov_group:
            doc_code = "PE3" if (has_stmt_group and is_auth_group) else ("PE2" if has_stmt_group else "PE1")

        naimenovanje = NaimenovanjeDraft(
            item_id=str(uuid.uuid4()),
            ordinal_no=ordinal_no,
            # Osnovne informacije (iz prve linije - koristi InvoiceLine field names!)
            tariff_code=first_line.tarifni_broj or '',
            tariff_suffix=first_line.tariff_suffix or '000',
            origin_country_code=first_line.zemlja_porijekla or '',
            currency=first_line.valuta or 'EUR',
            package_code='PK',  # Podrazumevano
            procedure_code='4000',  # Podrazumevano
            procedure_prev_code='000',
            preference_code=first_line.povlastica or '',  # Povlastica (EUP/CEFTAP/TRP)
            # Agregirani podaci
            goods_description=goods_description,
            goods_trade_name=first_line.naziv_robe or '',  # Trgovački naziv (I31_12) iz prve linije
            gross_mass_kg=gross_mass_kg,
            net_mass_kg=net_mass_kg,
            package_qty=package_qty,
            item_value=item_value,
            statistical_value=item_value,
            package_marks='X',  # Podrazumevano: "X" (Oznake i broj)
            # EUR.1 u Rub.44.4 (plavi border - master polje) - format: "PE1 {broj}" ili "PE2 {broj}"
            # Ako nema broja — postavi samo šifru (PE1/PE2) kao podsjetnik za ručni unos
            attached_document4=f"{doc_code} {eur1_number}".strip() if doc_code else "",
            # Praćenje izvora
            source_invoice_refs=source_refs
        )

        apply_supplementary_unit(naimenovanje)
        return naimenovanje


# ─────────────────────────────────────────────────────────────
# Dopunska jedinica mjere — lookup iz tarife
# ─────────────────────────────────────────────────────────────

_DOPUNSKA_JM_MAP = {
    'kd':  'NAR', 'kom': 'NAR', 'nar': 'NAR', 'par': 'NAR', 'pa': 'NAR',
    'l':   'LTR', 'lit': 'LTR', 'ltr': 'LTR',
    'm2':  'MTK', 'm²': 'MTK', 'mtk': 'MTK',
    'm3':  'MTQ', 'm³': 'MTQ', 'mtq': 'MTQ',
    'm':   'MTR', 'mtr': 'MTR',
    'g':   'GRM', 'grm': 'GRM',
    'kg':  'KGM', 'kgm': 'KGM',
    'ce':  'CE',  'ct': 'CT',
}

# Prefix pravila za složene JM kodove iz tarife (npr. 'l alc. 100%', 'kg N', 'm² (¹)')
_DOPUNSKA_JM_PREFIX = [
    ('l ',    'LTR'), ('l ', 'LTR'),  # 'l alc. 100%' i slično
    ('kg',    'KGM'),                        # 'kg N', 'kg P2O5', 'kg 90%...'
    ('m²',    'MTK'), ('m2',     'MTK'),
    ('m³',    'MTQ'), ('m3',     'MTQ'),
    ('kd',    'NAR'),                        # 'kd (²)', '1000 kd' handled below
    ('1000',  'NAR'),                        # '1000 kd'
    ('gi',    'GRM'),                        # 'gi F/S' — gram izomerije
]


def get_supplementary_unit(tariff_code: str) -> str:
    """Vrati ASYCUDA kod dopunske JM za tarifni broj, ili '' ako ne postoji."""
    if not tariff_code:
        return ""
    try:
        from services.tariff.tarifa_service import _get_conn
        conn = _get_conn()
        kod_clean = tariff_code.strip()

        # 1. Traži prefiks: kod u bazi koji JE prefiks traženog (npr. '220421' je prefiks '2204210000')
        candidates = [kod_clean[:n] for n in range(len(kod_clean), 3, -1)]
        placeholders = ','.join('?' * len(candidates))
        row = conn.execute(f"""
            SELECT dopunska_jm FROM tarifa_2026
            WHERE kod IN ({placeholders})
              AND dopunska_jm NOT IN ('', '–', '-')
            ORDER BY LENGTH(kod) DESC
            LIMIT 1
        """, candidates).fetchone()

        # 2. Ako nema → traži siblinge: kodove koji počinju istim 6-cifrenim prefiksom
        if not row:
            prefix6 = kod_clean[:6]
            row = conn.execute("""
                SELECT dopunska_jm, COUNT(*) as cnt FROM tarifa_2026
                WHERE kod LIKE ?
                  AND LENGTH(kod) >= 8
                  AND dopunska_jm NOT IN ('', '–', '-')
                GROUP BY dopunska_jm
                ORDER BY cnt DESC
                LIMIT 1
            """, (prefix6 + '%',)).fetchone()

        if row:
            raw = row['dopunska_jm'].strip()
            mapped = _DOPUNSKA_JM_MAP.get(raw.lower())
            if mapped:
                return mapped
            raw_lower = raw.lower()
            for prefix, code in _DOPUNSKA_JM_PREFIX:
                if raw_lower.startswith(prefix.lower()):
                    return code
    except Exception:
        pass
    # Fallback: poglavlja 01-24 → KGM (BiH ASYCUDA praxis)
    try:
        if int(tariff_code[:2]) in range(1, 25):
            return "KGM"
    except (ValueError, IndexError):
        pass
    return ""


def apply_supplementary_unit(naim: NaimenovanjeDraft) -> None:
    """Popuni supplementary_unit_code/qty na naimenovanju ako je propisano tarifom."""
    if (naim.supplementary_unit_code or "").strip():
        return  # Već postavljeno
    unit = get_supplementary_unit(naim.tariff_code)
    if not unit:
        return
    naim.supplementary_unit_code = unit
    if unit == "KGM" and naim.net_mass_kg:
        naim.supplementary_unit_qty = naim.net_mass_kg
    elif unit == "NAR" and naim.package_qty:
        naim.supplementary_unit_qty = naim.package_qty


# ═══════════════════════════════════════════════════════════
# SAMOSTALNI TEST
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.debug("\n" + "=" * 70)
    logger.debug("CREATE NAIMENOVANJA SERVICE - TEST")
    logger.debug("=" * 70)

    # Kreiraj test podatke
    draft = DeclarationDraft()

    # Dodaj test faktura linije sa različitim povlasticama (koristi InvoiceLine field names!)
    line1 = InvoiceLine()
    line1.tarifni_broj = "84713000"
    line1.naziv_robe = "Laptop HP EliteBook 840"
    line1.zemlja_porijekla = "CN"
    line1.povlastica = "100"  # Povlastica 100%
    line1.kolicina = 8.0
    line1.bruto_kg = 40.0
    line1.neto_kg = 37.6
    line1.iznos = 5800.0
    line1.valuta = "EUR"
    draft.invoice_lines.append(line1)

    line2 = InvoiceLine()
    line2.tarifni_broj = "85285200"
    line2.naziv_robe = "LED Monitor Dell 24 inch"
    line2.zemlja_porijekla = "CN"
    line2.povlastica = "300"  # Povlastica 300
    line2.kolicina = 10.0
    line2.bruto_kg = 50.0
    line2.neto_kg = 48.0
    line2.iznos = 2000.0
    line2.valuta = "EUR"
    draft.invoice_lines.append(line2)

    line3 = InvoiceLine()
    line3.tarifni_broj = "84713000"  # Isto kao line1!
    line
