import pytest

pytest.importorskip("reportlab")

from exporters import pdf_invoice_exporter as exporter_mod
from core.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft


def test_register_fonts_uses_discovered_directory(monkeypatch):
    target_prefix = "/home/test/.local/share/fonts"
    font_suffixes = {
        "LiberationSans-Regular.ttf",
        "LiberationSans-Bold.ttf",
        "LiberationSans-Italic.ttf",
        "LiberationSans-BoldItalic.ttf",
    }
    registered = []

    monkeypatch.setattr(exporter_mod.Path, "home", lambda: exporter_mod.Path("/home/test"))

    def fake_exists(path_obj):
        path_str = str(path_obj)
        return path_str.startswith(target_prefix) and any(
            path_str.endswith(suffix) for suffix in font_suffixes
        )

    monkeypatch.setattr(exporter_mod.Path, "exists", fake_exists, raising=False)
    monkeypatch.setattr(exporter_mod, "TTFont", lambda name, path: (name, path))
    monkeypatch.setattr(exporter_mod.pdfmetrics, "registerFont", lambda font: registered.append(font))

    exporter = exporter_mod.PDFInvoiceExporter()

    assert exporter.font_regular == "LibSans"
    assert exporter.font_bold == "LibSans-Bold"
    assert exporter.styles["CustomHeading"].fontName == "LibSans-Bold"
    assert exporter.styles["TableCell"].fontName == "LibSans"
    assert len(registered) == 4
    assert all(path.startswith(target_prefix) for _, path in registered)


def test_register_fonts_fallback_to_reportlab_defaults(monkeypatch):
    monkeypatch.setattr(exporter_mod.Path, "exists", lambda *_args, **_kwargs: False, raising=False)
    monkeypatch.setattr(exporter_mod, "TTFont", lambda name, path: (name, path))
    monkeypatch.setattr(exporter_mod.pdfmetrics, "registerFont", lambda _font: (_ for _ in ()).throw(AssertionError))

    exporter = exporter_mod.PDFInvoiceExporter()

    assert exporter.font_regular == "Helvetica"
    assert exporter.font_bold == "Helvetica-Bold"
    assert exporter.styles["CustomHeading"].fontName == "Helvetica-Bold"
    assert exporter.styles["TableCell"].fontName == "Helvetica"


def test_register_fonts_exception_keeps_defaults(monkeypatch):
    monkeypatch.setattr(exporter_mod.Path, "home", lambda: exporter_mod.Path("/home/test"))
    monkeypatch.setattr(exporter_mod.Path, "exists", lambda *_args, **_kwargs: True, raising=False)
    monkeypatch.setattr(exporter_mod, "TTFont", lambda name, path: (name, path))

    def fail_register(_font):
        raise RuntimeError("register failed")

    monkeypatch.setattr(exporter_mod.pdfmetrics, "registerFont", fail_register)

    exporter = exporter_mod.PDFInvoiceExporter()

    assert exporter.font_regular == "Helvetica"
    assert exporter.font_bold == "Helvetica-Bold"
    assert exporter.styles["NaimenovanjeHeader"].fontName == "Helvetica-Bold"
    assert exporter.styles["TableCell"].fontName == "Helvetica"


def test_export_includes_lines_without_assigned_ordinal(tmp_path):
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(
            line_no=1,
            invoice_number="1476/26",
            naziv_robe="TEST ROBA",
            tarifni_broj="21069098",
            zemlja_porijekla="AT",
            povlastica="EUPR",
            jm="KOM",
            kolicina=10,
            iznos=25.5,
            bruto_kg=2.1,
            neto_kg=1.9,
            assigned_naimenovanje_ordinal=0,
        )
    ]
    draft.items = [
        NaimenovanjeDraft(item_id="test-1", ordinal_no=1, tariff_code="21069098")
    ]
    output_path = tmp_path / "faktura_naimenovanja.pdf"

    assert exporter_mod.export_invoice_to_pdf(draft, str(output_path)) is True

    pdfplumber = pytest.importorskip("pdfplumber")
    with pdfplumber.open(output_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "STAVKE BEZ NAIMENOVANJA" in text
    assert "TEST ROBA" in text
