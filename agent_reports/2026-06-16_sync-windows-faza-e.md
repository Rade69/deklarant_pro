# Sync Windows → Linux — Faza E

**Datum:** 2026-06-16  
**Grana:** `sync/windows-agent-faza1-8`  
**Tip:** feat (GUI sync, 4 fajla + 2 nova)

---

## Šta je urađeno

Sinkronizovane sve GUI izmjene razvijene na Windows-u za 4 velika fajla i 2 nova fajla:

| Oblast | Fajl | Status |
|--------|------|--------|
| E1 | `gui/utils/display_profile.py` (NOVO) | ✅ |
| E1 | `styles/display_profiles.qss` (NOVO) | ✅ |
| E1 | `gui/main_window.py` | ✅ |
| E2 | `gui/tabs/zaglavlje_view.py` | ✅ |
| E2 | `gui/tabs/zaglavlje_controller.py` | ✅ |
| E3 | `gui/tabs/naimenovanja_view.py` | ✅ |
| E4 | `gui/tabs/faktura_view.py` | ✅ |

---

## Kako je urađeno (tehnički pristup)

### E1 — DisplayProfile + main_window

Kreiran `DisplayProfile` dataclass sa tri profila (COMPACT/STANDARD/LARGE) na osnovu
rezolucije ekrana. `display_key_for_screen()` gradi SHA1 ključ koji uključuje ime, 
proizvođača, model, serijski broj, rezoluciju i DPR — jedinstven per-monitor ključ.

`main_window.py` sada:
- Čita profil pri pokretanju, stavlja ga kao `displayProfile` Qt property
- Pamti geometriju/maximized stanje per-ekran u QSettings
- Kreira `btn_exit_app` (QPushButton, qtawesome ikona) i pozicionira ga desno od tab bara
- `_confirm_safe_to_exit()` provjerava da li agent worker radi prije izlaska

### E2 — zaglavlje_view + controller

`IspravaDelegate` dobio live feedback: `textEdited.connect(_on_text_edited)` odmah popunjava
Naziv kolonu dok korisnik kuca Šifru — ne čeka dropdown selekciju.

`close_requested` Signal, `btn_izlaz` i `_on_close()` uklonjeni jer je Exit preuzeo main_window.

### E3 — naimenovanja_view

**Ključna promjena:** `_on_save()` sada koristi `DeclarationDraftService().save()` za
snimanje cijelog nacrta kao XML fajl (ranije je samo prikazivao "Naimenovanje sačuvano").

**Novi `_apply_xml_import_to_zaglavlje()`:** pri uvozu ASYCUDA XML-a popunjava zaglavlje
(izvoznik, uvoznik, valuta, dokumenti) ali PRESKAČA transport polja (Rb.18/21) jer nova
deklaracija može imati drugačiji prijevoz.

**PE dedup fix:** `seen: set[tuple[str,str]]` → `seen: set[str]` — dedup po šifri dokumenta,
ne po (šifra, broj) paru. Rješava bug: jedna deklaracija dobila dva EUR.1 reda u zaglavlju.

### E4 — faktura_view

**Bojenje redova:** Crvena boja sada i za redove bez `zemlja_porijekla` (ranije samo tarifni_broj).

**Col 9 fix:** `_on_item_changed` čita `item.text()` i stripa emoji prefiks umjesto
`Qt.UserRole` — rješava bug gdje ručna promjena zemlja_porijekla nije bila sačuvana.

**Evidence-based bojenje:** `_apply_country_confidence_color()` koristi `evidence_from_preference()`
iz evidence_model. Neutralna boja (#dfe4ea) za nepotvrdene zemlje, ikone samo za potvrđenu povlasticu.
Nova `_apply_preference_confidence_color()` boji Povlastica kolonu (col 10) odvojeno.

**Status bar:** Detalji validacije ("3 bez tarife | 1 bez zemlje") uz tooltip.
`_refresh_analysis_summary_from_draft()` i `_pending_validate_rows.clear()` na kraju.

**Batch uvoz:** Mapping Excel (tarife/porekla/ptp) se preskača ako je u folderu sa PDF
fakturama — ista logika kao `ProcessingWorker._is_mapping_xlsx` u agent uvozu.

**`_postprocess_master_frigo_pairs_records()` (NOVO):** sparuje MF PDF+Excel u batch ručnom
uvozu (ranije radilo samo u agent uvozu).

**`_show_scrollable_info_dialog()` (NOVO):** Fiksni dijalog sa QTextEdit+QDialogButtonBox
umjesto QMessageBox koji se širi sa sadržajem. Ovo rješava problem gdje dugme OK ispadne
van ekrana pri većim rezultatima auto-popunjavanja.

**`_show_tariff_mapping_result()`:** Prikazuje `naziv_robe` umjesto `product_code` u listi
popunjenih stavki — šifre poput "609ER004" korisniku ništa ne znače, dok "GREJAC SPIRALA 600W"
odmah otkriva potencijalnu grešku.

---

## Zašto (poslovni razlog)

1. **DisplayProfile** — Windows klijent ima manji ekran (1366×768), trebao je kompaktan UI profil
2. **Exit dugme** — trebalo je biti na logičnom mjestu (naslovni bar), ne unutar zaglavlje taba
3. **PE dedup** — korisnik prijavio bug: jedna deklaracija dobila dva EUR.1 unosa u zaglavlju
4. **Col 9 fix** — korisnik nije mogao ručno mijenjati zemlju porijekla (bug u UserRole čitanju)
5. **Scrollable dialog** — dugme OK ispadalo van ekrana na manjem monitoru
6. **naziv_robe u rezultatima** — korisnik nije mogao provjeriti jesu li tarife ispravne

---

## Commitovi

| Hash | Opis |
|------|------|
| `8a96937` | feat(gui): DisplayProfile sistem i Exit dugme u main_window |
| `203b494` | feat(zaglavlje): IspravaDelegate live naziv, Exit dugme migriran |
| `76e606c` | feat(naimenovanja): _on_save via DeclarationDraftService, PE dedup fix |
| `8ba1907` | feat(faktura): validacija, bojenje, batch uvoz i auto-popuni poboljšanja |
| `86ce5fa` | chore(docs): ažuriraj GitNexus broj simbola |

---

## Testovi

- 553 unit testova prolazi ✅
- 2 pre-postojeća failova u `test_declaration_search_service.py` (nisu naš kod)
- `from gui.tabs.faktura_view import FakturaView` → ✅
- `from gui.main_window import MainWindow` → ✅
- `from gui.tabs.zaglavlje_view import ZaglavljeView` → ✅
- `from gui.tabs.naimenovanja_view import NaimenovanjaView` → ✅
