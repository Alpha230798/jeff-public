from __future__ import annotations

import re
import unicodedata


_TOKEN = re.compile(r"[^\W_]+(?:'[^\W_]+)?", re.UNICODE)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "do", "for", "from",
    "have", "he", "her", "how", "i", "in", "is", "it",     "je", "ki", "la", "le",
    "les", "li", "ma", "me", "mo", "my", "ne", "no", "not", "nous", "of",
    "on", "or", "pa", "p", "pe", "pour", "que", "qui", "sa", "she", "so",
    "the", "they", "this", "to", "tu", "un", "une", "we", "what", "when",
    "where", "why", "with", "you", "your", "zot",
}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold().replace("’", "'"))
    return "".join(char for char in normalized if not unicodedata.combining(char))


def lookup_dictionary_entries(
    text: str,
    entries: list[str],
    limit: int = 5,
) -> str:
    tokens: set[str] = set()
    for raw_token in _TOKEN.findall(text):
        if any(char.islower() for char in raw_token) and any(
            char.isupper() for char in raw_token[1:]
        ):
            continue
        token = _normalize(raw_token)
        if len(token) > 1 and token not in _STOPWORDS:
            tokens.add(token)
    if not tokens or limit <= 0:
        return ""

    matches: list[str] = []
    for entry in entries:
        headword_section = entry.split(":", 1)[0].split("[", 1)[0]
        headwords = set(_TOKEN.findall(_normalize(headword_section)))
        if tokens & headwords:
            matches.append(entry.strip()[:350])
            if len(matches) >= limit:
                break

    return "\n".join(f"- {entry}" for entry in matches)
