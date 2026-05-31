# importers/imamoglu_excel_importer.py

"""
IMAMOGLU Excel Importer

Podržava dva Excel formata koje IMAMOGLU (Turska) šalje:

1. PACKING LIST (xlsx) — sheet "ÇEKİ LİSTESİ"
   Header u redu 6: NO | CODE | DESCRIPTION | QUANTITY | UNIT | ... | NET WEIGHT | GROSS WEIGHT

2. Mal tanımları (xls) — Turkish ERP export, sheet "Sayfa1"
   Header u redu 1: Türü | Statü | Kodu | Açıklaması | ... | Miktar | Birim |
                    Dövizli Birim Fiyat | Döviz | Dövizli Tutar | ... | GTIP Kodu | Menşei(Kamu)
"""

import logging
import re
from typing import List, Optional, Tuple, Dict
from pathlib import Path

import openpyxl

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult

logger = logging.getLogger("deklarant_pro.import.imamoglu_excel")


# ─── DETEKCIJA ───────────────────────────────────────────────────────────────

def detect_imamoglu_packing_list(filepath: str) -> bool:
    """
    Detektuje IMAMOGLU Packing List format (.xlsx).

    Kriteriji:
    - Extension .xlsx
    - Sheet ime sadrži 'ÇEK' ili 'PACKING' (case-insensitive)
    - Ili: header (pretrage u prvih 8 redova) sadrži CODE + DESCRIPTION + NET WEIGHT + GROSS WEIGHT
    """
    try:
        if not filepath.lower().endswith('.xlsx'):
            return False

        wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
        try:
            for sheet in wb.worksheets:
                name_upper = sheet.title.upper()

                # Detekcija po imenu sheet-a
                if 'ÇEK' in name_upper or 'PACKING' in name_upper:
                    logger.debug(f"IMAMOGLU Packing List — sheet name match: '{sheet.title}'")
                    return True

                # Detekcija po header-u (prvih 8 redova)
                for row in sheet.iter_rows(max_row=8, values_only=True):
                    row_text = " ".join(str(v).upper() for v in row if v)
                    if ("CODE" in row_text or "DESCRIPTION" in row_text) and \
                       ("NET WEIGHT" in row_text or "GROSS WEIGHT" in row_text):
                        logger.debug(f"IMAMOGLU Packing List — header match u '{sheet.title}'")
                        return True
        finally:
            wb.close()

        return False

    except Exception as e:
        logger.warning(f"Greška pri detekciji IMAMOGLU Packing List: {e}")
        return False


def detect_imamoglu_mal_tanimlari(filepath: str) -> bool:
    """
    Detektuje IMAMOGLU Turkish ERP export format (.xls).

    Kriteriji:
    - Extension .xls
    - Header sadrži karakteristične turske kolone: 'GTIP Kodu' ili
      kombinacija 'Kodu' + 'Miktar' + 'Dövizli'
    """
    try:
        if not filepath.lower().endswith('.xls'):
            return False

        import xlrd
        wb = xlrd.open_workbook(filepath)
        try:
            for sheet in wb.sheets():
                if sheet.nrows < 1:
                    continue
                # Header u redu 0
                header_vals = [str(sheet.cell_value(0, j)).strip()
                               for j in range(sheet.ncols)]
                header_text = " ".join(header_vals).upper()

                # Turski ERP kolone
                if 'GTIP' in header_text and ('KODU' in header_text or 'MIKTAR' in header_text):
                    logger.debug(f"IMAMOGLU Mal Tanımları — header match u '{sheet.name}'")
                    return True

                # Alternativna detekcija: Dövizli + Miktar + Kodu
                has_kodu = any('kodu' in h.lower() for h in header_vals)
                has_miktar = any('miktar' in h.lower() for h in header_vals)
                has_doviz = any('döviz' in h.lower() for h in header_vals)
                if has_kodu and has_miktar and has_doviz:
                    logger.debug(f"IMAMOGLU Mal Tanımları — kombinovana detekcija u '{sheet.name}'")
                    return True
        finally:
            wb.release_resources()

        return False

    except Exception as e:
        logger.warning(f"Greška pri detekciji IMAMOGLU Mal Tanımları: {e}")
        return False


# ─── PARSERI ─────────────────────────────────────────────────────────────────

