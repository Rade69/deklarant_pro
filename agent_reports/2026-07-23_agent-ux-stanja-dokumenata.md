## Datum

2026-07-23

## Agent

Codex

## Scope

- `gui/tabs/agent/widgets/upload_area.py`
- `gui/tabs/agent/widgets/document_panel.py`
- `gui/tabs/agent/widgets/file_table.py`
- `gui/tabs/agent/widgets/chat_panel.py`
- odgovarajuće `dist_client` runtime kopije

## GitNexus impact

Rizik je LOW. `UploadArea`, `ModeCard`, `DocumentPanel` i `ChatPanel` nemaju
evidentirane zavisne procese. `FileTable` ima devet zavisnih uvoza do dubine tri,
bez pogođenih izvršnih procesa. Završni `detect_changes` nije prepoznao worktree
diff jer je indeks vezan za glavni checkout; zato je scope dodatno provjeren
ciljanim `git diff` pregledom i eksplicitnim stagingom osam fajlova.

## Šta je urađeno

- Upload zona se nakon dodavanja dokumenta sažima, a nakon uklanjanja posljednjeg
  fajla ili čišćenja vraća na punu visinu.
- Aktivni režim obrade ima jasnu oznaku, a tekst glavnog dugmeta prati režim.
- Statusi fajlova prikazuju se na srpskom, bez promjene internih statusnih vrijednosti.
- Tabela je zbijena i više prostora ostavlja nazivu fajla.
- Chat unos preciznije objašnjava da korisnik može pitati o uvezenim dokumentima.

## Zašto je urađeno

Nakon učitavanja fajlova velika upload zona više nije primarni zadatak i zauzimala
je prostor potreban tabeli i rezultatima. Režim obrade i glavna akcija morali su
jasnije pokazivati šta će se desiti pritiskom na dugme.

## Kako je urađeno

Dodano je eksplicitno kompaktno stanje u `UploadArea`, povezano sa postojećim
signalima dodavanja, uklanjanja i čišćenja u `DocumentPanel`. Prikaz statusa je
lokalizovan mapom samo na nivou tabele, dok `FileItem.status` ostaje nepromijenjen.
Source i runtime fajlovi su sinhronizovani.

## Šta nije dirano

- Signali i controller/service tokovi.
- Parsiranje, analiza, uvoz u deklaraciju i puna automatizacija.
- Struktura i indeksi kolona tabele.
- Chat memorija, streaming i LLM provider.
- Navigacija ka kartici Faktura.
- Postojeće nepovezane izmjene u UI i projektnim instrukcijama.

## Verifikacija

- `py_compile` za osam izmijenjenih Python fajlova: prošao.
- Qt offscreen provjera proširenog/sažetog stanja, sva tri režima, loading
  povratka, statusa, uklanjanja i čišćenja: prošla.
- Source/dist hash parovi: identični.
- `tests/unit/test_agent_file_status_normalization.py`: 2/2 prošla.
- `tests/unit/test_chat_panel.py`: nisu izvršena jer aktivni runtime nema
  `pytest-qt` i `qtbot` fixture.
- `git diff --check`: prošao.

## Pronađeni problemi

Virtualno okruženje nije u worktree `dist_client` direktoriju nego u glavnom
`dist_client/.venv`. GitNexus indeks je vezan za glavni checkout i završni
`detect_changes` ne mapira izmjene iz ovog worktree-a.

## Konflikti / kontradiktorni izvori

Nema konflikta u kodu. GitNexus završni prikaz nije bio važeći za worktree diff,
pa je korišten ciljano pregledan i eksplicitno staged Git diff. Korisnička potvrda
za ovu tehničku odluku nije potrebna.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `a3a07e7` | `feat(agent): unaprijedi rad sa dokumentima` |

## Rizici / ograničenja

Visina od 64 px provjerena je offscreen, ali korisnik treba vizuelno potvrditi
odnos na svom DPI skaliranju. Dugme za direktno otvaranje Fakture nije dodano jer
još nema potvrđen navigacioni ugovor.

## Potreban follow-up

Ako je potreban direktan prelazak na Fakturu nakon uspješnog uvoza, prvo povezati
novi signal sa postojećom navigacijom glavnog prozora i pokriti ga testom.

## Potrebna korisnička potvrda

Provjeriti da li je sažeta upload zona dovoljno visoka i da li lokalizovani
statusi ostaju čitljivi pri uobičajenoj širini Agent kartice.
