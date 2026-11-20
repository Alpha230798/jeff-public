import unittest

from jarvis.documents import split_text
from jarvis.retrieval import cosine_similarity


class SplitTextTests(unittest.TestCase):
    def test_splits_with_overlap_and_source(self) -> None:
        chunks = split_text("abcdefghij", "notes.txt", size=6, overlap=2)

        self.assertEqual([chunk.text for chunk in chunks], ["abcdef", "efghij"])
        self.assertTrue(all(chunk.source_label == "notes.txt" for chunk in chunks))

    def test_normalizes_whitespace(self) -> None:
        chunks = split_text("hello \n  world", "notes.txt")

        self.assertEqual([chunk.text for chunk in chunks], ["hello world"])

    def test_rejects_invalid_overlap(self) -> None:
        with self.assertRaises(ValueError):
            split_text("text", "notes.txt", size=4, overlap=4)


class CosineSimilarityTests(unittest.TestCase):
    def test_identical_vectors_have_similarity_one(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1, 2], [1, 2]), 1.0)

    def test_orthogonal_vectors_have_similarity_zero(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_rejects_different_dimensions(self) -> None:
        with self.assertRaises(ValueError):
            cosine_similarity([1], [1, 2])


if __name__ == "__main__":
    unittest.main()
