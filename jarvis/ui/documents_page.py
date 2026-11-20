from __future__ import annotations

import streamlit as st

from jarvis.documents import DocumentError, extract_chunks
from jarvis.ollama import OllamaError
from jarvis.ui.content import new_client
from jarvis.ui_common import render_current_privacy_status, render_error


def render_documents_page() -> None:
    render_current_privacy_status()
    with st.container(width=880):
        st.title("Documents")
        st.write(
            "Add files when you want Jeff to answer questions using their contents. "
            "Supported formats are PDF, DOCX, TXT, and Markdown."
        )
        with st.container(border=True):
            st.subheader("Add documents")
            st.caption(
                "Document text and relevant excerpts are sent to your configured "
                "Ollama server when indexed or used in a question."
            )
            uploaded_files = st.file_uploader(
                "Choose documents",
                type=["pdf", "docx", "txt", "md"],
                accept_multiple_files=True,
                key="document_uploads",
            )
            if st.button(
                "Index selected documents",
                type="primary",
                disabled=not uploaded_files,
            ):
                try:
                    with st.spinner(
                        "Jeff is reading the documents and preparing them for questions…"
                    ):
                        chunks, errors = extract_chunks(uploaded_files)
                        if not chunks:
                            raise DocumentError(
                                "No readable text was found in the selected files. "
                                + " ".join(errors)
                            )
                        vectors = new_client().embed([chunk.text for chunk in chunks])
                        if len(vectors) != len(chunks):
                            raise OllamaError(
                                "Ollama returned a different number of embeddings than requested."
                            )
                        st.session_state["document_index"] = {
                            "chunks": chunks,
                            "vectors": vectors,
                        }
                    st.success(f"Jeff indexed {len(chunks)} passages.")
                    if errors:
                        st.info(
                            "Some files could not be read. The files that worked are ready to use."
                        )
                        with st.expander("Technical details"):
                            st.code("\n".join(errors))
                except (DocumentError, OllamaError) as exc:
                    render_error(exc)

        index = st.session_state.get("document_index")
        if not index:
            st.info(
                "No documents are indexed for this conversation yet. "
                "Choose a file above to get started."
            )
            return

        chunks = index["chunks"]
        with st.container(border=True):
            st.subheader("Indexed for this session")
            st.caption(
                f"{len(chunks)} passages from "
                f"{len({chunk.source_label.split(', page ')[0] for chunk in chunks})} source file(s)."
            )
            for source in sorted({chunk.source_label for chunk in chunks}):
                st.markdown(f"- {source}")
