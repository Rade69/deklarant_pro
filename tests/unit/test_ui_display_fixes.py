from gui.tabs.agent.widgets.upload_area import ModeCard
from services.admin.admin_service import format_architecture


def test_selected_mode_card_keeps_title_unchanged(qtbot):
    card = ModeCard("Puna automatizacija", "fa5s.magic", "Opis")
    qtbot.addWidget(card)

    card.set_selected(True)

    assert card._title_lbl.text() == "Puna automatizacija"


def test_formats_intel_amd64_as_x86_64(monkeypatch):
    monkeypatch.setenv(
        "PROCESSOR_IDENTIFIER",
        "Intel64 Family 6 Model 186 Stepping 3, GenuineIntel",
    )

    assert format_architecture("AMD64") == "64-bit (x86-64, Intel)"


def test_formats_amd_vendor_without_confusing_machine_name(monkeypatch):
    monkeypatch.setenv(
        "PROCESSOR_IDENTIFIER",
        "AMD64 Family 25 Model 33 Stepping 0, AuthenticAMD",
    )

    assert format_architecture("AMD64") == "64-bit (x86-64, AMD)"


def test_formats_unknown_x86_64_without_vendor(monkeypatch):
    monkeypatch.delenv("PROCESSOR_IDENTIFIER", raising=False)

    assert format_architecture("x86_64") == "64-bit (x86-64)"
