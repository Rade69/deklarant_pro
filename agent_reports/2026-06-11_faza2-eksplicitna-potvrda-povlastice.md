# Agent report — Faza 2: eksplicitna potvrda povlastice

**Datum:** 2026-06-11  
**Agent:** Codex  
**Scope:** Faktura tab, Agent import pipeline, auto-fill/mapping servisi, preflight validacija

## Sta je uradjeno

- Ukinuto je automatsko upisivanje povlastice iz parsera, zemlje porijekla, tariff mappinga i product master lista.
- `FakturaView` sada prikazuje potvrdu povlastice samo kada postoji dokaz PE1, PE2 ili PE3 koji je prosao korisnicku potvrdu ili rucni unos.
- Agent pipeline sada prijavljuje PE2/PE3 kandidate i EUR1 pending stanje, ali ne pise Rub.36.
- Preflight dijalog vise ne tretira samu zemlju porijekla kao dokaz; upozorava kada povlastica postoji bez PE1/PE2/PE3 dokaza.
- Dodan je test koji pokriva da PE2 kandidat bez potvrde deklaranta ne postavlja povlasticu, kao i test za preflight dokaz povlastice.

## Zasto je donesena odluka

U stvarnom toku rada parser cita fakturu i moze prepoznati da postoji izjava o porijeklu ili da treba EUR1 obrazac. To nije isto sto i carinska potvrda povlastice. Deklarant mora provjeriti tekst izjave, fakturu, zemlju i eventualni EUR1 broj, pa tek nakon potvrde aplikacija smije primijeniti povlasticu.

Zbog toga su PE2/PE3/EUR1 tokovi ostavljeni kao kandidati i dijalozi za potvrdu. Automatska logika smije pomoci u pronalazenju dokaza, ali ne smije sama donijeti odluku o Rub.36.

## Kljucne granice

- Nije mijenjan parser za Blagic/Loren niti XML export.
- Nije mijenjana rucna izmjena u tabeli fakture.
- Nije mijenjan PE2/EUR1 dijalog osim indirektnog pravila da su oni mjesto potvrde.
- Historijski i mapping servisi i dalje mogu nositi informaciju o mogucem porijeklu, ali vise ne smiju automatski upisati aktivnu povlasticu.

## Verifikacija

- `python -m py_compile` nad izmijenjenim Python fajlovima.
- `python -m pytest tests\unit\test_auto_handle_povlastice_agent.py tests\unit\test_preflight_preference_evidence.py tests\unit\test_evidence_model.py tests\unit\test_eur1_quick_dialog.py -q`
- Rezultat: `42 passed, 1 skipped`.

