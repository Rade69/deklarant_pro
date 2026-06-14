"""
Tool Dispatcher — DeepSeek Tool Use za chat routing.

Zamjenjuje 3-slojni sistem (regex → IntentClassifier → ChatWorker)
sa jednim Tool Use pozivom DeepSeek-u.

📄 Povezano: docs/decisions/001-tool-use-refactoring.md
   Zavisnosti:
   - services/agent/chat/tool_definitions.py  (TOOLS, SYSTEM_PROMPT)
   - gui/tabs/agent/widgets/llm_provider.py     (DeepSeek API)
   - services/agent/chat/*_intent_service.py    (servisi za izvršenje)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QThread, Signal

from services.agent.chat.tool_definitions import TOOLS, SYSTEM_PROMPT

logger = logging.getLogger("deklarant_pro.agent.tool_dispatcher")


@dataclass
class ToolCall:
    """Rezultat tool use poziva — jedan alat sa argumentima."""
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DispatchResult:
    """Rezultat dispatch operacije."""
    tool_call: Optional[ToolCall] = None   # Ako je model pozvao alat
    plain_text: str = ""                   # Ako je model odgovorio direktno
    error: str = ""                        # Ako je došlo do greške


def _clean_query(value: str) -> str:
    text = re.sub(r"[?.!,;:]+$", "", value or "").strip()
    text = re.sub(
        r"^(?:taj|ta|to|ovu|ove|ovaj|proizvod|robu|artikl)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


def _extract_after_patterns(message: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return _clean_query(match.group(1))
    return ""


def route_local_tool(message: str) -> Optional[ToolCall]:
    text = (message or "").strip()
    if not text:
        return None
    msg = text.lower()

    if any(k in msg for k in ("stanje aplikacije", "sta je ucitano", "šta je učitano")):
        return ToolCall("pregled_stanja_aplikacije", {"scope": "all"})
    if any(k in msg for k in ("tab faktura", "faktura tab", "u fakturi")):
        return ToolCall("pregled_stanja_aplikacije", {"scope": "faktura"})
    if any(k in msg for k in ("zaglavlje", "u zaglavlju")):
        return ToolCall("pregled_stanja_aplikacije", {"scope": "zaglavlje"})
    if any(k in msg for k in ("naimenovanja", "naimenovanje")) and any(
        k in msg for k in ("pogledaj", "pokazi", "pokaži", "prikazi", "prikaži", "sta je", "šta je")
    ):
        return ToolCall("pregled_stanja_aplikacije", {"scope": "naimenovanja"})

    if any(k in msg for k in ("analiziraj tarifne", "historija tarifa", "istorija tarifa")):
        return ToolCall("analiziraj_tarifne", {})
    if "uporedi" in msg and "tarif" in msg and any(k in msg for k in ("histor", "istor")):
        return ToolCall("analiziraj_tarifne", {})

    if any(k in msg for k in ("provjeri tarife", "provjeri tarifne", "provjeru tarifa")):
        return ToolCall("provjeri_tarife", {})
    if "tarif" in msg and any(k in msg for k in ("isprav", "valid")):
        return ToolCall("provjeri_tarife", {})

    if any(k in msg for k in ("popuni sve tarif", "predlozi tarife", "predloži tarife")):
        return ToolCall("predlozi_tarife", {})
    if "tarif" in msg and any(k in msg for k in ("popuni sve", "za sve stavke", "batch")):
        return ToolCall("predlozi_tarife", {})

    origin_query = _extract_after_patterns(text, (
        r"(?:porijeklo|poreklo|origin|zemlja porijekla|zemlja porekla)\s+(?:proizvoda|robe|za)?\s+(.+)$",
        r"(?:za)\s+(.+?)\s+(?:porijeklo|poreklo|origin)$",
    ))
    if origin_query and len(origin_query) >= 3:
        return ToolCall("pretrazi_porijeklo", {"naziv": origin_query})

    similar_query = _extract_after_patterns(text, (
        r"(?:slicni|slični|raniji slicni|raniji slični)\s+(?:proizvodi|slucajevi|slučajevi)?\s*(?:za)?\s+(.+)$",
        r"(?:sta istorijski lici na|šta istorijski liči na|sta istorijski slici na|šta istorijski sliči na)\s+(.+)$",
    ))
    if similar_query and len(similar_query) >= 3:
        return ToolCall("pronadji_slicne_proizvode", {"naziv": similar_query})

    tariff_query = _extract_after_patterns(text, (
        r"(?:koji je|koja je|pronadji|pronađi|nadji|nađi|trazi|traži|predlozi|predloži)\s+"
        r"(?:mi\s+)?(?:tarifni broj|tarifu|tarif)\s+(?:za)?\s+(.+)$",
        r"(?:tarifni broj|tarifa|tarif)\s+(?:za)\s+(.+)$",
    ))
    if tariff_query and len(tariff_query) >= 3 and "sve" not in tariff_query.lower():
        return ToolCall("pretrazi_tarifu", {"naziv": tariff_query})

    return None


class ToolDispatcherWorker(QThread):
    """
    QThread worker koji šalje korisničku poruku DeepSeek-u sa Tool Use.

    Signali:
        tool_call_received(name: str, arguments: dict)
            Emituje se kada model pozove alat.
        fallback_to_chat(text: str)
            Emituje se kada model odgovori direktno (plain text).
        error_occurred(message: str)
            Emituje se kada dođe do greške.
    """

    tool_call_received = Signal(str, dict)
    fallback_to_chat = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self._message = message

    def run(self):
        """Pošalji poruku DeepSeek-u i emituj rezultat."""
        try:
            result = self._dispatch(self._message)
            if result.error:
                self.error_occurred.emit(result.error)
            elif result.tool_call:
                self.tool_call_received.emit(
                    result.tool_call.name,
                    result.tool_call.arguments
                )
            else:
                self.fallback_to_chat.emit(result.plain_text or "")
        except Exception as e:
            logger.error(f"[ToolDispatcher] Fatal error: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    @staticmethod
    def _dispatch(message: str) -> DispatchResult:
        """
        Poziva DeepSeek API sa tools i parsira odgovor.

        Statička metoda radi lakšeg testiranja bez Qt zavisnosti.
        """
        local_tool = route_local_tool(message)
        if local_tool is not None:
            logger.debug("[ToolDispatcher] Local tool routed: %s(%s)", local_tool.name, local_tool.arguments)
            return DispatchResult(tool_call=local_tool)

        from gui.tabs.agent.widgets.llm_provider import LLMProvider

        provider = LLMProvider()

        if not provider.has_deepseek():
            return DispatchResult(
                error="DeepSeek API ključ nije podešen. Dodaj DEEPSEEK_API_KEY u .env"
            )

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=provider.deepseek_key,
                base_url="https://api.deepseek.com"
            )

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ]

            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=300,
            )

            choice = resp.choices[0]
            msg = choice.message

            if msg.tool_calls:
                tool_call = msg.tool_calls[0]
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                logger.debug(f"[ToolDispatcher] Tool called: {name}({args})")
                return DispatchResult(
                    tool_call=ToolCall(name=name, arguments=args)
                )
            else:
                text = msg.content or ""
                logger.debug(f"[ToolDispatcher] Plain text: {text[:80]}...")
                return DispatchResult(plain_text=text)

        except Exception as e:
            from gui.tabs.agent.widgets.llm_provider import parse_llm_error
            err_msg = parse_llm_error(e)
            logger.warning(f"[ToolDispatcher] API error: {err_msg}")
            return DispatchResult(error=err_msg)
