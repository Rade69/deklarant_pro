from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable, Sequence

from core.draft.draft import InvoiceLine, NaimenovanjeDraft


@dataclass(frozen=True)
class Rub31Result:
    description_of_goods: str
    commercial_description: str


_MAX_LINE = 55
_MAX_LINES = 4
_MAX_DESC = 280


def build_asycuda_rub31(
    item: NaimenovanjeDraft,
    invoice_lines: Sequence[InvoiceLine] | None = None,
    tariff_heading: str = "",
    max_description_chars: int = _MAX_DESC,
) -> Rub31Result:
    assigned_lines = _assigned_lines(item, invoice_lines or [])
    product_names = _product_names_from_invoice_lines(assigned_lines)
    invoice_text = _invoice_text_from_lines(assigned_lines)
    trade_parts, trade_invoice_text = _parse_trade_text(item.goods_trade_name or "")

    if not product_names:
        product_names = _product_names_from_trade_parts(trade_parts)
    if not invoice_text:
        invoice_text = trade_invoice_text

    description = _choose_tariff_description(
        item=item,
        tariff_heading=tariff_heading,
        product_names=product_names,
        trade_parts=trade_parts,
        max_chars=max_description_chars,
    )

    commercial_lines = _commercial_lines(
        description=description,
        product_names=product_names,
        trade_parts=trade_parts,
        invoice_text=invoice_text,
        max_chars=max_description_chars,
    )

    return Rub31Result(
        description_of_goods=description or ".",
        commercial_description="\n".join(commercial_lines) or ".",
    )


def normalize_tariff_text(text: str) -> str:
    return (text or "").replace("–", "-").replace("−", "-")


def is_generic_tariff_text(text: str) -> bool:
    normalized = re.sub(r"[^a-zA-ZčćžšđČĆŽŠĐ]", "", text or "").lower()
    return normalized in {"ostalo", "ostali", "ostale"}


def _assigned_lines(
    item: NaimenovanjeDraft,
    invoice_lines: Sequence[InvoiceLine],
) -> list[InvoiceLine]:
    ordinal_no = getattr(item, "ordinal_no", None)
    if ordinal_no is None:
        return []
    return [
        line for line in invoice_lines
        if getattr(line, "assigned_naimenovanje_ordinal", None) == ordinal_no
    ]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _key(text: str) -> str:
    return re.sub(r"[^a-zA-ZčćžšđČĆŽŠĐ0-9]+", " ", text or "").strip().casefold()


def _clip(text: str, limit: int = _MAX_LINE) -> str:
    text = _norm(text)
    if len(text) <= limit:
        return text
    return text[:limit - 3].rstrip() + "..."


def _looks_like_product(text: str) -> bool:
    text = _norm(text)
    if not text:
        return False
    if re.search(r"\d", text):
        return True
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
    return upper_ratio > 0.70 and len(text) <= 90


