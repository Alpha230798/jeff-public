from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


PUBLIC_APP_PATH = Path(__file__).resolve().parents[1] / "public_app.py"


class PublicAppTests(unittest.TestCase):
    def test_preview_renders_without_chat_or_file_upload_controls(self):
        app = AppTest.from_file(str(PUBLIC_APP_PATH)).run()

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("This public preview is read-only" in item.value for item in app.info))
        self.assertEqual(len(app.chat_input), 0)
        self.assertEqual(len(app.get("file_uploader")), 0)

    def test_preview_includes_the_chat_screenshot(self):
        app = AppTest.from_file(str(PUBLIC_APP_PATH)).run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get("image")), 1)


if __name__ == "__main__":
    unittest.main()
