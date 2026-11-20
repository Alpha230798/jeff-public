from __future__ import annotations

from pathlib import Path

import streamlit as st

from jarvis.glossary import GlossaryError, list_entries, relevant_entries
from jarvis.ollama import OllamaError
from jarvis.retrieval import cosine_similarity
from jarvis.ui.content import make_messages, new_client, select_reply_language
from jarvis.ui_common import (
    check_ollama_models,
    render_current_privacy_status,
    render_error,
    setup_is_ready,
)
from jarvis.ui.content import DICTIONARY_ENTRIES
from jarvis.ui.spelling import uncertain_spelling_suggestions
from jarvis.vpn import VpnError, connect as connect_vpn, disconnect as disconnect_vpn
from jarvis.vpn import list_connections as list_vpn_connections, requested_vpn_action
from phonetic import SpellingIndex, load_variants

CHAT_INPUT_KEY = "chat_prompt_input"
CHAT_SUGGESTIONS = (
    (
        "Ask about a document",
        "What does my indexed document say about …?",
    ),
    (
        "Teach Jeff a Kreol word",
        "Help me add a Kreol word with its English and French meanings.",
    ),
    (
        "Write something in French",
        "Help me write a polite message in French.",
    ),
)
JEFF_ICON = str(Path(__file__).resolve().parents[2] / "assets" / "jeff-icon.svg")


def _check_setup() -> None:
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


def _render_setup_banner() -> None:
    status = st.session_state.get("ollama_status")
    if setup_is_ready(status):
        return
    with st.container(border=True):
        st.markdown("**Let's get Jeff ready**")
        st.caption("A quick setup check confirms the Ollama connection and selected models.")
        if st.button("Check Ollama setup", key="chat_check_setup"):
            _check_setup()
            status = st.session_state.get("ollama_status")
        if status and status.get("error"):
            render_error(OllamaError(status["error"]))
        reachable = bool(status and status.get("reachable"))
        rows = [
            ("Ollama reachable", reachable, "Not checked" if status is None else "Not reachable"),
            (
                f"Chat model present: {st.session_state['setting_chat_model']}",
                bool(status and status.get("chat_model_present")),
                "Not checked" if status is None else "Not found",
            ),
            (
                f"Embedding model present: {st.session_state['setting_embedding_model']}",
                bool(status and status.get("embedding_model_present")),
                "Not checked" if status is None else "Not found",
            ),
        ]
        for label, ready, pending in rows:
            st.write(f"{'✓' if ready else '○'} {label}: {'Ready' if ready else pending}")
        st.caption("You can change the server or model names in Settings.")
        if status and status.get("reachable") and not setup_is_ready(status):
            st.caption("For a missing model, run `ollama pull <model name>` in Terminal, then check again.")


def _render_spelling_suggestions() -> None:
    pending = st.session_state.get("pending_spelling_suggestions", [])
    notice = st.session_state.pop("spelling_notice", None)
    if notice:
        st.success(notice)
    if not pending:
        return
    with st.expander("Did you mean…? Jeff is unsure about a spelling", expanded=False):
        st.caption("Choose a meaning only if it matches what you intended. Jeff saves it only after your click.")
        for suggestion_number, suggestion in enumerate(pending):
            variant = str(suggestion["variant"])
            st.write(f"Did you mean one of these for **{variant}**?")
            choices = list(suggestion["candidates"])
            columns = st.columns(max(1, len(choices) + 1))
            for index, canonical in enumerate(choices):
                with columns[index]:
                    if st.button(
                        f"Remember {canonical}",
                        key=f"remember_spelling_{suggestion_number}_{index}",
                        help=f"Save {variant} as your spelling for {canonical} on this computer.",
                    ):
                        try:
                            SpellingIndex(DICTIONARY_ENTRIES, load_variants()).learn(
                                variant, str(canonical)
                            )
                            st.session_state["pending_spelling_suggestions"] = [
                                item for item in pending if item["variant"] != variant
                            ]
                            st.session_state["spelling_notice"] = (
                                f"Saved your spelling: {variant} means {canonical}."
                            )
                        except OSError as exc:
                            render_error(
                                exc,
                                action="Check that Jeff can write to the local spelling-memory file.",
                            )
                        else:
                            st.rerun()
            with columns[-1]:
                if st.button("Skip", key=f"skip_spelling_{suggestion_number}"):
                    st.session_state["pending_spelling_suggestions"] = [
                        item for item in pending if item["variant"] != variant
                    ]
                    st.rerun()


