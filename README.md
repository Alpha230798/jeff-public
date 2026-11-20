# Jeff — Phase 1

A local-first personal assistant with a native macOS app and an Ollama-backed
Python service. Jeff provides text chat, document question-answering with
retrieved source references, and a private, editable Mauritian Kreol glossary.
It currently focuses on English and French. An optional Firefox Developer
Edition companion adds user-confirmed, constrained page actions through a local
Python bridge. Jeff does not have general control of other apps, voice, or
general long-term memory.

See the [conversation guide](docs/CONVERSATION_GUIDE.md) for language selection,
mood settings, Kreol spelling tools, and browser access.

The public preview is a static, read-only page. It does not accept prompts or
files or connect to a model. Its source will be published at
[`Alpha230798/jeff-public`](https://github.com/Alpha230798/jeff-public).
Try the [live read-only preview](https://jeff-public.streamlit.app/).

## Requirements

- Python 3.12 (recommended; Python 3.10 or newer may also work)
- [Ollama](https://ollama.com/) installed and running
- A chat model and multilingual embedding model downloaded in Ollama
- Firefox Developer Edition for the optional Browser page
- macOS with OpenVPN Connect 3.9+ for Jeff's optional VPN controls

This source repository does not include generated application bundles. Follow
the [macOS app guide](docs/MACOS_APP.md) to build the Apple Silicon app and DMG.

Download a smaller chat model to start with (the previously suggested 7B model
may be slow on some computers), plus the embedding model used for document
search:

```bash
ollama pull qwen2.5:3b
ollama pull bge-m3
```

If you already downloaded `qwen2.5:7b`, you can use it instead, but it may
respond more slowly. Jeff is currently focused on English and French replies.
The Kreol glossary and spelling features remain available as reference tools,
but Jeff's chat replies are currently focused on English and French.

## Public web preview

The public preview is intentionally read-only: it shows a static example and
does not accept chat messages or document uploads. It does not connect to
Ollama, access the local Firefox/VPN integrations, or save user content. Run it
locally with `streamlit run public_app.py`. It includes a screenshot of Jeff's
macOS Chat screen. The full local app remains available with
`streamlit run app.py`.

## Run locally

The packaged macOS app runs in its own native window and does not require
Python. Start Ollama before using it. To run the Streamlit development UI from
source, open Terminal in the project directory and run these setup commands
once:

```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
python -m pip install -r requirements.txt
```

For each later development session, activate the existing environment and start
the development UI:

```bash
cd jeff-public
source .venv312/bin/activate
streamlit run app.py
```

Leave that Terminal window open while using the development UI. Open the local
URL printed by Streamlit. On the **Settings** page, set **Chat model** to `qwen2.5:3b` and
**Embedding model** to `bge-m3`. The **Chat** page is the main
conversation and keeps its message box at the bottom. Use **Documents** to add
PDF, DOCX, TXT, or Markdown files and select **Index selected documents** before
asking questions about their contents. The Chat page includes a setup checklist
for the Ollama connection and both selected models.

The **Browser** page can open Firefox Developer Edition in a dedicated Jeff
profile, show a preview of the current page's visible text, and let you add that
text to your next chat. The native app uses its own window; this separate
floating Firefox companion is documented in
[docs/FIREFOX_COMPANION.md](docs/FIREFOX_COMPANION.md). It can read page text
only after you ask, and supports confirmed scroll/highlight, refresh, and
monitor tasks. It never submits forms or clicks page controls. The Jeff profile
is separate from your
everyday Firefox profile; sign in to sites in that profile yourself. Its cookies
and site data are kept locally in `~/.jeff/firefox_jeff_profile`. The first
launch may download GeckoDriver through Selenium Manager.

Use the app menu in the top-right corner to switch between the light and dark
themes. The short connection message above each page shows whether Jeff is
configured for localhost or a remote Ollama server. Settings explains which data
is sent to that server.

The Firefox companion uses its own local bridge and settings. It requests no
general website access: page injection follows a toolbar click and the
activeTab permission. Selected chat/page text and relevant Kreol references
are sent to the Ollama endpoint chosen in the bridge environment. The widget
shows a warning for remote Ollama endpoints; the extension also declares its
conversation and website-content transmission in Firefox's install disclosure.
On macOS, the **VPN location** page can control OpenVPN Connect profiles already
registered in System Settings → VPN. Jeff asks for confirmation before each
connect/disconnect; the VPN routes traffic for the whole Mac. See the
[VPN controls guide](docs/VPN_CONTROL.md).
The full [Firefox companion setup, architecture, packaging, privacy, and
troubleshooting guide](docs/FIREFOX_COMPANION.md) explains profile differences
and the temporary-installation process. Build the unsigned development package
locally by following that guide.

## Teach Jeff your Kreol

Open **Kreol Glossary** from the page navigation and add a word or phrase with
its English or French meaning. You can also add spelling variations, your own
example sentence, and pronunciation or spelling notes. Entries can be reviewed,
searched, edited, or deleted there. The **My spellings** section lists personal
spelling choices that Jeff has saved.

When Jeff finds an uncertain spelling match in a chat message, it may show a
local **Did you mean...?** prompt. Select **Remember** for the intended word to
save that spelling on this computer, or select **Skip**. Jeff never saves a
suggestion without that click. Personal spellings are stored in
`~/.jeff/spelling_variants.json` and can be removed from **My spellings**.

The glossary is saved locally at `~/.jeff/kreol_glossary.sqlite3`. When you chat,
Jeff selects a few relevant entries (or recent examples) and sends them to the
configured Ollama server as context. This is personalization through retrieval,
not model training or fine-tuning. Jeff currently focuses on English and French
replies; the glossary remains available as a local Kreol reference.
Use examples you wrote or have permission to store. Glossary entries are sent
to the Ollama server along with the chat request.

You can also import a text-based vocabulary PDF from the glossary section. Jeff
extracts candidate words and meanings using the selected Ollama chat model, then
shows an editable preview. Review the spellings and translations, select only
the entries you want, and save them to your local glossary. Duplicate phrases
are skipped. PDF text is sent to the configured Ollama server for extraction;
scanned/image-only PDFs are not supported because OCR is not included. The
importer analyzes at most the first 18,000 characters and returns at most 40
candidates. Model-extracted meanings may be wrong, so check each candidate.

The [Creole Mauritius vocabulary dictionary](https://creolemauritius.com/vocabulary/)
can be used as a personal reference. Its
[terms](https://creolemauritius.com/terms-and-conditions/) allow sharing links
and short quotations, but prohibit automated scraping or copying the whole
dictionary into another app. Jeff does not scrape or bulk-import that site.

The bundled `dictionary.json` is based on *Diksyoner Kreol Morisyen —
Mauritian-English Dictionary with etymologies*, Version 1 (2012), compiled by
Andras Rajki and edited and published by Ahuv de Chazal. The source is released
under the Open Publication License v1.8 or later; retain this attribution and
check the applicable license terms when redistributing it.

## Privacy and limitations

The app sends chat prompts to the Ollama server configured in **Settings**. It
also sends relevant glossary entries with chat requests and relevant document
passages when documents are indexed or used to answer a question. Browser page
text is sent only when you add it to the next chat, and then only with that chat
request. With the
default localhost URL, Ollama runs on this computer. If you configure a remote
server, those prompts and selected context go to that server; only use an
address you trust. A compact status appears above each page, and Settings gives
the longer explanation.

The document index and conversation live in the current app session. The
glossary is stored locally in `~/.jeff/kreol_glossary.sqlite3`. Spellings that
you explicitly confirm are stored locally in `~/.jeff/spelling_variants.json`.
These personal files are not sent wholesale; relevant glossary entries and
spelling hints may be included in a prompt sent to the configured Ollama server.

English and French are requested through the system prompt; this is not a
guarantee of fluency. Reply language can be set in **Settings**; Auto uses a
lightweight word-based estimate, and non-French messages default to English.
Evaluate the selected models with real examples.
Scanned PDFs without a text layer are not OCR-processed. Only the most relevant
document passages are provided for each question.

## Tests

```bash
python -m unittest discover -s tests
node --test browser_extension/logic.test.js
web-ext lint --source-dir browser_extension
```

## Next phases

1. Add push-to-talk speech recognition and speech output after evaluating
   language quality and latency.
2. Add explicit, inspectable long-term memory controls.
3. Expand the companion's constrained tool set only after separate review and
   explicit confirmation.
