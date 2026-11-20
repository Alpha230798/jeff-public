from __future__ import annotations

from phonetic import SpellingIndex, expand_letter_names, strip_accents


def uncertain_spelling_suggestions(
    text: str,
    entries: list[str],
    variants: dict[str, str],
) -> list[dict[str, object]]:
    """Return only ambiguous or skeleton-based candidates for user confirmation."""
    index = SpellingIndex(entries, variants)
    suggestions: list[dict[str, object]] = []
    for token, candidates in index.interpret(text):
        key = strip_accents(token).lower()
        expanded_key = expand_letter_names(token).lower()
        if variants.get(key) or variants.get(expanded_key):
            continue
        headwords = list(dict.fromkeys(candidate["headword"] for candidate in candidates))
        uncertain = len(headwords) > 1 or any(
            candidate["why"] == "skeleton" for candidate in candidates
        )
        if uncertain:
            suggestions.append({"variant": token, "candidates": headwords[:3]})
    return suggestions
