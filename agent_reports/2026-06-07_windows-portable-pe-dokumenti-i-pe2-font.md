# Agent report - Windows portable instalacija, PE dokumenti i PE2 font

Datum: 2026-06-07
Grana: windows

## Sta je uradjeno

- Dodano je novo uputstvo `docs/WINDOWS_PORTABLE_VENV_INSTALL.md` za instalaciju aplikacije na drugi Windows racunar preko `dist_client + .venv`.
- Uputstvo pokriva kopiranje foldera, provjeru `.env`, pokretanje preko `.venv\Scripts\python.exe run.py`, pravljenje `.bat` launchera, Desktop precicu, Tesseract OCR, licencu, nadogradnju i najcesce greske.
- U `PE2QuickDialog` je povecan samo pomocni tekst ispod zelenog headera (`font-size: 11px`) da PE2/PE3 instrukcije budu citljivije na Windows skaliranju.
- U `ZaglavljeController` i `ZaglavljeService` je zadrzana/ucvrscena logika da se PE1/PE2/PE3 dokumenti u zaglavlju ne dedupliraju samo po sifri dokumenta, nego da se mogu sacuvati razliciti brojevi/referencije.
- U `AGENTS.md`, `CLAUDE.md` i `docs/CONTEXT.md` dopunjeno je pravilo za Rub.31: GUI moze prikazati duzi pregled, ali ASYCUDA XML izlaz mora ostati ogranicen na max 280 karaktera i najvise 3 linije.

## Zasto su donesene ove odluke

- `.exe` build trenutno pravi previse trenja zbog PySide6, Qt pluginova, OCR-a, parsera i assets fajlova. Portable `dist_client + .venv` pristup je manje elegantan, ali stabilniji za stvarnu upotrebu dok se GUI i poslovna logika jos aktivno popravljaju.
- PE dokumenti se ne smiju deduplirati samo po sifri `PE2`, jer vise faktura moze imati izjavu o porijeklu. Ako se cuva samo jedna PE2 referenca, zaglavlje deklaracije gubi dio dokumentacije.
- Font u PE2/PE3 pomocnom tekstu povecan je minimalno i lokalno, bez promjene layouta ili logike, jer je cilj bio samo bolja citljivost dijaloga.
- Rb.31 pravilo je dopunjeno da agenti ubuduce ne mijesaju GUI pregled sa ASYCUDA XML ogranicenjem. GUI moze biti komforan za korisnika, ali XML mora ostati u pravilima koja ASYCUDA prihvata.

## Provjera

- Vizuelne izmjene su uske i lokalne.
- Prije commita treba pokrenuti GitNexus `detect_changes`.
- Nisu ukljuceni nepovezani untracked fajlovi poput `assets/icons/ikonica-DL.png`, `docs/TODO_canon-lbp6670-cups-setup.md` i `docs/UPUTSTVO_XML_ARCHIVE_SETUP.md`.

