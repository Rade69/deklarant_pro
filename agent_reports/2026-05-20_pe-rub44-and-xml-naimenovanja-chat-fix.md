# Agent report — PE Rub.44 i XML naimenovanja u chat agentu

Datum: 2026-05-20

## Problem

Korisnik je prijavio dva regresiona slučaja:

- Rub.44 je i dalje prikazivala neispravan oblik `PE1` u gornjem redu i `PE1 PE1 A` u master polju.
- Nakon uvoza gotovog ASYCUDA XML-a u tab Naimenovanja, chat agent je tvrdio da je draft prazan jer je gledao samo `draft.invoice_lines`, iako su `draft.items` bila popunjena.

## Urađeno

- Dodata normalizacija PE dokumenata:
  - `PE1 PE1 A` -> `PE1 A`
  - `PE2 PE2 266VP-2026` -> `PE2 266VP-2026`
- Sekundarna PE polja u Rub.44 se čiste kada master polje `attached_document4` sadrži `PE1`, `PE2` ili `PE3`.
- Ista zaštita primijenjena je u:
  - Naimenovanja tabu
  - Faktura tabu
  - Agentskom import pipeline-u
- Chat agent sada prepoznaje upite tipa:
  - `Pregledaj naimenovanja`
  - `U tabu naimenovanja pogledaj`
  - `Pregledaj n aimenovanja`
- Chat kontekst i intent classifier sada koriste `draft.items` kada XML uvoz ima naimenovanja bez fakturnih linija.

## Testovi

Pokrenuto:

```bash
python -m pytest tests/test_tool_use_offline.py tests/unit/test_pe_rub44_consistency.py tests/unit/test_asycuda_goods_description.py -q
```

Rezultat:

```text
47 passed
```

## Napomena

`AGENTS.md` i `CLAUDE.md` su imali nevezane lokalne izmjene i nisu dio ove promjene.
