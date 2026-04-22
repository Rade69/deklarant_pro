"""
ASYCUDA XML Builder - Kreira AsycudaWorld XML iz DeclarationDraft-a.

Format uskladen sa referentnim XML fajlovima generisanim od strane Asycuda aplikacije.
"""

import logging
import xml.etree.ElementTree as ET
from math import ceil
from pathlib import Path
from typing import Optional

from core.draft.draft import AttachedDocument, DeclarationDraft, NaimenovanjeDraft

logger = logging.getLogger(__name__)

# Mapiranje preference_code → Attached_document_code za dokaz o porijeklu
_PREF_TO_DOC_CODE = {
    "EUP": "EUPT",
    "EUPT": "EUPT",
    "CEFTAP": "FTAP",
    "CEFTAT": "FTAT",
    "TRP": "TRPD",
    "TRPD": "TRPD",
}

# Mapiranje preference_code → naziv dokumenta
_PREF_TO_DOC_NAME = {
    "EUPT": "Dokaz o preferencijalnom porijeklu robe iz Evropske unije",
    "FTAP": "Dokaz o porijeklu robe po CEFTA/PEM",
    "FTAT": "Dokaz o pref.porijeklu robe po CEFTA\\Tranziciona (prelazna) pravila",
    "TRPD": "Dokaz o turskom preferencijalnom porijeklu robe",
}


def _null(parent: ET.Element, tag: str) -> ET.Element:
    """Kreira <tag><null/></tag> element."""
    elem = ET.SubElement(parent, tag)
    ET.SubElement(elem, "null")
    return elem


def _text(parent: ET.Element, tag: str, value: str) -> ET.Element:
    """Kreira <tag>value</tag> ili <tag><null/></tag> ako je prazno."""
    elem = ET.SubElement(parent, tag)
    if value and value.strip():
        elem.text = value
    else:
        ET.SubElement(elem, "null")
    return elem


def _val(parent: ET.Element, tag: str, value: str) -> ET.Element:
    """Kreira <tag>value</tag> element (uvijek, bez null fallbacka)."""
    elem = ET.SubElement(parent, tag)
    elem.text = value if value else ""
    return elem


def _fmt_party_name(*parts: str) -> str:
    """Formatira naziv stranke kao multi-line tekst (naziv\\ngrad\\nadresa)."""
    return "\n".join(p.strip() for p in parts if p and p.strip())


def _parse_cost(cost_str: str) -> float:
    try:
        return float(str(cost_str).replace(",", ".").replace(" ", ""))
    except Exception:
        return 0.0


def _gs_cost_section(parent: ET.Element, tag: str, amount: float) -> None:
    """Kreira Gs_* sekciju troška u zaglavlju."""
    gs = ET.SubElement(parent, tag)
    _val(gs, "Amount_national_currency", f"{amount:.1f}" if amount else "0.0")
    _val(gs, "Amount_foreign_currency", f"{amount:.1f}" if amount else "0.0")
    if amount:
        _null(gs, "Currency_code")   # <null/> kad postoji iznos
    else:
        ET.SubElement(gs, "Currency_code")  # prazan kad je 0
    _val(gs, "Currency_name", "Nema stranih valuta")
    _val(gs, "Currency_rate", "1" if amount else "0")


def _item_cost_section(parent: ET.Element, tag: str) -> None:
    """Kreira item_* sekciju troška stavke (prazna — popunjava Asycuda)."""
    gs = ET.SubElement(parent, tag)
    ET.SubElement(gs, "Amount_national_currency")
    ET.SubElement(gs, "Amount_foreign_currency")
    _null(gs, "Currency_code")
    _val(gs, "Currency_name", "Nema stranih valuta")
    _val(gs, "Currency_rate", "1")


