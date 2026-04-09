"""
Test XML export gap fixes na stvarnim Blagić-Attoš fakturama.
"""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from importers.blagic_attos_importer import parse_blagic_attos_with_auto_combine
from core.draft.draft import DeclarationDraft, NaimenovanjeDraft, InvoiceLine
from services.create_naimenovanja_service import CreateNaimenovanjaService
from exporters.asycuda_xml_builder import export_to_xml
import xml.etree.ElementTree as ET


FAKTURE_DIR = Path(__file__).resolve().parent.parent / "najavauvoza" / "blagic-attos"


def _check_xpath(root: ET.Element, tag: str) -> str:
    """Nađi vrijednost prvog elementa sa datim tagom."""
    for elem in root.iter(tag):
        # Provjeri ima li text
        if elem.text and elem.text.strip():
            return elem.text.strip()
        # Provjeri child elemente za Amount_foreign_currency itd.
        for c in elem:
            if c.tag == "null":
                continue
            if c.text and c.text.strip():
                return c.text.strip()
            # Nested (npr. item_external_freight > Amount_foreign_currency)
            for gc in c:
                if gc.text and gc.text.strip():
                    return gc.text.strip()
        # Provjeri ima li <null/>
        has_null = any(c.tag == "null" for c in elem)
        if has_null and not any(c.text and c.text.strip() for c in elem):
            return "(prazno)"
    return "(nije pronađeno)"


def _find_all_items(root: ET.Element):
    """Nađi sve Item elemente."""
    return list(root.iter("Item"))


