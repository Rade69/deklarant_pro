# Runtime logging u Knowledge Base servisima

## Cilj

Zamijeniti produkcione emoji `print()` pozive strukturisanim loggerom da Windows
cp1252 konzola ne može srušiti runtime i da greške ostanu dijagnostički vidljive.

## Pogođeno

Početni GitNexus impact za `KnowledgeBaseService`: MEDIUM, 17 zavisnih simbola,
bez evidentiranih procesa. Završni `detect_changes`: HIGH, 10 procesa, jer je
pomjeranje linija mapirano i na neizmijenjene metode `get_tariff_descriptions` i
`list_documents`. `pretrazi_dokumente`: LOW, 7 simbola i 2 chat procesa.

## Plan

1. Dodati module logger u dva root servisa.
2. Mirrorati identične izmjene u `dist_client`.
3. Dodati testove za DB-error i Groq rerank fallback.
4. Pokrenuti ciljane i pune testove.
5. Potvrditi root/dist identičnost i GitNexus obuhvat prije commita.

## Šta NE dirati

- SQL upite i transakcije
- BM25 rangiranje i sadržaj rezultata
- Groq reranking i njegov fallback
- API potpise i izuzetke
- demo `__main__` ispise u dijalozima i servisnim test helperima

## Konflikti

Početni simbolski impact je MEDIUM, a završni diff impact HIGH. HIGH se tretira
kao važeći za commit gate, dok je razlika objašnjena mapiranjem pomjerenih linija.
Korisnička potvrda nije potrebna jer nema promjene funkcionalnog ponašanja, ali
test gate i pregled obuhvata su obavezni.

## Tip promjene

Safety patch / observability.

## Prihvatljiv ishod (scope lock)

Identični rezultati i fallbackovi; jedina vidljiva promjena je da dijagnostika
ide kroz Python logging umjesto direktnog konzolnog ispisa.

## Nivo dozvole

Mandatory review i puni test gate; bez automatskog spajanja van aktivne grane.
