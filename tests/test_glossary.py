import tempfile
import unittest
from pathlib import Path

from jarvis.glossary import (
    GlossaryError,
    add_entry,
    add_entries,
    GlossaryDraft,
    delete_entry,
    list_entries,
    relevant_entries,
    update_entry,
)


class GlossaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "glossary.sqlite3"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_entries_persist_and_can_be_updated_and_deleted(self) -> None:
        entry_id = add_entry(
            "mo kontan",
            alternative_spellings="mo content",
            english_meaning="I am happy",
            french_meaning="Je suis content",
            example="Mo kontan pou twa.",
            pronunciation_notes="Personal spelling note",
            path=self.database_path,
        )
        stored = list_entries(self.database_path)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].id, entry_id)
        self.assertEqual(stored[0].alternative_spellings, "mo content")

        update_entry(
            entry_id,
            "mo bien kontan",
            english_meaning="I am very happy",
            path=self.database_path,
        )
        updated = list_entries(self.database_path)[0]
        self.assertEqual(updated.kreol_phrase, "mo bien kontan")
        self.assertEqual(updated.english_meaning, "I am very happy")
        self.assertEqual(updated.french_meaning, "")

        delete_entry(entry_id, self.database_path)
        self.assertEqual(list_entries(self.database_path), [])

    def test_requires_phrase_and_at_least_one_meaning(self) -> None:
        with self.assertRaises(GlossaryError):
            add_entry("", english_meaning="meaning", path=self.database_path)
        with self.assertRaises(GlossaryError):
            add_entry("mo", path=self.database_path)

    def test_retrieves_matching_entries_and_uses_recent_examples_as_fallback(self) -> None:
        kontan_id = add_entry(
            "kontan",
            english_meaning="happy",
            path=self.database_path,
        )
        bonzur_id = add_entry(
            "bonzur",
            english_meaning="hello",
            path=self.database_path,
        )
        entries = list_entries(self.database_path)

        matched = relevant_entries("I feel happy", entries)
        self.assertEqual([entry.id for entry in matched], [kontan_id])

        fallback = relevant_entries("Mo pe koz Kreol", entries)
        self.assertEqual({entry.id for entry in fallback}, {kontan_id, bonzur_id})

    def test_missing_entry_update_and_delete_are_reported(self) -> None:
        with self.assertRaises(GlossaryError):
            update_entry(999, "phrase", english_meaning="meaning", path=self.database_path)
        with self.assertRaises(GlossaryError):
            delete_entry(999, self.database_path)

    def test_bulk_add_skips_duplicates_and_validates_before_writing(self) -> None:
        add_entry("bonzur", english_meaning="hello", path=self.database_path)
        added, skipped = add_entries(
            [
                GlossaryDraft("bonswar", english_meaning="good evening"),
                GlossaryDraft("bonzur", english_meaning="hello"),
                GlossaryDraft("Bonswar", french_meaning="bonsoir"),
            ],
            self.database_path,
        )
        self.assertEqual(added, 1)
        self.assertEqual(skipped, ["bonzur", "Bonswar"])
        self.assertEqual(len(list_entries(self.database_path)), 2)

        with self.assertRaises(GlossaryError):
            add_entries(
                [
                    GlossaryDraft("valid", english_meaning="meaning"),
                    GlossaryDraft("invalid"),
                ],
                self.database_path,
            )
        self.assertEqual(len(list_entries(self.database_path)), 2)


if __name__ == "__main__":
    unittest.main()
