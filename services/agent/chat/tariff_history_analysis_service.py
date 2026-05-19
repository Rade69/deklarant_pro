"""
TariffHistoryAnalysisService — uporedi tarifne brojeve u aktivnom draftu
sa istorijskim podacima iz tariff_doc_history (SQLite) i product_tariff_mapping (PG).

Poziva se iz agenta alatom 'analiziraj_tarifne'.
"""

import logging
import os
import sqlite3
from html import escape
from typing import List

logger = logging.getLogger("deklarant_pro.agent.tariff_history_analysis")

_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "database", "deklarant_sistem.db"
)


def _sqlite_history(codes: list[str]) -> dict[str, int]:
    """Vraća {tariff_code: ukupna_frekvencija} iz tariff_doc_history."""
    if not codes:
        return {}
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        placeholders = ",".join("?" * len(codes))
        cur.execute(
            f"SELECT tariff_code, SUM(count) FROM tariff_doc_history "
            f"WHERE tariff_code IN ({placeholders}) GROUP BY tariff_code",
            codes,
        )
        result = {r[0]: int(r[1]) for r in cur.fetchall()}
        conn.close()
        return result
    except Exception as e:
        logger.warning(f"SQLite tariff_doc_history greška: {e}")
        return {}


def _sqlite_tarifa_naziv(codes: list[str]) -> dict[str, str]:
    """Vraća {tariff_code: naziv_iz_tarifa_2026}."""
    if not codes:
        return {}
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        nazivi = {}
        for code in codes:
            # Pokušaj match po 8 znakova + razni sufiksi
            found = False
            for suffix in ("00", "10", "20", "30", "90"):
                cur.execute(
                    "SELECT naziv FROM tarifa_2026 WHERE kod = ? LIMIT 1",
                    (code[:8] + suffix,),
                )
                row = cur.fetchone()
                if row:
                    nazivi[code] = row[0]
                    found = True
                    break
            if not found:
                # Pokušaj 6-cifreni
                cur.execute(
                    "SELECT naziv FROM tarifa_2026 WHERE kod = ? LIMIT 1",
                    (code[:6],),
                )
                row = cur.fetchone()
                if row:
                    nazivi[code] = row[0]
        conn.close()
        return nazivi
    except Exception as e:
        logger.warning(f"SQLite tarifa_2026 greška: {e}")
        return {}


