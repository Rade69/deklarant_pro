from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from psycopg2.extras import Json

from database.db import get_db_connection

logger = logging.getLogger("deklarant_pro.tariff_feedback")


def get_tariff_validation_feedback_summary(
    match: Any,
    user_id: str = "default",
) -> dict[str, int]:
    item_key = _item_key(match)
    summary = {"accept": 0, "reject": 0}

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT action_type, COUNT(*) AS cnt
                    FROM catalogs.user_feedback
                    WHERE user_id = %s
                      AND item_type = 'tariff_validation'
                      AND item_key = %s
                      AND action_type IN ('accept', 'reject')
                    GROUP BY action_type
                    """,
                    (user_id, item_key),
                )
                for row in cur.fetchall():
                    summary[row["action_type"]] = int(row["cnt"] or 0)
    except Exception as exc:
        logger.warning("Tariff feedback summary nije učitan: %s", exc)

    return summary


def record_tariff_validation_feedback(
    match: Any,
    action_type: str,
    accept_mode: str = "manual",
    user_id: str = "default",
) -> bool:
    if action_type not in {"accept", "reject"}:
        raise ValueError(f"Nepoznat action_type: {action_type}")

    item_key = _item_key(match)
    context = {
        "source": "TariffValidationDialog",
        "accept_mode": accept_mode,
        "line_index": getattr(match, "line_index", None),
        "naziv_robe_original": getattr(match, "naziv_robe_original", "") or "",
        "naziv_robe_historijski": getattr(match, "naziv_robe_historijski", "") or "",
        "source_detail": getattr(match, "source", "") or "",
        "usage_count": int(getattr(match, "usage_count", 0) or 0),
        "match_confidence": float(getattr(match, "confidence", 0.0) or 0.0),
        "decision_outcome": getattr(match, "decision_outcome", "") or "",
        "decision_score": int(getattr(match, "decision_score", 0) or 0),
        "decision_reason": getattr(match, "decision_reason", "") or "",
    }

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO catalogs.user_feedback
                        (user_id, action_type, item_type, item_key,
                         original_value, new_value, confidence, context, processed)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE)
                    """,
                    (
                        user_id,
                        action_type,
                        "tariff_validation",
                        item_key,
                        getattr(match, "tarifni_broj_trenutni", "") or "",
                        getattr(match, "tarifni_broj_historijski", "") or "",
                        float(getattr(match, "confidence", 1.0) or 0.0),
                        Json(context),
                    ),
                )
        return True
    except Exception as exc:
        logger.warning("Tariff feedback nije snimljen: %s", exc)
        return False


def _item_key(match: Any) -> str:
    parts = [
        _normalize(getattr(match, "source", "") or ""),
        _normalize(getattr(match, "naziv_robe_original", "") or ""),
        _digits(getattr(match, "tarifni_broj_trenutni", "") or ""),
        _digits(getattr(match, "tarifni_broj_historijski", "") or ""),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"tariff_validation:{digest}"


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().upper())


def _digits(value: str) -> str:
    return re.sub(r"\D+", "", str(value))
