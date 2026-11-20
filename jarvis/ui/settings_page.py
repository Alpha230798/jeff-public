from __future__ import annotations

import streamlit as st

from jarvis.ollama import OllamaError
from jarvis.ui.content import MOOD_OPTIONS, REPLY_LANGUAGE_OPTIONS, new_client
from jarvis.ui_common import check_ollama_models, render_current_privacy_status, render_error
from jarvis.ui_state import persist_setting, setting_widget


def render_settings_page() -> None:
    render_current_privacy_status()
    with st.container(width=760):
        st.title("Settings")
        with st.container(border=True):
            st.subheader("Ollama connection")
            for key, label, help_text in (
                (
                    "setting_ollama_url",
                    "Ollama server address",
                    "Usually http://localhost:11434 when Ollama runs on this computer.",
                ),
                ("setting_chat_model", "Chat model", "For example, qwen2.5:3b."),
                ("setting_embedding_model", "Embedding model", "For example, bge-m3."),
            ):
                st.text_input(
                    label,
                    key=setting_widget(key),
                    help=help_text,
                    on_change=lambda setting_key=key: persist_setting(setting_key),
                )

        with st.container(border=True):
            st.subheader("How Jeff replies")
            st.selectbox(
                "Mood",
                list(MOOD_OPTIONS),
                key=setting_widget("setting_mood"),
                on_change=lambda: persist_setting("setting_mood"),
                help="Mood guides tone for the current session; it is not saved as a long-term preference.",
            )
            st.selectbox(
                "Reply language",
                REPLY_LANGUAGE_OPTIONS,
                key=setting_widget("setting_reply_language"),
                on_change=lambda: persist_setting("setting_reply_language"),
                help="Auto uses a lightweight language guess based on your message. Results are not guaranteed.",
            )

        with st.container(border=True):
            st.subheader("Privacy")
            st.write(
                "Jeff sends chat prompts to the Ollama server shown above. When relevant, "
                "it also sends glossary entries and retrieved excerpts from documents. "
                "The glossary database stays on this computer; document indexes and chat "
                "history stay in this browser session."
            )
            st.write(
                "If the server address points to another computer, the chat messages, "
                "relevant glossary entries, document excerpts, and webpage text you choose "
                "to add to a chat go to that server. Only use an address you trust."
            )
            st.write(
                "Firefox page text stays in this browser session unless you choose "
                "**Add this page to my next chat**. That text is then sent with your next "
                "message to the configured Ollama server."
            )

        if st.button("Check connection and models", type="primary", key="settings_check_setup"):
            try:
                st.session_state["ollama_status"] = check_ollama_models(
                    new_client(),
                    st.session_state["setting_chat_model"],
                    st.session_state["setting_embedding_model"],
                )
            except OllamaError as exc:
                st.session_state["ollama_status"] = {
                    "reachable": False,
                    "models": [],
                    "chat_model_present": False,
                    "embedding_model_present": False,
                    "error": str(exc),
                }

        status = st.session_state.get("ollama_status")
        if status and status.get("reachable"):
            with st.container(border=True):
                st.subheader("Setup checklist")
                st.write(f"{'✓' if status['reachable'] else '○'} Ollama reachable")
                st.write(
                    f"{'✓' if status['chat_model_present'] else '○'} "
                    f"Chat model {st.session_state['setting_chat_model']} "
                    f"{'available' if status['chat_model_present'] else 'not found'}"
                )
                st.write(
                    f"{'✓' if status['embedding_model_present'] else '○'} "
                    f"Embedding model {st.session_state['setting_embedding_model']} "
                    f"{'available' if status['embedding_model_present'] else 'not found'}"
                )
                if not status["chat_model_present"] or not status["embedding_model_present"]:
                    st.info("To add a missing model, run `ollama pull <model name>` in Terminal, then check again.")
        elif status:
            render_error(OllamaError(status.get("error", "Could not reach Ollama.")))

        st.caption(
            "Jeff is currently set up to reply in English or French. "
            "Language detection and model quality can still vary."
        )
        st.caption("Use the app menu in the top-right corner to switch between light and dark appearance.")
