# Agent Report: Proširenje auto-dodavanja obaveznih priloženih dokumenata (Rub.44)

**Datum**: 2026-06-07
**Grana**: windows

---

## Šta je urađeno

Korisnik je primijetio da se u tabu Zaglavlje, u tabeli "Priložene isprave (Rub.44)",
automatski upisuju samo dva dokumenta — **PZT** (Zavisni troškovi) i **N730** (Tovarni list)
— i posumnjao da se Windows klijent po tom pitanju razlikuje od dev/Linux verzije.

Nakon poređenja koda potvrđeno je da je auto-dodavanje **identično** u `windows` i `origin/dev`
granama (uvedeno commitom `73ac502` na dev-u, preneseno u `windows` kroz `0149de9`). Razlika
nije bila u branch-evima nego u samom pravilu: validacija exporta (`OBAVEZNE_SIFRE` u
`_validate...`) već je zahtijevala i **N380, DIS i DV1** kao obavezne, ali auto-dodavanje
(`load_from_draft`) ih nije generisalo — pa je korisnik morao ručno dodavati ove tri šifre
prije svakog exporta.

Korisnik je potvrdio kompletnu listu obaveznih dokumenata: **PZT, N730, N380, DIS, DV1**
(plus uslovno VOZ zavisno od Incoterms pariteta), dok ostali dokumenti (OST, PE1/PE2/PE3...)
zavise od pariteta i vrste robe i dodaju se posebnim pravilima (već implementirano).

## Kako je urađeno

Prošireni `for` loop u `ZaglavljeService.load_from_draft()` (i `services/zaglavlje_service.py`
i `dist_client/services/zaglavlje_service.py`) sa liste `[PZT, N730]` na punu listu
`[PZT, N730, N380, DIS, DV1]`. N380 zadržava prioritet sa stvarnim brojevima faktura
(postojeći blok iznad, koji se izvršava prije ovog loop-a) — ako N380 već nije dodan tim
putem, fallback ga dodaje sa praznom referencom kao i ostale obavezne šifre.

```python
for _code, _name in [
    ('PZT', 'Zavisni troškovi'),
    ('N730', 'Tovarni list'),
    ('N380', 'Faktura komercijalna'),
    ('DIS', 'Dispozicija'),
    ('DV1', 'Prijava o carinskoj vrijednosti'),
]:
    if not self._has_attached_doc_code(data['attached_documents'], _code):
        data['attached_documents'].append(
            self._attached_doc_dict(_code, _name, '', True)
        )
```

`gitnexus_impact` na `load_from_draft` (upstream) vratio je rizik **LOW** (0 pozivalaca u grafu —
metoda se poziva preko controller→service runtime ugovora koji GitNexus ne prati statički).
`gitnexus_detect_changes()` potvrdio je da su dotaknuti samo `load_from_draft` i `ZaglavljeService`.

## Zašto

Bez ovog fallback-a korisnik je pri svakoj deklaraciji morao ručno upisivati N380, DIS i DV1
prije exporta — inače bi validacija blokirala export sa "Nedostaju obavezne isprave: N380, DIS, DV1".
Sinhronizacija auto-dodavanja sa već postojećom validacijskom listom (`OBAVEZNE_SIFRE`) eliminiše
taj ručni korak i sprečava buduću pojavu iste konfuzije ("zašto se ovo ne dodaje samo kao ostalo").

## Tabela commitova

| Hash | Tip | Opis |
|------|-----|------|
| `a7dae71` | fix | Auto-dodavanje N380/DIS/DV1 uz postojeće PZT/N730 u Rub.44 |

---

## Napomena za buduće sesije

Ako se ikad mijenja `OBAVEZNE_SIFRE` lista u validaciji (services/zaglavlje_service.py, ~linija 1841),
provjeriti i listu u `load_from_draft()` — moraju ostati sinhronizovane, inače se ponavlja ista
konfuzija (validacija traži dokument koji se nigdje automatski ne dodaje).