def _render_empty_state() -> None:
    name = str(st.session_state.get("setting_name", "")).strip()
    greeting = f"Hello {name}, how can I help?" if name else "Hello, how can I help?"
    st.title(greeting)
    st.caption("Your private assistant for questions, documents, and ideas.")
    st.write("Try one of these to get started:")
    columns = st.columns(2)
    for index, (label, prompt) in enumerate(CHAT_SUGGESTIONS):
        with columns[index % 2]:
            if st.button(label, key=f"chat_suggestion_{index}", width="stretch"):
                st.session_state[CHAT_INPUT_KEY] = prompt
                st.rerun()


def _render_pending_vpn_action() -> None:
    pending = st.session_state.get("pending_vpn_action")
    if not pending:
        return
    with st.container(border=True):
        if pending["action"] == "connect":
            st.markdown(f"**Confirm connection to {pending['label']}?**")
        else:
            st.markdown(f"**Confirm disconnect from {pending['label']}?**")
        st.caption("This changes the Mac's VPN connection for all apps, not just Firefox.")
        confirm, cancel = st.columns(2)
        with confirm:
            button_label = "Connect" if pending["action"] == "connect" else "Disconnect"
            if st.button(button_label, key="confirm_vpn_action", type="primary"):
                try:
                    action = connect_vpn if pending["action"] == "connect" else disconnect_vpn
                    status = action(pending["service_id"])
                    if pending["action"] == "connect":
                        if status.casefold() == "connected":
                            outcome = (
                                f"Connected to {pending['label']}. Reload the webpage to check its "
                                "IP-based location; sites may use other signals."
                            )
                        else:
                            outcome = (
                                f"The {pending['label']} connection is {status.lower()}. "
                                "Check the VPN page before relying on the new location."
                            )
                    else:
                        outcome = (
                            f"Disconnected from {pending['label']}."
                            if status.casefold() == "disconnected"
                            else f"The {pending['label']} connection is {status.lower()}."
                        )
                    st.session_state["conversation"].append(
                        {
                            "role": "assistant",
                            "content": outcome,
                        }
                    )
                    st.session_state.pop("pending_vpn_action", None)
                    st.rerun()
                except VpnError as exc:
                    render_error(exc)
        with cancel:
            if st.button("Cancel", key="cancel_vpn_action"):
                st.session_state["conversation"].append(
                    {"role": "assistant", "content": "Cancelled. I did not change the VPN connection."}
                )
                st.session_state.pop("pending_vpn_action", None)
                st.rerun()


def _route_vpn_request(question: str) -> bool:
    request = requested_vpn_action(question)
    if request is None:
        return False
    action, target = request
    conversation = st.session_state.setdefault("conversation", [])
    conversation.append({"role": "user", "content": question})
    try:
        connections = list_vpn_connections()
    except VpnError as exc:
        conversation.append(
            {"role": "assistant", "content": "I couldn't check your VPN profiles. See the technical details below."}
        )
        st.session_state["conversation"] = conversation[-20:]
        st.session_state["vpn_chat_error"] = {
            "message": str(exc),
            "technical_details": exc.technical_details,
        }
        st.rerun()

    if action == "disconnect":
        active = [item for item in connections if item.status.casefold() == "connected"]
        if not active:
            reply = "No OpenVPN profile appears to be connected, so I left the VPN unchanged."
        elif len(active) > 1:
            reply = "More than one VPN reports connected. Disconnect the extra connection in System Settings → VPN first."
        else:
            selected = active[0]
            st.session_state["pending_vpn_action"] = {
                "action": "disconnect",
                "service_id": selected.service_id,
                "label": selected.label,
            }
            reply = f"I found {selected.label}. Please confirm before I disconnect it."
    elif not target:
        reply = "Which saved location would you like to use: Japan, Canada, or the United States?"
    else:
        selected = next(
            (item for item in connections if item.label.casefold().startswith(target.casefold())),
            None,
        )
        if selected is None:
            reply = f"I couldn't find a saved OpenVPN profile for {target}. No VPN change was made."
        elif selected.status.casefold() == "connected":
            reply = f"{selected.label} is already connected. Reload the webpage if you want it to check the VPN IP again."
        elif selected.status.casefold() != "disconnected":
            reply = f"{selected.label} is {selected.status.lower()}. Refresh the VPN page before trying again."
        else:
            st.session_state["pending_vpn_action"] = {
                "action": "connect",
                "service_id": selected.service_id,
                "label": selected.label,
            }
            reply = f"I found {selected.label}. Please confirm before I connect it."
    conversation.append({"role": "assistant", "content": reply})
    st.session_state["conversation"] = conversation[-20:]
    st.rerun()
    return True