def _pg_mapping_stats(codes: list[str]) -> dict[str, dict]:
    """Vraća {tariff_code: {pg_count, suppliers, primjer}} iz product_tariff_mapping."""
    if not codes:
        return {}
    try:
        from database.db import get_db_connection

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT commodity_code,
                       SUM(usage_count)         AS total,
                       COUNT(DISTINCT NULLIF(supplier,'')) AS suppliers,
                       MAX(naziv_robe)           AS primjer
                FROM catalogs.product_tariff_mapping
                WHERE commodity_code = ANY(%s)
                GROUP BY commodity_code
                """,
                (codes,),
            )
            return {
                r["commodity_code"]: {
                    "pg_count": int(r["total"] or 0),
                    "suppliers": int(r["suppliers"] or 0),
                    "primjer": (r["primjer"] or "")[:55],
                }
                for r in cur.fetchall()
            }
    except Exception as e:
        logger.warning(f"PG product_tariff_mapping greška: {e}")
        return {}


def analiziraj_tarifne_historiju(draft) -> str:
    """
    Analizira tarifne brojeve u aktivnom draftu i poredi ih sa istorijskim podacima.
    Vraća formatirani HTML string za prikaz u agentu.
    """
    # --- Skupi tarifne kodove ---
    naim_codes: list[tuple[str, str]] = []  # (tariff_code, opis_naim)

    if draft and getattr(draft, "items", None):
        for item in draft.items:
            tc = (getattr(item, "tariff_code", "") or "").strip()
            goods = (getattr(item, "goods_description", "") or
                     getattr(item, "goods_trade_name", "") or "")[:50]
            if tc:
                naim_codes.append((tc, goods))

    if not naim_codes and draft and getattr(draft, "invoice_lines", None):
        seen: set[str] = set()
        for line in draft.invoice_lines:
            tc = (getattr(line, "tarifni_broj", "") or "").strip()
            naziv = (getattr(line, "naziv_robe", "") or "")[:50]
            if tc and tc not in seen:
                naim_codes.append((tc, naziv))
                seen.add(tc)

    if not naim_codes:
        return "⚠️ Nema tarifnih brojeva u aktivnoj deklaraciji. Učitaj fakturu i kreiraj naimenovanja."

    unique_codes = list(dict.fromkeys(c for c, _ in naim_codes))

    # --- Dohvati historijske podatke ---
    hist = _sqlite_history(unique_codes)
    nazivi = _sqlite_tarifa_naziv(unique_codes)
    pg = _pg_mapping_stats(unique_codes)

    # --- Grupiši retke po kodu (isti kod može biti u više naim) ---
    code_rows: dict[str, list[str]] = {}
    for tc, goods in naim_codes:
        code_rows.setdefault(tc, []).append(goods)

    # --- Gradi HTML ---
    rows_html = []
    novi_kodovi = []
    for code in unique_codes:
        h_puta = hist.get(code, 0)
        pg_info = pg.get(code, {})
        pg_count = pg_info.get("pg_count", 0)
        pg_sup = pg_info.get("suppliers", 0)
        primjer = pg_info.get("primjer", "")
        naziv = nazivi.get(code, "")
        descs = code_rows.get(code, [])
        desc_str = "; ".join(d for d in descs if d)[:60]

        if h_puta == 0 and pg_count == 0:
            novi_kodovi.append(code)
            badge = '<span style="color:#c0392b;font-weight:bold;">● NOVO</span>'
        elif h_puta == 0:
            badge = '<span style="color:#e67e22;">● Nije u historiji</span>'
        elif h_puta >= 200:
            badge = f'<span style="color:#27ae60;font-weight:bold;">✔ {h_puta}x</span>'
        else:
            badge = f'<span style="color:#2980b9;">✔ {h_puta}x</span>'

        pg_str = ""
        if pg_count > 0:
            pg_str = (
                f' &nbsp;<small style="color:#7f8c8d;">'
                f'mapping: {pg_count}x'
                f'{", " + str(pg_sup) + " dob." if pg_sup else ""}'
                f"</small>"
            )

        naziv_str = (
            f'<br><small style="color:#555;">{escape(naziv[:70])}</small>'
            if naziv
            else ""
        )
        desc_html = (
            f' &nbsp;<small style="color:#888;">[{escape(desc_str)}]</small>'
            if desc_str
            else ""
        )

        rows_html.append(
            f"<tr>"
            f"<td style='padding:2px 8px;font-family:monospace;'>{escape(code)}</td>"
            f"<td style='padding:2px 8px;'>{badge}{pg_str}</td>"
            f"<td style='padding:2px 8px;'>{desc_html}{naziv_str}</td>"
            f"</tr>"
        )

    n_naim = len(naim_codes)
    n_unique = len(unique_codes)
    n_novi = len(novi_kodovi)
    status_color = "#27ae60" if n_novi == 0 else "#c0392b"
    status_text = (
        "Svi tarifni brojevi su konzistentni sa istorijom."
        if n_novi == 0
        else f"{n_novi} kod(a) se nikad ranije nije koristio — provjeri ručno."
    )

    html = (
        f"<b>Analiza tarifnih brojeva — historijska provjera</b><br>"
        f"Naimenovanja: <b>{n_naim}</b> &nbsp;|&nbsp; "
        f"Jedinstvenih kodova: <b>{n_unique}</b><br>"
        f"<span style='color:{status_color};'>{escape(status_text)}</span>"
        f"<br><br>"
        f"<table style='border-collapse:collapse;width:100%;'>"
        f"<tr style='background:#f0f0f0;'>"
        f"<th style='padding:3px 8px;text-align:left;'>Tarifni</th>"
        f"<th style='padding:3px 8px;text-align:left;'>Historija</th>"
        f"<th style='padding:3px 8px;text-align:left;'>Naziv / Opis</th>"
        f"</tr>"
        + "".join(rows_html)
        + "</table>"
    )

    if novi_kodovi:
        html += (
            f"<br><b style='color:#c0392b;'>Kodovi bez historije:</b> "
            + ", ".join(f"<code>{escape(c)}</code>" for c in novi_kodovi)
        )

    return html
