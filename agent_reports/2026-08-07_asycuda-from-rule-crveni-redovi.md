## Datum
2026-08-07

## Agent
Claude Code (Sonnet 5)

## Scope
`gui/tabs/zaglavlje_view.py`, `dist_client/gui/tabs/zaglavlje_view.py` (metoda `get_data()`).

## Status izvora
N/A — istraga je krenula od korisnikovog uočenog ponašanja u ASYCUDA World aplikaciji, ne od ranijeg agent_report-a/memorije.

## Impact analiza
`gitnexus_impact` na `ZaglavljeView.get_data` (i `ZaglavljeService.load_from_draft`): risk **LOW**, 0 direktnih pozivalaca u indeksu (Qt signal/slot poziv iz Controller-a nije statički uhvaćen — funkcionalno se poziva pri svakom snimanju/exportu Zaglavlja). `gitnexus_detect_changes(scope=all)`: 49 promijenjenih simbola/12 fajlova ukupno u working tree-u, ali VEĆINA su pre-existing WIP tuđi/raniji (vidi "Šta nije dirano") — moje izmjene ograničene na `get_data`/`set_data` (potonje lažni pozitiv zbog pomjeraja linija, vidi "Pronađeni problemi"). `affected_processes: []`, risk_level "low".

## Reprodukcija prije izmjene
Korisnik je dao direktan dokaz: screenshot ASYCUDA Rb.44 panela sa crvenim (nepotpunim) N380/DIS/DV1 redovima uprkos već upisanoj referenci, plus tri XML fajla za poređenje — `BLAGIĆ-SRECKO.xml` (naš export), `BLAGIĆ-SRECKO-asycuda.xml` (isti export nakon ASYCUDA provjere/procesiranja) i dva ASYCUDA-nativna kontrolna fajla (`BLAGIC-ATOS.xml`, `BLAGIC-LOREN.xml`, kreirani direktno u ASYCUDA aplikaciji, ne pokazuju problem). Strukturno poređenje `Attached_documents` blokova za N380/DIS/DV1 između problematičnog i kontrolnih fajlova potvrdilo je tačan mehanizam prije bilo kakve izmjene koda (vidi "Zašto je urađeno").

## Kontekst korišćen
`exporters/asycuda_xml_builder.py` (funkcije `_normalize_attached_document`, `_add_items`, `_add_attached_doc`) i `services/zaglavlje_service.py` (`load_from_draft`, `save_to_draft`, `_attached_doc_dict`) pročitani u cijelosti u relevantnim sekcijama da se utvrdi kompletan put podatka od GUI table do XML-a, ne samo mjesto gdje je bug nađen.

## Šta je urađeno
U `get_data()` (obje kopije, `gui/` i `dist_client/`) zamijenjeno hardkodovano `"from_rule": False` sa `"from_rule": code.strip().upper() in {"N380", "DIS", "DV1", "DUIM"}`.

## Zašto je urađeno
Korisnik je prijavio da ASYCUDA World pri uvozu/provjeri naših deklaracija traži ponovni unos N380/DIS/DV1 iako su već upisani sa ispravnom referencom (crveni red u Rb.44), dok se isto NE dešava sa XML fajlovima kreiranim direktno u ASYCUDA aplikaciji. Ova razlika je oborila moju prvu hipotezu ("ASYCUDA kvirk, nema veze sa nama") i tražila poređenje sa ASYCUDA-nativnim kontrolnim fajlovima.

Poređenjem je utvrđeno: u kontrolnim fajlovima N380/DIS/DV1/DUIM UVIJEK nose `Attached_document_from_rule=1` ZAJEDNO sa popunjenom referencom u istom `<Attached_documents>` bloku. U problematičnom fajlu ta dva podatka su bila razdvojena u DVA odvojena bloka (referenca bez from_rule, i prazan blok sa from_rule=1 bez reference — potonji je crveni red). ASYCUDA-in rule engine prepoznaje da je obavezni dokument već zadovoljen SAMO preko `from_rule=1` — bez tog taga dodaje sopstveni prazan "otvoreni" zapis.

