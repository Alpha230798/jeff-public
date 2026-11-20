import unittest

from jarvis.dictionary import lookup_dictionary_entries


class DictionaryLookupTests(unittest.TestCase):
    def test_matches_headwords_not_substrings_or_common_words(self):
        entries = [
            "korek : correct; OK.",
            "ki [from Fre qui] : what.",
            "mang [from Fre mangue] : mango.",
            "manze [from Fre manger] : to eat.",
            "mokan [from Fre moquer] : to mock.",
        ]

        result = lookup_dictionary_entries("mo p faim, ki mo kav manG?", entries)
        self.assertEqual(result, "")

    def test_returns_exactly_relevant_headword_entries(self):
        entries = [
            "manze [from Fre manger] : to eat.",
            "dipen [from Fre du pain] : bread.",
            "mokan [from Fre moquer] : to mock.",
        ]

        result = lookup_dictionary_entries("Mo kontan manze dipen.", entries)
        self.assertIn("manze", result)
        self.assertIn("dipen", result)
        self.assertNotIn("mokan", result)


if __name__ == "__main__":
    unittest.main()