def render_chat_page() -> None:
    render_current_privacy_status()
    _render_setup_banner()
    browser_context = st.session_state.get("browser_chat_context")
    if browser_context:
        st.info(f"Next message will include this browser page: {browser_context['title'] or browser_context['url']}")
        if st.button("Remove browser page context", key="chat_remove_browser_context"):
            st.session_state.pop("browser_chat_context", None)
            st.rerun()

    conversation = st.session_state.setdefault("conversation", [])
    with st.container(width=760):
        if not conversation:
            _render_empty_state()
        else:
            st.title("Chat")
        st.caption(
            f"{st.session_state['setting_reply_language']} · "
            f"Mood: {st.session_state['setting_mood']} · "
            "automatic language detection is approximate."
        )
        for turn in conversation:
            with st.chat_message(
                turn["role"],
                avatar=JEFF_ICON if turn["role"] == "assistant" else None,
            ):
                st.markdown(turn["content"])
        _render_pending_vpn_action()
        vpn_error = st.session_state.pop("vpn_chat_error", None)
        if vpn_error:
            render_error(VpnError(vpn_error["message"], vpn_error["technical_details"]))
        _render_spelling_suggestions()
        question = st.chat_input("Message Jeff…", key=CHAT_INPUT_KEY)
    if not question:
        return
    if _route_vpn_request(question):
        return

    with st.container(width=760), st.chat_message("user"):
        st.markdown(question)
    conversation.append({"role": "user", "content": question})
    st.session_state["conversation"] = conversation[-20:]
    st.session_state["pending_spelling_suggestions"] = uncertain_spelling_suggestions(
        question,
        DICTIONARY_ENTRIES,
        load_variants(),
    )
    try:
        try:
            entries = list_entries()
        except GlossaryError as exc:
            render_error(exc, action="Jeff can still answer, but the local glossary could not be included.")
            entries = []
        relevant_glossary = relevant_entries(question, entries)
        retrieved: list[dict[str, str]] = []
        client = new_client()
        index = st.session_state.get("document_index")
        if index:
            query_vector = client.embed([question])[0]
            ranked = sorted(
                zip(index["chunks"], index["vectors"]),
                key=lambda pair: cosine_similarity(query_vector, pair[1]),
                reverse=True,
            )[:5]
            retrieved = [
                {
                    "citation": f"S{position}",
                    "source": chunk.source_label,
                    "text": chunk.text,
                }
                for position, (chunk, _) in enumerate(ranked, start=1)
            ]
        browser_context = st.session_state.get("browser_chat_context")
        if browser_context:
            retrieved.append(
                {
                    "citation": "B1",
                    "source": f"Firefox page: {browser_context['title']} ({browser_context['url']})",
                    "text": browser_context["text"],
                }
            )

        with st.container(width=760), st.chat_message(
            "assistant",
            avatar=JEFF_ICON,
        ):
            selected_language = select_reply_language(
                question,
                st.session_state["setting_reply_language"],
            )
            thinking = "Jeff réfléchit…" if selected_language == "French" else "Jeff is thinking…"
            with st.spinner(thinking):
                answer = client.chat(
                    make_messages(question, retrieved, conversation[:-1], relevant_glossary)
                )
            st.markdown(answer)
            if retrieved:
                with st.expander("Sources Jeff used"):
                    for passage in retrieved:
                        st.markdown(f"**[{passage['citation']}] {passage['source']}**")
                        st.caption(passage["text"])
            if relevant_glossary:
                with st.expander("Kreol glossary entries used"):
                    for entry in relevant_glossary:
                        st.markdown(f"**{entry.kreol_phrase}**")
                        if entry.alternative_spellings:
                            st.caption(f"Also written: {entry.alternative_spellings}")
                        if entry.english_meaning:
                            st.caption(f"English: {entry.english_meaning}")
                        if entry.french_meaning:
                            st.caption(f"French: {entry.french_meaning}")
                        if entry.example:
                            st.text(f"Example: {entry.example}")
        conversation.append({"role": "assistant", "content": answer})
        st.session_state["conversation"] = conversation[-20:]
        st.session_state.pop("browser_chat_context", None)
    except OllamaError as exc:
        render_error(exc)
        st.session_state["conversation"] = conversation[-20:]
    _render_spelling_suggestions()
