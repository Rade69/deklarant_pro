# gui/tabs/agent/token_budget.py
"""
TokenBudgetTracker — praćenje tokena po Agent tab sesiji.

Pošto LLM provider ne vraća tačan broj tokena u streaming modu,
koristimo aproksimaciju: 1 token ≈ 4 karaktera (latinični tekst).

Pragovi:
  soft_warn  — upozorenje korisniku (sesija je skupa, razmisli o resetu)
  hard_stop  — blokada novih LLM poziva, zahtijeva reset sesije
"""

import logging
from typing import Literal

logger = logging.getLogger("asycuda_pro.token_budget")

# Karaktera po tokenu (konzervativna procjena za bosanski/srpski)
_CHARS_PER_TOKEN = 3.5

# Podrazumijevani pragovi
_DEFAULT_SOFT_WARN = 40_000
_DEFAULT_HARD_STOP = 100_000


class TokenBudgetTracker:
    """
    Prati ulazne i izlazne tokene sesije.
    Aproksimacija iz dužine teksta jer Groq/Gemini streaming ne vraća usage.
    """

    def __init__(self, soft_warn: int = _DEFAULT_SOFT_WARN, hard_stop: int = _DEFAULT_HARD_STOP):
        self._input: int = 0
        self._output: int = 0
        self._soft_warn: int = soft_warn
        self._hard_stop: int = hard_stop
        self._warn_emitted: bool = False

    # ─────────────────────────────────────────────────
    # Dodavanje
    # ─────────────────────────────────────────────────

    def add(self, input_tokens: int = 0, output_tokens: int = 0):
        """Dodaj tačan broj tokena (ako API vrati usage)."""
        self._input += input_tokens
        self._output += output_tokens

    def estimate_input(self, text: str) -> int:
        """Procijeni input tokene iz dužine teksta i dodaj."""
        tokens = max(1, int(len(text) / _CHARS_PER_TOKEN))
        self._input += tokens
        return tokens

    def estimate_output(self, text: str) -> int:
        """Procijeni output tokene iz dužine teksta i dodaj."""
        tokens = max(1, int(len(text) / _CHARS_PER_TOKEN))
        self._output += tokens
        return tokens

    # ─────────────────────────────────────────────────
    # Provjera budgeta
    # ─────────────────────────────────────────────────

    def check(self) -> tuple[Literal['ok', 'warn', 'stop'], str | None]:
        """
        Provjeri stanje budgeta.

        Returns:
            ('stop', poruka)  — prekoračen hard limit, blokirati LLM poziv
            ('warn', poruka)  — prekoračen soft limit, samo upozoriti
            ('ok',   None)    — sve je u redu
        """
        total = self.total
        if total >= self._hard_stop:
            return 'stop', (
                f"⛔ Token limit dostignut ({total:,} ~tokena). "
                f"Resetuj sesiju da nastaviš rad."
            )
        if total >= self._soft_warn and not self._warn_emitted:
            self._warn_emitted = True
            return 'warn', (
                f"⚠️ Sesija koristi ~{total:,} tokena "
                f"({self._input:,} ulaz / {self._output:,} izlaz). "
                f"Razmisli o resetovanju sesije."
            )
        return 'ok', None

    # ─────────────────────────────────────────────────
    # Stanje
    # ─────────────────────────────────────────────────

    @property
    def total(self) -> int:
        return self._input + self._output

    @property
    def input_tokens(self) -> int:
        return self._input

    @property
    def output_tokens(self) -> int:
        return self._output

    def summary(self) -> str:
        """Kratki prikaz za UI (header/status bar)."""
        return f"↑{self._input:,} ↓{self._output:,} ≈{self.total:,} tok"

    def reset(self):
        self._input = 0
        self._output = 0
        self._warn_emitted = False
