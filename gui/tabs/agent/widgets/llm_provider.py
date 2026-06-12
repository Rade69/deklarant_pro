"""
LLMProvider — Apstrakcija nad LLM providerima (Groq + Gemini + OpenRouter + DeepSeek).

Redoslijed:
  1. Groq (llama-3.3-70b-versatile) — primarni free provider
  2. Gemini (gemini-2.5-flash-lite) — sekundarni fallback
  3. OpenRouter (openrouter/free) — treći fallback
  4. DeepSeek (deepseek-chat) — opcioni plaćeni fallback

Upotreba:
    provider = LLMProvider()
    # Streaming chat:
    for token in provider.stream_chat(messages):
        ...
    # Batch (bez streaminga):
    text = provider.complete(messages)
"""

import logging
import os
import re
from pathlib import Path

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
        return "🔑 Neispravan API ključ. Provjeri .env (GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY ili DEEPSEEK_API_KEY)."
    if '402' in msg or 'insufficient_balance' in msg.lower() or 'insufficient balance' in msg.lower():
        return (
            "💳 Nedovoljno kredita na AI nalogu (402 Insufficient Balance).\n"
            "Dopuni kredit za trenutni provider ili podesi drugi (GROQ_API_KEY, GEMINI_API_KEY "
            "ili OPENROUTER_API_KEY) u .env."
        )
    if 'timeout' in msg.lower() or 'connection' in msg.lower():
        return "🌐 Greška veze sa AI serverom. Provjeri internet i pokušaj ponovo."
    return f"⚠️ AI greška: {msg[:200]}"


class LLMProvider:
    """
    Wrapper koji transparentno prebacuje između Groq, Gemini, OpenRouter i DeepSeek.

    Streaming radi za Groq; Gemini vraća token po token simulacijom
    (Gemini streaming je podržan ali se ovdje koristi non-streaming radi
    jednostavnosti — response se šalje odjednom).
    """

    DEEPSEEK_MODEL = "deepseek-chat"
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    GROQ_MODEL = "llama-3.3-70b-versatile"
    GROQ_BATCH_MODEL = "llama-3.1-8b-instant"
    GEMINI_MODEL = "gemini-2.5-flash-lite"
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL = "openrouter/free"

    def __init__(self):
        env = _load_env()
        self.deepseek_key = env.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or ""
        self.groq_key = env.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") or ""
        self.gemini_key = env.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        self.openrouter_key = env.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY") or ""
        self.openrouter_model = env.get("OPENROUTER_MODEL") or os.getenv("OPENROUTER_MODEL") or self.OPENROUTER_MODEL

    def has_deepseek(self) -> bool:
        return bool(self.deepseek_key)

    def has_groq(self) -> bool:
        return bool(self.groq_key)

    def has_gemini(self) -> bool:
        return bool(self.gemini_key)

    def has_openrouter(self) -> bool:
        return bool(self.openrouter_key)

    def active_provider(self) -> str:
        """Koji provider je trenutno aktivan (primarni)."""
        if self.has_groq():
            return "groq"
        if self.has_gemini():
            return "gemini"
        if self.has_openrouter():
            return "openrouter"
        if self.has_deepseek():
            return "deepseek"
        return "none"

    # ── DeepSeek implementacija ─────────────────────────────────────────────

    def _deepseek_stream(self, messages: list, max_tokens: int):
        from openai import OpenAI
        client = OpenAI(api_key=self.deepseek_key, base_url=self.DEEPSEEK_BASE_URL)
        stream = client.chat.completions.create(
            model=self.DEEPSEEK_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    def _deepseek_complete(self, messages: list, max_tokens: int) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.deepseek_key, base_url=self.DEEPSEEK_BASE_URL)
        resp = client.chat.completions.create(
            model=self.DEEPSEEK_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    # ── Streaming chat ────────────────────────────────────────────────

    def stream_chat(self, messages: list, max_tokens: int = 1500):
        """Generator koji yield-uje tokene jedan po jedan. Groq → Gemini → OpenRouter → DeepSeek."""
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
                logger.warning("Gemini greška (%s) → prelazim na OpenRouter", e)
                last_error = e

        if self.has_openrouter():
            try:
                yield from self._openrouter_stream(messages, max_tokens)
                return
            except Exception as e:
                logger.warning("OpenRouter greška (%s) → prelazim na DeepSeek", e)
                last_error = e

        if self.has_deepseek():
            try:
                yield from self._deepseek_stream(messages, max_tokens)
                return
            except Exception as e:
                last_error = e

        if last_error:
            raise last_error

        raise RuntimeError(
            "Nema dostupnog AI providera. "
            "Dodaj GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY ili DEEPSEEK_API_KEY u .env."
        )

    # ── Batch complete (za TariffLLMWorker) ───────────────────────────────────

    def complete(self, messages: list, max_tokens: int = 1200,
                 use_small_model: bool = True) -> str:
        """Jednokratni poziv bez streaminga. Groq → Gemini → OpenRouter → DeepSeek."""
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
                logger.warning("Gemini greška (%s) → prelazim na OpenRouter (batch)", e)
                last_error = e

        if self.has_openrouter():
            try:
                return self._openrouter_complete(messages, max_tokens)
            except Exception as e:
                logger.warning("OpenRouter greška (%s) → prelazim na DeepSeek (batch)", e)
                last_error = e

        if self.has_deepseek():
            try:
                return self._deepseek_complete(messages, max_tokens)
            except Exception as e:
                last_error = e

        if last_error:
            raise last_error

        raise RuntimeError(
            "Nema dostupnog AI providera. "
            "Dodaj GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY ili DEEPSEEK_API_KEY u .env."
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

    # ── OpenRouter implementacija ─────────────────────────────────────────────

    def _openrouter_stream(self, messages: list, max_tokens: int):
        from openai import OpenAI

        client = OpenAI(api_key=self.openrouter_key, base_url=self.OPENROUTER_BASE_URL)
        stream = client.chat.completions.create(
            model=self.openrouter_model,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    def _openrouter_complete(self, messages: list, max_tokens: int) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.openrouter_key, base_url=self.OPENROUTER_BASE_URL)
        resp = client.chat.completions.create(
            model=self.openrouter_model,
            messages=messages,
            temperature=0.1,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

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

