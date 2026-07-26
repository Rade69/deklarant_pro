"""
Lokalna pravila za klasifikaciju korisničke namjere.

Plan §12: "Lokalna pravila samo za visoko pouzdane, nedvosmislene obrasce."
Koriste se PRIJE LLM Tool Use-a. Samo ono što je izvjesno >95%.

Pravila su izvučena iz characterization fixture-a (Faza 0) i kanonske
matrice (plan §9.1). Svako pravilo ima test.
"""

from services.agent.chat.intent_model import (
    AgentIntent,
    IntentAction,
    IntentSource,
    IntentTarget,
)

# ── Akcioni keyword setovi ─────────────────────────────────────────────────

_SHOW_KEYWORDS = frozenset({
    "prikaži", "prikazi", "pokaži", "pokazi",
    "šta ima", "sta ima", "šta je učitano", "sta je ucitano",
    "pogledaj",
})

_VALIDATE_KEYWORDS = frozenset({
    "provjeri", "validiraj", "validiraj",
    "pregledaj",  # SEMA: "pregledaj" + poslovni objekat = VALIDATE (plan §9.1)
    "da li su", "jesu li", "da li je",
    "šta fali", "sta fali", "nedostaje",
    "ispravn", "grešk", "gresk", "problem",
})

_ANALYZE_KEYWORDS = frozenset({
    "analiziraj", "uporedi", "istraži", "istrazi",
})

_PROPOSE_KEYWORDS = frozenset({
    "predloži", "predlozi", "sugeriši", "sugerisi",
})

_MUTATE_KEYWORDS = frozenset({
    "upiši", "upisi", "ispravi", "primijeni", "primijeni",
    "promijeni", "promeni", "postavi",
})

_WORKFLOW_KEYWORDS = frozenset({
    "pripremi", "završi", "zavrsi", "nastavi",
})

_EXPORT_KEYWORDS = frozenset({
    "izvezi", "eksportuj", "eksportiraj", "izvoz",
})

_CONFIRM_KEYWORDS = frozenset({
    "da", "odobri", "potvrdi", "yes", "ok", "u redu", "slažem se",
})

_CANCEL_KEYWORDS = frozenset({
    "ne", "odustani", "cancel", "no", "storno", "otkaži", "otkazi",
})

# Negacijski markeri — poništavaju VALIDATE i vraćaju na SHOW
_NEGATION_MARKERS = ("samo ", "samo prikaži", "samo pokaži", "let me see",
                     "samo prikazi", "samo pokazi", "self explanatory")


# ── Target keyword setovi ──────────────────────────────────────────────────

_TARGET_FACTURA = frozenset({"faktura", "fakturi", "fakture", "fakturu",
                             "tab faktura", "tabu faktura"})

_TARGET_NAIMENOVANJA = frozenset({"naimenov", "naim", "naimenovanja",
                                  "naimenovanje", "naimenovanju"})

_TARGET_TARIFE = frozenset({"tarif", "tarife", "tarifa", "tarifni"})

_TARGET_ORIGIN = frozenset({"porijekl", "porekl", "zemlj", "origin"})

_TARGET_ZAGLAVLJE = frozenset({"zaglav"})

_TARGET_DEKLARACIJA = frozenset({"deklaracij", "cijela", "sve", "kompletn"})

_TARGET_XML = frozenset({"xml", "asycuda", "izvoz"})


# ── Pravila ────────────────────────────────────────────────────────────────


