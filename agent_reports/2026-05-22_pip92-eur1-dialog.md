# Agent Report: PIP92 test i EUR1 dijalog po fakturi

**Datum:** 2026-05-22
**Grana:** dev

---

## Problem

Kod rucnog grupnog uvoza faktura, EUR1 dijalog se mogao otvarati prerano i
nepregledno. U jednoj posiljci moze postojati vise faktura, vise zemalja
porijekla i kombinacija robe sa ili bez povlastice, pa nije dovoljno pitati samo
na nivou cijele posiljke ili jedne zemlje.

Za PIP92 je dodat realni regression test jer faktura nema izjavu o porijeklu,
ali roba ima zemlju porijekla RS, sto je tipican slucaj u kojem korisnik moze
imati EUR1 obrazac odvojeno od fakture.

---

## Rjesenje

Rucni grupni uvoz sada odgadja EUR1 dijalog dok se ne obrade sve fakture u
batch-u. Nakon toga se otvara jedan dijalog koji grupise stavke po kombinaciji:

```text
broj fakture + zemlja porijekla
```

Korisnik posebno oznacava samo one grupe za koje stvarno postoji EUR1 obrazac.
Povlastica i PE1 dokument se primjenjuju samo na oznacene grupe sa unesenim
EUR1 brojem. Neoznacene grupe ostaju bez povlastice.

PE2/PE3 tok za fakture koje imaju izjavu o porijeklu nije mijenjan.

---

## Testovi

Dodati su testovi:

- `tests/unit/test_pip_food_parser.py`
  - provjerava realni `PIP92.pdf`
  - potvrduje 25 stavki, 3 fakture, bruto/neto mase, ukupnu vrijednost,
    zemlju porijekla RS i odsustvo izjave o porijeklu
  - provjerava routing preko `parse_smart_pdf`

- `tests/unit/test_eur1_quick_dialog.py`
  - provjerava grupisanje EUR1 dijaloga po fakturi i zemlji
  - provjerava da se EUR1 primjenjuje samo na oznacenu grupu

Pokrenuto:

```text
python -m pytest tests/unit/test_pip_food_parser.py tests/unit/test_eur1_quick_dialog.py -q
```

Rezultat:

```text
4 passed
```

---

## Napomene

U radnom stablu postoje i druge necommitovane izmjene koje nisu dio ovog rada
(`AGENTS.md`, `CLAUDE.md` i raniji agent report). One nisu dirane u ovoj izmjeni.