Praćenjem koda unazad utvrđeno da su `exporters/asycuda_xml_builder.py` (piše `from_rule=1` kad god `doc.from_rule == True`, zajedno sa referencom — tačno ponašanje) i `services/zaglavlje_service.py::save_to_draft` (ispravno čita `from_rule` iz ulaznog dict-a) OBOJE ispravni. Gubitak se dešavao isključivo u `gui/tabs/zaglavlje_view.py::get_data()`, koja je pri čitanju tabele priloženih isprava (nakon pregleda/potvrde od strane korisnika) hardkodovala `"from_rule": False` za SVAKI red, bez obzira šta je `load_from_draft`/`set_data` originalno postavio (koji korektno postavlja `True`).

## Kako je urađeno
Zamjena fiksne vrijednosti sa provjerom šifre protiv skupa `{"N380", "DIS", "DV1", "DUIM"}`, potvrđenog direktno iz kontrolnih fajlova (VOZ/OST/PZT/N730 nisu imali `from_rule` u istim fajlovima, pa nisu dodati u skup). Ista izmjena primijenjena identično u `dist_client/` kopiji jer je to Windows-runtime build koji korisnik stvarno pokreće.

## Šta nije dirano
- `exporters/asycuda_xml_builder.py`, `services/zaglavlje_service.py` — već ispravni, nije bilo potrebe za izmjenom.
- PE/EUR.1-izvedeni dokumenti (FTAP/EUP/TRP, `_PREF_TO_DOC_CODE` u exporteru) — kontrolni fajlovi su pokazivali `from_rule=1` i za te šifre, ali to NIJE bio prijavljeni problem i nije nezavisno provjereno da li isti bug postoji na toj putanji (ona ide odvojeno, iz `item.preference_code`, ne kroz `zaglavlje_view.py` tabelu) — ostavljeno za budući zadatak ako se pojavi crveni red na tim šiframa.
- PZT/N730 (koji `zaglavlje_service.py` i dalje tretira kao "obavezne isprave" za auto-dodavanje) namjerno ostavljeni sa `from_rule=False` — nisu imali taj tag u kontrolnim fajlovima, pa bi dodavanje bilo nagađanje bez dokaza.
- Ostali fajlovi izmijenjeni u working tree-u prije ovog zadatka (AGENTS.md, CLAUDE.md, `dist_client/gui/dialogs/tariff_suggestion_dialog.py`, `dist_client/gui/tabs/naimenovanja_controller.py`, `services/naimenovanja/constants.py`, itd.) — pre-existing WIP, nepovezan sa ovim zadatkom, nije staged niti commitovan (provjereno `git status --short` prije i poslije `git add`, samo moja 2 fajla stage-ovana).

## Verifikacija
1. `python -m py_compile` na oba izmijenjena fajla — OK.
2. `pytest tests/unit/test_asycuda_goods_description.py -q` — 35/35 prošlo (postojeći testovi već pokrivaju `from_rule=True` → `Attached_document_from_rule="1"` u exporteru, bez regresije).
3. Direktan poziv STVARNE `ZaglavljeView.get_data()` metode (unbound, na mock `self` sa pravim `QTableWidget`/`QTableWidgetItem` redovima N380/DIS/DV1/PZT) — potvrđeno: N380/DIS/DV1 → `from_rule=True`, PZT → `from_rule=False`.
4. `ZaglavljeService.save_to_draft()` pozvan sa tim istim podacima na praznom `DeclarationDraft` — potvrđeno da `from_rule` korektno stiže do `AttachedDocument` objekata (N380/DIS/DV1 `True`, PZT `False`).

Nije rađen pun end-to-end izvoz cijele deklaracije u XML i ponovan uvoz u ASYCUDA (nije bilo praktično dostupno u ovoj sesiji) — to je preostala ručna potvrda, vidi "Potrebna korisnička potvrda".

