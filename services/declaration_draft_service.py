import json
import re
import xml.etree.ElementTree as ET
from dataclasses import fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.draft.draft import (
    AttachedDocument,
    DeclarationDraft,
    InvoiceLine,
    NaimenovanjeDraft,
    Party,
)


DRAFT_ROOT_TAG = "DeklarantProDraft"
DRAFT_VERSION = "1"


def _json_value(value: Any) -> Any:
    if is_dataclass(value):
        return {
            field_info.name: _json_value(getattr(value, field_info.name))
            for field_info in fields(value)
            if not field_info.name.startswith("_")
        }
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def serialize_draft(draft: DeclarationDraft) -> dict[str, Any]:
    return _json_value(draft)


def _dataclass_kwargs(cls, data: dict[str, Any]) -> dict[str, Any]:
    allowed = {field_info.name for field_info in fields(cls)}
    return {key: value for key, value in data.items() if key in allowed}


def _invoice_line(data: dict[str, Any]) -> InvoiceLine:
    values = _dataclass_kwargs(InvoiceLine, data)
    values["exporter"] = Party(**_dataclass_kwargs(Party, data.get("exporter", {})))
    values["importer"] = Party(**_dataclass_kwargs(Party, data.get("importer", {})))
    return InvoiceLine(**values)


def _naimenovanje(data: dict[str, Any]) -> NaimenovanjeDraft:
    values = _dataclass_kwargs(NaimenovanjeDraft, data)
    values["attached_documents"] = [
        AttachedDocument(**_dataclass_kwargs(AttachedDocument, document))
        for document in data.get("attached_documents", [])
    ]
    return NaimenovanjeDraft(**values)


def deserialize_draft(payload: dict[str, Any]) -> DeclarationDraft:
    draft = DeclarationDraft()
    for field_info in fields(DeclarationDraft):
        name = field_info.name
        if name.startswith("_") or name not in payload:
            continue
        value = payload[name]
        if name == "invoice_lines":
            value = [_invoice_line(item) for item in value]
        elif name == "items":
            value = [_naimenovanje(item) for item in value]
        elif name == "header_attached_documents":
            value = [
                AttachedDocument(**_dataclass_kwargs(AttachedDocument, item))
                for item in value
            ]
        elif name == "invoice_weights":
            value = {key: tuple(weights) for key, weights in value.items()}
        setattr(draft, name, value)
    return draft


def suggested_title(draft: DeclarationDraft) -> str:
    references = []
    for line in draft.invoice_lines:
        reference = str(line.invoice_number or "").strip()
        if reference and reference not in references:
            references.append(reference)
    if references:
        return "Deklaracija " + ", ".join(references[:3])
    if draft.ref_br.strip():
        return f"Deklaracija {draft.ref_br.strip()}"
    return f"Deklaracija {datetime.now():%d.%m.%Y. %H-%M}"


def suggested_filename(draft: DeclarationDraft) -> str:
    filename = re.sub(r"[^\w .-]+", "_", suggested_title(draft), flags=re.UNICODE)
    filename = filename.strip(" .") or "Deklaracija"
    return f"{filename}.xml"


def default_drafts_directory() -> Path:
    path = Path.home() / "Documents" / "Deklarant Pro" / "Nacrti"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = Path.home() / "Deklarant Pro" / "Nacrti"
        path.mkdir(parents=True, exist_ok=True)
    return path


def is_draft_file(path: str | Path) -> bool:
    try:
        return ET.parse(path).getroot().tag == DRAFT_ROOT_TAG
    except (ET.ParseError, OSError):
        return False


class DeclarationDraftService:
    def save(self, draft: DeclarationDraft, output_path: str | Path) -> Path:
        path = Path(output_path)
        if path.suffix.lower() != ".xml":
            path = path.with_suffix(".xml")
        path.parent.mkdir(parents=True, exist_ok=True)

        root = ET.Element(
            DRAFT_ROOT_TAG,
            version=DRAFT_VERSION,
            title=path.stem,
            saved_at=datetime.now().isoformat(timespec="seconds"),
        )
        payload = ET.SubElement(root, "Payload", encoding="json")
        payload.text = json.dumps(serialize_draft(draft), ensure_ascii=False)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return path

    def load(self, input_path: str | Path) -> DeclarationDraft:
        path = Path(input_path)
        root = ET.parse(path).getroot()
        if root.tag != DRAFT_ROOT_TAG:
            raise ValueError("Izabrani XML nije Deklarant Pro nacrt.")
        if root.get("version") != DRAFT_VERSION:
            raise ValueError("Verzija nacrta nije podržana.")
        payload = root.find("Payload")
        if payload is None or not payload.text:
            raise ValueError("Nacrt ne sadrži podatke deklaracije.")
        draft = deserialize_draft(json.loads(payload.text))
        draft._persistent_draft_path = str(path)
        draft.dirty = False
        return draft
