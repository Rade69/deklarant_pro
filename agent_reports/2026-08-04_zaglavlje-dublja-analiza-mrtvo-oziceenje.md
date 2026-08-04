## Datum
2026-08-04

## Agent
Claude Code (Sonnet 5)

## Scope
Dublja analiza (na eksplicitan zahtjev korisnika): `gui/tabs/zaglavlje_view.py`,
`gui/tabs/zaglavlje_controller.py` i njihove `dist_client/` kopije.

## Status izvora
Nastavak `agent_reports/2026-08-03_zaglavlje-3layer-audit-dead-code-cleanup.md` — taj izvještaj je
eksplicitno naveo da nije urađen isti nivo detalja kao Naimenovanja audit (samo ciljani grep za
poznate red-flag obrasce). Ovaj zadatak je taj dublji nivo — svih 11 View signala provjereno na
emisiju, svaki `_on_*`/closure handler pregledan.

## Impact analiza
GitNexus `impact` nije direktno pozvan za pojedinačne simbole ovog kruga (isti obrazac pouzdanosti
kao ranije: repo-wide grep je jači dokaz za "0 pozivalaca/0 emitera" tvrdnje od statičkog
poziv-grafa koji ne prati Qt signal/slot emisiju). Rizik procijenjen LOW za sve izmjene — sva tri
nalaza su dokazano nedostižan/uzaludan kod, ne živa poslovna logika.

## Reprodukcija prije izmjene
N/A — nije bugfix, dublji audit + cleanup mrtvog/uzaludnog koda.

## Kontekst korišćen
- `gui/tabs/zaglavlje_view.py` — NIJE pročitan u cijelosti (2579 linija), ali sistematski pretražen:
  svih 21 `.connect(` poziva, svih 7 `.emit(` poziva, svi Signal definicije, svaki od 6
  `_on_*`/imenovanih closure handlera pročitan u cijelosti sa kontekstom.
- `gui/tabs/zaglavlje_controller.py` — svih 20 top-level metoda popisano; pročitane u cijelosti:
  `_connect_signals`, `_on_save`, `_populate_oznaka_combo`, `_on_dekl_sifra_changed`,
  `_on_valuta_changed`, `_on_export_xml` (radi MainWindow-reach nalaza), `_on_import_jci`.
- `gui/tabs/base_controller.py` — pročitan (dokumentacioni template koji objašnjava porijeklo
  `_on_save` zaostatka).
- `gui/tabs/base_view.py` — provjeren za `save_requested` signal (potvrda da `ZaglavljeView`
  redefiniše, ne nasljeđuje značenje tog imena).

## Šta je urađeno
1. Popisano svih 11 View signala; za svaki provjereno DA LI SE STVARNO EMITUJE (ne samo definisan)
   — grep za `.emit(` pozive i `.connect(self.X.emit)` obrazac, plus repo-wide grep za eksterne
   emitere.
2. Otkriveno: `save_requested` definisan + povezan na `Controller._on_save`, ali NIKAD emitovan
   (dugme "Snimi" zapravo emituje `validation_requested`) → `_on_save` nedostižan.
   `load_requested` definisan, NIKAD ni povezan ni emitovan → potpuno siroče.
3. Istraženo porijeklo: `base_controller.py` (BaseTabController) ima dokumentacioni primjer koji
   doslovno pokazuje `self.view.save_requested.connect(self._on_save)` kao "kako koristiti bazu
   klasu" — ali `ZaglavljeController` NE nasljeđuje `BaseTabController` (plain klasa). Zaključak:
   `_on_save` je zaostatak iz kopiranog template obrasca, ne živa namjera.
4. Otkriveno sjenčeno dupliranje: `_populate_oznaka_combo` postoji i u View-u i u Controlleru, sa
   RAZLIČITIM izvorima podataka (Controller: IM/EX-specifične oznake iz `vrste_deklaracija`; View:
   generičan A/Z/B iz `tipovi_deklaracija`, docstring "isti za IM i EX"). Praćenjem redoslijeda
   izvršavanja u `_on_sifra_activated` (View) utvrđeno: signal `deklaracija_sifra_changed` se emituje
   PRIJE nego View pozove svoju vlastitu verziju → Controller-ova verzija se izvrši sinhrono i
   ODMAH se prepiše View-ovom. Krajnji rezultat uvijek ispravan, ali svaki klik na IM/EX combo radi
   nepotreban DB round-trip kroz Controller→Service koji se odbacuje.
