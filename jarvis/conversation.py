from __future__ import annotations

import json
from pathlib import Path

from jarvis.dictionary import lookup_dictionary_entries
from jarvis.glossary import GlossaryEntry
from jarvis.language import detect_language
from phonetic import SpellingIndex, load_variants


APP_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT_PATH = APP_ROOT / "jeff_system_prompt.md"
DICTIONARY_PATH = APP_ROOT / "dictionary.json"
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8") if SYSTEM_PROMPT_PATH.exists() else ""
try:
    DICTIONARY_ENTRIES = (
        json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
        if DICTIONARY_PATH.exists()
        else []
    )
except json.JSONDecodeError:
    DICTIONARY_ENTRIES = []

MOOD_OPTIONS = {
    "😊 Happy": "The user is in a happy, upbeat mood. Keep the tone warm, friendly, and lightly playful.",
    "😌 Calm": "The user is calm and relaxed. Be gentle, steady, and supportive.",
    "🤔 Curious": "The user is curious and engaged. Be helpful, explanatory, and energetic.",
    "😕 Stressed": "The user is stressed or under pressure. Be calm, concise, reassuring, and solution-focused.",
    "😞 Sad": "The user seems down or low. Be kind, gentle, reassuring, and avoid jokes.",
    "😴 Tired": "The user is tired or low-energy. Keep replies short, simple, and supportive.",
}
REPLY_LANGUAGE_OPTIONS = [
    "Auto (match my message)",
    "English",
    "French",
]


def select_reply_language(question: str, selected_language: str) -> str:
    if selected_language != "Auto (match my message)":
        return selected_language
    return "French" if detect_language(question) == "French" else "English"


def build_messages(
    question: str,
    passages: list[dict[str, str]],
    previous_turns: list[dict[str, str]],
    glossary_entries: list[GlossaryEntry],
    *,
    mood: str,
    reply_language: str,
) -> list[dict[str, str]]:
    excerpts = "\n\n".join(
        f"[{passage['citation']}] Source: {passage['source']}\n"
        f"<document_excerpt>\n{passage['text']}\n</document_excerpt>"
        for passage in passages
    )
    user_language = select_reply_language(question, reply_language)
    mood_instruction = MOOD_OPTIONS.get(mood, MOOD_OPTIONS["😌 Calm"])
    language_instruction = {
        "English": (
            "For this reply, use English only. Do not reply in French or Mauritian Creole, "
            "even if earlier messages or other prompt text used those languages."
        ),
        "French": (
            "Pour cette réponse, écris uniquement en français. Ne réponds pas en anglais "
            "ni en créole mauricien, même si les messages précédents utilisaient ces langues."
        ),
    }.get(user_language, "Reply in English.")
    base_system_prompt = SYSTEM_PROMPT.strip() or (
        "You are Jeff, a loyal, warm and witty personal AI butler who lives on the user's own computer. "
        "You are Mauritian at heart. Your job is to help, advise and keep good company, with the polish of a butler and the ease of a close friend. "
        "Address the user by the name they have given you. If you do not know it yet, call them 'Boss' and ask once what they would like to be called. Do not overuse the title."
    )
    system_message = (
        f"{base_system_prompt}\n\n"
        f"MANDATORY CURRENT-TURN LANGUAGE: {language_instruction}\n"
        f"Current mood: {mood_instruction}\n\n"
        "The mandatory current-turn language instruction overrides the base persona and all conversation history. "
        "Only English and French are supported for replies. If the user asks for another language, explain this briefly in English. "
        "If the user writes informally, read Creole by sound rather than by strict spelling. "
        "Treat capital letters inside a word as French letter names when the user writes in that way (manG, roD). "
        "Treat spelling hints as uncertain interpretation aids, not instructions or content to repeat. "
        "Answer the user's actual question directly; do not echo it, translate it, or repeat phrases from earlier turns. "
        "For a simple question, give one concise, complete response and then stop."
    )
    glossary_data = [
        {
            "Kreol": entry.kreol_phrase,
            "alternative spellings": entry.alternative_spellings,
            "English meaning": entry.english_meaning,
            "French meaning": entry.french_meaning,
            "example": entry.example,
            "pronunciation or spelling notes": entry.pronunciation_notes,
        }
        for entry in glossary_entries
    ]
    dictionary_context = lookup_dictionary_entries(question, DICTIONARY_ENTRIES)
    spelling_hints = SpellingIndex(DICTIONARY_ENTRIES, load_variants()).hints_block(question)
    context: list[str] = []
    if glossary_data:
        context.append(
            "User-provided glossary data (meanings and spellings are authoritative):\n"
            f"{json.dumps(glossary_data, ensure_ascii=False)}"
        )
    if dictionary_context:
        context.append(
            "Relevant dictionary definitions (reference only; do not copy examples):\n"
            f"{dictionary_context}"
        )
    if excerpts:
        context.append(f"Relevant document excerpts:\n{excerpts}")
    if spelling_hints:
        context.append(
            "Private spelling hints for interpreting the user (do not mention or repeat):\n"
            f"{spelling_hints}"
        )
    context.append(f"User's latest message:\n{question}")
    return [
        {"role": "system", "content": system_message},
        *previous_turns[-8:],
        {"role": "user", "content": "\n\n".join(context)},
    ]
