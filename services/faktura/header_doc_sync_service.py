"""
Header Document Sync Service — sinhronizacija PE i inspekcijskih dokumenata u zaglavlje
"""

_PE_DOC_CODES = {"PE1", "PE2", "PE3"}


def _pe_doc_code(value: str) -> str:
    code = (value or "").strip().split(" ", 1)[0].upper()
    return code if code in _PE_DOC_CODES else ""


def collect_pe_docs_from_items(items) -> list[tuple[str, str]]:
    """Sakupi jedinstvene (sifra, broj) PE1/PE2/PE3 parove iz naimenovanja."""
    pe_entries: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        doc4 = (getattr(item, 'attached_document4', '') or '').strip()
        if not doc4:
            continue
        parts = doc4.split(' ', 1)
        sifra = parts[0].strip()
        broj = parts[1].strip() if len(parts) > 1 else ''
        if sifra in _PE_DOC_CODES:
            key = (sifra, broj)
            if key not in seen:
                seen.add(key)
                pe_entries.append(key)
    return pe_entries


def build_pe_attached_documents(pe_entries: list[tuple[str, str]]) -> list:
    """Kreira AttachedDocument objekte za PE1/PE2/PE3 unose."""
    from core.draft.draft import AttachedDocument

    naziv_map = {
        "PE1": "EUR.1 obrazac",
        "PE2": "Izjava na fakturi",
        "PE3": "Izjava ovlaštenog izvoznika",
    }
    result = []
    for sifra, broj in pe_entries:
        naziv = naziv_map.get(sifra, f"Dokument {sifra}")
        result.append(AttachedDocument(
            code=sifra,
            name=naziv,
            number=broj,
            from_rule=sifra == "PE1",
        ))
    return result


def collect_inspection_docs_from_items(items, existing_codes: set[str] | None = None) -> list:
    """Sakupi obavezne inspekcijske dokumente na osnovu tarifnih brojeva."""
    if existing_codes is None:
        existing_codes = set()

    try:
        from services.tariff_controls_service import get_tariff_controls_service
        svc = get_tariff_controls_service()
    except Exception:
        return []

    from core.draft.draft import AttachedDocument

    result = []
    seen = set(existing_codes)
    for item in items:
        tariff_code = (getattr(item, "tariff_code", "") or "").strip()
        if not tariff_code:
            continue
        try:
            docs = svc.get_required_docs(tariff_code)
        except Exception:
            continue
        for doc in docs:
            code = (doc.get("code") or "").strip()
            if not code or code in seen:
                continue
            result.append(AttachedDocument(
                code=code,
                name=doc.get("name", ""),
                number="",
                from_rule=False,
            ))
            seen.add(code)
    return result