class AsycudaXMLBuilder:
    """
    Builduje ASYCUDA XML iz DeclarationDraft-a.
    Format uskladen sa XML fajlovima koje generiše AsycudaWorld aplikacija.
    """

    def __init__(self, draft: DeclarationDraft):
        self.draft = draft
        self.root = ET.Element("ASYCUDA")

    def _g(self, attr: str, default: str = "") -> str:
        """Sigurno čita atribut iz draft-a (getattr sa fallback-om)."""
        return str(getattr(self.draft, attr, None) or default)

    def build(self) -> ET.Element:
        """Kreira kompletan XML tree."""
        self._add_assessment_notice()
        self._add_global_taxes()
        self._add_property()
        self._add_identification()
        self._add_traders()
        self._add_representative()
        self._add_declarant()
        self._add_general_information()
        self._add_transport()
        self._add_financial()
        self._add_warehouse()
        self._add_transit()
        self._add_valuation()
        self._add_items()
        return self.root

    # ─────────────────────────────────────────────────────────────
    # Sekcije zaglavlja
    # ─────────────────────────────────────────────────────────────

    def _add_assessment_notice(self) -> None:
        """<Assessment_notice> sa 14 praznih <Item_tax_total/>."""
        notice = ET.SubElement(self.root, "Assessment_notice")
        for _ in range(14):
            ET.SubElement(notice, "Item_tax_total")

    def _add_global_taxes(self) -> None:
        """<Global_taxes> sa 8 praznih <Global_tax_item/>."""
        gt = ET.SubElement(self.root, "Global_taxes")
        for _ in range(8):
            ET.SubElement(gt, "Global_tax_item")

    def _add_property(self) -> None:
        """<Property> — osnovna svojstva deklaracije."""
        n_items = len(self.draft.items)
        n_forms = ceil(n_items / 3) if n_items > 0 else 1

        prop = ET.SubElement(self.root, "Property")
        _val(prop, "Sad_flow", "I")

        forms = ET.SubElement(prop, "Forms")
        _val(forms, "Number_of_the_form", "1")
        _val(forms, "Total_number_of_forms", str(n_forms))

        nbers = ET.SubElement(prop, "Nbers")
        _val(nbers, "Number_of_loading_lists", self._g("tovarni_listovi", "1") or "1")
        _val(nbers, "Total_number_of_items", str(n_items))

        _null(prop, "Place_of_declaration")
        ET.SubElement(prop, "Date_of_declaration")
        _val(prop, "Selected_page", "1")

    def _add_identification(self) -> None:
        """<Identification> — identifikacija deklaracije."""
        ident = ET.SubElement(self.root, "Identification")

        office = ET.SubElement(ident, "Office_segment")
        # ured_odredista može biti: "BA097012" (samo sifra) ili "BA097012  CI Bijeljina"
        ured = self._g("ured_odredista")
        if ured and len(ured) <= 10:
            # Samo šifra — nađi naziv iz baze
            try:
                from database.db import get_db_connection
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT naziv FROM catalogs.carinske_ispostave WHERE sifra = %s",
                            (ured,)
                        )
                        row = cur.fetchone()
                        if row:
                            office_code = ured
                            naziv = row["naziv"]
                            # "1. Carinska ispostava Banja Luka" → "CI Banja Luka"
                            if ". Carinska ispostava" in naziv:
                                office_name = "CI " + naziv.split(". Carinska ispostava ")[-1]
                            elif "Carinski referat" in naziv:
                                office_name = "CR " + naziv.split("Carinski referat ")[-1]
                            else:
                                office_name = naziv
                        else:
                            office_code = ured
                            office_name = ured
            except Exception:
                office_code = ured
                office_name = ured
        else:
            # Puni format: "BA097012  CI Bijeljina"
            ured_parts = ured.split()
            office_code = ured_parts[0] if ured_parts else ""
            office_name = " ".join(ured_parts[1:]) if len(ured_parts) > 1 else ured
        _val(office, "Customs_clearance_office_code", office_code)
        _val(office, "Customs_Clearance_office_name", office_name)

        type_elem = ET.SubElement(ident, "Type")
        _val(type_elem, "Type_of_declaration", self._g("deklaracija_tip", "IM"))
        _val(type_elem, "Type_of_Declaration_X", self._g("deklaracija_a", "A"))
        _val(type_elem, "Declaration_gen_procedure_code", self._g("deklaracija_oznaka", "H"))
        _null(type_elem, "Type_of_transit_document")

        _null(ident, "Manifest_reference_number")

        reg = ET.SubElement(ident, "Registration")
        _null(reg, "Serial_number")
        _null(reg, "Number")
        ET.SubElement(reg, "Date")

        assess = ET.SubElement(ident, "Assessment")
        _null(assess, "Serial_number")
        ET.SubElement(assess, "Number")
        ET.SubElement(assess, "Date")

        receipt = ET.SubElement(ident, "receipt")
        _null(receipt, "Serial_number")
        ET.SubElement(receipt, "Number")
        ET.SubElement(receipt, "Date")

    def _add_traders(self) -> None:
        """<Traders> — izvoznik, primalac, finansijski."""
        traders = ET.SubElement(self.root, "Traders")

        # Exporter
        exporter = ET.SubElement(traders, "Exporter")
        exp_id = self._g("izvoznik_id")
        if exp_id:
            _val(exporter, "Exporter_code", exp_id)
        else:
            _null(exporter, "Exporter_code")
        exp_name = _fmt_party_name(
            self._g("izvoznik_naziv"),
            self._g("izvoznik_grad"),
            self._g("izvoznik_drzava"),
        )
        _val(exporter, "Exporter_name", exp_name)

        # Consignee
        consignee = ET.SubElement(traders, "Consignee")
        _val(consignee, "Consignee_code", self._g("primalac_id"))
        cons_name = _fmt_party_name(
            self._g("primalac_naziv"),
            self._g("primalac_grad"),
            self._g("primalac_adresa"),
        )
        _val(consignee, "Consignee_name", cons_name)

        # Financial (prazno)
        financial = ET.SubElement(traders, "Financial")
        _null(financial, "Financial_code")
        _null(financial, "Financial_name")

    def _add_representative(self) -> None:
        """<Representative> — vrsta zastupanja."""
        rep = ET.SubElement(self.root, "Representative")
        _val(rep, "Representative_code", "2")  # 2 = direktno zastupanje

    def _add_declarant(self) -> None:
        """<Declarant> — podaci o deklarantu."""
        declarant = ET.SubElement(self.root, "Declarant")

        _val(declarant, "Declarant_code", self._g("deklarant_id"))
        decl_name = _fmt_party_name(
            self._g("deklarant_naziv"),
            self._g("deklarant_grad"),
            self._g("deklarant_adresa"),
        )
        _val(declarant, "Declarant_name", decl_name)

        predstavnik = self._g("deklarant_predstavnik")
        if predstavnik:
            _val(declarant, "Declarant_representative", predstavnik)
        else:
            _null(declarant, "Declarant_representative")

        ref = ET.SubElement(declarant, "Reference")
        ref_br = self._g("ref_br")
        if ref_br:
            _val(ref, "Number", ref_br)
        else:
            ET.SubElement(ref, "Number")

    def _add_general_information(self) -> None:
        """<General_information> — opšte informacije."""
        gen_info = ET.SubElement(self.root, "General_information")
        country = ET.SubElement(gen_info, "Country")

        _null(country, "Country_first_destination")
        _null(country, "Trading_country")

        export = ET.SubElement(country, "Export")
        _val(export, "Export_country_code", self._g("drzava_izvoza_sifra"))
        _val(export, "Export_country_name", self._g("drzava_izvoza_naziv"))
        _null(export, "Export_country_region")

        destination = ET.SubElement(country, "Destination")
        _null(destination, "Destination_country_code")
        _null(destination, "Destination_country_name")
        _null(destination, "Destination_country_region")

        # Zemlja porijekla na nivou zaglavlja — naziv (ne šifra)
        origin_code = self._g("drzava_porijekla")
        origin_name = ""
        if origin_code:
            from sifrarnici.zemlje import get_zemlja_by_kod
            z = get_zemlja_by_kod(origin_code.upper())
            origin_name = z.naziv if z else origin_code
        if not origin_name and self.draft.items:
            # Fallback: uzmi naziv iz prvog naimenovanja
            from sifrarnici.zemlje import get_zemlja_by_kod
            c = self.draft.items[0].origin_country_code or ""
            z = get_zemlja_by_kod(c.upper())
            origin_name = z.naziv if z else (self.draft.items[0].origin_country_name or "")
        _val(country, "Country_of_origin_name", origin_name)

        # Value_details = zbir vanjskog + unutrašnjeg frahta
        t1 = _parse_cost(self._g("trosak_1"))
        t4 = _parse_cost(self._g("trosak_4"))
        val_details = t1 + t4
        vd_elem = ET.SubElement(gen_info, "Value_details")
        if val_details:
            vd_elem.text = f"{val_details:.1f}"

        _null(gen_info, "CAP")
        _null(gen_info, "Additional_information")
        _null(gen_info, "Comments_free_text")

    def _add_transport(self) -> None:
        """<Transport> — transportni podaci."""
        transport = ET.SubElement(self.root, "Transport")

        means = ET.SubElement(transport, "Means_of_transport")

        dep_arr = ET.SubElement(means, "Departure_arrival_information")
        _val(dep_arr, "Identity", self._g("transport_id"))
        _val(dep_arr, "Nationality",
             self._g("transport_nacionalnost") or self._g("drzava_izvoza_sifra"))

        border_info = ET.SubElement(means, "Border_information")
        _val(border_info, "Identity", self._g("aktivno_transport") or self._g("transport_id"))
        _val(border_info, "Nationality",
             self._g("aktivno_transport_nat") or self._g("transport_nacionalnost") or self._g("drzava_izvoza_sifra"))
        vid = self._g("vid_granica") or "30"
        _val(border_info, "Mode", vid)

        vid_unutra = self._g("vid_unutra")
        if vid_unutra:
            _val(means, "Inland_mode_of_transport", vid_unutra)
        else:
            _null(means, "Inland_mode_of_transport")

        kontejner = getattr(self.draft, "kontejner", False)
        _val(transport, "Container_flag", "true" if kontejner else "false")
        kontejner_broj = self._g("kontejner_broj")
        if kontejner and kontejner_broj:
            _val(transport, "Container_number", kontejner_broj)

        delivery = ET.SubElement(transport, "Delivery_terms")
        _val(delivery, "Code", self._g("uslovi_kod"))
        _val(delivery, "Place", self._g("uslovi_mjesto"))
        _null(delivery, "Situation")

        # Izlazna carinarnica (format: "BA097098" ili "BA097098 - CR/GP Rača")
        border_office = ET.SubElement(transport, "Border_office")
        izlazna = self._g("izlazna_carinarnica")
        if " - " in izlazna:
            parts = izlazna.split(" - ", 1)
            _val(border_office, "Code", parts[0].strip())
            _val(border_office, "Name", parts[1].strip())
        else:
            _val(border_office, "Code", izlazna)
            ET.SubElement(border_office, "Name")

        place_loading = ET.SubElement(transport, "Place_of_loading")
        mjesto_ot = self._g("mjesto_otvaraca")
        if mjesto_ot:
            _null(place_loading, "Code")
            _val(place_loading, "Name", mjesto_ot)
        else:
            _null(place_loading, "Code")
            _null(place_loading, "Name")
        _null(place_loading, "Country")

        lok = self._g("lokacija_robe")
        if lok:
            _val(transport, "Location_of_goods", lok)
        else:
            _null(transport, "Location_of_goods")

    def _add_financial(self) -> None:
        """<Financial> — finansijski podaci."""
        financial = ET.SubElement(self.root, "Financial")

        fin_trans = ET.SubElement(financial, "Financial_transaction")
        _val(fin_trans, "code1", self._g("vrsta_trans_1", "1"))
        _val(fin_trans, "code2", self._g("vrsta_trans_2", "1"))

        bank = ET.SubElement(financial, "Bank")
        _null(bank, "Code")
        _null(bank, "Name")
        _null(bank, "Branch")
        _null(bank, "Reference")

        terms = ET.SubElement(financial, "Terms")
        _null(terms, "Code")
        _null(terms, "Description")

        # Total_invoice — prazno na nivou Financial (ASYCUDA ignoriše, vrijednost je u Valuation/Total)
        ET.SubElement(financial, "Total_invoice")

        deffered = ET.SubElement(financial, "Deffered_payment_reference")
        deffered.text = self._g("odgodjeno_placanje") or ""

        _val(financial, "Mode_of_payment", "PLAĆANJE ")

        amounts = ET.SubElement(financial, "Amounts")
        ET.SubElement(amounts, "Total_manual_taxes")
        _val(amounts, "Global_taxes", "0")
        ET.SubElement(amounts, "Totals_taxes")

        guarantee = ET.SubElement(financial, "Guarantee")
        _null(guarantee, "Name")
        _val(guarantee, "Amount", "0")
        ET.SubElement(guarantee, "Date")
        excluded = ET.SubElement(guarantee, "Excluded_country")
        _null(excluded, "Code")
        _null(excluded, "Name")

    def _add_warehouse(self) -> None:
        """<Warehouse> — skladište."""
        wh = ET.SubElement(self.root, "Warehouse")
        sklad = self._g("identifikacija_skladista")
        if sklad:
            _val(wh, "Identification", sklad)
        else:
            _null(wh, "Identification")
        ET.SubElement(wh, "Delay")

    def _add_transit(self) -> None:
        """<Transit> — tranzitni podaci (uglavnom prazno za IM)."""
        transit = ET.SubElement(self.root, "Transit")

        principal = ET.SubElement(transit, "Principal")
        _null(principal, "Code")
        _null(principal, "Name")
        _null(principal, "Representative")

        sig = ET.SubElement(transit, "Signature")
        _null(sig, "Place")
        ET.SubElement(sig, "Date")

        dest = ET.SubElement(transit, "Destination")
        _null(dest, "Office")
        _null(dest, "Country")

        seals = ET.SubElement(transit, "Seals")
        ET.SubElement(seals, "Number")
        _null(seals, "Identity")

        _null(transit, "Result_of_control")
        ET.SubElement(transit, "Time_limit")
        _null(transit, "Officer_name")

    def _add_valuation(self) -> None:
        """<Valuation> — vrijednosti na nivou zaglavlja."""
        val = ET.SubElement(self.root, "Valuation")

        _val(val, "Calculation_working_mode", "0")

        weight = ET.SubElement(val, "Weight")
        total_gross = sum(item.gross_mass_kg or 0.0 for item in self.draft.items)
        gross_w = ET.SubElement(weight, "Gross_weight")
        if total_gross:
            gross_w.text = f"{total_gross:.0f}"

        t1 = _parse_cost(self._g("trosak_1"))
        t2 = _parse_cost(self._g("trosak_2"))
        t3 = _parse_cost(self._g("trosak_3"))
        t4 = _parse_cost(self._g("trosak_4"))
        t5 = _parse_cost(self._g("trosak_5"))
        total_cost = t1 + t2 + t3 + t4 + t5

        cost_elem = ET.SubElement(val, "Total_cost")
        cost_elem.text = f"{total_cost:.1f}" if total_cost else ""

        kurs = self.draft.kurs or 1.0
        iznos = self.draft.iznos or 0.0

        # Total_CIF = iznos_BAM + ext_freight (ista logika kao na stavkama)
        # Formula iz referentnih fajlova: Total_CIF = (iznos_EUR × kurs) + Gs_external_freight
        iznos_bam = round(iznos * kurs, 2)
        total_cif = iznos_bam + t1
        cif_elem = ET.SubElement(val, "Total_CIF")
        if total_cif:
            cif_elem.text = f"{total_cif:.2f}"

        gs_inv = ET.SubElement(val, "Gs_Invoice")
        # Amount_national_currency = iznos u BAM (EUR × kurs)
        anc_inv = ET.SubElement(gs_inv, "Amount_national_currency")
        if iznos_bam:
            anc_inv.text = f"{iznos_bam:.2f}"
        amt_inv = ET.SubElement(gs_inv, "Amount_foreign_currency")
        # Rb.22 — iznos fakture u stranoj valuti (uvijek iz draft-a)
        if iznos:
            amt_inv.text = f"{iznos:.2f}"
        _val(gs_inv, "Currency_code", self._g("valuta", "EUR"))
        _val(gs_inv, "Currency_name", "Nema stranih valuta")
        _val(gs_inv, "Currency_rate", f"{kurs:.5f}")

        # Troškovi: t1=prevoz vanjski, t2=osiguranje, t3=ostalo, t4=unutrašnji, t5=popust
        _gs_cost_section(val, "Gs_external_freight", t1)
        _gs_cost_section(val, "Gs_internal_freight", t4)
        _gs_cost_section(val, "Gs_insurance", t2)
        _gs_cost_section(val, "Gs_other_cost", t3)
        _gs_cost_section(val, "Gs_deduction", t5)

        total = ET.SubElement(val, "Total")
        ti = ET.SubElement(total, "Total_invoice")
        if iznos_bam:
            ti.text = f"{iznos_bam:.2f}"
        total_net = sum(item.net_mass_kg or 0.0 for item in self.draft.items)
        tw = ET.SubElement(total, "Total_weight")
        if total_net:
            tw.text = f"{total_net:.0f}"

    # ─────────────────────────────────────────────────────────────
    # Item sekcije
    # ─────────────────────────────────────────────────────────────

    def _add_items(self) -> None:
        """Dodaje <Item> za svako naimenovanje."""
        header_docs = list(getattr(self.draft, "header_attached_documents", []) or [])

        # Skupi dokumente o porijeklu sa svih stavki i dodaj na prvu stavku.
        # ASYCUDA World standard: svi Attached_documents idu samo na prvu stavku.
        seen_origin_keys: set[tuple] = set()
        for item in self.draft.items:
            pref_doc_code = _PREF_TO_DOC_CODE.get(item.preference_code or "", "")
            if pref_doc_code:
                origin_ref = item.attached_document1 or ""
                key = (pref_doc_code, origin_ref)
                if key not in seen_origin_keys:
                    seen_origin_keys.add(key)
                    header_docs.append(AttachedDocument(
                        code=pref_doc_code,
                        name=_PREF_TO_DOC_NAME.get(pref_doc_code, ""),
                        number=origin_ref,
                        from_rule=True,
                    ))

        for idx, item in enumerate(self.draft.items):
            is_first = idx == 0
            self._add_single_item(item, header_docs if is_first else [], is_first)

    def _add_single_item(
        self,
        item: NaimenovanjeDraft,
        header_docs: list,
        is_first: bool,
    ) -> None:
        """Dodaje jednu <Item> sekciju."""
        item_elem = ET.SubElement(self.root, "Item")

        # Troškovi na nivou zaglavlja (za Valuation_item alpha raspodjelu)
        t1 = _parse_cost(self._g("trosak_1"))
        t2 = _parse_cost(self._g("trosak_2"))
        t3 = _parse_cost(self._g("trosak_3"))
        t4 = _parse_cost(self._g("trosak_4"))
        t5 = _parse_cost(self._g("trosak_5"))
        total_items_value = sum(it.item_value or 0.0 for it in self.draft.items)
        item_val = item.item_value or 0.0
        alpha = item_val / total_items_value if total_items_value > 0 else 0.0

        # Priložene isprave
        from_rule_codes: list[str] = []

        # 1. Header dokumenti (samo za prvu stavku)
        for doc in header_docs:
            self._add_attached_doc(item_elem, doc)
            if doc.from_rule:
                from_rule_codes.append(doc.code)

        # 2. Strukturirani dokumenti stavke (bez pref_doc — ti su prebačeni na prvu stavku)
        if item.attached_documents:
            for doc in item.attached_documents:
                self._add_attached_doc(item_elem, doc)
                if doc.from_rule:
                    from_rule_codes.append(doc.code)

        # Packages
        packages = ET.SubElement(item_elem, "Packages")
        qty = int(item.package_qty) if item.package_qty and item.package_qty > 0 else 1
        _val(packages, "Number_of_packages", str(qty))
        _val(packages, "Marks1_of_packages", item.package_marks or "X")
        _val(packages, "Marks2_of_packages", "X")
        _val(packages, "Kind_of_packages_code", item.package_code or "PK")
        _val(packages, "Kind_of_packages_name", item.package_name or "Pakovanje")

        # IncoTerms (na nivou stavke = isti kao zaglavlje)
        incoterms = ET.SubElement(item_elem, "IncoTerms")
        _val(incoterms, "Code", self._g("uslovi_kod"))
        _val(incoterms, "Place", self._g("uslovi_mjesto"))

        # Tarification
        tarif = ET.SubElement(item_elem, "Tarification")
        _null(tarif, "Tarification_data")

        hscode = ET.SubElement(tarif, "HScode")
        _val(hscode, "Commodity_code", item.tariff_code or "")
        _val(hscode, "Precision_1", item.tariff_suffix or "000")
        _null(hscode, "Precision_2")
        _null(hscode, "Precision_3")
        _null(hscode, "Precision_4")

        pref_elem = ET.SubElement(tarif, "Preference_code")
        if item.preference_code:
            pref_elem.text = item.preference_code
        else:
            ET.SubElement(pref_elem, "null")

        _val(tarif, "Extended_customs_procedure", item.procedure_code or "4000")
        _val(tarif, "National_customs_procedure", item.procedure_prev_code or "000")

        quota_code_e = ET.SubElement(tarif, "Quota_code")
        if item.quota_code:
            quota_code_e.text = item.quota_code
        else:
            ET.SubElement(quota_code_e, "null")

        quota = ET.SubElement(tarif, "Quota")
        _null(quota, "QuotaCode")
        _null(quota, "QuotaId")
        quota_item = ET.SubElement(quota, "QuotaItem")
        _null(quota_item, "ItmNbr")

        # 3x Supplementary_unit (prazno)
        for _ in range(3):
            su = ET.SubElement(tarif, "Supplementary_unit")
            _null(su, "Suppplementary_unit_code")
            _null(su, "Suppplementary_unit_name")
            ET.SubElement(su, "Suppplementary_unit_quantity")

        item_price = ET.SubElement(tarif, "Item_price")
        if item.item_value:
            item_price.text = f"{item.item_value:.2f}"

        _val(tarif, "Valuation_method_code", "1")

        # Value_item — formula troškova: ext_freight+int_freight+insurance+other-deduction
        # Ista logika kao _fill_item_valuation (raspodjela po alpha koeficijentu)
        if total_items_value > 0:
            _vi_alpha = item_val / total_items_value
        else:
            _vi_alpha = 0.0
        _vi_ext = t1 * _vi_alpha
        _vi_int = t4 * _vi_alpha
        _vi_ins = t2 * _vi_alpha
        _vi_oth = t3 * _vi_alpha
        _vi_ded = t5 * _vi_alpha
        vi_elem = ET.SubElement(tarif, "Value_item")
        vi_elem.text = f"{_vi_ext:.2f}+{_vi_int:.2f}+{_vi_ins:.2f}+{_vi_oth:.2f}-{_vi_ded:.2f}"

        # Attached_doc_item — na prvoj stavci: space-separated from_rule kodovi
        # Na ostalim stavkama: null (ASYCUDA World standard)
        if is_first and from_rule_codes:
            adi = ET.SubElement(tarif, "Attached_doc_item")
            adi.text = " ".join(from_rule_codes) + " "
        else:
            _null(tarif, "Attached_doc_item")

        ai_code = ET.SubElement(tarif, "A.I._code")
        ET.SubElement(ai_code, "null")

        # Goods_description
        goods = ET.SubElement(item_elem, "Goods_description")
        _val(goods, "Country_of_origin_code", item.origin_country_code or "")
        _null(goods, "Country_of_origin_region")
        _val(goods, "Description_of_goods", item.goods_description or ".")
        _val(goods, "Commercial_Description", item.goods_trade_name or "")

        # Previous_doc — Rub.40 (category/type/broj)
        prev = ET.SubElement(item_elem, "Previous_doc")
        prev_cat = item.previous_document or ""
        prev_type = item.previous_document2 or ""
        prev_num = item.previous_document3 or ""

        if prev_cat:
            _val(prev, "Previous_category", prev_cat)
        else:
            _null(prev, "Previous_category")

        if prev_type:
            _val(prev, "Previous_type", prev_type)
        else:
            _null(prev, "Previous_type")

        _val(prev, "Summary_declaration", prev_num)
        _null(prev, "Summary_declaration_sl")
        _null(prev, "Previous_document_reference")
        _null(prev, "Previous_warehouse_code")

        _null(item_elem, "Licence_number")
        ET.SubElement(item_elem, "Amount_deducted_from_licence")
        ET.SubElement(item_elem, "Quantity_deducted_from_licence")

        # Free_text_1 — PE1/PE2 referenca iz le_rubrika44_4 (attached_document4)
        ft1_val = item.attached_document4 or item.attached_document2 or ""
        if ft1_val:
            _val(item_elem, "Free_text_1", ft1_val)
        else:
            _null(item_elem, "Free_text_1")

        _null(item_elem, "Free_text_2")

        # Taxation (prazno — računa AsycudaWorld)
        taxation = ET.SubElement(item_elem, "Taxation")
        ET.SubElement(taxation, "Item_taxes_amount")
        ET.SubElement(taxation, "Item_taxes_guaranted_amount")
        _val(taxation, "Item_taxes_mode_of_payment", "1")
        ET.SubElement(taxation, "Counter_of_normal_mode_of_payment")
        ET.SubElement(taxation, "Displayed_item_taxes_amount")

        for _ in range(8):
            tl = ET.SubElement(taxation, "Taxation_line")
            _null(tl, "Duty_tax_code")
            ET.SubElement(tl, "Duty_tax_Base")
            ET.SubElement(tl, "Duty_tax_rate")
            ET.SubElement(tl, "Duty_tax_amount")
            _null(tl, "Duty_tax_MP")
            _null(tl, "Duty_tax_Type_of_calculation")

        # Valuation_item — sa CIF kalkulacijom
        val_item = ET.SubElement(item_elem, "Valuation_item")

        wi = ET.SubElement(val_item, "Weight_itm")
        gw = ET.SubElement(wi, "Gross_weight_itm")
        if item.gross_mass_kg:
            gw.text = f"{item.gross_mass_kg:.0f}"
        nw = ET.SubElement(wi, "Net_weight_itm")
        if item.net_mass_kg:
            nw.text = f"{item.net_mass_kg:.0f}"

        self._fill_item_valuation(val_item, item, total_items_value, t1, t2, t3, t4, t5)

    def _fill_item_valuation(
        self,
        val_item: ET.Element,
        item: NaimenovanjeDraft,
        total_items_value: float,
        t1: float, t2: float, t3: float, t4: float, t5: float,
    ) -> None:
        """Popuni Valuation_item sekciju sa stvarnim CIF kalkulacijama.

        Rb.22 = Item_price = cijena robe u EUR (strana valuta)
        Rb.46 = Statistical_value = cijena robe u BAM + vanjski prevoz do granice
                Formula: (Item_price_EUR × kurs) + ext_freight_BAM
        """
        item_value = item.item_value or 0.0
        kurs = self.draft.kurs or 1.0

        # Alpha koeficijent — proporcionalni udio ove stavke u ukupnoj vrijednosti
        if total_items_value > 0:
            alpha = item_value / total_items_value
        else:
            alpha = 0.0

        # Raspodjela troškova proporcionalno
        item_ext_freight = t1 * alpha
        item_int_freight = t4 * alpha
        item_insurance = t2 * alpha
        item_other = t3 * alpha
        item_deduction = t5 * alpha  # popust

        total_cost_itm = item_ext_freight + item_int_freight + item_insurance + item_other - item_deduction

        # Rb.46 — statistička vrijednost = vrijednost robe u BAM + vanjski prevoz do granice
        # (NE uključuje unutrašnji prevoz, osiguranje, ostalo)
        item_value_bam = round(item_value * kurs, 2)
        total_cif_itm = item_value_bam + item_ext_freight

        # --- Total_cost_itm ---
        tci = ET.SubElement(val_item, "Total_cost_itm")
        if total_cost_itm:
            tci.text = f"{total_cost_itm:.2f}"

        # --- Total_CIF_itm (= Statistical_value = Rb.46) ---
        cif_itm = ET.SubElement(val_item, "Total_CIF_itm")
        if total_cif_itm:
            cif_itm.text = f"{total_cif_itm:.2f}"

        _val(val_item, "Rate_of_adjustement", "1")

        # --- Statistical_value = Rb.46 ---
        sv = ET.SubElement(val_item, "Statistical_value")
        if total_cif_itm:
            sv.text = f"{total_cif_itm:.2f}"

        # --- Alpha koeficijent ---
        ac = ET.SubElement(val_item, "Alpha_coeficient_of_apportionment")
        if alpha:
            ac.text = f"{alpha:.10f}"

        # --- Item_Invoice ---
        ii = ET.SubElement(val_item, "Item_Invoice")
        # Amount_national_currency = vrijednost robe u BAM (EUR × kurs)
        anc = ET.SubElement(ii, "Amount_national_currency")
        if item_value_bam:
            anc.text = f"{item_value_bam:.2f}"
        iv = ET.SubElement(ii, "Amount_foreign_currency")
        if item_value:
            iv.text = f"{item_value:.2f}"
        _val(ii, "Currency_code", item.currency or "EUR")
        _null(ii, "Currency_name")
        _val(ii, "Currency_rate", f"{kurs:.5f}")

        # --- Troškovi po stavci ---
        self._item_cost_section_filled(val_item, "item_external_freight", item_ext_freight)
        self._item_cost_section_filled(val_item, "item_internal_freight", item_int_freight)
        self._item_cost_section_filled(val_item, "item_insurance", item_insurance)
        self._item_cost_section_filled(val_item, "item_other_cost", item_other)
        self._item_cost_section_filled(val_item, "item_deduction", item_deduction)

        # --- Market_valuer ---
        mv = ET.SubElement(val_item, "Market_valuer")
        ET.SubElement(mv, "Rate")
        _null(mv, "Currency_code")
        ET.SubElement(mv, "Currency_amount")
        _null(mv, "Basis_description")
        ET.SubElement(mv, "Basis_amount")

    def _item_cost_section_filled(self, parent: ET.Element, tag: str, amount: float, negative: bool = False) -> None:
        """Kreira item_* sekciju troška stavke sa stvarnom vrijednošću."""
        gs = ET.SubElement(parent, tag)
        val = -amount if negative else amount
        _val(gs, "Amount_national_currency", f"{val:.2f}" if val else "0.0")
        _val(gs, "Amount_foreign_currency", f"{val:.2f}" if val else "0.0")
        if val:
            _null(gs, "Currency_code")   # <null/> kad postoji iznos
        else:
            ET.SubElement(gs, "Currency_code")  # prazan kad je 0
        _val(gs, "Currency_name", "Nema stranih valuta")
        _val(gs, "Currency_rate", "1" if val else "0")

    def _add_attached_doc(self, item_elem: ET.Element, doc: AttachedDocument) -> None:
        """Dodaje <Attached_documents> element."""
        attached = ET.SubElement(item_elem, "Attached_documents")
        _val(attached, "Attached_document_code", doc.code)
        if doc.name:
            _val(attached, "Attached_document_name", doc.name)
        ref = ET.SubElement(attached, "Attached_document_reference")
        ref.text = doc.number or ""
        if doc.from_rule:
            _val(attached, "Attached_document_from_rule", "1")


# ─────────────────────────────────────────────────────────────────────────────
# Javna API funkcija
# ─────────────────────────────────────────────────────────────────────────────

def export_to_xml(draft: DeclarationDraft, output_path: str) -> bool:
    """
    Exportuje DeclarationDraft u ASYCUDA XML fajl.

    Args:
        draft: Draft sa svim podacima
        output_path: Putanja za snimanje XML fajla

    Returns:
        True ako je uspješno, False inače
    """
    try:
        builder = AsycudaXMLBuilder(draft)
        root = builder.build()

        tree = ET.ElementTree(root)
        ET.indent(tree, space="")  # Bez indentacije — Asycuda preferuje kompaktan format

        tree.write(
            output_path,
            encoding="UTF-8",
            xml_declaration=True,
            short_empty_elements=True,
        )

        file_size = Path(output_path).stat().st_size
        print(f"XML exportovan: {output_path} ({file_size:,} bytes, {len(draft.items)} stavki)")
        return True

    except Exception as e:
        logger.error(f"Greska pri exportu XML: {e}", exc_info=True)
        print(f"GRESKA pri exportu XML: {e}")
        return False
