import unittest

from jarvis.language import detect_language, thinking_label


class ThinkingLabelTests(unittest.TestCase):
    def test_english_message_uses_english_label(self):
        self.assertEqual(detect_language("Hello, what can you do?"), "English")
        self.assertEqual(thinking_label("Hello, what can you do?"), "Thinking...")
        self.assertEqual(thinking_label("I want to learn the answer."), "Thinking...")

    def test_french_message_uses_french_label(self):
        self.assertEqual(detect_language("Bonjour, comment ça va ?"), "French")
        self.assertEqual(thinking_label("Bonjour, comment ça va ?"), "Réflexion...")
        self.assertEqual(thinking_label("Je veux une réponse."), "Réflexion...")

    def test_kreol_message_uses_kreol_label(self):
        self.assertEqual(detect_language("Mo pe koz Kreol avek Jeff."), "Mauritian Kreol")
        self.assertEqual(thinking_label("Mo pe koz Kreol avek Jeff."), "Pe reflesi...")
        self.assertEqual(detect_language("Ki position?"), "Mauritian Kreol")
        self.assertEqual(detect_language("non mo p koz kreol"), "Mauritian Kreol")

    def test_ambiguous_short_message_defaults_to_english(self):
        self.assertEqual(detect_language("Hi!"), "English")
        self.assertEqual(thinking_label("Hi!"), "Thinking...")

    def test_explicit_language_switch_requests(self):
        self.assertEqual(detect_language("Please answer in English from now on."), "English")
        self.assertEqual(detect_language("Réponds-moi en français, s'il te plaît."), "French")
        self.assertEqual(detect_language("Reponn mwa an kreol silvouple."), "Mauritian Kreol")


if __name__ == "__main__":
    unittest.main()