def parse_imamoglu_packing_list(filepath: str) -> ImportResult:
    """
    Parsira IMAMOGLU Packing List (xlsx).

    Vraća stavke sa: CODE, DESCRIPTION (engleski), QUANTITY, UNIT, NET/GROSS po stavci.
    Ukupne težine se čitaju iz summary reda na kraju tabele.
    """
    logger.info(f"IMAMOGLU Packing List parsing: {filepath}")

    wb = openpyxl.load_workbook(filepath, data_only=True)
    try:
        sheet = wb.worksheets[0]
        logger.info(f"Sheet: {sheet.title}, redova: {sheet.max_row}")

        # Pronađi header red (sadrži CODE i DESCRIPTION i NET WEIGHT)
        header_row_idx = None
        header_map = {}
        for row_idx in range(1, min(10, sheet.max_row + 1)):
            row_vals = [cell.value for cell in sheet[row_idx]]
            row_text = " ".join(str(v).upper() for v in row_vals if v)
            if "CODE" in row_text and "DESCRIPTION" in row_text and "NET" in row_text:
                header_row_idx = row_idx
                # Mapiraj kolone
                for col_idx, cell in enumerate(sheet[row_idx]):
                    if not cell.value:
                        continue
                    h = str(cell.value).strip().upper().replace('\n', ' ')
                    if h == "CODE":
                        header_map["code"] = col_idx
                    elif h == "DESCRIPTION":
                        header_map["description"] = col_idx
                    elif h == "QUANTITY":
                        header_map["quantity"] = col_idx
                    elif h == "UNIT" and "unit" not in header_map:
                        header_map["unit"] = col_idx
                    elif "NET" in h and "WEIGHT" in h:
                        header_map["net_weight"] = col_idx
                    elif "GROSS" in h and "WEIGHT" in h:
                        header_map["gross_weight"] = col_idx
                logger.info(f"Header na redu {header_row_idx}: {header_map}")
                break

        if header_row_idx is None:
            raise ValueError("Nije pronađen header red u IMAMOGLU Packing List")

        # Parsiranje stavki
        items: List[InvoiceLine] = []
        bruto_total = 0.0
        neto_total = 0.0

        for row_idx in range(header_row_idx + 1, sheet.max_row + 1):
            row = list(sheet[row_idx])

            def _cell(col_key: str) -> str:
                idx = header_map.get(col_key)
                if idx is not None and idx < len(row):
                    v = row[idx].value
                    return str(v).strip() if v is not None else ""
                return ""

            def _float(col_key: str) -> float:
                raw = _cell(col_key)
                if not raw:
                    return 0.0
                try:
                    return float(re.sub(r'[^\d\.\-]', '', raw.replace(',', '.')))
                except ValueError:
                    return 0.0

            description = _cell("description")
            code = _cell("code").strip()

            # Preskači prazne redove i summary red
            if not description and not code:
                continue

            # Preskači summary red (nema opisa, ali ima ukupne težine)
            qty = _float("quantity")
            if not description and qty == 0.0:
                # Pokušaj pročitati ukupne težine
                nw = _float("net_weight")
                gw = _float("gross_weight")
                if nw > 0 or gw > 0:
                    bruto_total = gw
                    neto_total = nw
                continue

            if not description or len(description) < 2:
                continue

            net_w = _float("net_weight")
            gross_w = _float("gross_weight")
            unit = _cell("unit") or "PCS"

            item = InvoiceLine(
                line_no=len(items) + 1,
                naziv_robe=description,
                product_code=code,
                tarifni_broj="",
                zemlja_porijekla="TR",  # IMAMOGLU je turski dobavljač
                kolicina=qty,
                cijena_jed=0.0,
                iznos=0.0,
                valuta="EUR",
                bruto_kg=gross_w,
                neto_kg=net_w,
                jm=_normalize_unit(unit),
                povlastica=""
            )
            items.append(item)

        # Ako summary red nije pronađen, saberi po stavkama
        if neto_total == 0.0:
            neto_total = sum(i.neto_kg for i in items)
        if bruto_total == 0.0:
            bruto_total = sum(i.bruto_kg for i in items)

        invoice_name = Path(filepath).stem
        logger.info(f"IMAMOGLU Packing List: {len(items)} stavki, "
                    f"bruto={bruto_total:.2f} kg, neto={neto_total:.2f} kg")

        _exp = Party(name="IMAMOGLU")
        _imp = Party(name="IMAMOGLU D.O.O. SARAJEVO")  # domaća BiH firma
        for item in items:
            item.exporter = _exp
            item.importer = _imp

        return ImportResult(
            items=items,
            bruto_kg=bruto_total,
            neto_kg=neto_total,
            invoice_name=invoice_name,
            currency="EUR",
            import_type="imamoglu_packing_list",
            exporter=_exp,
            importer=_imp,
        )
    finally:
        wb.close()


