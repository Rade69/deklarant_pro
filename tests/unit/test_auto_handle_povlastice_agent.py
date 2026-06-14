import os
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.draft.draft import InvoiceLine
from gui.tabs.faktura_view import FakturaView


def _fake_view(items):
    """Minimalni 'self' za _auto_handle_povlastice_agent — bez QWidget instanciranja."""
    draft = types.SimpleNamespace(exporter="", invoice_lines=items)
    fake_self = types.SimpleNamespace(draft=draft)
    fake_self._suggest_preference_by_country = types.MethodType(
        FakturaView._suggest_preference_by_country, fake_self
    )
    return fake_self


def test_eu_bez_dokumenta_ostaje_neutralna_ali_pending():
    """EU stavka bez izjave i bez EUR.1 -> povlastica ostaje prazna, eur1_pending=1."""
    item = InvoiceLine(zemlja_porijekla="DE", has_origin_statement=False, exporter="")
    fake_self = _fake_view([item])

    result = FakturaView._auto_handle_povlastice_agent(fake_self, [item], has_origin_statement=False)

    assert item.povlastica == ""
    assert result == {"pe2": 0, "eur1_pending": 1}


def test_cn_bez_dokumenta_ostaje_bez_povlastice_i_bez_pending():
    """Kina nema povlasticu po definiciji -> ne postaje pending."""
    item = InvoiceLine(zemlja_porijekla="CN", has_origin_statement=False, exporter="")
    fake_self = _fake_view([item])

    result = FakturaView._auto_handle_povlastice_agent(fake_self, [item], has_origin_statement=False)

    assert item.povlastica == ""
    assert result == {"pe2": 0, "eur1_pending": 0}


def test_pe2_izjava_o_porijeklu_ne_postavlja_povlasticu_bez_potvrde():
    """Stavka sa izjavom ostaje bez povlastice dok deklarant ne potvrdi PE2/PE3 dialog."""
    item = InvoiceLine(zemlja_porijekla="RS", has_origin_statement=True, exporter="")
    fake_self = _fake_view([item])

    result = FakturaView._auto_handle_povlastice_agent(fake_self, [item], has_origin_statement=True)

    assert item.povlastica == ""
    assert result == {"pe2": 1, "eur1_pending": 0}


def test_vec_potvrdjena_eur1_stavka_se_ne_broji_kao_pending():
    """Stavka koja vec ima povlasticu+eur1_number (ranija PE1 potvrda) -> ne ulazi u eur1_pending."""
    item = InvoiceLine(
        zemlja_porijekla="DE",
        povlastica="EUP",
        eur1_number="A-12345",
        has_origin_statement=False,
        exporter="",
    )
    fake_self = _fake_view([item])

    result = FakturaView._auto_handle_povlastice_agent(fake_self, [item], has_origin_statement=False)

    assert item.povlastica == "EUP"
    assert result == {"pe2": 0, "eur1_pending": 0}
