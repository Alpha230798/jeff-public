from __future__ import annotations

import streamlit as st


def render_public_preview() -> None:
    st.title("Jeff")
    st.subheader("A local-first assistant for documents, language, and ideas.")
    st.info(
        "This public preview is read-only. Live chat, file uploads, and personal "
        "data features are disabled."
    )

    st.header("A sample interaction")
    with st.container(border=True):
        st.markdown("**Example question**")
        st.write("What does my indexed document say about energy use?")
        st.markdown("**Example response**")
        st.write(
            "In the full app, Jeff retrieves relevant document passages and cites "
            "their sources. This preview uses a static example; it does not process "
            "questions or documents."
        )

    st.header("Features in the desktop app")
    features = st.columns(2)
    with features[0]:
        st.markdown("**Document Q&A**")
        st.write("Ask about PDF, DOCX, TXT, and Markdown files with cited passages.")
        st.markdown("**Personal language tools**")
        st.write("Keep a private Mauritian Kreol glossary and spelling preferences.")
        st.markdown("**Private by default**")
        st.write("The desktop app uses Ollama on your Mac by default.")
    with features[1]:
        st.markdown("**Constrained browser companion**")
        st.write("Choose when to share a page excerpt and confirm limited actions.")
        st.markdown("**macOS VPN controls**")
        st.write("Review registered profiles and confirm before connecting.")
        st.markdown("**Network status**")
        st.write("See connectivity and an estimated download speed in the app.")

    st.header("Privacy")
    st.write(
        "This preview makes no model calls, accepts no prompts or files, and does "
        "not write user content to disk. The hosting provider may retain standard "
        "service access logs."
    )
    st.link_button(
        "View the source on GitHub",
        "https://github.com/Alpha230798/jeff-public",
    )


st.set_page_config(page_title="Jeff | Public Preview", page_icon="J", layout="centered")
st.navigation(
    [st.Page(render_public_preview, title="Public preview")],
    position="hidden",
).run()