5. Provjereno: `_on_import_jci` je namjerno nedovršena funkcija (TODO komentar "u izradi"), nikad
   povezana ni na jedan signal — NIJE tretirana kao nalaz za brisanje, samo napomenuta.
6. Provjereno: `Controller._on_export_xml` sam otvara `QFileDialog` (suprotno konvenciji "View
   bira fajl") i jednom radi `self.view.window()` za MainWindow poziv
   (`continue_with_pending_declaration`, ASYCUDA 99-stavki-limit nastavak) — izolovan, sa `hasattr`
   provjerom i fallback porukom. Napomenuto kao manji nalaz, NIJE mijenjano (nije bilo dio
   korisnikovog odobrenja, funkcionalno je ispravno i guardovano).
7. Predstavljeni nalazi 1 i 2 korisniku (AskUserQuestion, dva pitanja) — korisnik odobrio
   preporučene opcije za oba: brisanje `save_requested`/`load_requested`/`Controller._on_save`, i
   brisanje `Controller._populate_oznaka_combo`/`_on_dekl_sifra_changed`/wiring.
8. Izvršene izmjene u `gui/tabs/zaglavlje_view.py` i `gui/tabs/zaglavlje_controller.py` (+
   `dist_client/` kopije): uklonjeni `save_requested`/`load_requested` Signal definicije,
   `Controller._on_save()`, `Controller._populate_oznaka_combo()`, `Controller._on_dekl_sifra_changed()`,
   i odgovarajuće `.connect()` linije + docstring reference u `_connect_signals`.
9. `py_compile` na sva 4 fajla — OK.
10. Puna `pytest tests/ -q` (bez DB-zavisnih testova, isti razlog kao ranije — `dmserver`
    nedostupan) — identičan baseline, nema regresije.
11. `npx gitnexus analyze` + `detect_changes` — risk_level low.
12. Commit `7a3fe20`.

## Zašto je urađeno
Korisnik je eksplicitno zatražio "napravi dublju analizu" (dva puta, za naglasak) nakon prethodnog
plićeg audita koji je sam sebe okarakterisao kao nepotpun. Cilj: primijeniti isti nivo detalja kao
Naimenovanja audit (svaki `_on_*` handler klasifikovan) na Zaglavlje. Nalazi su predstavljeni
korisniku prije izmjene (AskUserQuestion) jer, iako je rizik nizak, odluka "da li obrisati kod za
koji NIJE 100% izvjesno da nema buduću namjenu" (naročito `save_requested`/`_on_save`, koji bi
teoretski mogao biti planiran za budući "brzi save bez validacije" put) je poslovna/arhitektonska
odluka, ne tehnička činjenica — u skladu sa AGENTS.md "Facts vs Decisions" pravilom.

## Kako je urađeno
Vidi "Šta je urađeno" — sistematski grep-audit (emisija svakog signala, poziv svake metode)
praćen ciljanim brisanjem potvrđeno-nedostupnog koda, isti standard dokaza kao prethodna dva
kruga (Naimenovanja i prvi Zaglavlje audit) ove sesije.

## Šta nije dirano
- `deklaracija_sifra_changed` Signal definicija i `.emit()` poziv u View-u — NAMJERNO ostavljeni
  (korisnikovo odobrenje je pokrivalo samo "Controller verziju + wiring", ne i View-ovu stranu
  signala). Signal se sada emituje "u prazno" (niko ne sluša) — bezopasno, ali nije 100% čist
  cleanup; vidi "Potreban follow-up".
- `ZaglavljeService.get_vrste_deklaracija()`/`get_vid_unutra()` — sada nemaju pozivaoce u
  produkcionom kodu (posljedica ove izmjene, jer su njihovi jedini pozivaoci bili upravo obrisane
  Controller metode + ranije obrisan `load_dropdowns()`). NIJE obrisano — van odobrenog obima ovog
  zadatka, korisnik nije eksplicitno pitan za ovaj specifičan sloj. Evidentirano kao follow-up.
- `Controller._on_export_xml`-ov `QFileDialog`/`self.view.window()` obrazac — napomenuto, nije
  mijenjano (funkcionalno ispravno, izolovano, guardovano).
- `_on_import_jci` — namjerna nedovršena funkcija, nije dirana.
- Ostatak View-a/Controllera (UI konstrukcija, layout metode) — nije pregledan linija-po-linija;
  fokus je bio na signal/handler grafu, ne na svakoj metodi u fajlu.

