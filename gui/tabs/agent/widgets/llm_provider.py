"""
LLMProvider — Apstrakcija nad LLM providerima (Groq + Gemini).

Redoslijed (AGENTS.md kanonska politika):
  1. Groq (llama-3.3-70b-versatile) — primarni free provider
  2. Gemini (gemini-2.5-flash-lite) — fallback

DeepSeek i OpenRouter su namjerno uklonjeni iz lanca (2026-07-19, Faza B —
docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md). `LLMProvider`
ostaje jedina dozvoljena ulazna tačka za LLM pozive — nijedan pozivalac ne
smije direktno instancirati Groq/Gemini/bilo koji drugi provider klijent.

Upotreba:
    provider = LLMProvider()
    # Streaming chat:
    for token in provider.stream_chat(messages):
        ...
    # Batch (bez streaminga):
    text = provider.complete(messages)
    # Tool use (Tool Dispatcher):
    response = provider.complete_with_tools(messages, tools=TOOLS)
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("deklarant_pro.agent.llm")


def _load_env() -> dict:
    """Učitaj .env iz root projekta."""
    try:
        from dotenv import dotenv_values
        env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
        return dotenv_values(env_path) if env_path.exists() else {}
    except Exception:
        return {}


def _is_rate_limit(exc) -> bool:
    return '429' in str(exc) or 'rate_limit_exceeded' in str(exc)


def parse_llm_error(exc) -> str:
    """Pretvori LLM API grešku u poruku čitljivu korisniku."""
    msg = str(exc)
    if '429' in msg or 'rate_limit_exceeded' in msg or 'RESOURCE_EXHAUSTED' in msg:
        wait = re.search(r'Please try again in ([^\'".]+)', msg)
        wait_str = wait.group(1).strip() if wait else 'nekoliko minuta'
        used = re.search(r'Used (\d+)', msg)
        limit = re.search(r'Limit (\d+)', msg)
        if used and limit:
            return (
                f"⏳ Dnevni limit tokena iskorišten ({used.group(1)}/{limit.group(1)}).\n"
                f"Sačekaj {wait_str} pa pokušaj ponovo.\n"
                f"💡 Savjet: pričekaj do ponoći kad se limit resetuje."
            )
        return f"⏳ AI limit dostignut. Pokušaj za: {wait_str}"
    if '401' in msg or 'invalid_api_key' in msg or 'API_KEY_INVALID' in msg:
        return "🔑 Neispravan API ključ. Provjeri .env (GROQ_API_KEY ili GEMINI_API_KEY)."
    if '402' in msg or 'insufficient_balance' in msg.lower() or 'insufficient balance' in msg.lower():
        return (
            "💳 Nedovoljno kredita na AI nalogu (402 Insufficient Balance).\n"
            "Dopuni kredit za trenutni provider ili podesi drugi (GROQ_API_KEY ili "
            "GEMINI_API_KEY) u .env."
        )
    if 'timeout' in msg.lower() or 'connection' in msg.lower():
        return "🌐 Greška veze sa AI serverom. Provjeri internet i pokušaj ponovo."
    return f"⚠️ AI greška: {msg[:200]}"


@dataclass
class ProviderToolResponse:
    """
    Neutralan rezultat complete_with_tools() poziva — bez provider-specifičnih
    objekata, isti oblik bez obzira da li je odgovorio Groq ili Gemini.
    """
    tool_name: Optional[str] = None
    tool_arguments: Dict[str, Any] = field(default_factory=dict)
    content: str = ""      # Plain text odgovor, ako model nije pozvao alat.
    provider: str = ""     # Koji je provider stvarno završio poziv ("groq"/"gemini") — za audit.
    error: str = ""


class LLMProvider:
    """
    Wrapper koji transparentno prebacuje između Groq i Gemini.

    Streaming radi za Groq; Gemini vraća token po token simulacijom
    (Gemini streaming je podržan ali se ovdje koristi non-streaming radi
    jednostavnosti — response se šalje odjednom).
    """

    GROQ_MODEL = "llama-3.3-70b-versatile"
    GROQ_BATCH_MODEL = "llama-3.1-8b-instant"
    GEMINI_MODEL = "gemini-2.5-flash-lite"

    def __init__(self):
        env = _load_env()
        self.groq_key = env.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") or ""
        self.gemini_key = env.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""

    def has_groq(self) -> bool:
        return bool(self.groq_key)

    def has_gemini(self) -> bool:
        return bool(self.gemini_key)

    def active_provider(self) -> str:
        """Koji provider je trenutno aktivan (primarni)."""
        if self.has_groq():
            return "groq"
        if self.has_gemini():
            return "gemini"
        return "none"

    # ── Streaming chat ────────────────────────────────────────────────

    def stream_chat(self, messages: list, max_tokens: int = 1500):
        """Generator koji yield-uje tokene jedan po jedan. Groq → Gemini."""
        last_error = None
        if self.has_groq():
            try:
                yield from self._groq_stream(messages, max_tokens)
                return
            except Exception as e:
                logger.warning("Groq greška (%s) → prelazim na Gemini", e)
                last_error = e

        if self.has_gemini():
            try:
                yield from self._gemini_stream(messages, max_tokens)
                return
            except Exception as e:
                last_error = e

        if last_error:
            raise last_error

        raise RuntimeError(
            "Nema dostupnog AI providera. Dodaj GROQ_API_KEY ili GEMINI_API_KEY u .env."
        )

    # ── Batch complete (za TariffLLMWorker) ───────────────────────────────────

    def complete(self, messages: list, max_tokens: int = 1200,
                 use_small_model: bool = True) -> str:
        """Jednokratni poziv bez streaminga. Groq → Gemini."""
        last_error = None
        if self.has_groq():
            try:
                return self._groq_complete(messages, max_tokens, use_small_model)
            except Exception as e:
                logger.warning("Groq greška (%s) → prelazim na Gemini (batch)", e)
                last_error = e

        if self.has_gemini():
            try:
                return self._gemini_complete(messages, max_tokens)
            except Exception as e:
                last_error = e

        if last_error:
            raise last_error

        raise RuntimeError(
            "Nema dostupnog AI providera. Dodaj GROQ_API_KEY ili GEMINI_API_KEY u .env."
        )

    # ── Tool use (Tool Dispatcher) ─────────────────────────────────────────

    def complete_with_tools(self, messages: list, tools: List[dict],
                             max_tokens: int = 300) -> ProviderToolResponse:
        """
        Jednokratni poziv sa tool/function calling podrškom. Groq → Gemini.

        Vraća neutralan ProviderToolResponse bez obzira koji je provider
        stvarno odgovorio — pozivalac (tool_dispatcher.py) ne treba znati
        detalje Groq ili Gemini API formata.
        """
        last_error = None
        if self.has_groq():
            try:
                return self._groq_complete_with_tools(messages, tools, max_tokens)
            except Exception as e:
                logger.warning("Groq tool-use greška (%s) → prelazim na Gemini", e)
                last_error = e

        if self.has_gemini():
            try:
                return self._gemini_complete_with_tools(messages, tools, max_tokens)
            except Exception as e:
                last_error = e

        if last_error:
            return ProviderToolResponse(error=parse_llm_error(last_error))

        return ProviderToolResponse(
            error="Nema dostupnog AI providera. Dodaj GROQ_API_KEY ili GEMINI_API_KEY u .env."
        )

    # ── Groq implementacija ───────────────────────────────────────────────────

    def _groq_stream(self, messages: list, max_tokens: int):
        from groq import Groq
        client = Groq(api_key=self.groq_key)
        stream = client.chat.completions.create(
            model=self.GROQ_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    def _groq_complete(self, messages: list, max_tokens: int,
                       use_small_model: bool) -> str:
        from groq import Groq
        model = self.GROQ_BATCH_MODEL if use_small_model else self.GROQ_MODEL
        client = Groq(api_key=self.groq_key)
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def _groq_complete_with_tools(self, messages: list, tools: List[dict],
                                   max_tokens: int) -> ProviderToolResponse:
        from groq import Groq
        client = Groq(api_key=self.groq_key)
        resp = client.chat.completions.create(
            model=self.GROQ_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=max_tokens,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            call = msg.tool_calls[0]
            try:
                args = json.loads(call.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}
            return ProviderToolResponse(
                tool_name=call.function.name, tool_arguments=args, provider="groq",
            )
        return ProviderToolResponse(content=msg.content or "", provider="groq")

    # ── Gemini implementacija ─────────────────────────────────────────────────

    def _gemini_messages(self, messages: list) -> tuple:
        """
        Konvertuj OpenAI format u Gemini format.

        Returns:
            (system_instruction: str, contents: list)
        """
        system_parts = []
        contents = []

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        system_instruction = "\n\n".join(system_parts) if system_parts else None
        return system_instruction, contents

    def _gemini_stream(self, messages: list, max_tokens: int):
        """Gemini streaming — yield tokeni."""
        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=self.gemini_key)
        system_instruction, contents = self._gemini_messages(messages)

        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=0.2,
            system_instruction=system_instruction,
        )

        for chunk in client.models.generate_content_stream(
            model=self.GEMINI_MODEL,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    def _gemini_complete(self, messages: list, max_tokens: int) -> str:
        """Gemini bez streaminga — vraća kompletan tekst."""
        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=self.gemini_key)
        system_instruction, contents = self._gemini_messages(messages)

        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=0.1,
            system_instruction=system_instruction,
        )

        resp = client.models.generate_content(
            model=self.GEMINI_MODEL,
            contents=contents,
            config=config,
        )
        return resp.text or ""

    @staticmethod
    def _gemini_tool_declarations(tools: List[dict]):
        """Konvertuj OpenAI-stil TOOLS listu u Gemini FunctionDeclaration listu."""
        from google.genai import types

        declarations = []
        for t in tools:
            func = t.get("function", t)
            declarations.append(types.FunctionDeclaration(
                name=func["name"],
                description=func.get("description", ""),
                parameters=func.get("parameters", {}),
            ))
        return declarations

    def _gemini_complete_with_tools(self, messages: list, tools: List[dict],
                                     max_tokens: int) -> ProviderToolResponse:
        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=self.gemini_key)
        system_instruction, contents = self._gemini_messages(messages)
        gemini_tool = types.Tool(function_declarations=self._gemini_tool_declarations(tools))

        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=0.1,
            system_instruction=system_instruction,
            tools=[gemini_tool],
        )

        resp = client.models.generate_content(
            model=self.GEMINI_MODEL,
            contents=contents,
            config=config,
        )

        candidates = resp.candidates or []
        if candidates and candidates[0].content and candidates[0].content.parts:
            for part in candidates[0].content.parts:
                fc = getattr(part, "function_call", None)
                if fc is not None and fc.name:
                    return ProviderToolResponse(
                        tool_name=fc.name,
                        tool_arguments=dict(fc.args) if fc.args else {},
                        provider="gemini",
                    )

        return ProviderToolResponse(content=resp.text or "", provider="gemini")
