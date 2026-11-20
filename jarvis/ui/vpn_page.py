from __future__ import annotations

import streamlit as st

from jarvis.ui_common import render_current_privacy_status, render_error
from jarvis.vpn import VpnConnection, VpnError, connect, disconnect, list_connections


def _status_text(status: str) -> str:
    normalized = status.casefold()
    if normalized == "connected":
        return "Connected"
    if normalized == "disconnected":
        return "Disconnected"
    if "connect" in normalized:
        return "Connecting"
    return status


def _render_connection(connection: VpnConnection, connections: list[VpnConnection]) -> None:
    with st.container(border=True):
        st.subheader(connection.label)
        st.write(f"Status: **{_status_text(connection.status)}**")
        if connection.status.casefold() == "connected":
            if st.button("Disconnect", key=f"vpn_disconnect_{connection.service_id}"):
                try:
                    st.session_state["vpn_action_notice"] = (
                        f"{connection.label}: {_status_text(disconnect(connection.service_id))}."
                    )
                    st.rerun()
                except VpnError as exc:
                    render_error(exc)
            return

        active = next(
            (
                item
                for item in connections
                if item.service_id != connection.service_id
                and item.status.casefold() != "disconnected"
            ),
            None,
        )
        busy = connection.status.casefold() != "disconnected"
        if active:
            st.caption(f"Disconnect {active.label} before connecting to another profile.")
        elif busy:
            st.caption("The connection is still starting. Refresh the status in a moment.")
        else:
            if st.button(f"Connect to {connection.label}", type="primary", key=f"vpn_connect_{connection.service_id}"):
                try:
                    st.session_state["vpn_action_notice"] = (
                        f"{connection.label}: {_status_text(connect(connection.service_id))}."
                    )
                    st.rerun()
                except VpnError as exc:
                    render_error(exc)


def render_vpn_page() -> None:
    render_current_privacy_status()
    with st.container(width=760):
        st.title("VPN location")
        st.write(
            "Choose one of your OpenVPN Connect profiles. Jeff uses macOS's registered VPN service "
            "to connect or disconnect; your credentials stay in OpenVPN Connect."
        )
        st.warning(
            "A VPN changes network routing for the whole Mac, not just Firefox. "
            "After connecting, reload the webpage. A site may use browser location, account details, "
            "or other signals instead of your VPN's IP location."
        )
        notice = st.session_state.pop("vpn_action_notice", None)
        if notice:
            st.info(notice)

        if st.button("Refresh VPN status", key="vpn_refresh"):
            st.rerun()

        try:
            connections = list_connections()
        except VpnError as exc:
            render_error(exc)
            return

        if not connections:
            st.info(
                "Jeff couldn't find an OpenVPN Connect profile in macOS. Open OpenVPN Connect, "
                "approve its VPN permission if prompted, and check System Settings → VPN."
            )
            return

        for connection in connections:
            _render_connection(connection, connections)