## Verifikacija
- `py_compile` na sva 4 izmijenjena fajla — OK.
- Puna `pytest tests/ -q -k "not test_db_ and not test_decision_characterization and not
  tariff_learning_ledger"` — 1650 passed, identično baseline-u (3 pre-postojeća fail-a nepovezana,
  `dmserver` nedostupan za DB testove).
- Repo-wide grep prije brisanja potvrdio 0 emitera/pozivalaca za sve obrisane simbole.

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: LOW rizik (dokazano nedostupan/uzaludan kod, puna test svita zelena), korisnik direktno
  odlučio o obimu prije izmjene (AskUserQuestion). Po AGENTS.md kriterijumu, nezavisna provjera
  nije obavezna za ovaj obim.

## Pronađeni problemi
- Peti primjer iste klase nalaza u sesiji (nakon 2x Naimenovanja, 1x Zaglavlje `load_dropdowns`):
  kod koji izgleda kao "treba popraviti" je zapravo nedostupan/zasjenjen. Ovaj put suptilnija
  varijanta — `_populate_oznaka_combo` NIJE bio 100% mrtav (Controller-ova verzija se STVARNO
  izvršava), samo je njen rezultat uvijek odbačen. Vrijedna razlika za buduće audite: "0 poziva" i
  "poziva se, ali rezultat se uvijek prepiše" su dvije različite kategorije nalaza koje zahtijevaju
  različit nivo dokaza (prvo: grep pozivalaca; drugo: praćenje redoslijeda izvršavanja/signal
  emisije).
- `_on_save` porijeklo (doslovno kopiran iz `base_controller.py` docstring primjera bez stvarnog
  nasljeđivanja te klase) je koristan nalaz za razumijevanje KAKO ovakav mrtav kod nastaje u ovom
  projektu — vrijedi zapamtiti kao obrazac za buduće audite drugih tabova koji možda imaju sličnu
  "kopiran template bez nasljeđivanja" istoriju.

## Odbačene opcije
- Opcija (razmatrana implicitno, nije eksplicitno ponuđena korisniku): obrisati i
  `deklaracija_sifra_changed` signal iz View-a i `get_vrste_deklaracija`/`get_vid_unutra` iz
  Service-a, kao potpuniji cleanup.
- Zašto je odbačena: van eksplicitno odobrenog obima (AskUserQuestion opcije su precizno navele šta
  se briše); širenje scope-a bez nove potvrde bi kršilo "ne mijenjati kod van scope-a zadatka".
- Kada odluku ponovo otvoriti: sledeći put kad se Zaglavlje dira, ili ako korisnik eksplicitno
  zatraži "dovrši taj cleanup".

## Konflikti / kontradiktorni izvori
Nema — svi nalazi su nezavisno potvrđeni sa dva izvora dokaza (grep + čitanje koda za redoslijed
izvršavanja) prije nego što su predstavljeni korisniku.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `7a3fe20` | `refactor(zaglavlje): ukloni mrtva signal-ozicenja i sjenceno dupliranje` |

## Rizici / ograničenja
- `deklaracija_sifra_changed` signal sada nema slušaoca (Controller strana uklonjena, View strana
  ostavljena) — bezopasno (Qt signal bez slušaoca je no-op), ali arhitektonski "napola očišćeno"
  stanje. Ako neko kasnije doda novog slušaoca očekujući staru semantiku (IM/EX-specifične oznake),
  treba znati da ta logika više ne postoji nigdje u kodu (obrisana, ne premještena).
- `get_vrste_deklaracija()`/`get_vid_unutra()` u Service-u su sada mrtav kod, ali nisu obrisani —
  sledeći audit će ih ponovo pronaći kao "0 pozivalaca" nalaz.
- Analiza NIJE bila linija-po-linija za cio View/Controller (fokus na signal/handler graf) — moguće
  da postoje dodatni suptilni nalazi van ovog fokusa (npr. u UI-konstrukcionim metodama koje nisu
  handleri).

## Potreban follow-up
Ako se sledeći put dira Zaglavlje: razmotriti brisanje `deklaracija_sifra_changed` (View signal +
emit) i `get_vrste_deklaracija`/`get_vid_unutra` (Service) za potpun cleanup ovog lanca — trenutno
namjerno ostavljeno van obima.

## Potrebna korisnička potvrda
Nema — sve izmjene su brisanje dokazano nedostupnog/uzaludnog koda, ne mijenjaju nijedno vidljivo
ponašanje, nije potrebna ručna GUI provjera specifično za ovu izmjenu.
