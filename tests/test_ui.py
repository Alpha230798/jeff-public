from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from jarvis.ollama import OllamaClient, OllamaError
from jarvis import conversation
from jarvis.ui import browser_page, chat_page, content
from jarvis.ui import glossary_page
from jarvis.ui import vpn_page
from jarvis.ui.spelling import uncertain_spelling_suggestions
from jarvis.ui_common import model_is_available
from jarvis.ui_state import is_local_server
from phonetic import SpellingIndex

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class SetupStatusTests(unittest.TestCase):
    def test_model_names_match_exact_tags_and_implicit_latest(self):
        available = ["qwen2.5:3b", "bge-m3:latest"]
        self.assertTrue(model_is_available("qwen2.5:3b", available))
        self.assertTrue(model_is_available("bge-m3", available))
        self.assertFalse(model_is_available("bge-m3:small", available))

    def test_privacy_status_recognizes_local_and_remote_addresses(self):
        for address in (
            "http://localhost:11434",
            "http://127.0.0.1:11434",
            "http://[::1]:11434",
        ):
            self.assertTrue(is_local_server(address))
        self.assertFalse(is_local_server("http://ollama.lan:11434"))

    def test_auto_reply_language_is_english_or_french_only(self):
        self.assertEqual(content.select_reply_language("Bonjour, comment ça va?", "Auto (match my message)"), "French")
        self.assertEqual(content.select_reply_language("Mo pe koz Kreol.", "Auto (match my message)"), "English")
        self.assertEqual(content.select_reply_language("Hello there.", "Auto (match my message)"), "English")
        self.assertNotIn("Mauritian Kreol", content.REPLY_LANGUAGE_OPTIONS)


class SpellingSuggestionTests(unittest.TestCase):
    def test_only_uncertain_spellings_are_suggested(self):
        entries = ["korek : correct; OK.", "manze [from Fre manger] : to eat."]
        self.assertEqual(uncertain_spelling_suggestions("mo pe manG", entries, {}), [])
        suggestions = uncertain_spelling_suggestions("mo pe krk", entries, {})
        self.assertEqual(suggestions[0]["variant"], "krk")
        self.assertIn("korek", suggestions[0]["candidates"])
        self.assertEqual(
            uncertain_spelling_suggestions("mo pe krk", entries, {"krk": "korek"}),
            [],
        )


