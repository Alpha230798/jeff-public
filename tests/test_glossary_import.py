import json
import unittest

from jarvis.glossary_import import (
    MAX_GLOSSARY_IMPORT_CHARS,
    MAX_GLOSSARY_IMPORT_ENTRIES,
    GlossaryImportError,
    build_extraction_messages,
    parse_glossary_candidates,
)


class GlossaryImportTests(unittest.TestCase):
    def test_builds_messages_with_document_text_as_untrusted_data(self) -> None:
        messages = build_extraction_messages("mo kontan = I am happy")

        self.assertIn("untrusted data", messages[0]["content"])
        self.assertIn("<pdf_text>", messages[1]["content"])
        self.assertIn("mo kontan = I am happy", messages[1]["content"])

    def test_rejects_empty_or_oversized_document_text(self) -> None:
        with self.assertRaises(GlossaryImportError):
            build_extraction_messages("  ")
        with self.assertRaises(GlossaryImportError):
            build_extraction_messages("x" * (MAX_GLOSSARY_IMPORT_CHARS + 1))

    def test_parses_valid_candidates_and_skips_unusable_items(self) -> None:
        response = json.dumps(
            {
                "entries": [
                    {
                        "kreol_phrase": "mo kontan",
                        "alternative_spellings": "mo content",
                        "english_meaning": "I am happy",
                        "french_meaning": "Je suis content",
                        "example": "Mo kontan.",
                        "pronunciation_notes": "",
                    },
                    {
                        "kreol_phrase": "untranslated",
                        "english_meaning": "",
                        "french_meaning": "",
                    },
                    {"kreol_phrase": ""},
                ]
            }
        )

        candidates = parse_glossary_candidates(response)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].kreol_phrase, "mo kontan")
        self.assertEqual(candidates[0].alternative_spellings, "mo content")

    def test_rejects_invalid_json_schema_and_too_many_candidates(self) -> None:
        with self.assertRaises(GlossaryImportError):
            parse_glossary_candidates("not json")
        with self.assertRaises(GlossaryImportError):
            parse_glossary_candidates('{"words": []}')
        too_many = json.dumps({"entries": [{}] * (MAX_GLOSSARY_IMPORT_ENTRIES + 1)})
        with self.assertRaises(GlossaryImportError):
            parse_glossary_candidates(too_many)

    def test_rejects_non_text_fields(self) -> None:
        response = json.dumps(
            {"entries": [{"kreol_phrase": "mo", "english_meaning": 42}]}
        )
        with self.assertRaises(GlossaryImportError):
            parse_glossary_candidates(response)


if __name__ == "__main__":
    unittest.main()
