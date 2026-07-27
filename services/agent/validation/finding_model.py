"""
Jedinstveni validacioni ugovor — ValidationFinding i ValidationSummary.

Plan §7.2: svi validatori vraćaju nalaze koji se mogu agregirati, testirati
i prikazati bez gubitka značenja. Adapteri iz §13 prevode postojeće tipove
u ovaj model — ne prepisuju postojeće validatore.

Inventar kolizija imena (Faza -1.D):
  - ValidationResult postoji na 2 mjesta → adapteri koriste alias
  - ValidationError postoji na 5 mjesta → adapteri koriste alias
"""

from dataclasses import dataclass, field


# ── Katalog kodova nalaza (§7.2) ──────────────────────────────────────────

class FindingCode:
    """Stabilni kodovi za svaki tip nalaza. Koriste se za testiranje i metrike."""

    # Tarife
    MISSING_TARIFF = "MISSING_TARIFF"
    INVALID_TARIFF_FORMAT = "INVALID_TARIFF_FORMAT"
    TARIFF_NOT_FOUND = "TARIFF_NOT_FOUND"
    UNCONFIRMED_TARIFF = "UNCONFIRMED_TARIFF"

    # Porijeklo
    MISSING_ORIGIN = "MISSING_ORIGIN"
    UNCONFIRMED_ORIGIN = "UNCONFIRMED_ORIGIN"

    # Povlastice
    UNCONFIRMED_PREFERENCE = "UNCONFIRMED_PREFERENCE"
    PREFERENCE_WITHOUT_EVIDENCE = "PREFERENCE_WITHOUT_EVIDENCE"

    # Vrijednosti
    MISSING_AMOUNT = "MISSING_AMOUNT"
    INVALID_QUANTITY = "INVALID_QUANTITY"

    # Težine
    INVALID_WEIGHT = "INVALID_WEIGHT"
    GROSS_LESS_THAN_NET = "GROSS_LESS_THAN_NET"
    WEIGHT_TOTAL_MISMATCH = "WEIGHT_TOTAL_MISMATCH"

    # Faktura
    INVOICE_TOTAL_MISMATCH = "INVOICE_TOTAL_MISMATCH"
    DUPLICATE_INVOICE_LINE = "DUPLICATE_INVOICE_LINE"

    # Naimenovanja
    MISSING_PACKAGE = "MISSING_PACKAGE"
    INVALID_PROCEDURE = "INVALID_PROCEDURE"
    MISSING_STATISTICAL_VALUE = "MISSING_STATISTICAL_VALUE"
    INVALID_RUB31 = "INVALID_RUB31"
    ITEM_GROUPING_MISMATCH = "ITEM_GROUPING_MISMATCH"
    ASYCUDA_ITEM_LIMIT = "ASYCUDA_ITEM_LIMIT"

    # Zaglavlje / međutabno
    HEADER_REQUIRED_FIELD = "HEADER_REQUIRED_FIELD"
    DOCUMENT_INCONSISTENCY = "DOCUMENT_INCONSISTENCY"
    CROSS_TAB_MISMATCH = "CROSS_TAB_MISMATCH"

    # XML
    XML_PREFLIGHT_BLOCKED = "XML_PREFLIGHT_BLOCKED"
    REQUIRED_CHECK_FAILED = "REQUIRED_CHECK_FAILED"


class FindingSeverity:
    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


# ── Modeli ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ValidationFinding:
    """Jedan validacioni nalaz — stabilan, testabilan, bez UI zavisnosti.

    Plan §7.2: svaki nalaz ima stabilan code, tačnu lokaciju, dokaz bez
    osjetljivih podataka, izvor provjere, eksplicitnu blokirajuću prirodu
    i prijedlog sljedeće akcije.
    """
    severity: str          # FindingSeverity: BLOCKING, WARNING, INFO
    code: str              # FindingCode — stabilan za testove i metrike
    target: str            # invoice, items, header, declaration, xml
    location: str          # "stavka 5", "naimenovanje 3", "zaglavlje Rb.24"
    message: str           # Ljudski čitljiva poruka na srpskom
    evidence: dict = field(default_factory=dict)   # Dokaz bez osjetljivih podataka
    source: str = ""       # Odakle dolazi nalaz (npr. "FakturaItemValidator")
    auto_fixable: bool = False
    suggested_action: str = ""
    blocking: bool = False  # True = ne može se nastaviti workflow

    def __post_init__(self):
        # Automatski postavi blocking na osnovu severity
        if self.severity == FindingSeverity.BLOCKING and not self.blocking:
            object.__setattr__(self, "blocking", True)


@dataclass
class ValidationSummary:
    """Agregirani rezultat svih provjera za jedan target.

    Plan §7.3: ready=True znači samo da su sve obavezne provjere izvršene
    i da nema blokada. Nije sinonim za „nema praznih polja".
    """
    target: str
    checked_count: int = 0
    findings: list[ValidationFinding] = field(default_factory=list)
    blocking_count: int = 0
    warning_count: int = 0
    ready: bool = False
    draft_revision: int = 0         # revision drafta na kojem je provjera rađena
    checks_run: tuple[str, ...] = ()
    checks_skipped: tuple[str, ...] = ()

    @property
    def has_blocking(self) -> bool:
        return self.blocking_count > 0

    @property
    def has_warnings(self) -> bool:
        return self.warning_count > 0

    @staticmethod
    def from_findings(target: str, findings: list[ValidationFinding],
                      draft_revision: int = 0) -> "ValidationSummary":
        """Kreiraj summary iz liste nalaza."""
        blocking = sum(1 for f in findings if f.blocking)
        warnings = sum(1 for f in findings if f.severity == FindingSeverity.WARNING)
        return ValidationSummary(
            target=target,
            checked_count=len(findings),
            findings=findings,
            blocking_count=blocking,
            warning_count=warnings,
            ready=blocking == 0,
            draft_revision=draft_revision,
        )
