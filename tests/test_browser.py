import unittest

from jarvis.browser import BrowserError, BrowserPage, FirefoxBrowser, normalize_web_url


class BrowserUrlTests(unittest.TestCase):
    def test_adds_https_to_a_plain_domain(self):
        self.assertEqual(normalize_web_url("example.com/hello"), "https://example.com/hello")
        self.assertEqual(normalize_web_url("localhost:8000"), "https://localhost:8000")

    def test_accepts_http_and_https_only(self):
        self.assertEqual(normalize_web_url("http://localhost:8000"), "http://localhost:8000")
        for address in (
            "javascript:alert(1)",
            "javascript:123",
            "file:///tmp/private.txt",
            "data:text/html,hello",
            "ftp://example.com",
        ):
            with self.subTest(address=address), self.assertRaises(BrowserError):
                normalize_web_url(address)

    def test_rejects_credentials_in_the_address(self):
        with self.assertRaisesRegex(BrowserError, "Remove any username or password"):
            normalize_web_url("https://user:secret@example.com")


class BrowserPageReadTests(unittest.TestCase):
    def test_reads_only_visible_body_text_and_caps_the_result(self):
        class FakeElement:
            text = "Visible page text"

        class FakeDriver:
            current_url = "https://example.com/"
            title = "Example page"

            @staticmethod
            def find_element(by, value):
                if (by, value) != ("tag name", "body"):
                    raise AssertionError("The browser adapter should only read the visible body element.")
                return FakeElement()

        browser = FirefoxBrowser(binary_path="/test/firefox", headless=True)
        browser._driver = FakeDriver()

        page = browser.read_current_page()

        self.assertEqual(
            page,
            BrowserPage("https://example.com/", "Example page", "Visible page text"),
        )
