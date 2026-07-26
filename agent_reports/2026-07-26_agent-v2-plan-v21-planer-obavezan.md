# Agent V2 plan v2.1 — planer obavezan scope, procjena usklađena sa paralelnim radom

## Datum

2026-07-26

## Agent

Claude (Sonnet 5, nastavak sesije započete pod Opus 5)

## Scope

- `docs/agent/AGENT_V2_IMPLEMENTACIONI_PLAN.md` — v2.0 → v2.1, ciljane izmjene
- `docs/CONTEXT.md` — nova sekcija 70
- Bez izmjene produkcionog koda ili testova

## Status izvora

| Izvor | Status |
| --- | --- |
| `AGENT_V2_IMPLEMENTACIONI_PLAN.md` v2.0 (commit `e62eae8`) | zamijenjen ovom izmjenom (v2.1); v2.0 dostupna kroz `git show e62eae8:...` |
| Korisnička odluka (ova konverzacija) | autoritativna za tri stavke — vidi „Zašto“ |
| Paralelna sesija (agent „Pi“) | **aktivno izvodi plan dok je ovaj dokument u izradi** — commiti `76c5a89`, `96a2911`, `2b4e815` zatvorili Fazu 0 i Fazu −1 prije nego što je v2.1 dovršena |

## GitNexus impact

Nije primjenjivo — isključivo dokumentaciona izmjena, nijedan simbol nije
dirnut. Provjerio sam stanje koda koje je paralelna sesija već promijenila
(`core/draft/draft.py`, `config/settings.py`) samo da bih **opisao** stvarno
stanje u planu, bez ikakve dalje izmjene tih fajlova.

## Šta je urađeno

Tri eksplicitne korisničke odluke unesene u plan:

1. **Faza 7 (planer) i Faza 8 (nivoi automatizacije) prestaju biti uslovne —
   postaju obavezan scope.** Uklonjeni „(USLOVNA)“ tagovi i blokirajući uslovi
   iz zaglavlja §18/§19; dodato objašnjenje da je odluka korisnička (2026-07-26)
   i da ne mijenja tehnički obim inverzije zavisnosti. Faza 8 je suženo
   fokusirana: Režim C („Priprema do XML-a“) je jedini aktivno isporučeni tok,
   Režimi A/B ostaju dizajnirani ali neizloženi dok se ne zatraže — ovo
   sprečava nezatraženo širenje obima (korisnik je tražio *jednu* komandu sa
   pauzama, ne tri konfigurabilna režima).
2. **Konsolidacija alata 12 → 8** — potvrđena bez izmjene sadržaja (već je bila
   ovako specificirana u v2.0).
3. **Kill-switch default `0`/`False`** — potvrđen bez izmjene (već ovako
   specificiran, i već implementiran u paralelnoj sesiji).

Procjena obima (§25) je u potpunosti prepisana:

- uklonjen model „radni dani jednog developera“;
- brojke preformulisane kao relativna implementaciona složenost (S/M/L) po
  fazi, ne kalendarski raspored;
- dodat §25.2 „Kritični put“ — deset sekvencijalnih koraka koji određuju
  wall-clock bez obzira na broj agenata;
- eksplicitno imenovana tri stvarna ograničenja koja NE zavise od broja
  agenata: (a) test gate po paketu, (b) obavezan korisnički pregled na
  HIGH/CRITICAL `gitnexus_impact` nalazima, (c) korisnikov dnevni token/poruka
  budžet;
- uklonjena razlika „obavezni dio“ vs „sa uslovnim fazama“ (40–62 / 53–83 dana)
  jer više nema uslovnog dijela.

Dodatno, otkriveno tokom rada (ne dio izvorne izmjene, ali direktno relevantno):
**Faza −1 i Faza 0 su već završene** u paralelnoj sesiji dok je ovaj dokument
bio u izradi. §10 i §11 dobili su status-blokove koji upućuju na stvarne
commite i fajlove, a §26 („Prvi konkretan implementacioni zadatak“) je
prepisan da pokazuje na **Fazu 1** kao sljedeći korak, sa referencom na
postojeći `intent_routing_cases.json` fixture (koji koristi polje
`expected_sloj`, ne `reachable_branch` iz originalnog primjera u v2.0/v2.1 —
plan je usklađen da to ne tretira kao neusklađenost).

## Zašto je urađeno

Korisnik je ispravno primijetio da je procjena u v2.0 (49–79, zatim 40–83 dana)
zasnovana na modelu koji ne odgovara stvarnosti: rad izvode paralelni AI
agenti, ne jedan developer koji ručno kuca kod. Ovo je potvrđeno u praksi u
istom danu — dok sam ja još pisao v2.1, druga sesija je već zatvorila Fazu −1 i
Fazu 0 iz v2.0 plana.

Za planer/workflow: korisnik je eksplicitno rekao da želi tačno tu mogućnost
(„ukucam jednu komandu, agent vodi proces uz pauze za potvrdu“) — to poništava
moju raniju preporuku da se Faza 7 odgodi dok se ne dokaže potreba. Potreba je
sada eksplicitno izražena, pa uslovnost više nema smisla.

## Kako je urađeno

