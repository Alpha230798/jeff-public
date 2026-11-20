from __future__ import annotations

import streamlit as st

from jarvis.documents import DocumentError, extract_pdf_text
from jarvis.glossary import (
    GlossaryEntry,
    GlossaryDraft,
    GlossaryError,
    add_entry,
    add_entries,
    default_database_path,
    delete_entry,
    list_entries,
    update_entry,
)
from jarvis.glossary_import import (
    GlossaryImportError,
    build_extraction_messages,
    parse_glossary_candidates,
)
from jarvis.ollama import OllamaError
from jarvis.ui.content import new_client
from jarvis.ui_common import render_current_privacy_status, render_error
from phonetic import forget_variant, load_variants


def persist_pdf_candidates(editor_key: str) -> None:
    edited = st.session_state.get(editor_key)
    if isinstance(edited, list):
        st.session_state["pdf_glossary_candidates"] = edited


def delete_glossary_entry_from_callback(entry_id: int) -> None:
    try:
        delete_entry(entry_id, default_database_path())
    except GlossaryError as exc:
        st.session_state["glossary_error"] = str(exc)
    else:
        st.session_state["glossary_notice"] = "Glossary entry deleted."
        st.session_state["glossary_selected_id"] = None
        st.session_state[f"confirm_glossary_delete_{entry_id}"] = False


def render_glossary() -> list[GlossaryEntry]:
    render_current_privacy_status()
    with st.container(width=960):
        return _render_glossary_content()


