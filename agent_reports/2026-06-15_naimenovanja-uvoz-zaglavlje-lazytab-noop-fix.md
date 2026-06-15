# Naimenovanja uvoz XML - Faza 5: LazyTab _noop root cause + Rb.10-13/16 parser fix

## Datum
2026-06-15

## Agent
Claude Sonnet 4.6

## Scope
- `gui/tabs/naimenovanja_view.py` (`_apply_xml_import_to_zaglavlje`)
- `dist_client/gui/tabs/naimenovanja_view.py` (identičan mirror)
- `services/zaglavlje_service.py` (`_parse_xml`)
- `dist_client/services/zaglavlje_service.py` (identičan mirror)

## Status izvora
- [2026-06-15_naimenovanja-uvoz-zaglavlje-popunjavanje-fix.md](2026-06-15_naimenovanja-uvoz-zaglavlje-popunjavanje-fix.md)
  (Faza 4, commit `1287bd6`) — **aktivan, ali nekompletan**. Faza 4 je
  ispravno popravila plumbing (`save_to_draft` na `self.draft`,
  Rub.40 preserve_codes/global_docs), ALI je u "Pronađeni problemi"
  sekciji SAMA identifikovala `LazyTab.__getattr__` → `_noop` rizik i
  pogrešno zaključila "Nije reprodukovano u stvarnoj app (Zaglavlje je
  obično prvi/eager tab)". Korisnikov stvarni test je pokazao da JE
  reprodukovano — Zaglavlje NIJE eager tab (vidi `gui/main_window.py`
  konstrukcija: Faktura je index 0/eager, Naimenovanja/Zaglavlje/
  Šifrarnici su `LazyTab` na indeksima 1/2/3). Ova faza je DOPUNA —
  Fazina 4 plumbing logika (preserve_codes čišćenje, Rb.18/21 izuzeće,
  `save_to_draft(self.draft, data)` poziv) ostaje netaknuta i ispravna,
  samo se prethodno NIKAD nije izvršila do kraja zbog `AttributeError`
  bačenog ranije u istoj funkciji.
- [2026-06-15_naimenovanja-uvoz-popunjava-zaglavlje.md](2026-06-15_naimenovanja-uvoz-popunjava-zaglavlje.md)
  (Faze 1-3, commit `d1fedec`) — aktivan, netaknut (vidi Fazu 4 status).

## GitNexus impact
- `gitnexus_impact(target_uid="Method:gui/tabs/naimenovanja_view.py:NaimenovanjaView._apply_xml_import_to_zaglavlje#1", direction="upstream")`
  → **LOW**, 1 direktan poziv (`_on_import_xml`), 0 procesa, 1 modul ("Tabs").
- `gitnexus_impact(target_uid="Method:services/zaglavlje_service.py:ZaglavljeService._parse_xml#1", direction="upstream")`
  → **LOW**, poziva ga samo `load_from_xml`, 0 procesa.
- `gitnexus_detect_changes(scope="unstaged")` (prije svakog commit-a) →
  `risk_level: low`, `affected_processes: []` oba puta.
- `npx gitnexus analyze` pokrenut nakon oba commita — incremental update
  (6 fajlova), 41.466 nodes | 63.981 edges | 1043 clusters | 300 flows.
  Index je trenutno AŽURAN (uključuje `4b56340` i `7c43c71`).

## Šta je urađeno
1. **`_apply_xml_import_to_zaglavlje`** (gui + dist_client): zamijenjen
   `service = getattr(zaglavlje_tab, "service", None) or ZaglavljeService()`
   sa `service = ZaglavljeService()`.
2. **`_parse_xml`** (gui + dist_client `services/zaglavlje_service.py`,
   ~linija 1058-1080): dodato čitanje `zem_10`, `zem_11`, `zem_12`, `zem_13`
   i ispravljeno čitanje `drzava_porijekla` (sada iz `Country` podstabla,
   ne direktno iz `General_information`).

