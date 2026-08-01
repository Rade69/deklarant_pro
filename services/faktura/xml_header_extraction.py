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

    header = {}

    izvoznik = _text('.//Traders/Exporter/Exporter_name')
    if izvoznik:
        header['izvoznik_naziv'] = izvoznik

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