def _render_glossary_content() -> list[GlossaryEntry]:
    st.title("Kreol Glossary")
    st.caption(
        "Add your own words, spellings, meanings, and examples. Jeff uses these as "
        "conversation context; this does not retrain the model."
    )

    with st.expander("Teach Jeff a word or phrase", expanded=False):
        notice = st.session_state.pop("glossary_notice", None)
        if notice:
            st.success(notice)
        error = st.session_state.pop("glossary_error", None)
        if error:
            render_error(GlossaryError(error))

        with st.form("add_kreol_glossary_entry", clear_on_submit=True):
            kreol_phrase = st.text_input(
                "Kreol word or phrase",
                key="add_kreol_phrase",
            )
            alternative_spellings = st.text_input(
                "Alternative spellings (optional)",
                help="Separate variations with commas.",
                key="add_kreol_alternatives",
            )
            english_meaning = st.text_input(
                "English meaning",
                key="add_kreol_english",
            )
            french_meaning = st.text_input(
                "French meaning (optional)",
                key="add_kreol_french",
            )
            example = st.text_area(
                "Example in context (optional)",
                key="add_kreol_example",
            )
            pronunciation_notes = st.text_area(
                "Pronunciation or spelling notes (optional)",
                key="add_kreol_notes",
            )
            add_submitted = st.form_submit_button(
                "Save glossary entry",
                key="save_kreol_entry",
            )

        if add_submitted:
            try:
                add_entry(
                    kreol_phrase,
                    alternative_spellings=alternative_spellings,
                    english_meaning=english_meaning,
                    french_meaning=french_meaning,
                    example=example,
                    pronunciation_notes=pronunciation_notes,
                    path=default_database_path(),
                )
                st.success("Saved to your local glossary.")
            except GlossaryError as exc:
                render_error(exc)

        st.markdown("#### Import vocabulary from a PDF")
        st.caption(
            "Jeff extracts candidate glossary entries using your Ollama model. "
            "Review and edit them before saving. Scanned PDFs require OCR and are not supported."
        )
        pdf_file = st.file_uploader(
            "Choose a Kreol vocabulary PDF",
            type=["pdf"],
            accept_multiple_files=False,
            key="kreol_glossary_pdf",
        )
        if st.button(
            "Extract glossary candidates",
            key="extract_kreol_pdf",
            disabled=pdf_file is None,
        ):
            try:
                if pdf_file is None:
                    raise DocumentError("Choose a PDF file first.")
                with st.spinner("Reading the PDF and asking Ollama for candidate entries..."):
                    pdf_text, truncated = extract_pdf_text(pdf_file)
                    response_text = new_client().chat_json(
                        build_extraction_messages(pdf_text)
                    )
                    candidates = parse_glossary_candidates(response_text)
                st.session_state["pdf_glossary_candidates"] = [
                    {
                        "Import": True,
                        "Kreol phrase": candidate.kreol_phrase,
                        "Alternative spellings": candidate.alternative_spellings,
                        "English meaning": candidate.english_meaning,
                        "French meaning": candidate.french_meaning,
                        "Example": candidate.example,
                        "Pronunciation notes": candidate.pronunciation_notes,
                    }
                    for candidate in candidates
                ]
                st.session_state["pdf_glossary_source"] = pdf_file.name
                st.session_state["pdf_glossary_revision"] = (
                    st.session_state.get("pdf_glossary_revision", 0) + 1
                )
                if truncated:
                    st.warning(
                        "Only the first 18,000 characters of selectable PDF text were analyzed."
                    )
                if not candidates:
                    st.warning(
                        "No usable glossary entries were found. Check that the PDF contains "
                        "selectable Kreol terms with English or French meanings."
                    )
            except (DocumentError, GlossaryImportError, OllamaError) as exc:
                render_error(exc)

        candidates = st.session_state.get("pdf_glossary_candidates", [])
        if candidates:
            st.caption(
                f"Candidates from {st.session_state.get('pdf_glossary_source', 'PDF')}. "
                "Correct the fields, uncheck entries you do not want, then save."
            )
            editor_revision = st.session_state.get("pdf_glossary_revision", 0)
            edited_candidates = st.data_editor(
                candidates,
                key=f"pdf_glossary_editor_{editor_revision}",
                on_change=persist_pdf_candidates,
                args=(f"pdf_glossary_editor_{editor_revision}",),
                hide_index=True,
                num_rows="fixed",
                column_config={
                    "Import": st.column_config.CheckboxColumn(
                        "Import",
                        help="Select the entries to add to your local glossary.",
                    ),
                    "Kreol phrase": st.column_config.TextColumn("Kreol phrase"),
                    "Alternative spellings": st.column_config.TextColumn(
                        "Alternative spellings"
                    ),
                    "English meaning": st.column_config.TextColumn("English meaning"),
                    "French meaning": st.column_config.TextColumn("French meaning"),
                    "Example": st.column_config.TextColumn("Example"),
                    "Pronunciation notes": st.column_config.TextColumn(
                        "Pronunciation notes"
                    ),
                },
            )
            if st.button(
                "Save selected PDF entries",
                key=f"save_pdf_glossary_{editor_revision}",
                type="primary",
            ):
                selected_drafts = [
                    GlossaryDraft(
                        kreol_phrase=str(row["Kreol phrase"]),
                        alternative_spellings=str(row["Alternative spellings"]),
                        english_meaning=str(row["English meaning"]),
                        french_meaning=str(row["French meaning"]),
                        example=str(row["Example"]),
                        pronunciation_notes=str(row["Pronunciation notes"]),
                    )
                    for row in edited_candidates
                    if bool(row["Import"])
                ]
                if not selected_drafts:
                    st.warning("Select at least one candidate to save.")
                else:
                    try:
                        added_count, skipped_phrases = add_entries(
                            selected_drafts,
                            path=default_database_path(),
                        )
                        st.session_state["pdf_glossary_candidates"] = []
                        st.session_state["glossary_import_result"] = (
                            added_count,
                            skipped_phrases,
                        )
                        st.rerun()
                    except GlossaryError as exc:
                        render_error(exc)

        import_result = st.session_state.pop("glossary_import_result", None)
        if import_result is not None:
            added_count, skipped_phrases = import_result
            st.success(f"Saved {added_count} glossary entr{'y' if added_count == 1 else 'ies'}.")
            if skipped_phrases:
                st.info(
                    "Skipped existing or duplicate phrases: "
                    + ", ".join(skipped_phrases)
                )

        try:
            entries = list_entries(default_database_path())
        except GlossaryError as exc:
            render_error(exc)
            return []

        if not entries:
            st.info("Your glossary is empty. Add a phrase above to get started.")
            render_my_spellings()
            return []

        st.caption(f"{len(entries)} entries saved on this computer.")
        search = st.text_input(
            "Search your glossary",
            placeholder="Search Kreol, spelling, or meaning",
            key="glossary_search",
        ).strip().casefold()
        matches = [
            entry
            for entry in entries
            if not search
            or search
            in " ".join(
                (
                    entry.kreol_phrase,
                    entry.alternative_spellings,
                    entry.english_meaning,
                    entry.french_meaning,
                    entry.example,
                    entry.pronunciation_notes,
                )
            ).casefold()
        ]
        if not matches:
            st.info("No glossary entries match that search. Try another word or clear the search.")
            render_my_spellings()
            return entries

        entries_by_id = {entry.id: entry for entry in matches}
        options = list(entries_by_id)
        if st.session_state.get("glossary_selected_id") not in options:
            st.session_state["glossary_selected_id"] = options[0]
        selected_id = st.selectbox(
            "Choose an entry to review or edit",
            options=options,
            format_func=lambda entry_id: (
                f"{entries_by_id[entry_id].kreol_phrase} — "
                f"{entries_by_id[entry_id].english_meaning or entries_by_id[entry_id].french_meaning}"
            ),
            key="glossary_selected_id",
        )
        selected = entries_by_id[selected_id]

        with st.form(f"edit_kreol_glossary_entry_{selected.id}"):
            edited_phrase = st.text_input(
                "Kreol word or phrase",
                value=selected.kreol_phrase,
                key=f"edit_kreol_phrase_{selected.id}",
            )
            edited_alternatives = st.text_input(
                "Alternative spellings",
                value=selected.alternative_spellings,
                key=f"edit_kreol_alternatives_{selected.id}",
            )
            edited_english = st.text_input(
                "English meaning",
                value=selected.english_meaning,
                key=f"edit_kreol_english_{selected.id}",
            )
            edited_french = st.text_input(
                "French meaning",
                value=selected.french_meaning,
                key=f"edit_kreol_french_{selected.id}",
            )
            edited_example = st.text_area(
                "Example in context",
                value=selected.example,
                key=f"edit_kreol_example_{selected.id}",
            )
            edited_notes = st.text_area(
                "Pronunciation or spelling notes",
                value=selected.pronunciation_notes,
                key=f"edit_kreol_notes_{selected.id}",
            )
            update_submitted = st.form_submit_button("Update entry")

        if update_submitted:
            try:
                update_entry(
                    selected.id,
                    edited_phrase,
                    alternative_spellings=edited_alternatives,
                    english_meaning=edited_english,
                    french_meaning=edited_french,
                    example=edited_example,
                    pronunciation_notes=edited_notes,
                    path=default_database_path(),
                )
                st.success("Glossary entry updated.")
                entries = list_entries(default_database_path())
            except GlossaryError as exc:
                render_error(exc)

        confirm_key = f"confirm_glossary_delete_{selected.id}"
        st.checkbox(
            "I understand this permanently deletes the selected glossary entry.",
            key=confirm_key,
        )
        st.button(
            "Delete selected entry",
            key=f"delete_glossary_entry_{selected.id}",
            disabled=not st.session_state.get(confirm_key, False),
            on_click=delete_glossary_entry_from_callback,
            args=(selected.id,),
        )
        render_my_spellings()
        return entries


def render_my_spellings() -> None:
    st.divider()
    st.subheader("My spellings")
    st.caption(
        "These are spellings you explicitly asked Jeff to remember. "
        "Jeff never saves a spelling from a suggestion without your click."
    )
    variants = load_variants()
    if not variants:
        st.info("No personal spellings saved yet.")
        return
    for number, (variant, canonical) in enumerate(sorted(variants.items()), start=1):
        left, right = st.columns([4, 1])
        left.write(f"**{variant}** means **{canonical}**")
        if right.button("Forget", key=f"forget_my_spelling_{number}"):
            try:
                forget_variant(variant)
                st.rerun()
            except OSError as exc:
                render_error(
                    exc,
                    action="Check that Jeff can write to the local spelling-memory file.",
                )


