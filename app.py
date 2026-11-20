from __future__ import annotations

from pathlib import Path

import streamlit as st

from jarvis.ui_state import initialize_settings

APP_ROOT = Path(__file__).resolve().parent
JEFF_ICON = APP_ROOT / "assets" / "jeff-icon.svg"

st.set_page_config(
    page_title="Jeff | Local Assistant",
    page_icon=str(JEFF_ICON),
    layout="wide",
)
initialize_settings()
st.logo(str(JEFF_ICON), size="small", icon_image=str(JEFF_ICON))
with st.sidebar:
    st.markdown("**Jeff**")
    st.caption("Your local assistant")

pages = {
    "Jeff": [
        st.Page("pages/chat.py", title="Chat", icon=":material/chat_bubble_outline:", default=True),
        st.Page("pages/browser.py", title="Browser", icon=":material/language:"),
        st.Page("pages/vpn.py", title="VPN location", icon=":material/vpn_key:"),
        st.Page("pages/documents.py", title="Documents", icon=":material/folder_open:"),
        st.Page("pages/glossary.py", title="Kreol Glossary", icon=":material/menu_book:"),
        st.Page("pages/settings.py", title="Settings", icon=":material/settings:"),
    ]
}
st.navigation(pages, position="sidebar").run()
