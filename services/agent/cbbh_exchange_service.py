"""
CBBH Exchange Rate Service

Preuzima aktuelni srednji kurs od Narodne banke BiH (www.cbbh.ba).
Koristi se u agentu za automatsko popunjavanje Rb.23 (kurs).

EUR ima fiksni kurs 1.95583 KM — provjera nije potrebna.
Za USD, GBP, CHF i ostale valute kurs se mijenja dnevno.
"""

import json
import logging
import urllib.request
from datetime import date
from typing import Optional

logger = logging.getLogger("deklarant_pro.cbbh_exchange")

CBBH_API_URL = "https://www.cbbh.ba/CurrencyExchange/GetJson"
EUR_FIXED_RATE = 1.95583
EUR_CODE = "EUR"


def get_cbbh_rate(currency_code: str, for_date: Optional[date] = None) -> Optional[float]:
    """
    Preuzmi srednji kurs za datu valutu od CBBH.

    Args:
        currency_code: ISO kod valute (npr. "USD", "GBP", "CHF")
        for_date: Datum kursa (default: danas)

    Returns:
        Srednji kurs kao float (npr. 1.7823), ili None ako ne može dohvatiti
    """
    if not currency_code:
        return None

    code = currency_code.upper().strip()

    # EUR ima fiksni kurs — nema potrebe za API pozivom
    if code == EUR_CODE:
        return EUR_FIXED_RATE

    query_date = (for_date or date.today()).strftime("%Y-%m-%d")
    url = f"{CBBH_API_URL}?date={query_date}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AsycudaPro/1.0"})
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read())

        items = data.get("CurrencyExchangeItems", [])
        for item in items:
            if item.get("AlphaCode", "").upper() == code:
                middle = item.get("Middle")
                if middle:
                    rate = float(str(middle).replace(",", "."))
                    units = int(item.get("Units", 1) or 1)
                    return round(rate / units, 6) if units != 1 else round(rate, 6)

        logger.warning(f"[CBBH] Valuta {code} nije nađena u kursnoj listi za {query_date}")
        return None

    except urllib.error.URLError as e:
        logger.warning(f"[CBBH] Nije moguće dohvatiti kursnu listu (offline?): {e}")
        return None
    except Exception as e:
        logger.error(f"[CBBH] Greška pri dohvatanju kursa za {code}: {e}")
        return None


def update_draft_kurs(draft, chat=None) -> Optional[float]:
    """
    Provjeri aktuelni kurs od CBBH i ažuriraj draft.kurs ako se razlikuje.

    Koristi se u agentu nakon primjene XML templatea.
    EUR se preskače (fiksni kurs).

    Returns:
        Novi kurs ako je ažuriran, None ako nije bilo potrebe ili greška
    """
    valuta = (getattr(draft, "valuta", "") or "").upper().strip()
    if not valuta or valuta == EUR_CODE:
        return None

    current_kurs = getattr(draft, "kurs", 0.0) or 0.0

    cbbh_rate = get_cbbh_rate(valuta)
    if cbbh_rate is None:
        if chat:
            chat.add_activity(f"⚠️ Nije moguće dohvatiti kurs za {valuta} od CBBH (offline?)")
        return None

    if abs(cbbh_rate - current_kurs) < 0.0001:
        if chat:
            chat.add_activity(f"✅ Kurs {valuta} = {cbbh_rate} KM (aktuelan, bez promjene)")
        return None

    draft.kurs = cbbh_rate
    if chat:
        chat.add_activity(
            f"✅ Kurs {valuta} ažuriran: {current_kurs:.4f} → <b>{cbbh_rate:.4f} KM</b> (CBBH, {date.today().strftime('%d.%m.%Y.')})"
        )
    return cbbh_rate
