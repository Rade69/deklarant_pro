from services.agent.validation.declaration_validator_service import DeclarationValidatorService


def test_tariff_lookup_accepts_10_digit_code_when_8_digit_level_exists(monkeypatch):
    calls = []

    def fake_trazi_po_kodu(code):
        calls.append(code)
        return code == "63079099"

    monkeypatch.setattr("services.tariff.tarifa_service.trazi_po_kodu", fake_trazi_po_kodu)

    service = DeclarationValidatorService()

    assert service._tariff_exists_in_db("6307909900") is True
    assert calls == ["6307909900", "63079099"]


def test_tariff_lookup_keeps_8_digit_to_6_digit_fallback(monkeypatch):
    calls = []

    def fake_trazi_po_kodu(code):
        calls.append(code)
        return code == "630790"

    monkeypatch.setattr("services.tariff.tarifa_service.trazi_po_kodu", fake_trazi_po_kodu)

    service = DeclarationValidatorService()

    assert service._tariff_exists_in_db("63079099") is True
    assert calls == ["63079099", "630790"]
