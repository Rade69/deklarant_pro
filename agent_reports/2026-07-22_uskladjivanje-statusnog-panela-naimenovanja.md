## Datum

2026-07-22

## Agent

Codex

## Scope

`gui/tabs/naimenovanja_view.py` i njegova runtime kopija `dist_client/gui/tabs/naimenovanja_view.py`.

## Status izvora

Aktuelni kod taba Naimenovanja i postojeća paleta statusne trake taba Faktura tretirani su kao aktivni izvori. Generisani UI fajlovi imaju ranije lokalne izmjene i nisu mijenjani.

## GitNexus impact

Prethodna impact provjera metode `NaimenovanjaView._add_status_bar` vratila je LOW rizik: jedan direktni pozivalac (`NaimenovanjaView.__init__`) i nijedan pogođeni proces. Završni `detect_changes` vratio je LOW i bez pogođenih procesa, ali nije mapirao Python diff iz izdvojenog worktree-ja; to je ograničenje indeksa/provjere, ne dokaz da izmjena ne postoji.

## Šta je urađeno

Donji statusni panel Naimenovanja usklađen je sa tamnoplavom paletom statusnog panela Fakture. Četiri metričke oznake imaju svijetao tekst na transparentnoj pozadini, dok je status validacije izdvojen kao jasan zaobljen indikator.

## Zašto je urađeno

Panel je vizuelno odstupao od već uređenog taba Faktura. Ujednačavanje poboljšava hijerarhiju i čitljivost bez promjene sadržaja ili načina rada.

## Kako je urađeno

Stil je postavljen u postojećoj View metodi `_add_status_bar`. Zadržane su visine statusne trake i oznaka, a postojeća metoda za dinamičko prikazivanje uspješnog i upozoravajućeg statusa ostala je netaknuta.

## Šta nije dirano

Nisu mijenjani položaji, širine, tekstovi, proračuni, validacija, signali, Controller, Service niti generisani UI fajlovi.

## Verifikacija

- `py_compile` je prošao za obje runtime varijante View fajla.
- Ciljani testovi `test_naimenovanja_view_display_values.py` i `test_pe_rub44_consistency.py`: 9/9 prošlo.
- `git diff --check` i provjera staged diff-a prošli su bez grešaka.
- Ručnim pregledom diff-a potvrđeno je da statusna traka ostaje 48 px, a oznake 30 px.

## Pronađeni problemi

Izdvojeni worktree nema vlastiti `dist_client/.venv`, pa su testovi pokrenuti interpreterom iz glavnog checkouta. GitNexus `detect_changes` nije prepoznao diff ove izdvojene grane.

## Konflikti / kontradiktorni izvori

Nema funkcionalnih konflikata. Ranije lokalne izmjene u generisanim UI i projektnim instrukcijama ostavljene su netaknute; korisnička potvrda nije potrebna za taj izbor.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `b1e32ea` | `style(naimenovanja): uskladi donji statusni panel` |

## Rizici / ograničenja

Rizik je nizak i ograničen na izgled statusnog panela. Konačan prikaz zavisi od Windows DPI skaliranja i treba ga vizuelno potvrditi u aplikaciji.

## Potreban follow-up

Naredni segment redizajna odabrati nakon vizuelne potvrde ovog panela.

## Potrebna korisnička potvrda

Provjeriti da su donji panel, metričke vrijednosti i indikator validacije čitljivi pri uobičajenom prozoru i DPI skaliranju.
