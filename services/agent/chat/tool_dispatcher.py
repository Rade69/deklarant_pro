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
