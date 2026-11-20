from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from typing import Protocol
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PyPdfError


class UploadedFile(Protocol):
    name: str

    def getvalue(self) -> bytes: ...


class DocumentError(Exception):
    """Raised when an uploaded document cannot be processed."""


@dataclass(frozen=True)
class Chunk:
    text: str
    source_label: str


def split_text(text: str, source_label: str, size: int = 1200, overlap: int = 180) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Chunk size must be positive and overlap must be smaller than size.")

    normalized = " ".join(text.split())
    chunks: list[Chunk] = []
    start = 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        part = normalized[start:end].strip()
        if part:
            chunks.append(Chunk(text=part, source_label=source_label))
        if end == len(normalized):
            break
        start = end - overlap
    return chunks


def extract_pdf_text(
    uploaded_file: UploadedFile,
    max_chars: int = 18000,
) -> tuple[str, bool]:
    if max_chars <= 0:
        raise ValueError("Maximum PDF text length must be positive.")
    if PurePath(uploaded_file.name).suffix.lower() != ".pdf":
        raise DocumentError("Choose a PDF file.")

    try:
        reader = PdfReader(BytesIO(uploaded_file.getvalue()))
        pages: list[str] = []
        character_count = 0
        truncated = False
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if not page_text.strip():
                continue
            page_text = page_text.strip()
            page_label = f"[Page {page_number}]\n"
            remaining = max_chars - character_count
            page_separator = "\n\n" if pages else ""
            overhead = len(page_separator) + len(page_label)
            if remaining <= overhead:
                truncated = True
                break

            page_content = page_text[: remaining - overhead]
            pages.append(f"{page_separator}{page_label}{page_content}")
            character_count += overhead + len(page_content)
            if len(page_content) < len(page_text):
                truncated = True
                break
        text = "".join(pages)
    except (PyPdfError, UnicodeDecodeError) as exc:
        raise DocumentError(f"{uploaded_file.name}: could not read PDF ({exc}).") from exc

    if not text.strip():
        raise DocumentError(
            "No selectable text was found in this PDF. Scanned/image-only PDFs need OCR, "
            "which Jeff does not support yet."
        )
    return text, truncated


def extract_chunks(files: list[UploadedFile]) -> tuple[list[Chunk], list[str]]:
    chunks: list[Chunk] = []
    errors: list[str] = []
    for uploaded_file in files:
        name = uploaded_file.name
        extension = PurePath(name).suffix.lower()
        data = uploaded_file.getvalue()
        try:
            if extension == ".pdf":
                reader = PdfReader(BytesIO(data))
                for page_number, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text() or ""
                    chunks.extend(
                        split_text(page_text, f"{name}, page {page_number}")
                    )
            elif extension == ".docx":
                document = Document(BytesIO(data))
                text = "\n".join(paragraph.text for paragraph in document.paragraphs)
                chunks.extend(split_text(text, name))
            elif extension in {".txt", ".md"}:
                chunks.extend(split_text(data.decode("utf-8-sig"), name))
            else:
                errors.append(f"{name}: unsupported file type.")
        except (PdfReadError, PackageNotFoundError, BadZipFile, UnicodeDecodeError) as exc:
            errors.append(f"{name}: could not read document ({exc}).")
    return chunks, errors
