from __future__ import annotations

import atexit

import streamlit as st

from jarvis.browser import BrowserError, BrowserPage, FirefoxBrowser
from jarvis.ui_common import render_current_privacy_status, render_error


def render_browser_page() -> None:
    render_current_privacy_status()
    with st.container(width=760):
        _render_browser_page_content()


def _render_browser_page_content() -> None:
    st.title("Browser")
    st.write(
        "Jeff can open a page in a separate Firefox profile and read its visible text. "
        "The first version is read-only: it will not click buttons, fill forms, or submit anything."
    )
    with st.container(border=True):
        st.markdown("**A separate Firefox profile**")
        st.caption(
            "Jeff uses `~/.jeff/firefox_jeff_profile`, separate from your everyday "
            "Firefox profile. Sign in to sites in this Jeff profile yourself."
        )

    controller = st.session_state.get("firefox_browser_controller")
    if controller is None or not controller.running:
        if st.button("Start Jeff's Firefox", type="primary", key="start_firefox_browser"):
            try:
                with st.spinner("Starting Firefox Developer Edition…"):
                    controller = FirefoxBrowser()
                    controller.start()
                atexit.register(controller.stop)
                st.session_state["firefox_browser_controller"] = controller
                st.success("Firefox is ready. Open a page or sign in to a site in this Jeff profile.")
                st.rerun()
            except BrowserError as exc:
                render_error(exc, action="Install Firefox Developer Edition and try again.")
        return

    st.success("Jeff's separate Firefox session is running.")
    address = st.text_input(
        "Website address",
        placeholder="https://example.com",
        key="browser_url",
    )
    if st.button("Open this page", key="open_browser_page", type="primary"):
        try:
            with st.spinner("Opening the page in Firefox…"):
                current_url = controller.navigate(address)
            st.session_state["browser_page_preview"] = None
            st.success(f"Firefox opened {current_url}")
        except BrowserError as exc:
            render_error(exc)

    if st.button("Read visible page text", key="read_browser_page"):
        try:
            st.session_state["browser_page_preview"] = controller.read_current_page()
            st.session_state["browser_page_revision"] = (
                st.session_state.get("browser_page_revision", 0) + 1
            )
        except BrowserError as exc:
            render_error(exc)

    page: BrowserPage | None = st.session_state.get("browser_page_preview")
    if page:
        st.subheader(page.title or "Current page")
        st.caption(page.url)
        st.text_area(
            "Page text preview (kept in this Streamlit session)",
            value=page.text,
            height=220,
            disabled=True,
            key=f"browser_page_text_preview_{st.session_state.get('browser_page_revision', 0)}",
        )
        st.caption("Reading is local. Page text is sent to Ollama only if you add it to a chat message.")
        if st.button("Add this page to my next chat", key="add_browser_context"):
            st.session_state["browser_chat_context"] = {
                "title": page.title,
                "url": page.url,
                "text": page.text,
            }
            st.success("Page context is ready. It will be sent with your next chat message.")

    context = st.session_state.get("browser_chat_context")
    if context:
        st.info(f"Next chat will include: {context['title'] or context['url']}")
        if st.button("Remove page from next chat", key="remove_browser_context"):
            st.session_state.pop("browser_chat_context", None)
            st.rerun()

    if st.button("Stop Jeff's Firefox", key="stop_firefox_browser"):
        try:
            controller.stop()
            st.session_state.pop("firefox_browser_controller", None)
            st.session_state.pop("browser_page_preview", None)
            st.success("Jeff's Firefox session is closed. Its sign-in remains in the dedicated Jeff profile.")
            st.rerun()
        except BrowserError as exc:
            render_error(exc)
