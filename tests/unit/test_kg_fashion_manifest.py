from pathlib import Path

import pytest

from importers.vendors.kg_fashion import kg_fashion_importer as kgi


KG_REAL_MANIFEST = Path("/home/radovan/Downloads/fwfakturekojepraterobupretaporter/15467- PTP 11.05.2026..xls")


def test_import_kg_fashion_marks_manifest_as_consumed(monkeypatch, tmp_path):
    pdf = tmp_path / "RAC.296.pdf"
    manifest = tmp_path / "15467- PTP 11.05.2026..xls"
    pdf.write_text("", encoding="utf-8")
    manifest.write_text("", encoding="utf-8")

    def fake_parse_pdf(_path):
        return {"invoice_no": "25-296/2026", "currency": "EUR"}, [
            kgi.KGLine(
                rbr=1,
                code="ART-1",
                naziv="BUENO CIPELE",
                unit="PAR",
                qty=2,
                price=10,
                amount=20,
                currency="EUR",
                tarifni_broj="64039900",
                co="",
            )
        ]

    monkeypatch.setattr(kgi, "parse_kg_fashion_pdf", fake_parse_pdf)
    monkeypatch.setattr(
        kgi,
        "_parse_manifest_xls",
        lambda _path: {296: {"has_eur1": True, "co": "TR", "bruto": 12.5, "neto": 11.5}},
    )

    result = kgi.import_kg_fashion(str(pdf))

    assert result.consumed_paths == [str(manifest)]
    assert result.has_origin_statement is False
    assert result.bruto_kg == 12.5
    assert result.neto_kg == 11.5
    assert result.items[0].zemlja_porijekla == "TR"
    assert result.items[0].has_origin_statement is False
    assert result.items[0].raw["eur1_suggested"] is True


def test_import_kg_fashion_preserves_pdf_country_over_manifest(monkeypatch, tmp_path):
    pdf = tmp_path / "RAC.296.pdf"
    manifest = tmp_path / "15467- PTP 11.05.2026..xls"
    pdf.write_text("", encoding="utf-8")
    manifest.write_text("", encoding="utf-8")

    def fake_parse_pdf(_path):
        return {"invoice_no": "25-296/2026", "currency": "EUR"}, [
            kgi.KGLine(
                rbr=1,
                code="ART-1",
                naziv="BUENO CIPELE",
                unit="PAR",
                qty=2,
                price=10,
                amount=20,
                currency="EUR",
                tarifni_broj="64039900",
                co="RS",
            )
        ]

    monkeypatch.setattr(kgi, "parse_kg_fashion_pdf", fake_parse_pdf)
    monkeypatch.setattr(
        kgi,
        "_parse_manifest_xls",
        lambda _path: {296: {"has_eur1": True, "co": "TR", "bruto": 12.5, "neto": 11.5}},
    )

    result = kgi.import_kg_fashion(str(pdf))

    assert result.items[0].zemlja_porijekla == "RS"


def test_import_kg_fashion_warns_when_pdf_has_no_tariffs(monkeypatch, tmp_path):
    pdf = tmp_path / "RAC.298.pdf"
    pdf.write_text("", encoding="utf-8")

    def fake_parse_pdf(_path):
        return {"invoice_no": "25-298/2026", "currency": "EUR", "gross_kg": 40.0, "net_kg": 33.0}, [
            kgi.KGLine(
                rbr=1,
                code="JG8622",
                naziv="Duks",
                unit="KOM",
                qty=4,
                price=14.07,
                amount=56.28,
                currency="EUR",
                tarifni_broj="",
                co="RS",
            )
        ]

    monkeypatch.setattr(kgi, "parse_kg_fashion_pdf", fake_parse_pdf)
    monkeypatch.setattr(kgi, "_apply_historical_tariff_suggestions", lambda _lines: (0, False))

    result = kgi.import_kg_fashion(str(pdf))

    assert result.bruto_kg == 40.0
    assert result.neto_kg == 33.0
    assert result.warnings == [
        "KG Fashion: 1/1 stavki nema tarifni broj u PDF fakturi; tarifu treba unijeti ručno ili iz istorije."
    ]


def test_import_kg_fashion_fills_missing_tariff_from_history(monkeypatch, tmp_path):
    pdf = tmp_path / "RAC.298.pdf"
    pdf.write_text("", encoding="utf-8")

    def fake_parse_pdf(_path):
        return {"invoice_no": "25-298/2026", "currency": "EUR"}, [
            kgi.KGLine(
                rbr=1,
                code="JG8622",
                naziv="Duks",
                unit="KOM",
                qty=4,
                price=14.07,
                amount=56.28,
                currency="EUR",
                tarifni_broj="",
                co="RS",
            )
        ]

    class FakeMapping:
        tarifni_broj = "61102099"
        precision_1 = "000"
        similarity = 0.95
        naziv_robe = "Duks JAGGER"
        usage_count = 6

    class FakeMappingService:
        def find_mapping(self, **kwargs):
            assert kwargs["min_similarity"] == 0.92
            assert kwargs["supplier"] == kgi._EXPORTER.name
            return FakeMapping()

    import services.tariff.tariff_mapping_service as tms

    monkeypatch.setattr(kgi, "parse_kg_fashion_pdf", fake_parse_pdf)
    monkeypatch.setattr(tms, "TariffMappingService", lambda: FakeMappingService())

    result = kgi.import_kg_fashion(str(pdf))

    line = result.items[0]
    assert line.tarifni_broj == "61102099"
    assert line.tariff_similarity == 0.95
    assert line.raw["tariff_source"] == "historical_suggestion"
    assert result.warnings == [
        "KG Fashion: 1 tarifnih brojeva popunjeno je iz baze znanja jer nisu bili upisani u PDF fakturi; provjeriti prije formiranja naimenovanja."
    ]


@pytest.mark.skipif(not KG_REAL_MANIFEST.exists(), reason="real KG Fashion manifest nije dostupan")
def test_kg_manifest_ignores_summary_row_for_jagger_298():
    data = kgi._parse_manifest_xls(str(KG_REAL_MANIFEST))

    assert data[298]["has_eur1"] is True
    assert data[298]["co"] == "RS"
    assert data[298]["bruto"] == pytest.approx(40.0)
    assert data[298]["neto"] == pytest.approx(33.0)
