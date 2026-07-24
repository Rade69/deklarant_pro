import re


_CHAR_CLASSES = {
    "a": "aAáÁàÀâÂäÄ",
    "c": "cCčČćĆ",
    "d": "dDđĐ",
    "e": "eEéÉèÈêÊëË",
    "i": "iIíÍìÌîÎïÏ",
    "o": "oOóÓòÒôÔöÖ",
    "s": "sSšŠ",
    "u": "uUúÚùÙûÛüÜ",
    "z": "zZžŽ",
}


def searchable_words(text: str, min_length: int = 3) -> list[str]:
    if not text or not text.strip():
        return []
    return [word for word in text.strip().split() if len(word) >= min_length]


def searchable_patterns(text: str, min_length: int = 3) -> list[str]:
    return [_word_pattern(word) for word in searchable_words(text, min_length)]


def _word_pattern(word: str) -> str:
    parts: list[str] = []
    i = 0
    while i < len(word):
        pair = word[i:i + 2].lower()
        if pair == "dj":
            parts.append("(?:[dD][jJ]|[đĐ])")
            i += 2
            continue

        ch = word[i]
        chars = _CHAR_CLASSES.get(ch.lower())
        parts.append(f"[{re.escape(chars)}]" if chars else re.escape(ch))
        i += 1
    return "".join(parts)
