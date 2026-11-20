import unittest
from io import BytesIO

from pypdf import PdfWriter

from jarvis.documents import DocumentError, extract_pdf_text


class UploadedFile:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self.data = data

    def getvalue(self) -> bytes:
        return self.data


class PdfImportTests(unittest.TestCase):
    def test_requires_pdf_extension(self) -> None:
        with self.assertRaisesRegex(DocumentError, "Choose a PDF"):
            extract_pdf_text(UploadedFile("notes.txt", b"some text"))

    def test_rejects_scanned_or_empty_pdf_without_text(self) -> None:
        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.write(output)

        with self.assertRaisesRegex(DocumentError, "OCR"):
            extract_pdf_text(UploadedFile("scan.pdf", output.getvalue()))

    def test_reports_invalid_pdf(self) -> None:
        with self.assertRaisesRegex(DocumentError, "could not read PDF"):
            extract_pdf_text(UploadedFile("broken.pdf", b"not a PDF"))

    def test_rejects_nonpositive_text_limit(self) -> None:
        with self.assertRaises(ValueError):
            extract_pdf_text(UploadedFile("scan.pdf", b""), max_chars=0)


if __name__ == "__main__":
    unittest.main()
