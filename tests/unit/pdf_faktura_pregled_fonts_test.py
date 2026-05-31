import pytest

pytest.importorskip("reportlab")

from exporters import pdf_faktura_pregled as exporter_mod


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

    exporter = exporter_mod.PDFFakturaPregled()

    assert exporter.font_regular == "LibSans"
    assert exporter.font_bold == "LibSans-Bold"
    assert exporter.styles["PregledTitle"].fontName == "LibSans-Bold"
    assert exporter.styles["PregledSubTitle"].fontName == "LibSans"
    assert exporter.styles["PregledTableCell"].fontName == "LibSans"
    assert len(registered) == 4
    assert all(path.startswith(target_prefix) for _, path in registered)


def test_register_fonts_fallback_to_reportlab_defaults(monkeypatch):
    monkeypatch.setattr(exporter_mod.Path, "exists", lambda *_args, **_kwargs: False, raising=False)
    monkeypatch.setattr(exporter_mod, "TTFont", lambda name, path: (name, path))
    monkeypatch.setattr(exporter_mod.pdfmetrics, "registerFont", lambda _font: (_ for _ in ()).throw(AssertionError))

    exporter = exporter_mod.PDFFakturaPregled()

    assert exporter.font_regular == "Helvetica"
    assert exporter.font_bold == "Helvetica-Bold"
    assert exporter.styles["PregledTitle"].fontName == "Helvetica-Bold"
    assert exporter.styles["PregledSubTitle"].fontName == "Helvetica"


def test_register_fonts_exception_keeps_defaults(monkeypatch):
    monkeypatch.setattr(exporter_mod.Path, "home", lambda: exporter_mod.Path("/home/test"))
    monkeypatch.setattr(exporter_mod.Path, "exists", lambda *_args, **_kwargs: True, raising=False)
    monkeypatch.setattr(exporter_mod, "TTFont", lambda name, path: (name, path))

    def fail_register(_font):
        raise RuntimeError("register failed")

    monkeypatch.setattr(exporter_mod.pdfmetrics, "registerFont", fail_register)

    exporter = exporter_mod.PDFFakturaPregled()

    assert exporter.font_regular == "Helvetica"
    assert exporter.font_bold == "Helvetica-Bold"
    assert exporter.font_italic == "Helvetica-Oblique"
    assert exporter.styles["PregledFakturaHeader"].fontName == "Helvetica-Bold"
    assert exporter.styles["PregledSubTitle"].fontName == "Helvetica"
