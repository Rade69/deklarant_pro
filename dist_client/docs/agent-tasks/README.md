# Agent Task Pack (Markdown)

Ovaj folder sluzi za orkestraciju vise coding agenata kroz male, jasno definisane `md` zadatke.

## Cilj

- Brze izvrsavanje kroz jeftinije agente.
- Kontrola kvaliteta kroz jasan scope i acceptance kriterije.
- Minimalan rizik regresija.

## Pravila rada

1. Agent radi samo po `Scope` i `Allowed Files`.
2. Bez refaktora van zadatka.
3. Nema rename/move fajlova osim ako je eksplicitno trazeno.
4. Svaki task mora imati dokaz verifikacije.
5. Ako je task blokiran, agent vraca status `BLOCKED` + razlog.

## Standardni format izlaza agenta

```
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI:
- path/...
STA JE URADJENO:
- ...
VERIFIKACIJA:
- komanda + rezultat
RIZICI:
- ...
```

## Workflow

1. Otvori `style-refactor/PHASE_PLAN.md`.
2. Izaberi sledeci `TASK-xxx.md`.
3. Dodijeli agentu 1 task (ili vise paralelno ako je write scope disjunktan).
4. Pregledaj diff i verifikaciju.
5. Tek onda merge/commit.
