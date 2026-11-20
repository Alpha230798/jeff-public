from __future__ import annotations

from urllib.parse import urlparse

import streamlit as st


DEFAULT_SETTINGS = {
    "setting_ollama_url": "http://localhost:11434",
    "setting_chat_model": "qwen2.5:3b",
    "setting_embedding_model": "bge-m3",
    "setting_mood": "😌 Calm",
    "setting_reply_language": "Auto (match my message)",
}

LEGACY_SETTINGS = {
    "setting_ollama_url": "ollama_url",
    "setting_chat_model": "chat_model_v2",
    "setting_embedding_model": "embedding_model",
    "setting_mood": "user_mood",
}


def initialize_settings() -> None:
    """Load persistent app-owned settings, migrating the original widget keys."""
    for key, default in DEFAULT_SETTINGS.items():
        old_key = LEGACY_SETTINGS.get(key)
        old_value = st.session_state.get(old_key) if old_key else None
        st.session_state.setdefault(key, old_value or default)
    if st.session_state["setting_reply_language"] not in {
        "Auto (match my message)",
        "English",
        "French",
    }:
        st.session_state["setting_reply_language"] = "Auto (match my message)"
    st.session_state.setdefault("ollama_status", None)


def setting_widget(key: str) -> str:
    """Create a page-local widget value from the persistent setting when needed."""
    widget_key = f"widget_{key}"
    st.session_state.setdefault(widget_key, st.session_state[key])
    return widget_key


def persist_setting(key: str) -> None:
    st.session_state[key] = st.session_state[f"widget_{key}"]
    if key in {"setting_ollama_url", "setting_chat_model", "setting_embedding_model"}:
        st.session_state["ollama_status"] = None


def is_local_server(url: str) -> bool:
    try:
        hostname = (urlparse(url if "://" in url else f"http://{url}").hostname or "").lower()
    except ValueError:
        return False
    return hostname in {"localhost", "127.0.0.1", "::1"}
