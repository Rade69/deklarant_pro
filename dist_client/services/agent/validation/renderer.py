"""
Renderer za validacione nalaze — Faza 9.

Plan §20/§21 (v2.1): standard odgovora validacije.
Ne ispisuje sve uredne redove, grupiše nalaze, razlikuje missing/unchecked/unavailable.
"""

from __future__ import annotations

from html import escape

from services.agent.validation.finding_model import (
    FindingSeverity,
    ValidationFinding,
    ValidationSummary,
)


def render_summary_html(summary: ValidationSummary, max_blocking: int = 10, max_warnings: int = 20) -> str:
    """Renderuj ValidationSummary kao HTML za Agent chat.

    Plan §20: standard odgovora — Zaključak / Provjereno / Kritične greške /
    Upozorenja / Šta nije provjereno / Sljedeći korak.

    `location`/`message` se HTML-escape-uju — dolaze iz naziva robe i sličnih
    korisničkih podataka koji mogu sadržati '<'/'>' i pokvariti prikaz u chatu
    (npr. proizvod nazvan "Cijev <5mm>"). Ova funkcija je prije popravke
    (2026-07-27) postojala samo u izolovanim testovima — sad je prvi put
    stvarno povezana na chat izlaz, pa nedostajući escape postaje realan bug.
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
        parts.append(f"Izvršene provjere: {escape(', '.join(summary.checks_run))}")

    # Kritične greške
    blocking = [f for f in summary.findings if f.blocking]
    if blocking:
        parts.append(f"<br><b>🔴 Kritične greške ({min(len(blocking), max_blocking)}):</b>")
        for f in blocking[:max_blocking]:
            parts.append(f"  • {escape(f.location)}: {escape(f.message)}")
        if len(blocking) > max_blocking:
            parts.append(f"  ... i još {len(blocking) - max_blocking}")

    # Upozorenja
    warnings = [f for f in summary.findings if f.severity == FindingSeverity.WARNING and not f.blocking]
    if warnings:
        parts.append(f"<br><b>🟡 Upozorenja ({min(len(warnings), max_warnings)}):</b>")
        for f in warnings[:max_warnings]:
            parts.append(f"  • {escape(f.location)}: {escape(f.message)}")
        if len(warnings) > max_warnings:
            parts.append(f"  ... i još {len(warnings) - max_warnings}")

    # Šta nije provjereno
    if summary.checks_skipped:
        parts.append(f"<br>Preskočene provjere: {escape(', '.join(summary.checks_skipped))}")

    # Sljedeći korak
    if summary.has_blocking:
        parts.append("<br><b>👉 Preporuka:</b> Ispravite kritične greške prije nastavka.")
    elif summary.has_warnings:
        parts.append("<br><b>👉 Preporuka:</b> Pregledajte upozorenja. Za XML izvoz pokrenite 'Provjeri spremnost za XML'.")
    else:
        parts.append("<br><b>👉 Spremno za sledeći korak.</b>")

    return "<br>".join(parts)


def render_xml_readiness_html(result) -> str:
    """Renderuj XmlReadinessResult (agregat nekoliko servisa, ne ValidationSummary).

    Zajednička implementacija za _dispatch_provjeri (target=xml),
    xml_workflow_service._izvezi_xml i declaration_workflow_service —
    prije popravke je ovo bilo duplicirano inline u chat_intent_handler.py.
    """
    icon = {"READY": "✅", "READY_WITH_WARNINGS": "⚠️", "BLOCKED": "❌"}
    status = result.status.value
    parts = [f"{icon.get(status, 'ℹ️')} <b>Spremnost za XML izvoz: {escape(status)}</b>"]
    parts.append(f"<br><small>Provjereno: {escape(', '.join(result.checks_run) or '—')}</small>")
    if result.checks_skipped:
        parts.append(f"<br><small>⚠️ Preskočeno: {escape(', '.join(result.checks_skipped))}</small>")
    if result.blocking_count:
        parts.append(f"<br><b>Blokade ({result.blocking_count}):</b>")
        for finding in [f for f in result.all_findings if f.blocking][:15]:
            parts.append(f"<br>• {escape(finding.message)} <small>({escape(finding.location)})</small>")
    if result.warning_count:
        parts.append(f"<br><small>Upozorenja: {result.warning_count}</small>")
    return "".join(parts)


def render_summary_text(summary: ValidationSummary) -> str:
    """Renderuj kao plain text (za audit/log)."""
    status = "READY" if summary.ready else "BLOCKED" if summary.has_blocking else "WARNINGS"
    return (
        f"[{status}] {summary.target}: {summary.checked_count} checked, "
        f"{summary.blocking_count} blocking, {summary.warning_count} warnings"
    )