class AppSmokeTests(unittest.TestCase):
    def test_all_pages_render_without_exceptions_with_ollama_mocked(self):
        with (
            patch.object(glossary_page, "list_entries", return_value=[]),
            patch.object(vpn_page, "list_connections", return_value=[]),
            patch.object(OllamaClient, "available_models", return_value=["qwen2.5:3b", "bge-m3"]),
            patch.object(OllamaClient, "chat", return_value="A mocked reply."),
            patch.object(OllamaClient, "embed", return_value=[[1.0, 0.0]]),
        ):
            app = AppTest.from_file(str(APP_PATH)).run()
            self.assertEqual(len(app.exception), 0, "Chat page")
            for page in (
                "pages/documents.py",
                "pages/glossary.py",
                "pages/browser.py",
                "pages/vpn.py",
                "pages/settings.py",
            ):
                app.switch_page(page).run()
                self.assertEqual(len(app.exception), 0, page)

    def test_browser_page_flow_uses_a_separate_profile_and_keeps_preview_local(self):
        class FakeBrowser:
            running = True

            def start(self):
                self.running = True

            @staticmethod
            def navigate(address):
                return address

            @staticmethod
            def read_current_page():
                from jarvis.browser import BrowserPage

                return BrowserPage("https://example.test", "Test page", "Private preview text")

            def stop(self):
                self.running = False

        with patch.object(browser_page, "FirefoxBrowser", return_value=FakeBrowser()) as factory:
            app = AppTest.from_file(str(APP_PATH)).run()
            app.switch_page("pages/browser.py").run()
            app.button(key="start_firefox_browser").click().run()
            factory.assert_called_once_with()
            self.assertTrue(app.session_state["firefox_browser_controller"].running)

            app.text_input(key="browser_url").set_value("https://example.test").run()
            app.button(key="open_browser_page").click().run()
            app.button(key="read_browser_page").click().run()
            self.assertEqual(app.session_state["browser_page_preview"].title, "Test page")
            self.assertNotIn("browser_chat_context", app.session_state)

            app.button(key="add_browser_context").click().run()
            self.assertEqual(app.session_state["browser_chat_context"]["text"], "Private preview text")

    def test_browser_page_reaches_ollama_only_with_the_next_chat_message(self):
        with (
            patch.object(chat_page, "list_entries", return_value=[]),
            patch.object(OllamaClient, "chat", return_value="Here is the summary.") as chat,
        ):
            app = AppTest.from_file(str(APP_PATH))
            app.session_state["browser_chat_context"] = {
                "title": "Test page",
                "url": "https://example.test",
                "text": "A private page excerpt.",
            }
            app.run()
            self.assertEqual(chat.call_count, 0)
            app.chat_input[0].set_value("Summarize this page").run()

        self.assertEqual(chat.call_count, 1)
        sent_messages = chat.call_args.args[0]
        self.assertIn("A private page excerpt.", sent_messages[-1]["content"])
        self.assertNotIn("browser_chat_context", app.session_state)

    def test_spelling_is_saved_only_after_explicit_confirmation(self):
        with (
            patch.object(chat_page, "list_entries", return_value=[]),
            patch.object(chat_page, "load_variants", return_value={}),
            patch.object(conversation, "load_variants", return_value={}),
            patch.object(OllamaClient, "chat", return_value="I think you mean korek."),
            patch.object(SpellingIndex, "learn") as remember,
        ):
            app = AppTest.from_file(str(APP_PATH)).run()
            app.chat_input[0].set_value("mo pe krk").run()
            remember.assert_not_called()

            app.button(key="remember_spelling_0_0").click().run()
            remember.assert_called_once_with("krk", "korek")

    def test_remote_privacy_warning_is_visible_on_each_page(self):
        with patch.object(glossary_page, "list_entries", return_value=[]):
            app = AppTest.from_file(str(APP_PATH))
            app.session_state["setting_ollama_url"] = "http://ollama.lan:11434"
            app.run()
            self.assertTrue(
                any("Remote Ollama server" in item.value for item in app.warning),
            )
            for page in (
                "pages/browser.py",
                "pages/documents.py",
                "pages/glossary.py",
                "pages/settings.py",
            ):
                app.switch_page(page).run()
                self.assertTrue(
                    any("Remote Ollama server" in item.value for item in app.warning),
                    page,
                )

    def test_settings_survive_navigation_page_switches(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        app.switch_page("pages/settings.py").run()
        app.text_input(key="widget_setting_ollama_url").set_value(
            "http://127.0.0.1:11434"
        ).run()

        app.switch_page("pages/documents.py").run()
        app.switch_page("pages/settings.py").run()

        self.assertEqual(
            app.text_input(key="widget_setting_ollama_url").value,
            "http://127.0.0.1:11434",
        )
        self.assertEqual(
            app.session_state["setting_ollama_url"],
            "http://127.0.0.1:11434",
        )

        app.selectbox(key="widget_setting_mood").select("😊 Happy").run()
        app.selectbox(key="widget_setting_reply_language").select("French").run()
        app.switch_page("pages/documents.py").run()
        app.switch_page("pages/settings.py").run()
        self.assertEqual(app.selectbox(key="widget_setting_mood").value, "😊 Happy")
        self.assertEqual(app.selectbox(key="widget_setting_reply_language").value, "French")

    def test_chat_page_renders_with_ollama_methods_mocked(self):
        with (
            patch.object(OllamaClient, "available_models", return_value=["qwen2.5:3b", "bge-m3"]),
            patch.object(OllamaClient, "chat", return_value="Hello."),
            patch.object(OllamaClient, "embed", return_value=[[1.0, 0.0]]),
        ):
            app = AppTest.from_file(str(APP_PATH)).run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.chat_input), 1)
        self.assertEqual(app.chat_input[0].placeholder, "Message Jeff…")

    def test_vpn_page_shows_registered_profiles_and_location_scope(self):
        from jarvis.vpn import VpnConnection

        with patch.object(
            vpn_page,
            "list_connections",
            return_value=[VpnConnection("service-id-123456789012345678901234", "Japan (Proton Free)", "Disconnected")],
        ):
            app = AppTest.from_file(str(APP_PATH)).run()
            app.switch_page("pages/vpn.py").run()

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Japan (Proton Free)" in item.value for item in app.subheader))
        self.assertTrue(any("whole Mac" in item.value for item in app.warning))
        self.assertTrue(any("Connect to Japan (Proton Free)" == item.label for item in app.button))

    def test_chat_vpn_request_requires_confirmation_before_connecting(self):
        from jarvis.vpn import VpnConnection

        with (
            patch.object(
                chat_page,
                "list_vpn_connections",
                return_value=[VpnConnection("258AB41A-4B3F-4C6E-AD7B-4C639165838C", "Japan (Proton Free)", "Disconnected")],
            ),
            patch.object(chat_page, "connect_vpn", return_value="Connected") as connect_vpn,
            patch.object(OllamaClient, "chat") as llm_chat,
        ):
            app = AppTest.from_file(str(APP_PATH)).run()
            app.chat_input[0].set_value("Change my VPN location to Japan").run()
            connect_vpn.assert_not_called()
            self.assertEqual(app.session_state["pending_vpn_action"]["label"], "Japan (Proton Free)")

            app.button(key="confirm_vpn_action").click().run()
            connect_vpn.assert_called_once_with("258AB41A-4B3F-4C6E-AD7B-4C639165838C")
            llm_chat.assert_not_called()
            self.assertNotIn("pending_vpn_action", app.session_state)
            self.assertTrue(any("Reload the webpage" in item.value for item in app.markdown))

    def test_empty_chat_suggestion_prefills_the_pinned_chat_input(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        self.assertTrue(any("Hello, how can I help?" in item.value for item in app.title))
        app.button(key="chat_suggestion_0").click().run()
        self.assertEqual(
            app.chat_input[0].value,
            "What does my indexed document say about …?",
        )

    def test_unreachable_ollama_shows_plain_language_and_technical_details(self):
        failure = OllamaError(
            "Could not reach Ollama at http://localhost:11434: connection refused"
        )
        with patch.object(OllamaClient, "available_models", side_effect=failure):
            app = AppTest.from_file(str(APP_PATH)).run()
            app.button(key="chat_check_setup").click().run()

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Jeff could not reach Ollama" in item.value for item in app.error))
        self.assertTrue(any("connection refused" in item.value for item in app.code))


if __name__ == "__main__":
    unittest.main()