Ciljane `Edit` izmjene (ne prepisivanje cijelog fajla), da bi se sačuvao ostatak
v2.0 sadržaja koji korisnik nije osporio (dijagnoza u §3, ugovori u §7,
konsolidacija alata u §8 itd.). Prije pisanja provjereno stvarno stanje koda
(`grep` za `revision`/`fingerprint` u `core/draft/draft.py`, `DEKLARANT_AGENT_V2`
u `config/settings.py`, postojanje `scripts/sync_dist_client.py`,
`git log --since` za commite paralelne sesije, čitanje oba `project_rooms/`
fajla iz Faze 0 i Faze −1.A) — da status-blokovi u §10/§11 navode tačne
commit hexove i putanje, ne pretpostavke.

## Šta nije dirano

- Nijedan red produkcionog koda (draft.py, settings.py, chat_intent_handler.py
  itd.) — sve to je već izmijenila paralelna sesija, ja sam samo pročitao
  rezultat.
- Dijagnoza u §3, zajednički ugovori u §7, konsolidacija alata u §8, semantika
  komandi u §9 — nepromijenjeni, korisnik ih nije osporio.
- Rad paralelne sesije (agent „Pi“) na Fazi −1/0 — nije reviewovan niti mijenjan,
  samo referenciran. Provjera kvaliteta tog rada nije bila dio ovog zadatka.
- Nepovezan rad iste sesije na paritetu isporuke/incoterm (commiti `2b0d1b4`,
  `dfa3d20`, `6f0a12d`, `851cf9b`) — potpuno drugi zadatak, netaknut.

## Verifikacija

- Ćirilica: nula pogodaka nad cijelim fajlom (`python -c` skripta).
- Nema zaostalih referenci na „uslovno“/„USLOVNA“ osim jedne nepovezane (odnosi
  se na preskočenu provjeru, ne na Fazu 7/8) — provjereno `grep`.
- Svaka referenca na commit hash i fajl u novim status-blokovima (§10, §11)
  provjerena direktno: `git show --stat`, `grep -n` u `core/draft/draft.py` i
  `config/settings.py`, `ls` za `scripts/sync_dist_client.py` i
  `tests/unit/test_draft_revision.py`.
- Slučajni typo (stray `//` umjesto `>` u citatu unutar §11) — uočen i ispravljen
  u istoj izmjeni, prije commita.

## Pronađeni problemi

Nijedan nov problem u kodu — ovaj zadatak je bio isključivo usklađivanje plana
sa korisničkom odlukom i sa stvarnim stanjem repozitorija.

## Konflikti / kontradiktorni izvori

| Konflikt | Tretman |
| --- | --- |
| v2.0 je predlagala polje `reachable_branch` u fixture primjeru; stvarni fixture iz Fazе 0 koristi `expected_sloj` | Plan ažuriran da eksplicitno kaže: zadržati `expected_sloj`, ne preimenovati radi usklađivanja sa dokumentom — kod je izvor istine |
| Project room za Fazu −1.A (`2026-07-26_faza-1a-draft-revision.md`) kaže „Commit tek nakon što korisnik potvrdi pristup“ (CRITICAL rizik), a commit `2b4e815` je već napravljen | Nisam mogao utvrditi iz ove sesije da li je korisnik odobrio u paralelnoj sesiji — nije dio mog scope-a da to auditiram; navedeno ovdje kao transparentnost, ne kao nalaz koji sam ispravljao |

**Potrebna korisnička potvrda:** DA — vidi zadnju sekciju.

## Commitovi

| Hash | Poruka |
| --- | --- |
| (vidi git log) | `docs(agent): planer i nivoi automatizacije postaju obavezan scope (v2.1)` |
| (vidi git log) | `docs(report): evidentiraj v2.1 izmjenu Agent V2 plana` |

## Rizici / ograničenja

- Procjena „2–3 dana kritičnog puta“ (§25.2) je uslovna na dvije stvari van
  kontrole ovog dokumenta: brzinu tvog pregleda na HIGH/CRITICAL kapijama i
  tvoj dnevni token budžet. Ako se ijedno od to dvoje uspori, kritični put se
  produžava — to nije greška u procjeni, nego iskrena zavisnost.
- Nisam reviewovao kvalitet rada paralelne sesije na Fazi −1/0 (npr. da li je
  ALT pristup za `draft.revision` zaista sigurniji od `__setattr__` kako
  project room tvrdi, ili da li je 278 pogođenih simbola stvarno provjereno
  jedan po jedan). To ostaje otvoreno ako ga želiš.

## Potreban follow-up

- Faza 1 je sljedeći korak (§26) — nije započeta.
- Ako želiš, mogu provjeriti kvalitet već završene Faze −1/0 iz paralelne
  sesije prije nego što se krene na Fazu 1 (drugi review, ne samo referenca).

## Potrebna korisnička potvrda

1. **Da li prihvataš da je project room za `draft.revision` tražio tvoju
   potvrdu prije commita, a commit je već napravljen** — provjeri da li si to
   ti odobrio u onoj sesiji ili je preskočeno. Ovo nije nešto što sam ja
   promijenio, samo prenosim transparentno.
2. **Da li se slažeš da Faza 1 krene odmah** koristeći postojeći
   `intent_routing_cases.json` fixture (polje `expected_sloj`), ili želiš da
   se prvo pregleda šta je paralelna sesija uradila.
