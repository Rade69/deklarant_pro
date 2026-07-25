"""
Testovi za ChatWorker._build_zaglavlje_zone() — maskiranje imena partnera.

Regresija: _build_session_zone (Zone B) maskira izvoznik/primalac imena kad
je SEND_SENSITIVE_DATA=false (default), ali _build_zaglavlje_zone (Zone B2)
je uključivala ista polja (plus deklarant_naziv) BEZ ikakve provjere — Zone
B2 se dodaje u isti _build_context() payload odmah nakon Zone B, pa je
maskiranje iz Zone B bilo efektivno zaobiđeno. Otkriveno pri poređenju
aplikacije sa "Kontrolisana podatkovna granica za AI agente" prijedlogom
(2026-07-25).
"""
from __future__ import annotations

from types import SimpleNamespace

from gui.tabs.agent.widgets.chat_worker import ChatWorker


def _fake_worker(draft, send_sensitive: bool):
    fake = type("FakeChatWorker", (), {})()
    fake.draft = draft
    fake._allow_sensitive_data = lambda: send_sensitive
    return fake


def _draft(**kwargs) -> SimpleNamespace:
    defaults = dict(
        deklaracija_tip="", deklaracija_oznaka="", deklaracija_a="",
        ured_odredista="",
        izvoznik_naziv="", izvoznik_drzava="",
        primalac_naziv="",
        deklarant_naziv="",
        valuta="", iznos=0.0, kurs=1.0,
        uslovi_kod="", uslovi_mjesto="",
        vid_granica="", vid_unutra="",
        drzava_izvoza_naziv="", drzava_izvoza_sifra="",
        trosak_1="0,00", trosak_2="0,00", trosak_3="0,00",
        trosak_4="0,00", trosak_5="0,00",
        header_attached_documents=[],
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_zaglavlje_zone_maskira_partnere_kad_je_sensitive_iskljucen():
    """SEND_SENSITIVE_DATA=false (default) — imena partnera se NE smiju pojaviti."""
    d = _draft(
        izvoznik_naziv="TAJNA FIRMA DOO",
        primalac_naziv="UVOZNIK DOO",
        deklarant_naziv="DEKLARANT DOO",
    )
    fake = _fake_worker(d, send_sensitive=False)

    lines = ChatWorker._build_zaglavlje_zone(fake)
    text = "\n".join(lines)

    assert "TAJNA FIRMA DOO" not in text
    assert "UVOZNIK DOO" not in text
    assert "DEKLARANT DOO" not in text
    assert "ime skriveno" in text


def test_zaglavlje_zone_prikazuje_partnere_kad_je_sensitive_ukljucen():
    """SEND_SENSITIVE_DATA=true (i lokalni provider) — imena partnera se prikazuju."""
    d = _draft(
        izvoznik_naziv="TAJNA FIRMA DOO",
        primalac_naziv="UVOZNIK DOO",
        deklarant_naziv="DEKLARANT DOO",
    )
    fake = _fake_worker(d, send_sensitive=True)

    lines = ChatWorker._build_zaglavlje_zone(fake)
    text = "\n".join(lines)

    assert "TAJNA FIRMA DOO" in text
    assert "UVOZNIK DOO" in text
    assert "DEKLARANT DOO" in text
    assert "ime skriveno" not in text


def test_zaglavlje_zone_ne_maskira_nepartnerska_polja():
    """Vrsta deklaracije, valuta/iznos i ostala polja nisu partner-imena — ostaju vidljiva bez obzira na flag."""
    d = _draft(deklaracija_tip="IM", deklaracija_oznaka="4", valuta="EUR", iznos=1234.56)
    fake = _fake_worker(d, send_sensitive=False)

    lines = ChatWorker._build_zaglavlje_zone(fake)
    text = "\n".join(lines)

    assert "IM" in text
    assert "1,234.56 EUR" in text or "1234.56" in text or "EUR" in text
