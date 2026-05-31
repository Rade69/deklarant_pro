# Agent status race fix for Blagic batch

## Problem

Pri agentskom uvozu nove Blagic-Loren posiljke iz:

`najavauvoza/LOREN/fwrauniipakingliste`

log je pokazivao da PDF parser vrati stavke, ali dio fajlova ostane u statusu `Processing`:

- `268VP-2026 SRETO BLAGIC.pdf -> Processing, lines=21`
- `267VP-2026 SRETO BLAGIC.pdf -> Processing, lines=22`
- slicno za jos nekoliko parova

Zbog toga `_on_all_completed()` broji samo fajlove sa statusom `Completed`, pa je draft dobio samo 9 stavki umjesto svih kombinovanih Blagic stavki.

## Uzrok

Parser i kombinovanje nisu bili glavni problem. Direktna reprodukcija `ProcessingWorker` toka dala je:

- `7 Completed`
- `7 Skipped`
- `71` ukupno uvezenih stavki

Problem je status race u GUI sloju: zakasnjeli `file_started` signal moze pozvati `_on_file_started()` nakon sto je worker vec postavio terminalni status (`Completed`, `Skipped`, `Error`). Tada tabela i isti `FileItem` objekat mogu biti vraceni na `Processing`, pa `_on_all_completed()` preskace validne stavke.

## Rjesenje

U `AgentController._on_file_started()` dodata je zastita:

- ako je fajl vec `Completed`, `Skipped` ili `Error`,
- ignorise se zakasnjeli start signal,
- status se ne vraca na `Processing`.

## Verifikacija

Pokrenuto:

```bash
python -m pytest tests/unit/test_blagic_loren_agent_import.py tests/unit/test_import_validator.py -q
```

Rezultat:

```text
27 passed
```

Dodatna reprodukcija agentskog batch-a:

```text
completed 7 skipped 7 lines 71
```

Izolovana provjera statusa:

```text
Completed False
```

To znaci da `_on_file_started()` nije pokusao da vec zavrsen fajl vrati na `Processing`.

## Napomena

U radnom stablu postoje nevezane izmjene/debug ispisi u `agent_controller.py`, `processing_worker.py`, validatoru i dokumentaciji. Ovaj commit treba obuhvatiti samo status guard i ovaj report.
