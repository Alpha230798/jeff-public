from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from jarvis import vpn


SERVICE_CA = "917FFF2F-1C6B-4330-BB4F-67D38A05F522"
SERVICE_JP = "258AB41A-4B3F-4C6E-AD7B-4C639165838C"
SERVICE_US = "B32B7021-0C00-49FE-8EC4-0534848487C9"


def completed(stdout: str = "", returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class FakeScutil:
    def __init__(self) -> None:
        self.states = {
            SERVICE_CA: "Disconnected",
            SERVICE_JP: "Disconnected",
            SERVICE_US: "Disconnected",
        }
        self.calls: list[list[str]] = []

    def __call__(self, command, **_kwargs):
        self.calls.append(command)
        operation = command[2]
        if operation == "list":
            lines = ["Available network connection services in the current set:"]
            for service_id, host in (
                (SERVICE_CA, "109.204.35.233 [ca-free-2.protonvpn.udp"),
                (SERVICE_JP, "103.125.235.18 [jp-free-1.protonvpn.udp"),
                (SERVICE_US, "149.40.62.21 [us-free-5.protonvpn.udp"),
            ):
                lines.append(
                    f'  * ({self.states[service_id]}) {service_id} '
                    f'VPN (org.openvpn.client.app) "{host} [VPN:org.openvpn.client.app]'
                )
            return completed("\n".join(lines))
        if operation == "status":
            return completed(self.states[command[3]])
        if operation == "start":
            self.states[command[3]] = "Connected"
            return completed("Connection started")
        if operation == "stop":
            self.states[command[3]] = "Disconnected"
            return completed("Connection stopped")
        raise AssertionError(f"Unexpected scutil command: {command}")


class VpnControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.platform = patch.object(vpn.sys, "platform", "darwin")
        self.platform.start()
        self.addCleanup(self.platform.stop)

    def test_lists_only_openvpn_profiles_with_friendly_country_labels(self):
        fake = FakeScutil()
        connections = vpn.list_connections(fake)
        self.assertEqual(
            [(connection.label, connection.status) for connection in connections],
            [
                ("Canada (Proton Free)", "Disconnected"),
                ("Japan (Proton Free)", "Disconnected"),
                ("United States (Proton Free)", "Disconnected"),
            ],
        )

    def test_connect_starts_selected_profile_without_passing_credentials(self):
        fake = FakeScutil()
        status = vpn.connect(SERVICE_JP, fake)
        self.assertEqual(status, "Connected")
        self.assertIn(["scutil", "--nc", "start", SERVICE_JP], fake.calls)
        self.assertTrue(all("--password" not in part for call in fake.calls for part in call))

    def test_disconnect_stops_selected_profile(self):
        fake = FakeScutil()
        fake.states[SERVICE_CA] = "Connected"
        self.assertEqual(vpn.disconnect(SERVICE_CA, fake), "Disconnected")
        self.assertIn(["scutil", "--nc", "stop", SERVICE_CA], fake.calls)

    def test_refuses_to_connect_a_second_profile_while_another_is_active(self):
        fake = FakeScutil()
        fake.states[SERVICE_CA] = "Connected"
        with self.assertRaisesRegex(vpn.VpnError, "Another VPN is already connected"):
            vpn.connect(SERVICE_JP, fake)
        self.assertFalse(any(call[2] == "start" for call in fake.calls))

    def test_control_is_limited_to_macos(self):
        with patch.object(vpn.sys, "platform", "linux"):
            with self.assertRaisesRegex(vpn.VpnError, "macOS only"):
                vpn.list_connections()

    def test_only_clear_vpn_requests_are_interpreted_as_actions(self):
        self.assertEqual(
            vpn.requested_vpn_action("Change my VPN location to Japan"),
            ("connect", "Japan"),
        )
        self.assertEqual(vpn.requested_vpn_action("Connect to Canada"), ("connect", "Canada"))
        self.assertEqual(vpn.requested_vpn_action("disconnect VPN"), ("disconnect", None))
        self.assertIsNone(vpn.requested_vpn_action("Tell me about Japan"))


if __name__ == "__main__":
    unittest.main()
