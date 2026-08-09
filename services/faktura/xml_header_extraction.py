"""
XML Header Extraction — parsiranje ASYCUDA XML zaglavlja
"""

from services.security.safe_xml import safe_parse


def extract_header_from_xml(xml_path: str) -> dict:
    """Parsira ASYCUDA XML i vraća dict sa header poljima za DeclarationDraft."""
    tree = safe_parse(xml_path)
    root = tree.getroot()

    def _text(xpath: str) -> str:
        el = root.find(xpath)
        return (el.text or '').strip().split('\n')[0].strip() if el is not None else ''

    def _lines(xpath: str) -> list:
        el = root.find(xpath)
        if el is None or not (el.text or '').strip():
            return []
        return [ln.strip() for ln in el.text.strip().split('\n') if ln.strip()]

    header = {}

    izv_lines = _lines('.//Traders/Exporter/Exporter_name')
    if izv_lines:
        header['izvoznik_naziv'] = izv_lines[0]
        if len(izv_lines) > 1:
            header['izvoznik_grad'] = izv_lines[1]
        if len(izv_lines) > 2:
            header['izvoznik_drzava'] = izv_lines[2]

    cons_lines = _lines('.//Traders/Consignee/Consignee_name')
    if cons_lines:
        header['primalac_naziv'] = cons_lines[0]
        if len(cons_lines) > 1:
            header['primalac_grad'] = cons_lines[1]
        if len(cons_lines) > 2:
            header['primalac_adresa'] = cons_lines[2]
    cons_code = _text('.//Traders/Consignee/Consignee_code')
    if cons_code:
        header['primalac_id'] = cons_code

    ured_sifra = _text('.//Identification/Office_segment/Customs_clearance_office_code')
    ured_naziv = _text('.//Identification/Office_segment/Customs_Clearance_office_name')
    if ured_sifra or ured_naziv:
        header['ured_odredista'] = f"{ured_sifra}  {ured_naziv}".strip()

    zem = _text('.//General_information/Country/Export/Export_country_code')
    if zem:
        header['drzava_izvoza_sifra'] = zem
        naziv = _text('.//General_information/Country/Export/Export_country_name')
        if naziv:
            header['drzava_izvoza_naziv'] = naziv

    val = _text('.//Valuation/Gs_Invoice/Currency_code')
    if val:
        header['valuta'] = val

    incoterm = _text('.//Item/IncoTerms/Code')
    if incoterm:
        header['uslovi_kod'] = incoterm
    place = _text('.//Item/IncoTerms/Place')
    if place:
        header['uslovi_mjesto'] = place

    tip = _text('.//Identification/Type/Type_of_declaration')
    if tip:
        header['deklaracija_tip'] = tip
    ozn = _text('.//Identification/Type/Declaration_gen_procedure_code')
    if ozn:
        header['deklaracija_oznaka'] = ozn
    tip_x = _text('.//Identification/Type/Type_of_Declaration_X')
    if tip_x:
        header['deklaracija_a'] = tip_x

    return header


def resolve_exporter_name(draft_izvoznik_naziv: str, invoice_lines) -> str:
    """Odredi izvoznika za pretragu prethodne deklaracije.

    Prioritet: već popunjeno draft zaglavlje (iz _apply_import_result_to_header),
    zatim exporter prve fakturne linije koja ga ima.
    """
    izvoznik = (draft_izvoznik_naziv or '').strip()
    if izvoznik:
        return izvoznik
    for line in invoice_lines or []:
        cand = (getattr(getattr(line, 'exporter', None), 'name', '') or '').strip()
        if cand:
            return cand.split('\n')[0].strip()
    return ''


def format_header_preview(header: dict, field_labels: dict) -> list:
    """Formatira header dict u listu prikaznih linija za potvrdni dijalog."""
    return [
        f"  {label}: {header[field]}"
        for field, label in field_labels.items()
        if header.get(field)
    ]


def apply_header_to_draft(draft, header: dict) -> None:
    """Upiši header vrijednosti u draft — samo postojeća polja, samo ne-prazne vrijednosti."""
    for field, value in header.items():
        if value and hasattr(draft, field):
            setattr(draft, field, value)
