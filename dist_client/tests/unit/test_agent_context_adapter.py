"""
Testovi za AgentSafeContext schemu i AgentContextAdapter (Faza 1,
project_rooms/2026-07-25_agent-safe-input-schema-plan.md).

Izolovano od ChatWorker-a — Faza 2 (kasniji zadatak) migrira Zone B/B2 da
koriste ovaj adapter umjesto ručnog maskiranja po polju.
"""
from __future__ import annotations

from types import SimpleNamespace

from services.agent.chat.context_adapter import AgentContextAdapter
from services.agent.chat.safe_context_schema import (
    AgentSafeContext,
    DeclarationHeaderSummary,
    DraftSummary,
    PartnerInfo,
)


def _line(tarifni_broj="12345678", zemlja_porijekla="DE", povlastica="", has_origin_statement=False, eur1_number=""):
    return SimpleNamespace(
        tarifni_broj=tarifni_broj,
        zemlja_porijekla=zemlja_porijekla,
        povlastica=povlastica,
        has_origin_statement=has_origin_statement,
        eur1_number=eur1_number,
    )


def _draft(**kwargs):
    defaults = dict(
        izvoznik_naziv="", primalac_naziv="", deklarant_naziv="",
        deklaracija_tip="", deklaracija_oznaka="", deklaracija_a="",
        ured_odredista="", valuta="", iznos=0.0, kurs=1.0,
        uslovi_kod="", uslovi_mjesto="", vid_granica="", vid_unutra="",
        drzava_izvoza_naziv="", drzava_izvoza_sifra="",
        trosak_1="0,00", trosak_2="0,00", trosak_3="0,00",
        trosak_4="0,00", trosak_5="0,00",
        header_attached_documents=[],
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_build_partner_info_maskira_kad_nije_dozvoljeno():
    adapter = AgentContextAdapter(
        _draft(izvoznik_naziv="TAJNA DOO", primalac_naziv="UVOZNIK DOO"),
        allow_sensitive=False,
    )
    partners = adapter.build_partner_info()

    assert len(partners) == 2
    for p in partners:
        assert p.name is None
        assert p.masked is True


def test_build_partner_info_prikazuje_kad_dozvoljeno():
    adapter = AgentContextAdapter(
        _draft(izvoznik_naziv="TAJNA DOO", primalac_naziv="UVOZNIK DOO", deklarant_naziv="DEKL DOO"),
        allow_sensitive=True,
    )
    partners = adapter.build_partner_info()

    assert len(partners) == 3
    names = {p.role: p.name for p in partners}
    assert names["izvoznik"] == "TAJNA DOO"
    assert names["primalac"] == "UVOZNIK DOO"
    assert names["deklarant"] == "DEKL DOO"
    assert all(not p.masked for p in partners)


def test_build_partner_info_preskace_prazna_imena():
    adapter = AgentContextAdapter(_draft(izvoznik_naziv="SAMO IZVOZNIK"), allow_sensitive=True)
    partners = adapter.build_partner_info()

    assert len(partners) == 1
    assert partners[0].role == "izvoznik"


def test_build_draft_summary_racuna_tacne_agregate():
    lines = [
        _line(tarifni_broj="", zemlja_porijekla="DE"),  # bez tarife
        _line(zemlja_porijekla=""),                      # bez zemlje
        _line(povlastica="P", has_origin_statement=False, eur1_number=""),  # ceka EUR1
        _line(povlastica="P", has_origin_statement=True),                    # ima izjavu, ne racuna se u ceka_eur1
        _line(),
    ]
    summary = AgentContextAdapter.build_draft_summary(lines)

    assert summary.total_items == 5
    assert summary.bez_tarife == 1
    assert summary.bez_zemlje == 1
    assert summary.sa_povlasticom == 2
    assert summary.ceka_eur1 == 1
    assert summary.zemlja_distribucija["DE"] >= 1
    assert summary.zemlja_distribucija.get("(nepoznato)") == 1


def test_build_header_vraca_none_bez_drafta():
    adapter = AgentContextAdapter(None, allow_sensitive=True)
    assert adapter.build_header() is None


def test_build_header_ukljucuje_prilozene_isprave_bez_maskiranja():
    doc = SimpleNamespace(name="EUR.1", number="A123456")
    d = _draft(valuta="EUR", iznos=1000.0, header_attached_documents=[doc])
    adapter = AgentContextAdapter(d, allow_sensitive=False)

    header = adapter.build_header()

    assert header is not None
    assert header.valuta == "EUR"
    assert header.iznos == 1000.0
    assert len(header.prilozene_isprave) == 1
    assert header.prilozene_isprave[0].number == "A123456"


def test_agent_safe_context_schema_validacija():
    ctx = AgentSafeContext(
        draft_summary=DraftSummary(total_items=1, bez_tarife=0, bez_zemlje=0, sa_povlasticom=0, ceka_eur1=0),
        partners=[PartnerInfo(role="izvoznik", name=None, masked=True)],
        header=DeclarationHeaderSummary(valuta="EUR"),
    )

    assert ctx.draft_summary.total_items == 1
    assert ctx.partners[0].masked is True
    assert ctx.header.valuta == "EUR"


def test_agent_safe_context_negativan_broj_stavki_odbijen():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DraftSummary(total_items=-1, bez_tarife=0, bez_zemlje=0, sa_povlasticom=0, ceka_eur1=0)
