from __future__ import annotations

import re
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


_NUM_RE = re.compile(r"^-?\d+([.,]\d+)?$")
_DATE_RE = re.compile(r"^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}$")  # 01.12.2025 / 1-12-25


def _strip_ns(tag: str) -> str:
    # ElementTree namespace format: "{ns}Tag"
    return tag.split("}", 1)[1] if "}" in tag else tag


def _infer_type(samples: list[str]) -> str:
    """
    Vrlo jednostavna inferencija tipa na osnovu viđenih vrijednosti.
    Tipovi: string | int | decimal | date | code
    """
    vals = [s.strip() for s in samples if (s or "").strip()]
    if not vals:
        return "string"

    # date
    if all(_DATE_RE.match(v) for v in vals):
        return "date"

    # numeric
    if all(_NUM_RE.match(v.replace(",", ".")) for v in vals):
        # int vs decimal
        # normalize and check for decimal separator
        def _is_decimal(s: str) -> bool:
            s = s.strip()
            if not s:
                return False
            return "." in s or "," in s

        has_decimal = any(_is_decimal(v) and ("." in v or "," in v) for v in vals)
        if has_decimal:
            return "decimal"
        return "int"

    # code (kratko, uppercase, digits)
    if all(len(v) <= 6 and re.match(r"^[A-Z0-9]+$", v) for v in vals):
        return "code"

    return "string"


# Note: this parser strips namespace prefixes when collecting paths via
# `_strip_ns`. ElementTree lookups using explicit tag names without namespace
# will miss values if the XML uses namespace-qualified tags and the caller
# attempts direct `.find()` with namespaced paths. The current approach
# collects and normalizes all paths (without namespaces) into flat maps
# via `_collect_paths`, which is safe for template generation. If you need
# to perform namespace-aware queries, pass a namespace map to ElementTree
# find methods or extend the helpers here.


def _collect_paths(elem: ET.Element, prefix: str, out: dict[str, list[str]]) -> None:
    tag = _strip_ns(elem.tag)
    path = f"{prefix}/{tag}"

    # attributes
    for k, v in elem.attrib.items():
        out.setdefault(f"{path}[@{k}]", []).append(str(v))

    # text
    text = (elem.text or "").strip()
    if text:
        out.setdefault(path, []).append(text)

    for child in list(elem):
        _collect_paths(child, path, out)


@dataclass
class AsycudaDocument:
    """
    Reprezentacija XML-a u neutralnom obliku:
    - header: flat dict xpath->value (prva vrijednost ako ih ima više)
    - items: list of flat dict xpath->value za svaku stavku (Item)
    """

    header: dict[str, str]
    items: list[dict[str, str]]


def read_asycuda_xml(xml_path: str) -> AsycudaDocument:
    """
    Parsira ASYCUDA XML i vraća neutralnu strukturu.

    header: svi čvorovi osim onih ispod /ASYCUDA/Item
    items: svaki <Item> se parsira u svoj flat dict (path->value) s prefixom /Item/...
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    root_tag = _strip_ns(root.tag)

    if root_tag != "ASYCUDA":
        raise ValueError(f"Očekivan root <ASYCUDA>, dobijen <{root_tag}>")

    # header paths (iz cijelog dokumenta, ali kasnije filtriramo Item)
    all_paths: dict[str, list[str]] = {}
    _collect_paths(root, "", all_paths)

    header: dict[str, str] = {}
    for path, values in all_paths.items():
        # filtriraj sve što je ispod /ASYCUDA/Item/...
        if path.startswith("/ASYCUDA/Item/") or path == "/ASYCUDA/Item":
            continue
        header[path] = values[0] if values else ""

    # items
    items: list[dict[str, str]] = []
    for item_elem in root.findall("Item"):
        item_paths: dict[str, list[str]] = {}
        _collect_paths(item_elem, "", item_paths)  # kreće sa /Item/...
        flat: dict[str, str] = {}
        for p, vals in item_paths.items():
            flat[p] = vals[0] if vals else ""
        items.append(flat)

    return AsycudaDocument(header=header, items=items)


def build_template_from_xml_files(xml_paths: list[str]) -> dict[str, Any]:
    """
    Prođe kroz više XML fajlova i napravi template:
    - header_fields: xpath -> {type, samples_count}
    - item_fields: xpath -> {type, samples_count}
    """
    header_samples: dict[str, list[str]] = {}
    item_samples: dict[str, list[str]] = {}

    for path in xml_paths:
        doc = read_asycuda_xml(path)

        for k, v in doc.header.items():
            header_samples.setdefault(k, []).append(v)

        for item in doc.items:
            for k, v in item.items():
                item_samples.setdefault(k, []).append(v)

    header_fields = {
        k: {
            "type": _infer_type(vs),
            "samples_count": len([x for x in vs if (x or "").strip()]),
        }
        for k, vs in sorted(header_samples.items(), key=lambda kv: kv[0])
    }
    item_fields = {
        k: {
            "type": _infer_type(vs),
            "samples_count": len([x for x in vs if (x or "").strip()]),
        }
        for k, vs in sorted(item_samples.items(), key=lambda kv: kv[0])
    }

    return {
        "template_id": "asycuda_autogenerated",
        "version": 1,
        "root": "/ASYCUDA",
        "header_fields": header_fields,
        "repeating_sections": {
            "items": {
                "node": "/ASYCUDA/Item",
                "fields": item_fields,
            }
        },
        "notes": "Autogenerisano iz XML uzoraka. Ručno uredi mapiranje na UI polja.",
    }


def write_xml_stub(template: dict[str, Any], data: dict[str, Any]) -> str:
    """
    Namjerno je STUB: daje validan XML skeleton.
    U sljedećem koraku, kad potvrdimo template mapiranje, ovo će popuniti stvarne node-ove.
    """
    root = ET.Element("ASYCUDA")
    meta = ET.SubElement(root, "GeneratedBy")
    meta.text = "ASYCUDA Pro Modern (stub exporter)"

    ET.SubElement(root, "Info").text = (
        "Exporter još nije implementiran. Template + data su spremni."
    )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
