# Spajanje grane redizajna u windows

## Cilj

Spojiti granu `codex/faktura-toolbar-razmaci` u `windows` i zadržati kompletan
UX/UI redizajn zajedno sa kasnijim funkcionalnim i stabilnosnim izmjenama na
grani `windows`.

## Pogođeno

GitNexus `detect_changes` za pripremljeni merge prijavio je CRITICAL opseg:
115 fajlova, 923 dodirnuta simbola i 33 povezana procesa. Najosjetljiviji su
glavni prozor, Faktura, Agent, Naimenovanja, Zaglavlje, Šifrarnici, Admin i
njihove `dist_client` runtime kopije.

## Plan

1. Izvršiti trostrani merge bez automatskog commita.
2. Ručno spojiti `docs/CONTEXT.md` bez gubitka odluka sa obje grane.
3. Pregledati automatski spojene runtime fajlove i potvrditi očuvanje import,
   QThread, validacionih i DB popravki sa `windows`.
4. Pokrenuti `py_compile`, ciljane GUI/import testove i puni pytest paket.
5. Provjeriti pripremljene promjene kroz GitNexus, napraviti merge commit i
   osvježiti indeks ako je zastario.

## Šta NE dirati

- Poslovnu logiku jedinstvenog import workflow-a iz `services.import_workflow`.
- Assembly/Master-list legacy fallback.
- DB putanje, migracije i QThread stabilnosne popravke sa `windows`.
- Namjerne razlike između root i `dist_client` fajlova.
- Ranije nepraćene korisničke fajlove u radnom stablu.

## Konflikti

Jedini tekstualni konflikt bio je u `docs/CONTEXT.md`: `windows` je sadržao
sekcije §35–53, a grana redizajna zasebne sekcije označene §31–33. Važeća su
oba izvora; sadržaj redizajna je sačuvan i prenumerisan u §54–56. Korisnička
potvrda nije potrebna jer se ne mijenja značenje nijedne odluke.
