# Faza −1.A — draft.revision na DeclarationDraft

**Plan**: `docs/agent/AGENT_V2_IMPLEMENTACIONI_PLAN.md` §10 −1.A
**Datum**: 2026-07-26
**Agent**: Pi

---

## Cilj

Dodati `revision: int` i `fingerprint` property na `DeclarationDraft` da bi
Faza 6 (XML readiness) i §7.3 (draft_revision u ValidationSummary) mogli
detektovati promjenu drafta poslije validacije.

## GitNexus impact — CRITICAL

- Simbol: `Class:core/draft/draft.py:DeclarationDraft`
- Direktni pozivaoci: **142**
- Ukupno pogođeno: **278 simbola**
- Procesi pogođeni: **0** (ali svi import tokovi koriste draft)

## Prihvatljiv ishod (scope lock)

- `revision` je **monotoni brojač** (int, počinje od 0)
- Inkrementira se samo na **izmjeni poslovnih polja** (invoice_lines, items, zaglavlje)
- **Ne inkrementira se** na čitanju, na `mark_dirty()`, na postavljanju `dirty` flag-a
- `fingerprint` je `hash(revision)` — brz, ne reflektuje sadržaj (nije kriptografski)
- **Nije** dio ASYCUDA XML izlaza (ne serijalizuje se)
- Postojeći `mark_dirty()` i `_notify_data_change()` **ostaju netaknuti**
- Svi postojeći testovi moraju proći bez izmjene

## Plan izmjena

1. Dodati `revision: int = 0` u `DeclarationDraft` dataclass
2. Dodati `@property def fingerprint(self) -> int: return hash(self.revision)`
3. Overridati `__setattr__` da inkrementira revision na izmjenama `invoice_lines`, `items` i svih zaglavlje polja
4. **ALT**: Umjesto `__setattr__`, koristiti jednostavniji pristup — `bump_revision()` metod koji se poziva eksplicitno u postojećim `mark_dirty()` mjestima

## Predloženi pristup

Opcija ALT je sigurnija — dodati `bump_revision()` i pozvati ga u `mark_dirty()`.
Ovo ne mijenja postojeće ponašanje (samo dodaje brojač) i ne dira `__setattr__`
(može izazvati rekurziju ili usporiti sve operacije nad draftom).

```python
revision: int = field(default=0, init=False, repr=False)

def bump_revision(self) -> None:
    self.revision += 1

@property
def fingerprint(self) -> int:
    return hash(self.revision)
```

Izmjena `mark_dirty()`:
```python
def mark_dirty(self) -> None:
    self.dirty = True
    self.bump_revision()
```

## Šta NE dirati

- `_data_change_callbacks` — ostaje nepromijenjen
- `_persistent_draft_path` — ostaje nepromijenjen
- `dirty` flag — ostaje nepromijenjen
- Serijalizacija (serialize/deserialize) — revision se ne serijalizuje
- XML builder — revision se ne izvozi
- Svi parseri/importeri — ne vide revision

## Rizik

- **Nizak** sa ALT pristupom: samo dodajemo brojač + poziv u `mark_dirty()`
- `mark_dirty()` se već poziva na ~20 mjesta — sva su testirana
- 278 pogođenih simbola su uglavnom čitaoci drafta (ne mjenjaju ga)
- Najvažniji test: `mark_dirty()` → `revision += 1`; `mark_dirty()` × 5 → `revision == 5`

## Testovi

- Novi `tests/unit/test_draft_revision.py`:
  - `test_revision_starts_at_zero`
  - `test_mark_dirty_increments_revision`
  - `test_multiple_mark_dirty_cumulative`
  - `test_fingerprint_changes_with_revision`
  - `test_read_operations_dont_increment`
  - `test_deserialized_draft_starts_at_zero`

## Nivo dozvole

- **Mandatory review** — CRITICAL rizik prema AGENTS.md proceduri
- Commit **tek nakon** što korisnik potvrdi pristup (ALT opcija)
