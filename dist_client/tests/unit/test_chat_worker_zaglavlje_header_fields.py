"""
Testovi za ChatWorker._build_zaglavlje_zone() ne-partner (header) polja —
Faza 4, project_rooms/2026-07-25_agent-safe-input-schema-plan.md.

Zone B2 header polja (valuta/iznos/kurs, uslovi isporuke, vid transporta,
država izvoza, troškovi, priložene isprave) sad računa AgentContextAdapter
.build_header() — ovi testovi provjeravaju tačan format teksta (uključujući
razmake) koji je prije migracije proizvodila ručna string-formatiranja u
_build_zaglavlje_zone (nije bilo pokriveno postojećim testovima, koji su
se fokusirali samo na partner maskiranje).
"""
from __future__ import annotations

from types import SimpleNamespace

from gui.tabs.agent.widgets.chat_worker import ChatWorker


def _fake_worker(draft, send_sensitive: bool = True):
    fake = type("FakeChatWorker", (), {})()
    fake.draft = draft
    fake._allow_sensitive_data = lambda: send_sensitive
    return fake


def _draft(**kwargs) -> SimpleNamespace:
    defaults = dict(
        deklaracija_tip="", deklaracija_oznaka="", deklaracija_a="",
        ured_odredista="",
        izvoznik_naziv="", izvoznik_drzava="", primalac_naziv="", deklarant_naziv="",
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


def test_valuta_iznos_kurs_format():
    d = _draft(valuta="EUR", iznos=1234.5, kurs=1.9558)
    fake = _fake_worker(d)
    text = "\n".join(ChatWorker._build_zaglavlje_zone(fake))
    assert "Valuta/iznos (Rb.22/23):   1,234.50 EUR  |  kurs: 1.9558" in text


def test_uslovi_isporuke_ne_prikazuje_se_bez_koda_iako_mjesto_postoji():
    """Ivica sačuvana pri migraciji: uslovi_kod prazan -> linija se NE prikazuje čak i ako uslovi_mjesto ima vrijednost."""
    d = _draft(uslovi_kod="", uslovi_mjesto="SARAJEVO")
    fake = _fake_worker(d)
    text = "\n".join(ChatWorker._build_zaglavlje_zone(fake))
    assert "Uslovi isporuke" not in text


def test_uslovi_isporuke_prikazuje_se_sa_kodom():
    d = _draft(uslovi_kod="DAP", uslovi_mjesto="SARAJEVO")
    fake = _fake_worker(d)
    text = "\n".join(ChatWorker._build_zaglavlje_zone(fake))
    assert "Uslovi isporuke (Rb.20):   DAP SARAJEVO" in text


def test_vid_transporta_format_dva_razmaka():
    d = _draft(vid_unutra="3", vid_granica="1")
    fake = _fake_worker(d)
    text = "\n".join(ChatWorker._build_zaglavlje_zone(fake))
    assert "Vid transporta (Rb.25/26): unutra=3  granica=1" in text


def test_troskovi_format():
    d = _draft(trosak_1="15,00", trosak_3="7,50")
    fake = _fake_worker(d)
    text = "\n".join(ChatWorker._build_zaglavlje_zone(fake))
    assert "Troškovi:                  T1=15,00, T3=7,50" in text


def test_prilozene_isprave_format():
    doc = SimpleNamespace(name="EUR.1", number="A123456")
    d = _draft(header_attached_documents=[doc])
    fake = _fake_worker(d)
    text = "\n".join(ChatWorker._build_zaglavlje_zone(fake))
    assert "Priložene isprave (Rb.44):" in text
    assert "    - EUR.1  A123456" in text