## Nezavisna provjera
- Checker korišćen: NE.
- Razlog: GitNexus impact LOW (0 pozivalaca u indeksu, izolovana metoda), izmjena je jednolinijska i logički jednostavna (mapiranje šifra→bool), pokrivena postojećim test suite-om bez regresije, i direktno testirana na stvarnoj metodi (ne samo pretpostavljena). Prema AGENTS.md "Nezavisna provjera" tabeli, nezavisan checker je obavezan za HIGH/CRITICAL impact ili XML export logiku koja NIJE pouzdano reprodukovana — ovdje je problem bio pouzdano reprodukovan (korisnikovi realni fajlovi) i impact je LOW, ali s obzirom da je u pitanju carinski XML, preporučujem korisniku da ipak uradi probni export+import u ASYCUDA test okruženje prije nego se ovo smatra potpuno zatvorenim (vidi "Potrebna korisnička potvrda").

## Pronađeni problemi
- `gitnexus_detect_changes` je lažno markirao `ZaglavljeView.set_data` kao "touched" u oba fajla — poznat obrazac (linija-pomjeraj: dodavanje 5 linija komentara iznad `get_data()` je pomjerilo `set_data()` ispod za isti broj linija), nisam dirao `set_data()`. Potvrđeno diff-om da je jedina stvarna izmjena unutar `get_data()`.
- `services/zaglavlje_service.py::load_from_draft()` (linija ~1090-1099, `parse_naimenovanja_from_xml` putanja) ima deduplikaciju po `(code, ref)` tuple-u umjesto po `code`, što teoretski može ostaviti duplikate ako izvorni XML ima i prazan i popunjen unos za istu šifru — primijećeno tokom istrage, NIJE dirano jer nije bio dio dokazanog uzroka ovog konkretnog problema (uzrok je bio isključivo u `zaglavlje_view.py::get_data()`).

## Odbačene opcije
- Opcija: dodati `from_rule` kao vidljivu/editabilnu kolonu u GUI tabeli priloženih isprava.
- Zašto je razmatrana: transparentnija, korisnik bi mogao ručno kontrolisati flag.
- Zašto je odbačena: nepotrebno proširenje UI-ja za podatak koji je, prema dokazu iz kontrolnih fajlova, čisto statična funkcija šifre dokumenta (ASYCUDA konvencija), ne nešto što korisnik treba ručno da bira po deklaraciji.
- Kada odluku ponovo otvoriti: ako se ikad nađe kontraprimjer gdje ista šifra (N380/DIS/DV1/DUIM) treba različit from_rule u različitim deklaracijama.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `9a9d993` | `fix(zaglavlje): sacuvaj Attached_document_from_rule za N380/DIS/DV1/DUIM` |

## Rizici / ograničenja
Fix je zasnovan na strukturnom obrascu potvrđenom u DVA kontrolna fajla (ukupno ~101 stavka) — nije formalna ASYCUDA specifikacija, pa postoji mala mogućnost da postoje edge-case-ovi (npr. druge šifre koje bi trebale from_rule u nekim procedurama/tipovima deklaracija) koje ovi konkretni fajlovi nisu pokrili. Nije rađen pun round-trip test (naš export → stvaran uvoz u ASYCUDA World → provjera da crveni red nestane) jer ASYCUDA aplikacija nije dostupna u ovoj sesiji.

## Potreban follow-up
- Provjeriti da li FTAP/EUP/TRP (PE/EUR.1-izvedeni dokumenti) imaju isti problem — kontrolni fajlovi sugerišu da bi i oni trebali `from_rule=1`, ali nije bio prijavljeni problem pa nije dirano.
- `parse_naimenovanja_from_xml` dedup-po-(code,ref) nalaz (vidi "Pronađeni problemi") — zaseban, manji, nepotvrđen nalaz za budući zadatak.

## Potrebna korisnička potvrda
Izvesti jednu stvarnu deklaraciju (npr. ponovo BLAGIĆ ili sličnu sa N380/DIS/DV1 popunjenim) i provjeriti u ASYCUDA World-u (import/provjera) da crveni redovi za te tri šifre više ne postoje. Ovo je jedini preostali korak jačeg dokaza (Definition of Done za XML export: "otvaranje generisanog fajla i potvrda da nije korumpiran" + poređenje sa referentnim — poređenje je urađeno na nivou strukture, ali ne i live ASYCUDA provjera).
