from openpyxl import Workbook

from services.naimenovanja.declaration_assembly import DeclarationAssembly


def test_glavna_lista_ulazi_u_draft_sa_osmocifrenom_tarifom(tmp_path):
    path = tmp_path / "glavna_lista.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "Rbr",
            "Šifra",
            "Naziv dobra / usluge",
            "JM",
            "Kol.",
            "Tarifni br",
            "Zemlja porekla",
            "Preferencijal",
        ]
    )
    sheet.append([1, "A-1", "GREJAC", "KOM", 2, "8516802090", "IT", "DA"])
    workbook.save(path)
    workbook.close()

    assembly = DeclarationAssembly()
    assembly.load_master_list(str(path))
    draft = assembly.create_draft()

    assert draft.invoice_lines[0].tarifni_broj == "85168020"
