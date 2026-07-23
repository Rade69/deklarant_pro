# Inline validacija GUI obrazaca

## Cilj

Preciznije pokazati mjesto greške bez uklanjanja postojećih modalnih provjera i bez promjene rasporeda tabova.

## Pogođeno

`FakturaView._validate_and_color_row` ima HIGH impact: 28 zavisnih simbola, 8 direktnih pozivalaca kroz učitavanje, uređivanje, grupne izmjene i provjeru. Naimenovanja, Zaglavlje i Šifrarnici imaju LOW impact.

## Plan

1. Na Fakturi zadržati postojeću validaciju, ali problem sa tarifom i zemljom označiti na odgovarajućoj ćeliji.
2. U Naimenovanjima omogućiti klik na status, prelazak na prvo neispravno naimenovanje i fokus/isticanje polja.
3. U modalu Zaglavlja dodati akciju za prikaz polja i fokusirati odgovarajući widget.
4. U Šifrarnicima fokusirati prvo obavezno prazno polje prije postojećeg upozorenja.
5. Dodati ciljane testove i provjeriti root i `dist_client` kopije.

## Šta NE dirati

Validaciona poslovna pravila, import/export, baze, draft modele, generisane UI fajlove, postojeće modale i geometriju tabova.

## Konflikti

U worktreeju postoje korisničke izmjene u `AGENTS.md`, `CLAUDE.md` i generisanim UI fajlovima. One se tretiraju kao aktivne i neće biti mijenjane. Korisnička potvrda nije potrebna jer se implementacija može potpuno odvojiti od tih fajlova.
