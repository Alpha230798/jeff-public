from __future__ import annotations

import streamlit as st

from jarvis.conversation import (
    DICTIONARY_ENTRIES,
    MOOD_OPTIONS,
    REPLY_LANGUAGE_OPTIONS,
    build_messages,
    select_reply_language,
)
from jarvis.glossary import GlossaryEntry
from jarvis.ollama import OllamaClient
from jarvis.ui_state import initialize_settings

__all__ = [
    "DICTIONARY_ENTRIES",
    "MOOD_OPTIONS",
    "REPLY_LANGUAGE_OPTIONS",
    "make_messages",
    "new_client",
    "select_reply_language",
]


def new_client() -> OllamaClient:
    initialize_settings()
    return OllamaClient(
        base_url=st.session_state["setting_ollama_url"],
        chat_model=st.session_state["setting_chat_model"],
        embedding_model=st.session_state["setting_embedding_model"],
    )


def make_messages(
    question: str,
    passages: list[dict[str, str]],
    previous_turns: list[dict[str, str]],
    glossary_entries: list[GlossaryEntry],
    settings: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    if settings is None:
        initialize_settings()
        message_settings = {
            "reply_language": st.session_state["setting_reply_language"],
            "mood": st.session_state["setting_mood"],
        }
    else:
        message_settings = settings
    return build_messages(
        question,
        passages,
        previous_turns,
        glossary_entries,
        mood=message_settings.get("mood", "😌 Calm"),
        reply_language=message_settings.get(
            "reply_language", "Auto (match my message)"
        ),
    )
