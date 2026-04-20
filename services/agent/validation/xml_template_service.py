"""
XML Template Service

Pretražuje stare XML deklaracije i pronalazi template
za istog pošiljaoca/dobavljača. Kopira samo whitelist polja
koja su konzistentna po dobavljaču.

Polja koja se NE kopiraju:
- Rb.3-7 (obrasci, tovarni, stavke, paketi, ref.br)
- Rb.18 (transport_id - tablica vozila)
- Rb.21 (aktivno_transport)
- Troškovi (trosak_1..5)
- Rb.40 broj (rb40_broj - mijenja se svaki put)
- Iznos/kurs (popunjava se iz fakture)
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# WHITELIST: Polja koja se smiju kopirati iz starog XML-a
# ══════════════════════════════════════════════════════════════

TEMPLATE_FIELDS = [
    # Rb.1 - Tip deklaracije
    "deklaracija_tip", "deklaracija_oznaka", "deklaracija_a", "ured_odredista",
    # Rb.2 - Izvoznik (pošiljalac)
    "izvoznik_id", "izvoznik_naziv", "izvoznik_adresa",
    "izvoznik_grad", "izvoznik_postanski_broj", "izvoznik_drzava",
    # Rb.8 - Primalac
    "primalac_id", "primalac_naziv", "primalac_adresa",
    "primalac_grad", "primalac_postanski_broj", "primalac_drzava",
    # Rb.14 - Deklarant
    "deklarant_id", "deklarant_naziv", "deklarant_adresa",
    "deklarant_grad", "deklarant_postanski_broj", "deklarant_drzava",
    "deklarant_predstavnik",
    # Rb.19 - Kontejner
    "kontejner",
    # Rb.25/26/27 - Vid transporta i mjesto
    "vid_unutra", "vid_granica", "mjesto_otvaraca",
    # Rb.29/30 - Carinarnica i lokacija
    "izlazna_carinarnica", "lokacija_robe",
    # Rb.9-13 - Zemlje
    "odg_zemlja_1", "odg_zemlja_2", "odg_zemlja_3", "odg_zemlja_4",
    "zem_10", "zem_11", "zem_12", "zem_13",
    # Rb.15/17 - Država izvoza/odredišta
    "drzava_izvoza_naziv", "drzava_izvoza_sifra",
    "drzava_odredista_naziv", "drzava_odredista_sifra",
    # Rb.20 - Uslovi isporuke
    "uslovi_kod", "uslovi_mjesto",
    # Rb.22/23 - Valuta, kurs i tip transakcije
    "vrsta_trans_1", "vrsta_trans_2", "kurs",
    # Rb.40 - Tip i šifra (BEZ broja)
    "rb40_tip", "rb40_skracenica",
    # Rb.48/49 - Plaćanje i skladište
    "odgodjeno_placanje", "identifikacija_skladista",
]


@dataclass
class TemplateMatch:
    """Rezultat pretrage - nađeni XML template."""
    filepath: str
    filename: str
    exporter_name: str      # Ime pošiljaoca iz XML-a
    match_score: float      # 0.0 - 1.0
    fields: dict            # Izvučena whitelist polja
    declaration_type: str = ""  # "IM" ili "EX" (iz XML-a)


class XmlTemplateService:
    """
    Pretražuje stare XML deklaracije i pronalazi template
    za istog pošiljaoca/dobavljača.
    """

    def __init__(self, xml_dir: str = None):
        # __file__ je services/agent/validation/xml_template_service.py
        # 4x parent → project root
        _root = Path(__file__).parent.parent.parent.parent
        if xml_dir is None:
            xml_dir = str(_root / "data" / "xml_deklaracije")
        self.xml_dir = Path(xml_dir)
        # Istorijske XML deklaracije iz NOVA ASIKUDA foldera
        _extra = _root / "docs" / "NOVA ASIKUDA"
        self.extra_xml_dirs = [_extra] if _extra.exists() else []

    def find_template(self, exporter_hint: str,
                      declaration_type: str = "") -> Optional[TemplateMatch]:
        """
        Pronađi najpodesniji XML template za datog pošiljaoca.

        Args:
            exporter_hint: Ime pošiljaoca ili dobavljača (iz fakture, naziva fajla, itd.)
            declaration_type: "IM" ili "EX" — filtriraj samo odgovarajući tip.
                              Ako je prazno, ne filtrira po tipu.

        Returns:
            TemplateMatch sa najboljim poklapanjem, ili None
        """
        if not exporter_hint:
            return None

        hint_norm = self._normalize(exporter_hint)
        decl_type_upper = (declaration_type or "").upper().strip()
        logger.info(
            f"[XmlTemplate] Tražim template za: '{exporter_hint}'"
            + (f" (tip: {decl_type_upper})" if decl_type_upper else "")
        )

        best: Optional[TemplateMatch] = None
        best_score = 0.0

        # Prikupi XML fajlove iz svih direktorija
        all_dirs = ([self.xml_dir] if self.xml_dir.exists() else []) + self.extra_xml_dirs
        xml_files = []
        for d in all_dirs:
            xml_files.extend(d.glob("*.xml"))
        logger.info(f"[XmlTemplate] Skeniram {len(xml_files)} XML fajlova iz {len(all_dirs)} direktorija...")

        for xml_path in xml_files:
            try:
                exporter_name, fields = self._parse_xml(xml_path)
                if not exporter_name:
                    continue

                # Filtriranje po tipu deklaracije (IM/EX)
                if decl_type_upper:
                    xml_decl_type = (fields.get("deklaracija_tip") or "").upper().strip()
                    # "IM4" startswith "IM", "EX1" startswith "EX"
                    if xml_decl_type and not xml_decl_type.startswith(decl_type_upper):
                        continue

                score = self._similarity(hint_norm, self._normalize(exporter_name))

                if score > best_score:
                    best_score = score
                    best = TemplateMatch(
                        filepath=str(xml_path),
                        filename=xml_path.name,
                        exporter_name=exporter_name,
                        match_score=score,
                        fields=fields,
                        declaration_type=fields.get("deklaracija_tip", ""),
                    )
            except Exception as e:
                logger.debug(f"[XmlTemplate] Greška pri parsiranju {xml_path.name}: {e}")
                continue

        if best and best_score >= 0.5:
            logger.info(
                f"[XmlTemplate] Nađen template: '{best.filename}' "
                f"(pošiljalac: '{best.exporter_name}', tip: {best.declaration_type}, score: {best_score:.0%})"
            )
            return best
        else:
            logger.info(f"[XmlTemplate] Nije nađen odgovarajući template (best score: {best_score:.0%})")
            return None

    def apply_to_draft(self, draft, fields: dict) -> list:
        """
        Primijeni template polja na draft. Kopira samo whitelist polja.

        Returns:
            Lista naziva polja koja su popunjena
        """
        # Polja koja imaju "praznu" defaultnu vrijednost (ne preskakovati samo zato što != None)
        NUMERIC_DEFAULTS = {"kurs": (0.0, 1.0)}  # kurs=1.0 je default, prepiši ako template ima pravi

        applied = []
        for field_name in TEMPLATE_FIELDS:
            value = fields.get(field_name)
            if value is None:
                continue
            # Ne prepisuj polja koja su već popunjena
            current = getattr(draft, field_name, None)
            if field_name in NUMERIC_DEFAULTS:
                # Za numerička polja: prepiši samo ako je current defaultna vrijednost
                defaults = NUMERIC_DEFAULTS[field_name]
                if current not in defaults and current:
                    continue
            elif current:
                continue
            try:
                setattr(draft, field_name, value)
                applied.append(field_name)
            except AttributeError:
                pass

        # Rb.22: valuta iz fakture (ne iz templatea, ali postavi default ako nema)
        if not draft.valuta:
            draft.valuta = fields.get("valuta", "EUR")
            applied.append("valuta")

        logger.info(f"[XmlTemplate] Primijenjeno {len(applied)} polja na draft")
        return applied

    # ══════════════════════════════════════════════════════════════
    # PRIVATNE METODE
    # ══════════════════════════════════════════════════════════════

    def _parse_xml(self, xml_path: Path) -> tuple[str, dict]:
        """
        Parsira XML fajl i vraća (exporter_name, fields_dict).
        fields_dict sadrži samo whitelist polja.

        Koristi TAČNE XPath putanje — generički tagovi (Code, Name, Mode)
        se pojavljuju na desetine mjesta u ASYCUDA XML-u pa se mora
        specificirati pun kontekst.
        """
        tree = ET.parse(str(xml_path))
        root = tree.getroot()

        def get(xpath: str) -> str:
            el = root.find(xpath)
            if el is None:
                return ""
            t = (el.text or "").strip()
            return "" if t in ("<null/>", "null") else t

        def get_bool(xpath: str) -> bool:
            return get(xpath).lower() == "true"

        def split_multiline(raw: str) -> list:
            return [l.strip() for l in raw.split("\n") if l.strip()]

        # ── Rb.2 Izvoznik ────────────────────────────────────────
        exporter_raw = get(".//Traders/Exporter/Exporter_name")
        exp_lines = split_multiline(exporter_raw)
        exporter_name = exp_lines[0] if exp_lines else ""
        exporter_grad = exp_lines[1] if len(exp_lines) > 1 else ""
        exporter_drzava = exp_lines[2] if len(exp_lines) > 2 else ""

        # ── Rb.8 Primalac ────────────────────────────────────────
        consignee_raw = get(".//Traders/Consignee/Consignee_name")
        con_lines = split_multiline(consignee_raw)
        primalac_naziv = con_lines[0] if con_lines else ""
        primalac_grad = con_lines[1] if len(con_lines) > 1 else ""
        primalac_adresa = con_lines[2] if len(con_lines) > 2 else ""

        # ── Rb.14 Deklarant ──────────────────────────────────────
        declarant_raw = get(".//Declarant/Declarant_name")
        dec_lines = split_multiline(declarant_raw)
        deklarant_naziv = dec_lines[0] if dec_lines else ""
        deklarant_grad = dec_lines[1] if len(dec_lines) > 1 else ""
        deklarant_adresa = dec_lines[2] if len(dec_lines) > 2 else ""

        # ── Rb.1 Carinarnica ─────────────────────────────────────
        office_code = get(".//Identification/Office_segment/Customs_clearance_office_code")
        office_name = get(".//Identification/Office_segment/Customs_Clearance_office_name")
        ured_odredista = f"{office_code}  {office_name}".strip() if office_code else ""

        # ── Rb.29 Izlazna carinarnica (Border_office) ────────────
        border_code = get(".//Transport/Border_office/Code")
        border_name = get(".//Transport/Border_office/Name")
        izlazna = f"{border_code}  {border_name}".strip() if border_code else ""

        # ── Rb.27 Mjesto otvarača (Place_of_loading/Name) ────────
        mjesto_otvaraca = get(".//Transport/Place_of_loading/Name")

        # ── Rb.25/26 Vid transporta ──────────────────────────────
        vid_unutra = get(".//Transport/Means_of_transport/Inland_mode_of_transport")
        vid_granica = get(".//Transport/Means_of_transport/Border_information/Mode")

        # ── Rb.30 Lokacija robe ──────────────────────────────────
        lokacija = get(".//Transport/Location_of_goods")

        # ── Rb.20 Uslovi isporuke ────────────────────────────────
        uslovi_kod = get(".//Transport/Delivery_terms/Code")
        uslovi_mjesto = get(".//Transport/Delivery_terms/Place")

        # ── Rb.22/23 Valuta i kurs ───────────────────────────────
        valuta = get(".//Valuation/Gs_Invoice/Currency_code") or "EUR"
        kurs_raw = get(".//Valuation/Gs_Invoice/Currency_rate")
        try:
            kurs = float(kurs_raw) if kurs_raw else 0.0
        except ValueError:
            kurs = 0.0
        vrsta_trans_1 = get(".//Financial/Financial_transaction/code1")
        vrsta_trans_2 = get(".//Financial/Financial_transaction/code2")

        # ── Rb.40 (uzimamo iz prvog Item-a) ──────────────────────
        rb40_tip = get(".//Item/Previous_doc/Previous_category")
        rb40_skr = get(".//Item/Previous_doc/Previous_type")

        # ── Rb.48/49 ─────────────────────────────────────────────
        odgodjeno = get(".//Financial/Deffered_payment_reference")
        skladiste = get(".//Warehouse/Identification")

        # ── Rb.9-13 Zemlje ───────────────────────────────────────
        drzava_izvoza_kod = get(".//General_information/Country/Export/Export_country_code")
        drzava_izvoza_naz = get(".//General_information/Country/Export/Export_country_name")
        drzava_odredista_kod = get(".//General_information/Country/Destination/Destination_country_code")
        drzava_odredista_naz = get(".//General_information/Country/Destination/Destination_country_name")

        fields = {
            # Rb.1
            "deklaracija_tip":        get(".//Identification/Type/Type_of_declaration"),
            "deklaracija_oznaka":     get(".//Identification/Type/Declaration_gen_procedure_code"),
            "deklaracija_a":          get(".//Identification/Type/Type_of_Declaration_X"),
            "ured_odredista":         ured_odredista,
            # Rb.2
            "izvoznik_id":            get(".//Traders/Exporter/Exporter_code"),
            "izvoznik_naziv":         exporter_name,
            "izvoznik_adresa":        "",
            "izvoznik_grad":          exporter_grad,
            "izvoznik_postanski_broj": "",
            "izvoznik_drzava":        exporter_drzava,
            # Rb.8
            "primalac_id":            get(".//Traders/Consignee/Consignee_code"),
            "primalac_naziv":         primalac_naziv,
            "primalac_adresa":        primalac_adresa,
            "primalac_grad":          primalac_grad,
            "primalac_postanski_broj": "",
            "primalac_drzava":        "",
            # Rb.14
            "deklarant_id":           get(".//Declarant/Declarant_code"),
            "deklarant_naziv":        deklarant_naziv,
            "deklarant_adresa":       deklarant_adresa,
            "deklarant_grad":         deklarant_grad,
            "deklarant_postanski_broj": "",
            "deklarant_drzava":       "",
            "deklarant_predstavnik":  get(".//Declarant/Declarant_representative"),
            # Rb.19
            "kontejner":              get_bool(".//Transport/Container_flag"),
            # Rb.25/26/27
            "vid_unutra":             vid_unutra,
            "vid_granica":            vid_granica,
            "mjesto_otvaraca":        mjesto_otvaraca,
            # Rb.29/30
            "izlazna_carinarnica":    izlazna,
            "lokacija_robe":          lokacija,
            # Rb.15/17
            "drzava_izvoza_sifra":    drzava_izvoza_kod,
            "drzava_izvoza_naziv":    drzava_izvoza_naz,
            "drzava_odredista_sifra": drzava_odredista_kod,
            "drzava_odredista_naziv": drzava_odredista_naz,
            # Rb.20
            "uslovi_kod":             uslovi_kod,
            "uslovi_mjesto":          uslovi_mjesto,
            # Rb.22/23
            "valuta":                 valuta,
            "kurs":                   kurs if kurs > 0 else None,
            "vrsta_trans_1":          vrsta_trans_1,
            "vrsta_trans_2":          vrsta_trans_2,
            # Rb.40
            "rb40_tip":               rb40_tip,
            "rb40_skracenica":        rb40_skr,
            # Rb.48/49
            "odgodjeno_placanje":     odgodjeno,
            "identifikacija_skladista": skladiste,
        }

        return exporter_name, fields

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalizuj tekst za poređenje (lowercase, strip)."""
        return " ".join(text.lower().split())

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Fuzzy sličnost između dva stringa (0.0 - 1.0)."""
        if not a or not b:
            return 0.0
        # Provjeri i token overlap (za slučaj kad je redosljed riječi drugačiji)
        seq_score = SequenceMatcher(None, a, b).ratio()
        # Token overlap
        a_tokens = set(a.split())
        b_tokens = set(b.split())
        if a_tokens and b_tokens:
            overlap = len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))
            return max(seq_score, overlap)
        return seq_score
