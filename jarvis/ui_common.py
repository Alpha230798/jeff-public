from __future__ import annotations

import streamlit as st

from jarvis.documents import DocumentError
from jarvis.browser import BrowserError
from jarvis.glossary import GlossaryError
from jarvis.glossary_import import GlossaryImportError
from jarvis.ollama import OllamaError
from jarvis.vpn import VpnError
from jarvis.ui_state import is_local_server
from jarvis.ui_state import initialize_settings


def render_privacy_status(url: str) -> None:
    if is_local_server(url):
        st.caption("Connection: localhost — your data stays on this computer.")
    else:
        st.warning(
            f"Remote Ollama server: {url}. Chat messages, relevant glossary entries, "
            "document excerpts, and webpage text you choose to use in chat are sent to this server."
        )


def render_current_privacy_status() -> None:
    initialize_settings()
    with st.sidebar:
        render_privacy_status(st.session_state["setting_ollama_url"])


def render_error(error: Exception, *, action: str = "Please check your settings and try again.") -> None:
    detail = str(error).strip() or error.__class__.__name__
    if error.__cause__:
        detail = f"{detail}\n{error.__cause__}"
    if isinstance(error, VpnError):
        detail = error.technical_details or detail
        title = str(error)
    elif isinstance(error, OllamaError):
        if "Could not reach Ollama" in detail:
            title = "Jeff could not reach Ollama. Start Ollama and check the server address in Settings."
        elif "HTTP 404" in detail or "not found" in detail.casefold():
            title = "Ollama could not find that model. Check its name in Settings and pull it in Ollama if needed."
        elif "within" in detail and "seconds" in detail:
            title = "Ollama took too long to respond. Try a smaller model or check that Ollama is still running."
        else:
            title = "Ollama could not complete that request. Check the connection and selected models."
    elif isinstance(error, DocumentError):
        title = "Jeff could not read one of those files. Check that it is a supported file with selectable text."
    elif isinstance(error, BrowserError):
        title = str(error)
    elif isinstance(error, GlossaryImportError):
        title = "Jeff could not prepare glossary entries from that PDF. Check that it has selectable vocabulary text and try again."
    elif isinstance(error, GlossaryError):
        if detail.startswith("Enter a Kreol word or phrase"):
            title = "Add a Kreol word or phrase, then save the entry."
            action = ""
        elif detail.startswith("Enter an English or French meaning"):
            title = "Add an English or French meaning, then save the entry."
            action = ""
        elif "no longer exists" in detail:
            title = "That glossary entry is no longer available. Refresh the page and choose it again."
            action = ""
        else:
            title = "Jeff could not update the local glossary. Check the entry and try again."
    else:
        title = "Jeff could not finish that action. Please try again."
    st.error(f"{title} {action}".strip())
    with st.expander("Technical details"):
        st.code(detail)


def model_is_available(model_name: str, available_models: list[str]) -> bool:
    wanted = model_name.strip()
    if not wanted:
        return False
    names = set(available_models)
    return wanted in names or (":" not in wanted and f"{wanted}:latest" in names)


def check_ollama_models(client, chat_model: str, embedding_model: str) -> dict[str, object]:
    models = client.available_models()
    return {
        "reachable": True,
        "models": models,
        "chat_model_present": model_is_available(chat_model, models),
        "embedding_model_present": model_is_available(embedding_model, models),
        "error": "",
    }


def setup_is_ready(status: dict[str, object] | None) -> bool:
    return bool(
        status
        and status.get("reachable")
        and status.get("chat_model_present")
        and status.get("embedding_model_present")
    )