def _product_names_from_invoice_lines(lines: Sequence[InvoiceLine]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        name = _norm(getattr(line, "naziv_robe", "") or "")
        key = _key(name)
        if name and key not in seen:
            seen.add(key)
            result.append(name)
    return result


def _invoice_text_from_lines(lines: Sequence[InvoiceLine]) -> str:
    if not lines:
        return ""
    invoices: OrderedDict[str, list[str]] = OrderedDict()
    for line in lines:
        inv = getattr(line, "invoice_number", "") or "?"
        invoices.setdefault(inv, []).append(str(getattr(line, "line_no", "")))
    return "Faktura: " + ", ".join(
        f"{inv} (rb. {', '.join(rb_list)})" for inv, rb_list in invoices.items()
    )


def _parse_trade_text(raw: str) -> tuple[list[str], str]:
    parts: list[str] = []
    invoice_lines: list[str] = []
    for raw_line in (raw or "").splitlines():
        line = _norm(raw_line)
        if not line:
            continue
        faktura_pos = line.lower().find("faktura:")
        if faktura_pos >= 0:
            before = line[:faktura_pos].rstrip(" ,;")
            invoice_line = line[faktura_pos:].strip()
            if before:
                parts.extend(_split_description_parts(before))
            if invoice_line:
                invoice_lines.append(invoice_line)
        else:
            parts.extend(_split_description_parts(line))
    return _dedupe(parts), _clip(" ".join(invoice_lines), _MAX_LINE) if invoice_lines else ""


def _split_description_parts(text: str) -> list[str]:
    if ";" not in text:
        return [_norm(text)] if _norm(text) else []
    return [_norm(part.strip(" ,;")) for part in text.split(";") if _norm(part.strip(" ,;"))]


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _norm(value)
        key = _key(text)
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _candidate_is_product_text(candidate: str, product_names: Sequence[str]) -> bool:
    candidate_key = _key(candidate)
    product_keys = {_key(name) for name in product_names if name}
    if candidate_key in product_keys:
        return True
    parts = [_key(part.strip(" ,;")) for part in re.split(r"[;\n]+", candidate) if part.strip(" ,;")]
    return bool(parts) and all(part in product_keys for part in parts)


def _choose_tariff_description(
    item: NaimenovanjeDraft,
    tariff_heading: str,
    product_names: Sequence[str],
    trade_parts: Sequence[str],
    max_chars: int,
) -> str:
    candidates = [
        getattr(item, "tariff_description1", "") or "",
        getattr(item, "goods_description", "") or "",
        *_trade_description_candidates(trade_parts),
        getattr(item, "tariff_description2", "") or "",
        tariff_heading or "",
    ]
    normalized_candidates: list[str] = []
    for candidate in candidates:
        text = _norm(normalize_tariff_text(candidate))
        if not text:
            continue
        if _candidate_is_product_text(text, product_names):
            continue
        normalized_candidates.append(text)
        if not is_generic_tariff_text(text):
            return _clip(text, max_chars)
    return _clip(normalized_candidates[0], max_chars) if normalized_candidates else "."


def _trade_description_candidates(trade_parts: Sequence[str]) -> list[str]:
    result: list[str] = []
    for part in trade_parts:
        text = _norm(part)
        if text and not _looks_like_product(text):
            result.append(text)
    return result


def _product_names_from_trade_parts(trade_parts: Sequence[str]) -> list[str]:
    product_parts = [part for part in trade_parts if _looks_like_product(part)]
    return _dedupe(product_parts or trade_parts)


def _commercial_lines(
    description: str,
    product_names: Sequence[str],
    trade_parts: Sequence[str],
    invoice_text: str,
    max_chars: int,
) -> list[str]:
    content_parts = _dedupe([*trade_parts, *product_names])
    desc_key = _key(description)
    content_parts = [
        part for part in content_parts
        if _key(part) != desc_key and not is_generic_tariff_text(part)
    ]

    reserved = (1 if description else 0) + (1 if invoice_text else 0)
    available = max(1, _MAX_LINES - reserved)
    lines: list[str] = []

    if description:
        lines.append(_clip(description))

    if content_parts and available:
        if len(content_parts) <= available:
            lines.extend(_clip(part) for part in content_parts)
        elif available == 1:
            lines.append(_clip(", ".join(content_parts)))
        else:
            lines.extend(_clip(part) for part in content_parts[:available - 1])
            lines.append(_clip(", ".join(content_parts[available - 1:])))

    if invoice_text:
        lines.append(_clip(invoice_text))

    return _fit_lines(lines[:_MAX_LINES], max_chars)


def _fit_lines(lines: list[str], max_chars: int) -> list[str]:
    result = [line for line in lines if line]
    if len("\n".join(result)) <= max_chars:
        return result

    invoice_index = len(result) - 1 if result and result[-1].lower().startswith("faktura:") else None
    while len("\n".join(result)) > max_chars and len(result) > (2 if invoice_index is not None else 1):
        remove_index = (invoice_index - 1) if invoice_index is not None else len(result) - 1
        if remove_index <= 0:
            break
        result.pop(remove_index)
        if invoice_index is not None:
            invoice_index -= 1

    if len("\n".join(result)) <= max_chars or not result:
        return result

    suffix_len = len("\n".join(result[1:]))
    newline_len = 1 if len(result) > 1 else 0
    available = max(1, max_chars - suffix_len - newline_len)
    result[0] = _clip(result[0], available)
    return result