def test_faktura(pdf_path: Path):
    print(f"\n{'='*70}")
    print(f"📄 Test: {pdf_path.name}")
    print(f"{'='*70}")

    # 1. Parsiraj fakturu
    print(f"\n🔍 Parsiram PDF...")
    try:
        result = parse_blagic_attos_with_auto_combine(str(pdf_path))
    except Exception as e:
        print(f"❌ Greška pri parsiranju: {e}")
        import traceback
        traceback.print_exc()
        return

    lines = result.items or []
    if not lines:
        print(f"⚠️ Nema stavki iz PDF-a")
        return

    print(f"✅ Parsirano: {len(lines)} stavki")
    total_val = sum(getattr(l, 'iznos', 0) or 0 for l in lines)
    print(f"   Ukupno: {total_val:.2f}")
    print(f"   Valuta: {result.currency or 'N/A'}")

    # 2. Kreiraj draft
    draft = DeclarationDraft()
    draft.invoice_lines = lines
    draft.iznos = total_val
    draft.valuta = result.currency or "EUR"
    draft.kurs = 1.0

    # Postavi osnovne zaglavlje podatke
    draft.ured_odredista = "BA097012 CI Bijeljina"
    draft.drzava_izvoza_sifra = "RS"
    draft.drzava_izvoza_naziv = "Srbija"
    draft.transport_id = "E25A456"
    draft.transport_nacionalnost = "BA"
    draft.aktivno_transport = "E25A456"
    draft.aktivno_transport_nat = "BA"
    draft.kontejner = False
    draft.vid_granica = "30"
    draft.uslovi_kod = "EXW"
    draft.uslovi_mjesto = "BEOGRAD"
    draft.mjesto_otvaraca = "BEOGRAD"
    draft.izlazna_carinarnica = "BA097098"
    draft.trosak_1 = "6020,0"    # external freight
    draft.trosak_4 = "4300,0"    # internal freight
    draft.trosak_2 = "100,0"     # insurance
    draft.trosak_3 = "0"         # other
    draft.trosak_5 = "0"         # deduction

    # Postavi zemlju porijekla
    for line in lines:
        if not getattr(line, 'zemlja_porijekla', ''):
            line.zemlja_porijekla = "RS"

    # 3. Kreiraj naimenovanja (one-to-one: svaka linija → naimenovanje)
    service = CreateNaimenovanjaService(draft)
    count = service.create_one_to_one()

    print(f"✅ Kreirano {len(draft.items)} naimenovanja")

    # 4. Exportuj XML
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        xml_path = f.name

    ok = export_to_xml(draft, xml_path)
    if not ok:
        print(f"❌ XML export nije uspio")
        return

    file_size = Path(xml_path).stat().st_size
    print(f"✅ XML exportovan: {file_size:,} bytes")

    # 5. Validiraj XML
    tree = ET.parse(xml_path)
    root = tree.getroot()

    print(f"\n{'─'*70}")
    print(f"📊 VALIDACIJA XML GAP-OVA")
    print(f"{'─'*70}")

    # Gap 1: Customs_clearance_office_code
    val = _check_xpath(root, "Customs_clearance_office_code")
    status = "✅" if val != "(prazno)" else "❌"
    print(f"  {status} Customs_clearance_office_code: {val}")

    # Gap 2: Nationality (Departure_arrival - NOT Border_information)
    nat_val = "(nije pronađeno)"
    for dep_arr in root.iter("Departure_arrival_information"):
        nat = dep_arr.find("Nationality")
        if nat is not None:
            if nat.text and nat.text.strip():
                nat_val = nat.text.strip()
            else:
                nat_val = "(prazno)"
            break
    status = "✅" if nat_val in ("BA", "RS", "DE", "HR", "SI") else "⚠️"
    print(f"  {status} Nationality (Departure): {nat_val}")

    # Gap 3: Amount_foreign_currency (Rb.22)
    val = _check_xpath(root, "Amount_foreign_currency")
    status = "✅" if val != "(prazno)" and val != "0" else "❌"
    print(f"  {status} Amount_foreign_currency: {val}")

    # Gap 4: Total_CIF
    val = _check_xpath(root, "Total_CIF")
    status = "✅" if val != "(prazno)" else "❌"
    print(f"  {status} Total_CIF: {val}")

    # Gap 5: Total_invoice
    val = _check_xpath(root, "Total_invoice")
    status = "✅" if val != "(prazno)" else "❌"
    print(f"  {status} Total_invoice: {val}")

    # Gap 6: Value_details
    val = _check_xpath(root, "Value_details")
    status = "✅" if val != "(prazno)" else "❌"
    print(f"  {status} Value_details: {val}")

    # Gap 7: Country_of_origin_name
    val = _check_xpath(root, "Country_of_origin_name")
    status = "✅" if val and val not in ("RS", "BA", "(prazno)") else "⚠️"
    print(f"  {status} Country_of_origin_name: {val}")

    # Gap 8: Per-stavka kalkulacija
    items = _find_all_items(root)
    print(f"\n  📦 Per-stavka kalkulacija ({len(items)} stavki):")

    all_items_ok = True
    for idx, item_el in enumerate(items[:3]):  # Prve 3 stavke
        val_item = item_el.find("Valuation_item")
        if val_item is None:
            print(f"    ❌ Stavka {idx+1}: Nema Valuation_item")
            all_items_ok = False
            continue

        cif_itm = _check_xpath(val_item, "Total_CIF_itm")
        alpha = _check_xpath(val_item, "Alpha_coeficient_of_apportionment")
        cost_itm = _check_xpath(val_item, "Total_cost_itm")
        stat_val = _check_xpath(val_item, "Statistical_value")
        value_item = _check_xpath(val_item, "Value_item")
        ext_f = _check_xpath(val_item, "item_external_freight")

        item_ok = (
            cif_itm != "(prazno)" and cif_itm != "(nije pronađeno)"
            and alpha != "(prazno)" and alpha != "(nije pronađeno)"
            and cost_itm != "(prazno)" and cost_itm != "(nije pronađeno)"
        )
        status = "✅" if item_ok else "❌"
        a_short = alpha[:15] if len(alpha) > 15 else alpha
        print(f"    {status} Stavka {idx+1}: CIF={cif_itm}, alpha={a_short}, cost={cost_itm}")
        if value_item != "(prazno)" and value_item != "(nije pronađeno)":
            print(f"       Value_item: {value_item}")
        if ext_f != "(prazno)" and ext_f != "(nije pronađeno)":
            print(f"       Ext_freight: {ext_f}")
        if not item_ok:
            all_items_ok = False

    # Summary
    print(f"\n{'─'*70}")
    if all_items_ok:
        print(f"✅ SVE PROVJERE PROŠLE — {pdf_path.name}")
    else:
        print(f"⚠️ NEKE PROVJERE NISU PROŠLE — {pdf_path.name}")
    print(f"{'─'*70}")

    # Cleanup
    os.unlink(xml_path)


def main():
    pdf_files = sorted(FAKTURE_DIR.glob("Faktura*.pdf"))
    if not pdf_files:
        print(f"❌ Nema PDF fajlova u {FAKTURE_DIR}")
        return

    for pdf in pdf_files:
        test_faktura(pdf)


if __name__ == "__main__":
    main()
