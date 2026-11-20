import json
import tempfile
import unittest
from pathlib import Path

import phonetic as P

ENTRIES = json.loads((Path(__file__).resolve().parents[1] / "dictionary.json").read_text(encoding="utf-8"))
IDX = P.SpellingIndex(ENTRIES, {})


class PhoneticTests(unittest.TestCase):
    def heads(self, token, n=2):
        return [c["headword"] for c in IDX.candidates(token, n)]

    def test_user_examples(self):
        self.assertIn("manze", self.heads("manG"))
        self.assertIn("rode", self.heads("roD"))
        self.assertIn("korek", self.heads("krk"))

    def test_spelling_variants_reach_same_word(self):
        for token in ["manger", "manje", "manzé", "mangé"]:
            self.assertIn("manze", self.heads(token))
        for token in ["corec", "correct", "korèk", "korek"]:
            self.assertIn("korek", self.heads(token))
        for token in ["roder", "rodé"]:
            self.assertIn("rode", self.heads(token))

    def test_letter_name_expansion_only_for_mixed_case(self):
        self.assertEqual(P.expand_letter_names("manG"), "manze")
        self.assertEqual(P.expand_letter_names("OK"), "OK")
        self.assertEqual(P.expand_letter_names("Bonzour"), "Bonzour")

    def test_learned_spelling_wins(self):
        idx = P.SpellingIndex(ENTRIES, {})
        idx.learn("mnm", "manze", path=Path("/tmp") / "jeff-v.json")
        self.assertEqual(idx.candidates("mnm", 1)[0]["why"], "learned")
        again = P.SpellingIndex(ENTRIES, P.load_variants(Path("/tmp") / "jeff-v.json"))
        self.assertEqual(again.candidates("mnm", 1)[0]["headword"], "manze")

    def test_forget_variant_removes_only_the_selected_spelling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "variants.json"
            P.save_variants({"mnm": "manze", "krk": "korek"}, path)

            self.assertTrue(P.forget_variant("mnm", path))
            self.assertEqual(P.load_variants(path), {"krk": "korek"})
            self.assertFalse(P.forget_variant("mnm", path))

    def test_no_noise_on_plain_creole_and_names(self):
        self.assertEqual(IDX.hints_block("Mo kontan manze dipen ek dilo"), "")
        self.assertNotIn("zafer", IDX.hints_block("Hello Jeff, what is the weather today?"))

    def test_ambiguous_sound_match_is_not_injected_as_a_hint(self):
        hints = IDX.hints_block("mo p faim, ki mo kav manG?")
        self.assertNotIn('"faim" probably', hints)
        self.assertIn('"manG" probably = manze', hints)


if __name__ == "__main__":
    unittest.main()
