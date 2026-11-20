from __future__ import annotations

import re


_FRENCH_WORDS = {
    "bonjour",
    "ce",
    "comment",
    "dans",
    "des",
    "elle",
    "est",
    "et",
    "je",
    "la",
    "le",
    "les",
    "mais",
    "merci",
    "mon",
    "ma",
    "mes",
    "ne",
    "nous",
    "pas",
    "pour",
    "pourquoi",
    "pouvez",
    "que",
    "qui",
    "suis",
    "une",
    "êtes",
    "être",
    "vous",
}
_KREOL_WORDS = {
    "bann",
    "bizin",
    "ena",
    "eski",
    "kapav",
    "ki",
    "kifer",
    "koman",
    "kot",
    "krwar",
    "la",
    "li",
    "mo",
    "nou",
    "pe",
    "pou",
    "sa",
    "zot",
}

_LANGUAGE_REQUESTS = (
    (
        "English",
        re.compile(
            r"\b(?:in english|en anglais|speak english|reply in english|answer in english|"
            r"parle(?:z)? anglais)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "French",
        re.compile(
            r"\b(?:in french|en fran[cç]ais|speak french|reply in french|answer in french|"
            r"parle(?:z)? fran[cç]ais|réponds en fran[cç]ais|reponds en fran[cç]ais)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Mauritian Kreol",
        re.compile(
            r"\b(?:in creole|in kreol|en créole|en kreol|speak creole|speak kreol|"
            r"reply in creole|reply in kreol|answer in creole|answer in kreol|"
            r"parle(?:z)? créole|parle(?:z)? kreol|reponn(?:\s+\w+)?\s+an kreol)\b",
            re.IGNORECASE,
        ),
    ),
)


def detect_language(text: str) -> str:
    for language, pattern in _LANGUAGE_REQUESTS:
        if pattern.search(text):
            return language

    words = set(re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE))
    french_score = len(words & _FRENCH_WORDS)
    kreol_score = len(words & _KREOL_WORDS)

    if any(character in text.casefold() for character in "àâçéèêëîïôùûüÿœ"):
        french_score += 2

    # Common Creole pronouns and question markers are more reliable than isolated French loanwords.
    creole_markers = {"mo", "li", "nou", "zot", "pe", "pou", "ki", "kot", "kifer", "eski"}
    if creole_markers & words:
        kreol_score += 3

    # A short Kreol prompt like "Ki position?" should map to Kreol even when it contains a French loanword.
    if "ki" in words and not any(word in words for word in {"bonjour", "merci", "comment", "pouvez", "je", "vous"}):
        kreol_score += 2

    if kreol_score >= french_score and kreol_score:
        return "Mauritian Kreol"
    if french_score > kreol_score and french_score:
        return "French"
    return "English"


def thinking_label(text: str) -> str:
    language = detect_language(text)
    if language == "French":
        return "Réflexion..."
    if language == "Mauritian Kreol":
        return "Pe reflesi..."
    return "Thinking..."
