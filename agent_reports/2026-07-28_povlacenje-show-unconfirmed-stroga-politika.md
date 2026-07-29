## Datum
2026-07-28

## Agent
Claude Code (Sonnet 5)

## Scope
- `services/agent/validation/tariff_decision_model.py` + `dist_client/` mirror (revert)
- `services/agent/validation/historical_tariff_search_service.py` + `dist_client/` mirror (revert)
- `tests/unit/test_historical_tariff_validation.py` (revert)
- `tests/unit/test_tariff_validation_dialog.py` (revert)
- `docs/CONTEXT.md` (§89)

## Status izvora
Direktan nastavak `agent_reports/2026-07-28_sussina-show-unconfirmed-cor22-fix.md`
(§88) — korisnik je taj pristup preispitao odmah nakon isporuke i eksplicitno
odbacio ga u istoj sesiji.

## GitNexus impact
Isti simbol kao §88 (`decide_tariff_match`, ranije prijavljen HIGH) — ovo je
`git revert` prethodnog commit-a, ne nova izmjena; vraća tačno prethodno
(već produkcijski provjereno) stanje. `detect_changes` nije ponovo pokretan
jer revert po definiciji vraća poznato, ranije verifikovano stanje.

## Šta je urađeno
`git revert 8b22281` (bez konflikta, commit `aac9b19`) — potpuno poništava
§88 izmjenu u sva 4 produkciona fajla (root+dist_client) i oba test fajla.
Dopunjen `docs/CONTEXT.md` §89 sa obrazloženjem odluke i posljedicama.

## Zašto je urađeno
Korisnik: "Ne možemo korisniku ponuditi prijedlog a da pritom ne znamo
odakle dolazi, šta je izvor te informacije — jer onda bismo ga mogli
dovesti u zabludu da aplikacija zna, da ne pominjem da greška u tarifiranju
može izazvati kazne." — eksplicitna, obrazložena potvrda da politika §65
vrijedi BEZ IZUZETKA, čak ni za jasno obilježen "izvor nepoznat, zahtijeva
potvrdu" prikaz. Ovo NIJE nesporazum o tome šta §88 radi (agent je prije
revert-a eksplicitno pitao i potvrdio da korisnik razumije da se ništa ne
primjenjuje automatski) — korisnik je svjesno odlučio da čak ni vidljivost
na ručni pregled nije prihvatljiva.

## Kako je urađeno
`git revert` umjesto ručnog re-editovanja — čist, provjerljiv povratak na
tačno stanje prije §88 bez rizika od djelimičnog/netačnog ručnog vraćanja.

## Šta nije dirano
- §65 politika sama (`has_meaningful_source` provjera) — bila je i ostaje
  netaknuta kroz cijeli §88→§89 ciklus.
- Sloj 1 nalaz iz §88 (`TariffMappingService.save_mapping()` ne piše izvor)
  — i dalje otvoren, sad JEDINI preostali put da se ovaj problem ikad
  riješi za buduće (ne postojeće) proizvode.
- Baza podataka — nikad nije mijenjana (samo pročitana radi istrage).

## Verifikacija
- `python -m pytest tests/unit/test_historical_tariff_validation.py
  tests/unit/test_tariff_validation_dialog.py -q`: 44 passed (vraćeno sa 45
  — ukloljen test specifičan za SHOW_UNCONFIRMED).
- `diff` root vs dist_client (oba servisna fajla): identično.
- `python -m py_compile` na sva 4 fajla: OK.

## Pronađeni problemi
Nema novih — ovo je čisto povlačenje prethodne odluke na osnovu korisnikove
ponovne procjene rizika.

## Konflikti / kontradiktorni izvori
§88 i §89 su direktno suprotni (§88 = "prikaži neprovjereno", §89 = "nikad
ne prikaži bez izvora") — §89 je NOVIJA i VAŽEĆA odluka. §88 ostaje u
CONTEXT.md kao istorijski zapis ZAŠTO je taj pristup probran i ZAŠTO je
odbačen, ne kao aktivno uputstvo. Isti obrazac kao ranija 2026-07-22 →
2026-07-26 promjena politike (vidi §27/§65) — dokumentovati obje strane,
tretirati topliju (noviju) kao trenutno važeću.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `aac9b19` | Revert "fix(tarifa): SHOW_UNCONFIRMED popravlja cor-22 za prijedloge bez izvora" |

## Rizici / ograničenja
SUSSINA (i svaki sličan "zlatni" zapis bez izvora) ostaje trajno
nevidljiv/nepotvrdiv u aplikaciji — ovo je sad PRIHVAĆENA, svjesna
posljedica korisnikove odluke o pravnom riziku, ne otvoren bug.

## Potreban follow-up
Sloj 1 fix (`save_mapping` da piše izvor za NOVE ručne potvrde) ostaje
jedina preostala mogućnost da se problem ne ponavlja za buduće proizvode
— i dalje čeka korisničku odluku da li se radi.

## Potrebna korisnička potvrda
Nema — odluka je eksplicitna i konačna za ovaj krug.
