from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable


class VpnError(RuntimeError):
    """A plain-language VPN control error with its original detail preserved."""

    def __init__(self, message: str, technical_details: str = "") -> None:
        super().__init__(message)
        self.technical_details = technical_details


@dataclass(frozen=True)
class VpnConnection:
    service_id: str
    label: str
    status: str


_SERVICE_LINE = re.compile(
    r'^\s*\*?\s*\((?P<state>[^)]+)\)\s+'
    r'(?P<id>[0-9A-Fa-f-]{36})\s+'
    r'VPN \(org\.openvpn\.client\.app\)\s+"(?P<label>.*)$'
)
_COUNTRY_NAMES = {
    "ca": "Canada",
    "jp": "Japan",
    "us": "United States",
    "nl": "Netherlands",
    "pl": "Poland",
    "ro": "Romania",
    "no": "Norway",
    "ch": "Switzerland",
    "sg": "Singapore",
    "mx": "Mexico",
}
_COUNTRY_ALIASES = {
    "canada": "Canada",
    "japan": "Japan",
    "united states": "United States",
    "usa": "United States",
    "us": "United States",
}


def requested_vpn_action(question: str) -> tuple[str, str | None] | None:
    """Recognize clear, literal VPN requests without asking an LLM to interpret them."""
    normalized = re.sub(r"[^a-z0-9]+", " ", question.casefold()).strip()
    if re.search(r"\b(disconnect|turn off|stop)\b.*\b(vpn|tunnel)\b|\b(vpn|tunnel)\b.*\b(disconnect|off)\b", normalized):
        return ("disconnect", None)
    has_action = bool(re.search(r"\b(connect|switch|change|move|set|use)\b", normalized))
    has_location_context = bool(re.search(r"\b(vpn|location|server|country)\b", normalized)) or any(
        re.search(rf"\b{re.escape(alias)}\b", normalized) for alias in _COUNTRY_ALIASES
    )
    if not has_action or not has_location_context:
        return None
    for alias, country_name in _COUNTRY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return ("connect", country_name)
    return ("connect", "")


def _run_scutil(
    arguments: list[str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    try:
        result = runner(
            ["scutil", "--nc", *arguments],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        raise VpnError(
            "Jeff could not reach macOS's VPN controls. Check that this is a Mac and try again.",
            str(exc),
        ) from exc
    if result.returncode:
        details = (result.stderr or result.stdout).strip()
        raise VpnError(
            "macOS could not complete that VPN request. Check the profile in System Settings → VPN.",
            details,
        )
    return result.stdout


def _friendly_label(raw_label: str, index: int) -> str:
    country_match = re.search(r"\[([a-z]{2})-free-\d+", raw_label, re.IGNORECASE)
    if country_match:
        country = _COUNTRY_NAMES.get(country_match.group(1).lower())
        if country:
            return f"{country} (Proton Free)"
    return f"OpenVPN connection {index}"


def _service_ids(output: str) -> list[tuple[str, str]]:
    services: list[tuple[str, str]] = []
    for line in output.splitlines():
        match = _SERVICE_LINE.match(line)
        if match:
            services.append((match.group("id"), _friendly_label(match.group("label"), len(services) + 1)))
    return services


def _require_macos() -> None:
    if sys.platform != "darwin":
        raise VpnError("Jeff's built-in VPN controls currently work on macOS only.")


def _read_services(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[VpnConnection]:
    _require_macos()
    services = _service_ids(_run_scutil(["list"], runner))
    connections: list[VpnConnection] = []
    for service_id, label in services:
        status_output = _run_scutil(["status", service_id], runner)
        status = status_output.splitlines()[0].strip() if status_output.splitlines() else "Unknown"
        connections.append(VpnConnection(service_id, label, status))
    return connections


def list_connections(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[VpnConnection]:
    """List only OpenVPN Connect profiles registered with macOS."""
    return _read_services(runner)


def _validate_service(
    service_id: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> VpnConnection:
    if not re.fullmatch(r"[0-9A-Fa-f-]{36}", service_id):
        raise VpnError("That VPN profile is not recognized. Refresh the list and try again.")
    connection = next(
        (item for item in _read_services(runner) if item.service_id.lower() == service_id.lower()),
        None,
    )
    if connection is None:
        raise VpnError("Jeff could not find that OpenVPN profile in macOS. Refresh the list and try again.")
    return connection


def connect(
    service_id: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Start one selected OpenVPN Connect profile; never pass credentials on argv."""
    _require_macos()
    connection = _validate_service(service_id, runner)
    if connection.status.casefold() != "disconnected":
        if connection.status.casefold() == "connected":
            return connection.status
        raise VpnError(f"{connection.label} is already {connection.status.lower()}. Refresh its status before trying again.")
    if any(
        item.service_id.lower() != connection.service_id.lower()
        and item.status.casefold() != "disconnected"
        for item in _read_services(runner)
    ):
        raise VpnError("Another VPN is already connected. Disconnect it in Jeff or System Settings first.")
    _run_scutil(["start", connection.service_id], runner)
    refreshed = _validate_service(connection.service_id, runner)
    return refreshed.status


def disconnect(
    service_id: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Stop one selected OpenVPN Connect profile."""
    _require_macos()
    connection = _validate_service(service_id, runner)
    _run_scutil(["stop", connection.service_id], runner)
    refreshed = _validate_service(connection.service_id, runner)
    return refreshed.status
