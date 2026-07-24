def searchable_words(text: str, min_length: int = 3) -> list[str]:
    if not text or not text.strip():
        return []
    return [word for word in text.strip().split() if len(word) >= min_length]
