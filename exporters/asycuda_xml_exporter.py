from __future__ import annotations

import re
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List


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


def write_xml_stub(template: dict[str, Any], data: dict[str, Any], format_type: str = "world") -> str:
    """
    Generiše XML skeleton za ASYCUDA World ili Pro format.
    
    Args:
        template: Template struktura
        data: Podaci za popunjavanje
        format_type: "world" ili "pro" (default: "world")
    
    Returns:
        XML string
    """
    if format_type.lower() == "pro":
        return _write_pro_xml_stub(template, data)
    else:
        return _write_world_xml_stub(template, data)

def _write_world_xml_stub(template: dict[str, Any], data: dict[str, Any]) -> str:
    """Generiše World format XML stub."""
    root = ET.Element("ASYCUDA")
    meta = ET.SubElement(root, "GeneratedBy")
    meta.text = "ASYCUDA Pro Modern (World format stub exporter)"

    ET.SubElement(root, "Info").text = (
        "World format exporter još nije implementiran. Template + data su spremni."
    )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

def _write_pro_xml_stub(template: dict[str, Any], data: dict[str, Any]) -> str:
    """Generiše Pro format XML stub."""
    # ASYCUDA Pro često koristi namespace
    ns = "http://www.asycuda.org/asycuda-pro"
    root = ET.Element(f"{{{ns}}}Declaration")
    
    # Dodaj namespace atribut
    root.set("xmlns", ns)
    
    # Osnovni podaci
    decl_number = ET.SubElement(root, f"{{{ns}}}DeclarationNumber")
    decl_number.text = data.get('broj_deklaracije', '')
    
    decl_date = ET.SubElement(root, f"{{{ns}}}DeclarationDate")
    decl_date.text = data.get('datum', '')
    
    decl_type = ET.SubElement(root, f"{{{ns}}}DeclarationType")
    decl_type.text = data.get('vrsta_deklaracije', 'IM')
    
    # Dodaj komentar
    comment = ET.Comment("ASYCUDA Pro format generisan od ASYCUDA Pro Modern aplikacije")
    root.insert(0, comment)
    
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

def export_to_pro_xml(draft_data: dict[str, Any], output_path: str) -> bool:
    """
    Eksportuje podatke u ASYCUDA Pro XML format.
    
    Args:
        draft_data: Podaci draft-a
        output_path: Putanja za čuvanje XML fajla
    
    Returns:
        True ako je uspešno, False inače
    """
    try:
        # Kreiraj Pro XML strukturu
        ns = "http://www.asycuda.org/asycuda-pro"
        root = ET.Element(f"{{{ns}}}Declaration")
        root.set("xmlns", ns)
        
        # Osnovni podaci
        if 'broj_deklaracije' in draft_data:
            decl_num = ET.SubElement(root, f"{{{ns}}}DeclarationNumber")
            decl_num.text = str(draft_data['broj_deklaracije'])
        
        if 'datum' in draft_data:
            decl_date = ET.SubElement(root, f"{{{ns}}}DeclarationDate")
            decl_date.text = str(draft_data['datum'])
        
        if 'vrsta_deklaracije' in draft_data:
            decl_type = ET.SubElement(root, f"{{{ns}}}DeclarationType")
            decl_type.text = str(draft_data['vrsta_deklaracije'])
        
        # Izvoznik
        if any(key.startswith('izvoznik') for key in draft_data.keys()):
            exporter = ET.SubElement(root, f"{{{ns}}}Exporter")
            
            if 'izvoznik_id' in draft_data:
                exp_id = ET.SubElement(exporter, f"{{{ns}}}ID")
                exp_id.text = str(draft_data['izvoznik_id'])
            
            if 'izvoznik_naziv' in draft_data:
                exp_name = ET.SubElement(exporter, f"{{{ns}}}Name")
                exp_name.text = str(draft_data['izvoznik_naziv'])
        
        # Stavke
        if 'items' in draft_data and draft_data['items']:
            goods_items = ET.SubElement(root, f"{{{ns}}}GoodsItems")
            for idx, item in enumerate(draft_data['items'][:10], 1):  # Ograniči na 10 za stub
                goods_item = ET.SubElement(goods_items, f"{{{ns}}}GoodsItem")
                
                item_num = ET.SubElement(goods_item, f"{{{ns}}}ItemNumber")
                item_num.text = str(idx)
                
                # Proveri da li je item dict ili objekat
                if isinstance(item, dict):
                    if 'naziv_robe' in item:
                        desc = ET.SubElement(goods_item, f"{{{ns}}}Description")
                        desc.text = str(item['naziv_robe'])
                elif hasattr(item, 'naziv_robe'):
                    desc = ET.SubElement(goods_item, f"{{{ns}}}Description")
                    desc.text = str(item.naziv_robe)
        
        # Snimi fajl
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        
        logger = logging.getLogger(__name__)
        logger.info(f"ASYCUDA Pro XML eksportovan: {output_path}")
        return True
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Greška pri eksportu Pro XML: {e}")
        return False

def batch_convert_xml(input_dir: str, output_dir: str, from_format: str = "world", to_format: str = "pro") -> Dict[str, Any]:
    """
    Batch konvertuje XML fajlove iz jednog formata u drugi.
    
    Args:
        input_dir: Direktorijum sa ulaznim XML fajlovima
        output_dir: Direktorijum za izlazne XML fajlove
        from_format: Izvorni format ("world" ili "pro")
        to_format: Ciljani format ("world" ili "pro")
    
    Returns:
        Statistika konverzije
    """
    import os
    from pathlib import Path
    import shutil
    
    logger = logging.getLogger(__name__)
    
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Kreiraj izlazni direktorijum ako ne postoji
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Pronađi sve XML fajlove
    xml_files = list(input_path.glob("*.xml"))
    stats['total'] = len(xml_files)
    
    for xml_file in xml_files:
        try:
            # Učitaj XML
            from .xml_importer import XMLImporter
            importer = XMLImporter()
            data = importer.import_file(xml_file, from_format)
            
            # Konvertuj podatke
            from .central_mapper import CentralMapper
            mapper = CentralMapper()
            
            if from_format == "world" and to_format == "pro":
                converted_data = mapper.convert_world_to_pro(data)
            elif from_format == "pro" and to_format == "world":
                converted_data = mapper.convert_pro_to_world(data)
            else:
                # Ako su isti formati, samo kopiraj
                converted_data = data
            
            # Eksportuj u novi format
            output_file = output_path / f"{xml_file.stem}_{to_format}.xml"
            
            if to_format == "pro":
                export_to_pro_xml(converted_data, str(output_file))
            else:
                # Za World format, kopiraj originalni XML
                shutil.copy2(xml_file, output_file)
            
            stats['success'] += 1
            
        except Exception as e:
            stats['failed'] += 1
            stats['errors'].append({
                'file': str(xml_file),
                'error': str(e)
            })
            logger.error(f"Greška pri konverziji {xml_file}: {e}")
    
    return stats