## Zašto je urađeno
Korisnik je nakon stvarnog testa (screenshot Zaglavlja nakon uvoza ASYCUDA
XML-a u Naimenovanja) prijavio da Faza 4 NIJE riješila problem:
- Izvoznik (Rb.2), Primalac/Uvoznik (Rb.8), Deklarant (Rb.14) — prazni.
- "1. Deklaracija" (4 dropdowna) i SVE od Rb.9 do Rb.20 — prazno, uz
  napomenu "a u xml-u se nalaze ti podatci".
- DIS (Rub.40) je ispravno prikazan "D-710" (Faza 4 fix za to RADI).
- Rub.40 3. kolona: šifre "CMR, ZUT, UVK, SAN, VET su stare šifre i ne
  popunjavaju se" — napomena korisnika.

**Provjera hipoteze (root cause #1 — empirijski potvrđena)**:
`_apply_xml_import_to_zaglavlje` poziva
`getattr(zaglavlje_tab, "service", None) or ZaglavljeService()`.
`zaglavlje_tab` je instanca `LazyTab` (`gui/tabs/lazy_tab.py`).
`LazyTab.__getattr__(self, name)`: ako `self._inner is None` (tab nikad
otvoren), vraća `_noop` — funkciju definisanu kao
`def _noop(*args, **kwargs): pass`, što je **istinita vrijednost**, ne
`None`. Dakle `getattr(zaglavlje_tab, "service", None)` vraća `_noop`
(ne `None`), pa `_noop or ZaglavljeService()` NIKAD ne padne na fallback
— `service = _noop`. Sljedeći red, `service.load_from_xml(filename)` =
`_noop.load_from_xml` → `AttributeError: 'function' object has no
attribute 'load_from_xml'`. Ovo hvata `except Exception` blok funkcije
(samo log, `return`), pa se CIJELA Faza 4 plumbing logika (koja je
ispravna!) NIKAD ne izvrši kad korisnik ide
Faktura → Naimenovanja → "Uvezi ASYCUDA XML" BEZ prethodnog otvaranja
Zaglavlje taba — što je upravo TOK koji je korisnik testirao i koji je
NORMALAN tok (Zaglavlje, kao `LazyTab` na indexu 2, se ne inicijalizuje
dok korisnik ne klikne na njega).

To objašnjava Issue 2 (Izvoznik/Primalac/Deklarant) i Issue 3 (1.
Deklaracija + Rb.9-20) u POTPUNOSTI. DIS (Rub.40) je radio jer
`_apply_xml_import_global_documents` — pozvan PRIJE, u `_on_import_xml`
— direktno piše `self.draft.header_attached_documents`, ne zavisi od
`zaglavlje_tab`/`service`, pa nije pogođen ovim bugom.

**Provjera hipoteze (parser gaps #2 — empirijski potvrđena)**: Nakon fixa
#1, simulacija punog flow-a na `data/knowledge_base/NOVA ASIKUDA/2.xml`
(root tag "ASYCUDA" — realniji format od `02.xml` korišćenog u Fazi 4)
otkrila je da `_parse_xml` IMA dvije dodatne greške NEZAVISNE od bug-a #1:
- `drzava_porijekla` (Rb.16) — kod je tražio `Country_of_origin_name` kao
  DIREKTNO dijete `General_information`, ali element je u stvarnosti
  unutar `General_information/Country/Country_of_origin_name`. UVIJEK je
  vraćao `''`, iako `2.xml` ima `Country_of_origin_name='TURSKA'`.
- `zem_12` (Rb.12 "Vrijednost") — `General_information/Value_details=
  '459.85'` postoji u XML-u i `save_to_draft` ima mapping za `zem_12`, ali
  `_parse_xml` taj ključ NIKAD nije postavljao — parser gap, ne
  "nema podatka".

Usput dodato (defanzivno, isti pattern): `zem_10`
(`Country/Country_first_destination`), `zem_11`
(`Country/Trading_country`), `zem_13` (`General_information/CAP`) — u
`2.xml` su ovi elementi `<null/>` (ASYCUDA placeholder za prazno polje),
pa i dalje vraćaju `''`, ali extrakcija je sada ispravna za XML-ove gdje
JESU popunjeni.

## Kako je urađeno
- `gui/tabs/naimenovanja_view.py` i `dist_client/gui/tabs/naimenovanja_view.py`,
  linija ~2308: `service = getattr(zaglavlje_tab, "service", None) or
  ZaglavljeService()` → `service = ZaglavljeService()`.
  `ZaglavljeService.__init__` (`services/zaglavlje_service.py:39-40`) je bez
  stanja (`self.logger = logger`) — direktno instanciranje je uvijek
  bezbjedno i ekvivalentno.
- `services/zaglavlje_service.py` i `dist_client/services/zaglavlje_service.py`,
  `_parse_xml`, ~linija 1058-1080 (unutar `if country_el is not None:` bloka
  i nakon njega):
  ```python
  # Rb. 10, 11: Zem.otp. / Trgov.zem.
  data['zem_10'] = _txt(country_el, "Country_first_destination")
  data['zem_11'] = _txt(country_el, "Trading_country")
  # Rb. 16: Država porijekla (nalazi se unutar Country, ne direktno u General_information)
  data['drzava_porijekla'] = _txt(country_el, "Country_of_origin_name")
  # ... (van if country_el):
  # Rb. 12, 13: Vrijednost / CAP
  data['zem_12'] = _txt(gen_info, "Value_details")
  data['zem_13'] = _txt(gen_info, "CAP")
  ```
  Rest funkcije nepromijenjen — `save_to_draft`/`load_from_draft` mapping
  za `zem_10-13`/`drzava_porijekla` već postojao (Faza 4 i ranije), samo
  `_parse_xml` nije punio te ključeve (ili je punio pogrešan put).

## Šta nije dirano
- Faza 4 plumbing (`save_to_draft(self.draft, data)`, Rb.18/21 izuzeće,
  `global_docs` non-DIS `.number=""` čišćenje) — netaknuto, logika je
  ispravna, samo se ranije nije izvršavala do kraja.
- `gui/tabs/lazy_tab.py` (`LazyTab.__getattr__`/`_noop`) — netaknuto.
  Mehanizam ostaje kakav je (vraća `_noop` za neinicijalizovane tabove);
  fix izbjegava oslanjanje na `zaglavlje_tab`-ov atribut umjesto da mijenja
  `LazyTab` (manji blast radius — `LazyTab` koristi više tabova).
- `odg_zemlja_1-4` (Rb.9 "Odgovorna zemlja / Podaci") — NIJE pronađen
  odgovarajući XML element ni u `2.xml` ni u `02.xml`. Ostavljeno kao
  follow-up.
- Rub.40 šifre CMR/ZUT/UVK/SAN/VET (korisnikova "Issue 1") — NIJE
  eksplicitno adresirano ovom izmjenom (vidi "Konflikti / kontradiktorni
  izvori" i "Potreban follow-up").
- Necommitovani WIP (`AGENTS.md`, `CLAUDE.md`,
  `agent_reports/2026-06-14_univerzalni-agent-md-template.md`,
  `client.log.lck`) — netaknuto.

## Verifikacija
- `python -m py_compile gui/tabs/naimenovanja_view.py
  dist_client/gui/tabs/naimenovanja_view.py services/zaglavlje_service.py
  dist_client/services/zaglavlje_service.py` → OK.
- Privremene dijagnostičke skripte (`tmp_diag2.py`, `tmp_diag3.py`,
  `tmp_diag4.py`, sve obrisane nakon verifikacije) na
  `data/knowledge_base/NOVA ASIKUDA/2.xml`:
  - Potvrđena XML struktura: `Country_of_origin_name`, `Value_details`,
    `CAP`, `Country_first_destination`, `Trading_country` — tačne putanje
    unutar `General_information`/`General_information/Country`.
  - Pun flow `load_from_xml` → `save_to_draft` (sa pre-postavljenim
    Rb.18/21 vrijednostima) → `load_from_draft`:
    - `izvoznik_r1='ASILAKS'`, `primalac_r1='GMP KOMPANI DOO'`,
      `deklarant_r1='DM-PROMET DOO'` — popunjeni. ✅
    - `deklaracija_1='IM'`, `deklaracija_oznaka='A'` — popunjeni. ✅
    - `ured_odredista_sifra='BA097012'`,
      `ured_odredista_naziv='CI Bijeljina'` — popunjeni. ✅
    - `zem_12='459.85'` — popunjen (PRIJE fixa: `''`). ✅
    - `drzava_porijekla='TURSKA'` — popunjen (PRIJE fixa: `''`). ✅
    - `drzava_izvoza_naziv='TURSKA'`, `uslovi_kod='FCA'`,
      `uslovi_mjesto='ISTANBUL'` — popunjeni (nepromijenjeno, već radilo). ✅
    - Rb.18/21 (`transport_id`/`aktivno_transport`/`aktivno_transport_nat`)
      — NEPROMIJENJENI kroz import (Faza 4 izuzeće radi i dalje). ✅
    - `odg_zemlja_*`, `zem_10`, `zem_11`, `zem_13`,
      `drzava_odredista_naziv/sifra` — ostaju `''`, jer su `<null/>` u
      `2.xml` (genuinely empty, ne bug).
- `gitnexus_detect_changes(scope="unstaged")` (oba puta, prije svakog
  commit-a) → `risk_level: low`, `affected_processes: []`.
- `git status --short` nakon oba commita — samo namjeravani fajlovi +
  pre-postojeći necommitovani WIP.

## Pronađeni problemi
- Faza 4 izvještaj je u "Pronađeni problemi" tačno IDENTIFIKOVAO ovaj
  `_noop` rizik, ali ga POGREŠNO procijenio kao "nije reprodukovano,
  Zaglavlje je obično prvi/eager tab" — lažno negativan zaključak.
  Stvarna konstrukcija tabova (`gui/main_window.py`) ima Faktura kao
  eager (index 0), a Zaglavlje kao `LazyTab` (index 2) — DAKLE Zaglavlje
  NIJE eager i bug SE reprodukuje u normalnom toku.
- Nije pronađen XML element koji bi mapirao na `odg_zemlja_1-4` (Rb.9) ni
  u `2.xml` ni u `02.xml` — moguće da ASYCUDA Box 9 ("Person responsible
  for financial settlement") jednostavno nije popunjen u ovim konkretnim
  deklaracijama; nije dovoljno za zaključak da extrakcija ne postoji jer
  ne TREBA postojati.

## Konflikti / kontradiktorni izvori
- Faza 4 (`2026-06-15_naimenovanja-uvoz-zaglavlje-popunjavanje-fix.md`)
  "Potrebna korisnička potvrda" je tražila da korisnik provjeri popunjenost
  Izvoznik/Uvoznik nakon uvoza — korisnikov test je pokazao da NIJE bilo
  popunjeno, što je DIREKTNO suprotno Fazinoj 4 verifikaciji (koja je
  prošla na simulaciji JER simulacija NIJE prolazila kroz
  `getattr(zaglavlje_tab, "service", None)` — tj. simulacija nije
  reprodukovala `LazyTab` okruženje). Ovaj izvještaj TRETIRA Fazu 4 kao
  DOPUNJENU (ne pogrešnu) — Fazina 4 plumbing logika je ispravna i
  POTREBNA, samo prethodno nikad nije dosegnuta. Faza 4 + Faza 5 zajedno
  čine kompletno rješenje. Nije potrebna dodatna korisnička potvrda za
  ovaj konflikt — riješen je ovim fixom, ali ZAHTIJEVA NOVI test u
  stvarnoj app (vidi "Potrebna korisnička potvrda" ispod).
- Korisnikova napomena o Rub.40 "CMR, ZUT, UVK, SAN, VET su stare šifre i
  ne popunjavaju se" — OSTAJE NERAZJAŠNJENO da li je ovo (a) opis OČEKIVANOG
  ponašanja nakon Faze 4 (te šifre su DOLE u listi, ali bez broja, jer
  `preserve_codes` ne uključuje sve 5 i Faza 4 je obrisala njihov `.number`)
  ili (b) zahtjev da se te šifre POTPUNO UKLONE iz Rub.40 tabele. Faza 4
  izvještaj je već flagovao identičan rizik za "CMR/FAK/SAN/VET/UVK" u
  "Rizici / ograničenja" i tražio korisničku potvrdu — ta potvrda još nije
  data. Tretirano kao OTVORENO — DA, potrebna korisnička potvrda (vidi
  ispod).

## Commitovi
| Hash | Poruka |
|------|--------|
| `4b56340` | `fix(naimenovanja): ukloni LazyTab _noop zamku pri uvozu XML u Zaglavlje` |
| `7c43c71` | `fix(zaglavlje): popuni Rb.10-13 i ispravi Rb.16 drzava porijekla iz ASYCUDA XML-a` |

## Rizici / ograničenja
- Fix #1 (ZaglavljeService() direktno) je lokalna popravka za OVU funkciju.
  Ako negdje drugo u kodu postoji isti `getattr(lazy_tab_instance, "attr",
  default) or fallback` pattern oslonjen na `LazyTab`, isti `_noop` bug
  može postojati i tamo — nije rađen sistematski grep van scope-a ove
  funkcije.
- `zem_10`/`zem_11`/`zem_13`/`drzava_odredista_naziv`/`drzava_odredista_sifra`
  extrakcija NIJE verifikovana na XML-u gdje su ti elementi STVARNO
  popunjeni (u `2.xml` su svi `<null/>`) — putanje su po analogiji s
  `Country_of_origin_name`/`Country/Destination`, ali bez populiranog
  primjera ne može se 100% garantovati ispravan naziv child elementa.
- `odg_zemlja_1-4` (Rb.9) ostaje nepopunjen — ako korisnikov XML STVARNO
  sadrži podatak za ovu rubriku, biće i dalje prazno nakon ovog fixa.

## Potreban follow-up
- `odg_zemlja_1-4` (Rb.9 "Odgovorna zemlja / Podaci") — locirati XML
  element ako korisnik potvrdi da konkretan XML ima podatak za ovu
  rubriku.
- Rub.40 CMR/ZUT/UVK/SAN/VET — odlučiti (uz korisnika) da li te šifre
  treba potpuno ukloniti iz Rub.40 tabele ili je trenutno ponašanje (šifra
  prikazana, referenca prazna) prihvatljivo.
- Verifikovati `zem_10`/`zem_11`/`zem_13`/`drzava_odredista_*` extrakciju na
  XML-u gdje su ti elementi populisani (ako/kad korisnik naiđe na takav
  XML).

## Potrebna korisnička potvrda
U pokrenutoj aplikaciji, OBAVEZNO testirati NOVI tok (Zaglavlje tab NIKAD
otvoren prije uvoza — ovo je tok koji je prethodno bio pokvaren):
1. Pokrenuti app, otvoriti Faktura tab (eager), NE klikati na Zaglavlje.
2. Naimenovanja tab → "Uvezi ASYCUDA XML" → izabrati XML.
3. Otvoriti Zaglavlje tab i provjeriti:
   - Izvoznik (Rb.2), Primalac/Uvoznik (Rb.8), Deklarant (Rb.14) — POPUNJENI.
   - "1. Deklaracija" (4 dropdowna) i Rb.9-20 — popunjeni (osim Rb.9
     "Odgovorna zemlja" koji ostaje prazan po dizajnu, vidi follow-up).
   - Rb.12 "Vrijednost" i Rb.16 "Drž. porijekla" — popunjeni (novi fix).
   - Rb.18/21 (prevoz) — NISU promijenjeni uvozom.
   - Rub.40: DIS ima referencu, ostale šifre — odlučiti da li je trenutni
     prikaz (šifra bez broja) prihvatljiv (vidi follow-up CMR/ZUT/UVK/SAN/VET).
