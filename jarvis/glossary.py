from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, Sequence


class GlossaryError(Exception):
    """Raised when a personal glossary entry cannot be accessed or changed."""


@dataclass(frozen=True)
class GlossaryEntry:
    id: int
    kreol_phrase: str
    alternative_spellings: str
    english_meaning: str
    french_meaning: str
    example: str
    pronunciation_notes: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class GlossaryDraft:
    kreol_phrase: str
    alternative_spellings: str = ""
    english_meaning: str = ""
    french_meaning: str = ""
    example: str = ""
    pronunciation_notes: str = ""


def default_database_path() -> Path:
    return Path.home() / ".jeff" / "kreol_glossary.sqlite3"


@contextmanager
def _database(path: str | Path) -> Iterator[sqlite3.Connection]:
    database_path = Path(path).expanduser()
    connection: sqlite3.Connection | None = None
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS kreol_glossary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kreol_phrase TEXT NOT NULL,
                alternative_spellings TEXT NOT NULL DEFAULT '',
                english_meaning TEXT NOT NULL DEFAULT '',
                french_meaning TEXT NOT NULL DEFAULT '',
                example TEXT NOT NULL DEFAULT '',
                pronunciation_notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        yield connection
        connection.commit()
    except (OSError, sqlite3.Error) as exc:
        if connection is not None:
            connection.rollback()
        raise GlossaryError(f"Could not access the local Kreol glossary: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


def _clean_fields(
    kreol_phrase: str,
    alternative_spellings: str,
    english_meaning: str,
    french_meaning: str,
    example: str,
    pronunciation_notes: str,
) -> tuple[str, str, str, str, str, str]:
    fields = tuple(
        value.strip()
        for value in (
            kreol_phrase,
            alternative_spellings,
            english_meaning,
            french_meaning,
            example,
            pronunciation_notes,
        )
    )
    phrase, alternatives, english, french, usage, pronunciation = fields
    if not phrase:
        raise GlossaryError("Enter a Kreol word or phrase.")
    if not english and not french:
        raise GlossaryError("Enter an English or French meaning.")
    return phrase, alternatives, english, french, usage, pronunciation


def _entry_from_row(row: sqlite3.Row) -> GlossaryEntry:
    return GlossaryEntry(
        id=row["id"],
        kreol_phrase=row["kreol_phrase"],
        alternative_spellings=row["alternative_spellings"],
        english_meaning=row["english_meaning"],
        french_meaning=row["french_meaning"],
        example=row["example"],
        pronunciation_notes=row["pronunciation_notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_entries(path: str | Path | None = None) -> list[GlossaryEntry]:
    with _database(path or default_database_path()) as connection:
        rows = connection.execute(
            "SELECT * FROM kreol_glossary ORDER BY kreol_phrase COLLATE NOCASE, id"
        ).fetchall()
    return [_entry_from_row(row) for row in rows]


def add_entry(
    kreol_phrase: str,
    *,
    alternative_spellings: str = "",
    english_meaning: str = "",
    french_meaning: str = "",
    example: str = "",
    pronunciation_notes: str = "",
    path: str | Path | None = None,
) -> int:
    fields = _clean_fields(
        kreol_phrase,
        alternative_spellings,
        english_meaning,
        french_meaning,
        example,
        pronunciation_notes,
    )
    now = datetime.now(UTC).isoformat()
    with _database(path or default_database_path()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO kreol_glossary (
                kreol_phrase, alternative_spellings, english_meaning,
                french_meaning, example, pronunciation_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*fields, now, now),
        )
        return int(cursor.lastrowid)


def add_entries(
    drafts: Sequence[GlossaryDraft],
    path: str | Path | None = None,
) -> tuple[int, list[str]]:
    validated = [
        _clean_fields(
            draft.kreol_phrase,
            draft.alternative_spellings,
            draft.english_meaning,
            draft.french_meaning,
            draft.example,
            draft.pronunciation_notes,
        )
        for draft in drafts
    ]
    now = datetime.now(UTC).isoformat()
    added = 0
    skipped: list[str] = []
    seen: set[str] = set()

    with _database(path or default_database_path()) as connection:
        existing = {
            row["phrase_key"]
            for row in connection.execute(
                "SELECT lower(kreol_phrase) AS phrase_key FROM kreol_glossary"
            )
        }
        for fields in validated:
            phrase_key = fields[0].casefold()
            if phrase_key in existing or phrase_key in seen:
                skipped.append(fields[0])
                continue
            connection.execute(
                """
                INSERT INTO kreol_glossary (
                    kreol_phrase, alternative_spellings, english_meaning,
                    french_meaning, example, pronunciation_notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*fields, now, now),
            )
            seen.add(phrase_key)
            added += 1
    return added, skipped


def update_entry(
    entry_id: int,
    kreol_phrase: str,
    *,
    alternative_spellings: str = "",
    english_meaning: str = "",
    french_meaning: str = "",
    example: str = "",
    pronunciation_notes: str = "",
    path: str | Path | None = None,
) -> None:
    fields = _clean_fields(
        kreol_phrase,
        alternative_spellings,
        english_meaning,
        french_meaning,
        example,
        pronunciation_notes,
    )
    now = datetime.now(UTC).isoformat()
    with _database(path or default_database_path()) as connection:
        cursor = connection.execute(
            """
            UPDATE kreol_glossary
            SET kreol_phrase = ?, alternative_spellings = ?, english_meaning = ?,
                french_meaning = ?, example = ?, pronunciation_notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (*fields, now, entry_id),
        )
        if cursor.rowcount == 0:
            raise GlossaryError(f"Glossary entry {entry_id} no longer exists.")


def delete_entry(entry_id: int, path: str | Path | None = None) -> None:
    with _database(path or default_database_path()) as connection:
        cursor = connection.execute(
            "DELETE FROM kreol_glossary WHERE id = ?",
            (entry_id,),
        )
        if cursor.rowcount == 0:
            raise GlossaryError(f"Glossary entry {entry_id} no longer exists.")


def relevant_entries(
    query: str,
    entries: list[GlossaryEntry],
    *,
    limit: int = 8,
    fallback_limit: int = 3,
) -> list[GlossaryEntry]:
    if limit <= 0 or fallback_limit < 0:
        raise ValueError("Glossary limits must be positive (fallback may be zero).")
    if not entries:
        return []

    query_tokens = set(re.findall(r"[^\W_]+", query.casefold()))
    if not query_tokens:
        return sorted(entries, key=lambda entry: entry.updated_at, reverse=True)[: min(limit, fallback_limit)]

    ranked: list[tuple[int, GlossaryEntry]] = []
    for entry in entries:
        phrase_tokens = set(
            re.findall(
                r"[^\W_]+",
                f"{entry.kreol_phrase} {entry.alternative_spellings}".casefold(),
            )
        )
        meaning_tokens = set(
            re.findall(
                r"[^\W_]+",
                f"{entry.english_meaning} {entry.french_meaning}".casefold(),
            )
        )
        example_tokens = set(
            re.findall(
                r"[^\W_]+",
                f"{entry.example} {entry.pronunciation_notes}".casefold(),
            )
        )
        score = (
            3 * len(query_tokens & phrase_tokens)
            + 2 * len(query_tokens & meaning_tokens)
            + len(query_tokens & example_tokens)
        )
        if score:
            ranked.append((score, entry))

    if ranked:
        ranked.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        return [entry for _, entry in ranked[:limit]]

    recent = sorted(entries, key=lambda entry: entry.updated_at, reverse=True)
    return recent[: min(limit, fallback_limit)]
