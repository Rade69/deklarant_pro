"""
Renderer za validacione nalaze — Faza 9.

Plan §20/§21 (v2.1): standard odgovora validacije.
Ne ispisuje sve uredne redove, grupiše nalaze, razlikuje missing/unchecked/unavailable.
"""

from __future__ import annotations

from services.agent.validation.finding_model import (
    FindingSeverity,
    ValidationFinding,
    ValidationSummary,
)


def render_summary_html(summary: ValidationSummary, max_blocking: int = 10, max_warnings: int = 20) -> str:
    """Renderuj ValidationSummary kao HTML za Agent chat.

    Plan §20: standard odgovora — Zaključak / Provjereno / Kritične greške /
    Upozorenja / Šta nije provjereno / Sljedeći korak.
    """
    parts = []

    # Zaključak
    if summary.ready:
        parts.append("<b>✅ Spremno</b>")
    elif summary.has_blocking:
        parts.append(f"<b>❌ Blokirano — {summary.blocking_count} kritičnih problema</b>")
    else:
        parts.append(f"<b>⚠️ Upozorenja — {summary.warning_count} problema</b>")

    # Provjereno
    parts.append(f"Provjereno: {summary.checked_count} nalaza")
    if summary.checks_run:
        parts.append(f"Izvršene provjere: {', '.join(summary.checks_run)}")

    # Kritične greške
    blocking = [f for f in summary.findings if f.blocking]
    if blocking:
        parts.append(f"<br><b>🔴 Kritične greške ({min(len(blocking), max_blocking)}):</b>")
        for f in blocking[:max_blocking]:
            parts.append(f"  • {f.location}: {f.message}")
        if len(blocking) > max_blocking:
            parts.append(f"  ... i još {len(blocking) - max_blocking}")

    # Upozorenja
    warnings = [f for f in summary.findings if f.severity == FindingSeverity.WARNING and not f.blocking]
    if warnings:
        parts.append(f"<br><b>🟡 Upozorenja ({min(len(warnings), max_warnings)}):</b>")
        for f in warnings[:max_warnings]:
            parts.append(f"  • {f.location}: {f.message}")
        if len(warnings) > max_warnings:
            parts.append(f"  ... i još {len(warnings) - max_warnings}")

    # Šta nije provjereno
    if summary.checks_skipped:
        parts.append(f"<br>Preskočene provjere: {', '.join(summary.checks_skipped)}")

    # Sljedeći korak
    if summary.has_blocking:
        parts.append("<br><b>👉 Preporuka:</b> Ispravite kritične greške prije nastavka.")
    elif summary.has_warnings:
        parts.append("<br><b>👉 Preporuka:</b> Pregledajte upozorenja. Za XML izvoz pokrenite 'Provjeri spremnost za XML'.")
    else:
        parts.append("<br><b>👉 Spremno za sledeći korak.</b>")

    return "<br>".join(parts)


def render_summary_text(summary: ValidationSummary) -> str:
    """Renderuj kao plain text (za audit/log)."""
    status = "READY" if summary.ready else "BLOCKED" if summary.has_blocking else "WARNINGS"
    return (
        f"[{status}] {summary.target}: {summary.checked_count} checked, "
        f"{summary.blocking_count} blocking, {summary.warning_count} warnings"
    )