def parse_imamoglu_mal_tanimlari(filepath: str) -> ImportResult:
    """
    Parsira IMAMOGLU Turkish ERP export (xls — mal tanımları).

    Kolone (header u redu 0):
    - Kodu (col 2)          → product_code
    - Açıklaması (col 3)    → naziv_robe
    - Miktar (col 8)        → kolicina
    - Birim (col 10)        → jm
    - Dövizli Birim (col 12)→ cijena_jed (EUR)
    - Dövizli Tutar (col 17)→ iznos (EUR ukupno)
    - Döviz (col 13)        → valuta
    - GTIP Kodu (col 49)    → tarifni_broj
    - Menşei(Kamu) (col 50) → zemlja_porijekla
    """
    import xlrd

    logger.info(f"IMAMOGLU Mal Tanımları parsing: {filepath}")

    wb = xlrd.open_workbook(filepath)
    try:
        sheet = wb.sheets()[0]
        logger.info(f"Sheet: {sheet.name}, redova: {sheet.nrows}")

        if sheet.nrows < 2:
            raise ValueError("Fajl nema podataka")

        # Dinamički mapiraj header (red 0)
        header_vals = [str(sheet.cell_value(0, j)).strip()
                       for j in range(sheet.ncols)]
        col = _build_column_map_mal_tanimlari(header_vals)
        logger.info(f"Kolone: {col}")

        items: List[InvoiceLine] = []

        for row_idx in range(1, sheet.nrows):
            def _val(key: str) -> str:
                idx = col.get(key)
                if idx is None or idx >= sheet.ncols:
                    return ""
                v = sheet.cell_value(row_idx, idx)
                return str(v).strip() if v != '' else ""

            def _flt(key: str) -> float:
                raw = _val(key)
                if not raw:
                    return 0.0
                try:
                    return float(re.sub(r'[^\d\.\-]', '', raw.replace(',', '.')))
                except ValueError:
                    return 0.0

            kod = _val("kodu")
            opis = _val("aciklama")
            opis2 = _val("aciklama2")  # Açıklaması2 — dodatni opis
            if not opis and not kod:
                continue

            # Kombiniraj opis + opis2 ako opis2 nije duplikat
            naziv = opis
            if opis2 and opis2 not in opis:
                naziv = f"{opis} {opis2}".strip()

            tarifni = _val("gtip")
            # GTIP iz xls može biti float (npr. 8302410000.0)
            if tarifni and '.' in tarifni:
                try:
                    tarifni = str(int(float(tarifni)))
                except ValueError:
                    pass
            # Vodeće nule: GTIP treba biti 10 cifara
            if tarifni and tarifni.isdigit() and len(tarifni) < 10:
                tarifni = tarifni.zfill(10)

            zemlja = _val("mensei") or "TR"

            jm_raw = _val("birim")
            kolicina = _flt("miktar")
            cijena = _flt("cij_eur")
            iznos = _flt("iznos_eur")
            valuta = _val("döviz") or "EUR"

            if not naziv or len(naziv) < 2:
                continue

            item = InvoiceLine(
                line_no=row_idx,
                naziv_robe=naziv,
                product_code=kod,
                tarifni_broj=tarifni,
                zemlja_porijekla=zemlja if len(zemlja) == 2 else "TR",
                kolicina=kolicina,
                cijena_jed=cijena,
                iznos=iznos if iznos > 0 else (cijena * kolicina),
                valuta=valuta,
                bruto_kg=0.0,  # nije u ovom fajlu
                neto_kg=0.0,   # nije u ovom fajlu
                jm=_normalize_unit(jm_raw),
                povlastica=""
            )
            items.append(item)

        invoice_name = Path(filepath).stem
        logger.info(f"IMAMOGLU Mal Tanımları: {len(items)} stavki")

        _exp = Party(name="IMAMOGLU")
        _imp = Party(name="IMAMOGLU D.O.O. SARAJEVO")
        for item in items:
            item.exporter = _exp
            item.importer = _imp

        return ImportResult(
            items=items,
            bruto_kg=0.0,
            neto_kg=0.0,
            invoice_name=invoice_name,
            currency="EUR",
            import_type="imamoglu_mal_tanimlari",
            exporter=_exp,
            importer=_imp,
        )
    finally:
        wb.release_resources()


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _build_column_map_mal_tanimlari(header_vals: List[str]) -> Dict[str, int]:
    """Gradi mapu kolona iz header reda Turkish ERP Excel-a."""
    col = {}
    for i, h in enumerate(header_vals):
        h_low = h.lower()
        if h_low == "kodu" and "kodu" not in col:
            col["kodu"] = i
        elif h_low in ("açıklaması", "aciklamasi") and "aciklama" not in col:
            col["aciklama"] = i
        elif h_low in ("açıklaması2", "aciklamasi2") and "aciklama2" not in col:
            col["aciklama2"] = i
        elif h_low == "miktar" and "miktar" not in col:
            col["miktar"] = i
        elif h_low == "birim" and "birim" not in col:
            col["birim"] = i
        elif "dövizli birim" in h_low and "cij_eur" not in col:
            col["cij_eur"] = i
        elif "dövizli tutar" in h_low and "iznos_eur" not in col:
            col["iznos_eur"] = i
        elif h_low == "döviz" and "döviz" not in col:
            col["döviz"] = i
        elif "gtip" in h_low and "gtip" not in col:
            col["gtip"] = i
        elif "menşei" in h_low or "mensei" in h_low:
            col["mensei"] = i
    return col


_UNIT_MAP = {
    "ADET": "kom",
    "PCS": "kom",
    "TK": "kom",
    "SET": "set",
    "METRE": "m",
    "MTS": "m",
    "KG": "kg",
    "MT": "m",
}


def _normalize_unit(raw: str) -> str:
    """Normalizuje jedinice mjere (ADET/PCS → kom, METRE/MTS → m, itd.)."""
    if not raw:
        return "kom"
    upper = raw.strip().upper()
    return _UNIT_MAP.get(upper, raw.lower())
