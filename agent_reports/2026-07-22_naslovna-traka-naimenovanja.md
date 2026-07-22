## Datum

2026-07-22

## Agent

Codex

## Scope

Naslovna traka kartice Naimenovanja i akcije „Sačuvaj nacrt“ / „Poništi“.

## GitNexus impact

LOW. `_add_section_heading` ima jednog direktnog pozivaoca, konstruktor prikaza; uklonjeno ručno pozicioniranje bilo je vezano samo za `resizeEvent`. Poslovni procesi nisu pogođeni.

## Šta je urađeno

Naslovna traka je povećana na 38 px, dobila je jasniju pozadinu i donju ivicu, a naslov veću tipografiju. Dugmad su ujednačena na 30 px i poravnata desno standardnim Qt rasporedom.

## Zašto je urađeno

Prethodni raspored je koristio fiksni razmak od 1017 px i ručno pomjeranje dugmadi, zbog čega je zavisio od konkretne širine prozora.

## Kako je urađeno

Fiksna koordinatna logika zamijenjena je `addStretch()` rasporedom. Izmjena je preslikana u izvornu i `dist_client` kopiju, uz ciljane QSS selektore za naslovnu traku.

## Šta nije dirano

Nisu mijenjani signali dugmadi, čuvanje nacrta, poništavanje, navigaciona traka iz prethodnog segmenta, formular ni poslovna logika.

## Verifikacija

Prošlo je 9 ciljnih unit testova, `py_compile` obje kopije prikaza i `git diff --check`.

## Pronađeni problemi

GitNexus `detect_changes` i dalje vidi nepovezane fajlove glavnog radnog stabla. Lokalni staged diff je zato korišten kao autoritativna provjera scope-a.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `04d813f` | `style(naimenovanja): uredi naslovnu traku` |

## Rizici / ograničenja

Potreban je ručni vizuelni pregled na korisnikovoj rezoluciji i DPI skali.

## Potreban follow-up

Nakon vizuelne potvrde može se nastaviti na prvi blok formulara Rub.31 kao zaseban segment.

## Potrebna korisnička potvrda

Provjeriti položaj oba dugmeta pri normalnoj i maksimalnoj širini prozora.
