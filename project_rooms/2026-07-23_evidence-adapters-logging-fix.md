# Plan: logging fix u evidence_adapters.py (CRITICAL GitNexus impact)

## Cilj
Dodati `logger.warning(...)` prije postojećeg `except Exception: pass` u
`adapt_tariff_evidence()` (`services/decision/evidence_adapters.py:91`) — trenutno
svaka greška pri traženju tarifnog mapiranja (DB nedostupan, neočekivan tip, itd.)
tiho nestaje, korisnik samo vidi "nema prijedloga" bez ijednog traga u logu.
Isti obrazac kao već popravljen `tariff_tree_service.py` bug (§45) koji je mjesecima
bio slomljen bez ikakve poruke.

## Pogođeno (iz gitnexus_impact, direction=upstream)
- **Risk: CRITICAL**, 16 impactedCount, 6 pogođenih procesa, 3 pogođena modula
  (Decision, Chat, Tabs)
- Lanac: `adapt_tariff_evidence` → `DeclarationDecisionService.evaluate_line` →
  `evaluate_line_for_display` / `sync_all_lines_after_draft_restore` /
  `sync_decision_state_after_autofill` → `FakturaView._on_auto_fill`,
  `TariffIntentService.execute_fill`, `chat_intent_handler.py:_on_accepted`
- Ovo je CENTRALNA funkcija auto-popune tarifnih brojeva — koristi je GUI
  (Faktura tab "Provjeri"/auto-fill), agent chat (execute_fill), i
  draft-restore/sync tok.

**Zašto je risk CRITICAL a izmjena ipak bezbjedna**: GitNexus risk odražava
POVEZANOST u grafu (koliko procesa prolazi kroz ovu funkciju), ne rizičnost SAME
izmjene. Izmjena je isključivo dodavanje `logger.warning(...)` reda — `except
Exception: pass` i dalje hvata SVE iste izuzetke i program i dalje nastavlja
identično (vraća `candidates` bez ovog kandidata). Nijedna grana kontrole toka,
povratna vrijednost, ni tajming se ne mijenja.

## Plan
1. `services/decision/evidence_adapters.py`: dodati `import logging` +
   `logger = logging.getLogger("deklarant_pro.decision.evidence")` na vrh fajla
2. Zamijeniti `except Exception:\n    pass` (linija 91-92) sa
   `except Exception as e:\n    logger.warning("Tariff mapping lookup failed: %s", e)`
3. Mirrorati identičnu izmjenu u `dist_client/services/decision/evidence_adapters.py`
4. `py_compile` oba fajla, `diff` provjera identičnosti
5. Pokrenuti pun test suite (očekivano: bez regresija, jer se ponašanje ne mijenja)
6. `gitnexus_detect_changes` prije commita — očekivan risk_level LOW/MEDIUM na
   nivou "changed", jer se dodaje samo log poziv, ne mijenja se logika

## Šta NE dirati
- Sama logika `try/except` bloka (koji izuzeci se hvataju, šta se vraća) — OSTAJE
  IDENTIČNA. Ovo NIJE promjena ponašanja, samo observabilnost.
- `min_similarity=0.92` threshold i logika biranja `score` — netaknuto
- Ostale funkcije u fajlu (`adapt_origin_evidence` i dr.) — van scope-a ovog fixa
  osim ako se u njima ne otkrije IDENTIČAN obrazac tokom provjere (u tom slučaju
  dodati poseban red u ovom planu prije izmjene, ne raditi tiho usput)

## Konflikti
Nema — ovo je čist dodatak logovanja, ne postoji suprotan raniji izvor koji bi
sugerisao da je `pass` bez loga namjeran/poželjan.

## Nivo dozvole
Draft change + mandatory test suite pass prije commita (standardna procedura,
ne treba dodatna eksplicitna korisnička potvrda jer je izmjena čisto aditivna
observabilnost bez promjene ponašanja — ali se korisniku eksplicitno
saopštava CRITICAL nalaz prije nastavka, per AGENTS.md).
