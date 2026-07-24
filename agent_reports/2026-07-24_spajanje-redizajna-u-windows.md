## Datum

2026-07-24

## Agent

Codex

## Scope

Spajanje grane `codex/faktura-toolbar-razmaci` u glavnu lokalnu granu
`windows`, uključujući root GUI i `dist_client` runtime kopiju.

## Status izvora

- `docs/CONTEXT.md` sa grane `windows`: aktivan i autoritativan za kasnije
  stabilnosne, DB i import odluke.
- Grana `codex/faktura-toolbar-razmaci`: aktivan izvor kompletnog UX/UI
  redizajna i pripadajućih testova/izvještaja.
- Pojedinačni agent izvještaji redizajna: aktivni; preneseni kroz merge.

## GitNexus impact

Provjera pripremljenog merge-a prijavila je CRITICAL opseg: 115 izmijenjenih
fajlova, 923 dodirnuta simbola i 33 povezana procesa. Visok nivo je posljedica
kompletnog redizajna šest glavnih kartica i paralelnih root/`dist_client`
runtime kopija, a ne jedne izolovane poslovne izmjene.

## Šta je urađeno

- Spojena je kompletna istorija grane redizajna u `windows`.
- Zadržane su kasnije funkcionalne izmjene sa `windows`, uključujući
  jedinstveni ručni/Agent/batch import workflow.
- Riješen je jedini tekstualni konflikt u `docs/CONTEXT.md`.
- Sekcije redizajna o inline validaciji, tastaturnoj navigaciji i hover
  standardu sačuvane su kao §54–56.
- Sačuvani su raniji nepraćeni korisnički fajlovi.

## Zašto je urađeno

Redizajn je razvijan u odvojenom worktree-u radi izbjegavanja konflikata sa
drugim agentima. Nakon završetka funkcionalnih izmjena na `windows` bilo je
potrebno objediniti vizuelni rad i noviji poslovni kod u jednu glavnu granu.

## Kako je urađeno

Prije stvarnog merge-a korišćen je probni trostrani merge. Stvarni merge je
pokrenut sa `--no-commit`, konflikt memorije je ručno spojen, a automatski
spojeni osjetljivi fajlovi pregledani su prije testiranja i commita.

## Šta nije dirano

- `services.import_workflow` poslovna pravila i atomska primjena plana.
- Assembly/Master-list legacy fallback.
- DB migracije, frozen DB putanje i QThread stabilnosne popravke.
- Raniji nepraćeni fajlovi u radnom stablu.
- Dva postojeća problema u test kolekciji koji nisu povezani sa merge-om.

## Verifikacija

- `py_compile` svih 64 spojenih Python fajlova: prošao.
- Ciljani GUI i import testovi: 155 prošlo.
- Puni paket: 1083 prošlo, 58 preskočeno, 5 xfailed, 1 fail i 1 error.
- Nevezani postojeći problemi:
  - `tests/test_model_benchmark.py::test_model` očekuje nepostojeći fixture
    `model_name`.
  - `tests/test_xml_parser_fix.py::test_xml_parser` koristi hardkodovanu
    lokalnu Linux putanju `/home/radovan/Documents/Računi/1.xml`.
- `git diff --check`: čist.
- Ključni root i `dist_client` ulazi za import, Agent, QThread i bezbjedan
  izlaz potvrđeni su nakon merge-a.

## Pronađeni problemi

Jedini merge konflikt bio je numerički/sadržajni konflikt sekcija u
`docs/CONTEXT.md`; nije bilo konflikata u Python ili QSS fajlovima.

## Konflikti / kontradiktorni izvori

`windows` je imao sekcije §35–53, dok je grana redizajna dodavala zasebne
sekcije numerisane §31–33. Oba sadržaja su važeća; zadržan je kompletan
`windows` sadržaj, a tri redizajn sekcije prenumerisane su u §54–56.
Korisnička potvrda nije potrebna.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `2542d6b` | `merge(gui): spoji redizajn u windows` |

## Rizici / ograničenja

Automatski testovi ne mogu potpuno zamijeniti ručnu vizuelnu provjeru svih
tabova pri stvarnoj rezoluciji i Windows skaliranju. `dist_client` ostaje
namjerno odvojena runtime kopija i ne smije se ubuduće mehanički prepisivati
cijelim root fajlovima.

## Potreban follow-up

Po želji zasebno popraviti dva nevezana problema u test kolekciji.

## Potrebna korisnička potvrda

Ručno pokrenuti aplikaciju iz `dist_client` i pregledati Fakturu,
Naimenovanja, Zaglavlje, Šifrarnike, Admin i Agent pri uobičajenoj rezoluciji.
