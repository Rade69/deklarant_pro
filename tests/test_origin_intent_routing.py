import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parent.parent
    / "gui"
    / "tabs"
    / "agent"
    / "services"
    / "chat_intent_handler.py"
)
spec = importlib.util.spec_from_file_location("chat_intent_handler_for_test", MODULE_PATH)
chat_intent_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat_intent_handler)
_extract_origin_product_query = chat_intent_handler._extract_origin_product_query


def test_extract_origin_query_from_product_prefix():
    message = "KONDENZATOR GCVC RD 045.2/24-53,potraži porijeklo ovog proizvoda"

    assert _extract_origin_product_query(message) == "KONDENZATOR GCVC RD 045.2/24-53"


def test_extract_origin_query_after_origin_phrase():
    message = "Potraži zemlju porijekla za KONDENZATOR GCVC RD 045.2/24-53"

    assert _extract_origin_product_query(message) == "KONDENZATOR GCVC RD 045.2/24-53"


def test_origin_query_does_not_intercept_column_update():
    message = "upiši porijeklo TR u fakturu"

    assert _extract_origin_product_query(message) == ""