def classify_action(msg: str) -> tuple[IntentAction, float]:
    """Odredi akciju iz poruke (čisto lokalno pravilo)."""
    msg_lower = msg.lower().strip()

    # Negacija — poništava VALIDATE
    has_negation = any(n in msg_lower for n in _NEGATION_MARKERS)

    # Potvrda / otkazivanje
    if msg_lower in _CONFIRM_KEYWORDS:
        return IntentAction.CONFIRM, 1.0
    if msg_lower in _CANCEL_KEYWORDS:
        return IntentAction.CANCEL, 1.0

    # Workflow
    if any(kw in msg_lower for kw in _WORKFLOW_KEYWORDS):
        return IntentAction.RUN_WORKFLOW, 0.9

    # Export
    if any(kw in msg_lower for kw in _EXPORT_KEYWORDS):
        return IntentAction.EXPORT, 0.95

    # Mutacija
    if any(kw in msg_lower for kw in _MUTATE_KEYWORDS):
        return IntentAction.REQUEST_CHANGE, 0.85

    # Analiza
    if any(kw in msg_lower for kw in _ANALYZE_KEYWORDS):
        return IntentAction.ANALYZE, 0.85

    # Prijedlog
    if any(kw in msg_lower for kw in _PROPOSE_KEYWORDS):
        return IntentAction.PROPOSE, 0.85

    # Provjera — "pregledaj" + poslovni objekat = VALIDATE (plan §9.1)
    # ALI: negacija ("samo prikaži") obara na SHOW
    has_validate = any(kw in msg_lower for kw in _VALIDATE_KEYWORDS)
    has_show = any(kw in msg_lower for kw in _SHOW_KEYWORDS)

    if has_validate and not has_negation:
        # "pregledaj" + poslovni objekat = VALIDATE
        # "pregledaj" bez poslovnog objekta → SHOW (isključivo "samo prikaži" značenje)
        if any(kw in msg_lower for kw in _VALIDATE_KEYWORDS if kw != "pregledaj"):
            return IntentAction.VALIDATE, 0.88
        # Samo "pregledaj" — provjeri da li postoji poslovni objekat
        if has_show:  # ima i "prikaži" etc. — klasičan SHOW
            return IntentAction.SHOW, 0.9
        # "pregledaj" je jedini akcioni keyword — vidi target
        return IntentAction.VALIDATE, 0.75  # niža confidence jer je "pregledaj" dvosmislen

    if has_show:
        return IntentAction.SHOW, 0.9

    # "provjeri" etc. bez target keyword-a — i dalje VALIDATE (cijela aplikacija)
    if any(kw in msg_lower for kw in ("provjeri", "validiraj", "validiraj",
                                       "da li su", "šta fali", "sta fali")):
        return IntentAction.VALIDATE, 0.8

    return IntentAction.OTHER, 0.0


def classify_target(msg: str) -> tuple[IntentTarget, float]:
    """Odredi metu iz poruke."""
    msg_lower = msg.lower().strip()

    if any(kw in msg_lower for kw in _TARGET_NAIMENOVANJA):
        return IntentTarget.ITEMS, 0.9
    if any(kw in msg_lower for kw in _TARGET_FACTURA):
        return IntentTarget.INVOICE, 0.9
    if any(kw in msg_lower for kw in _TARGET_TARIFE):
        return IntentTarget.TARIFFS, 0.9
    if any(kw in msg_lower for kw in _TARGET_ORIGIN):
        return IntentTarget.ORIGIN, 0.8
    if any(kw in msg_lower for kw in _TARGET_ZAGLAVLJE):
        return IntentTarget.HEADER, 0.9
    if any(kw in msg_lower for kw in _TARGET_XML):
        return IntentTarget.XML, 0.9
    if any(kw in msg_lower for kw in _TARGET_DEKLARACIJA):
        return IntentTarget.DECLARATION, 0.8

    return IntentTarget.APPLICATION, 0.7


def extract_ordinal(msg: str) -> int | None:
    """Pokušaj izvući broj reda/stavke iz poruke."""
    import re
    # "stavka 17", "naimenovanje 5", "red 3", "rb. 10"
    m = re.search(r'\b(?:stavk[aeu]|naimenovanj[aeu]|red|rb\.?)\s*(\d+)', msg, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # "stavku 22" (akuzativ)
    m = re.search(r'stavku\s+(\d+)', msg, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def apply_rules(message: str) -> AgentIntent | None:
    """Primijeni sva lokalna pravila na poruku.

    Vraća AgentIntent ako su pravila dovoljno pouzdana (>0.85)
    ili None ako treba LLM Tool Use.
    """
    if not message or not message.strip():
        return None

    msg = message.strip()
    action, action_conf = classify_action(msg)
    target, target_conf = classify_target(msg)
    ordinal = extract_ordinal(msg)

    confidence = min(action_conf, target_conf)

    # Ako je akcija OTHER ili confidence prenizak, prepusti LLM-u
    if action == IntentAction.OTHER or confidence < 0.75:
        return None

    # Ako je akcija CONFIRM/CANCEL, nema targeta
    if action in (IntentAction.CONFIRM, IntentAction.CANCEL):
        return AgentIntent(
            action=action,
            target=IntentTarget.APPLICATION,
            source=IntentSource.LOCAL,
            confidence=confidence,
        )

    # Specifičan red ako postoji ordinal
    if ordinal is not None:
        return AgentIntent(
            action=action,
            target=IntentTarget.SPECIFIC_ROW,
            ordinals=(ordinal,),
            scope=f"row:{ordinal}",
            source=IntentSource.LOCAL,
            confidence=confidence,
        )

    return AgentIntent(
        action=action,
        target=target,
        source=IntentSource.LOCAL,
        confidence=confidence,
    )
