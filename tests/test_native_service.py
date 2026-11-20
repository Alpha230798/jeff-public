from __future__ import annotations

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from jarvis.conversation import build_messages
from jarvis.native_service import APIError, DEFAULT_SETTINGS, NativeBackend, NativeServiceServer


class NativeSettingsTests(unittest.TestCase):
    def test_settings_accept_only_loopback_ollama_addresses(self):
        settings = NativeBackend.settings(DEFAULT_SETTINGS)
        self.assertEqual(settings["ollama_url"], "http://localhost:11434")
        for address in (
            "http://127.0.0.1:11434/",
            "https://[::1]:11434",
        ):
            updated = NativeBackend.settings(DEFAULT_SETTINGS | {"ollama_url": address})
            self.assertTrue(updated["ollama_url"].startswith(("http://", "https://")))

        with self.assertRaisesRegex(APIError, "only connects to an Ollama server on this Mac"):
            NativeBackend.settings(DEFAULT_SETTINGS | {"ollama_url": "http://ollama.lan:11434"})

    def test_invalid_mood_and_language_are_rejected(self):
        with self.assertRaises(APIError):
            NativeBackend.settings(DEFAULT_SETTINGS | {"mood": []})
        with self.assertRaises(APIError):
            NativeBackend.settings(DEFAULT_SETTINGS | {"reply_language": "Kreol"})

    def test_chat_route_uses_native_settings_and_returns_context_metadata(self):
        class FakeClient:
            @staticmethod
            def chat(messages):
                return "A local reply."

        payload = {
            "question": "Bonjour",
            "history": [],
            "settings": DEFAULT_SETTINGS | {
                "mood": "😊 Happy",
                "reply_language": "French",
            },
        }
        with (
            patch.object(NativeBackend, "client", return_value=FakeClient()),
            patch("jarvis.native_service.list_entries", return_value=[]),
            patch("jarvis.native_service.build_messages", return_value=[]) as builder,
            patch("jarvis.native_service.uncertain_spelling_suggestions", return_value=[]),
        ):
            status, response = NativeBackend().handle("POST", "/api/chat", payload)

        self.assertEqual(status, 200)
        self.assertEqual(response["answer"], "A local reply.")
        self.assertEqual(response["passages"], [])
        self.assertEqual(response["glossary_entries"], [])
        self.assertEqual(response["spelling_suggestions"], [])
        self.assertEqual(builder.call_args.kwargs["mood"], "😊 Happy")
        self.assertEqual(builder.call_args.kwargs["reply_language"], "French")

    def test_native_message_builder_does_not_read_streamlit_session_state(self):
        with patch("jarvis.ui_state.initialize_settings", side_effect=AssertionError):
            messages = build_messages(
                "Bonjour, comment ça va?",
                [],
                [],
                [],
                mood="😊 Happy",
                reply_language="Auto (match my message)",
            )
        self.assertIn("écris uniquement en français", messages[0]["content"])
        self.assertIn("happy, upbeat mood", messages[0]["content"])


class NativeServiceAuthTests(unittest.TestCase):
    def setUp(self):
        self.token = "a" * 64
        self.backend = NativeBackend()
        self.server = NativeServiceServer(("127.0.0.1", 0), self.token, self.backend)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.backend.close()
        self.thread.join(timeout=2)

    def test_service_requires_token_even_for_health_checks(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(f"{self.base_url}/api/health", timeout=2)
        self.assertEqual(error.exception.code, 401)

        request = Request(
            f"{self.base_url}/api/health",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(payload, {"ok": True})
            self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

