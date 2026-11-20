# Jeff conversation guide

Jeff is a local-first conversational assistant built with Streamlit and Ollama.
For installation and startup instructions, see the project [README](../README.md).

## Choosing a reply language

Jeff currently focuses on English and French replies. On the **Settings** page,
choose a fixed reply language or **Auto (match my message)**. Auto uses a
lightweight detector to choose French for French messages and English otherwise.
Detection is approximate, and model fluency is not guaranteed.

You can also request a language directly, for example:

- “Please answer in English.”
- “Réponds-moi en français.”

The selected language instruction takes priority over earlier messages.
Language selection is prompt guidance, not a guarantee of fluency; results
depend on the selected Ollama model. These settings remain selected while
moving between pages in the current browser session.

## Setting a mood

Choose a mood on the **Settings** page. It affects Jeff's response tone for the
current session and is not saved as a long-term preference:

- 😊 Happy
- 😌 Calm
- 🤔 Curious
- 😕 Stressed
- 😞 Sad
- 😴 Tired

The selected mood affects response tone. It is held in the current Streamlit
session and survives page switches, but is not saved as a long-term preference.

## Informal Kreol spelling

Jeff receives dictionary-based spelling hints for some informal Kreol forms,
including sound-alike spellings and consonant-only forms. They are suggestions,
not definitive interpretations, and are not meant to be repeated in the answer.
When Jeff finds an uncertain match, the Chat page may ask **Did you mean...?**
Choose **Remember** to explicitly save your spelling locally, or **Skip** to
dismiss the suggestion. Manage saved entries under **My spellings** on the
**Kreol Glossary** page, where each spelling can be forgotten. Clear matches do
not need confirmation. Dictionary lookup uses exact headwords rather than
matching arbitrary substrings.

The local dictionary is a reference for hints, not a complete account of
Mauritian Kreol. Jeff should not correct the user's spelling or treat missing
dictionary entries as proof that a word is not Kreol.

When a message is written in Kreol, Auto currently asks Jeff to reply in
English. The glossary and personal spelling tools remain available as references.

## Streamlit browser page

Use the **Browser** page to start Jeff's separate Firefox Developer Edition
profile, open a website, and read its visible text. The page text stays in the
current Streamlit session until you select **Add this page to my next chat**.
Then that text is sent with your next prompt to the Ollama server. Jeff's first
browser page is read-only; it does not click, fill, or submit page controls.

## VPN location controls

On macOS, use the **VPN location** page or ask Jeff to connect to one of the
saved OpenVPN Connect locations. Jeff shows the profile and waits for a click
before connecting or disconnecting. The VPN applies to the whole Mac; reload a
webpage after connecting. A website may use other location signals. See the
[VPN controls guide](VPN_CONTROL.md) for setup and limitations.

## Firefox companion

The optional floating Firefox WebExtension is separate from the Streamlit
Browser page. It reads text only after you ask and offers user-confirmed
scroll/highlight, refresh, and monitoring tasks. The first companion release
supports an explicitly selected experimental Kreol reply option; Auto remains
English/French. See the [Firefox Companion guide](FIREFOX_COMPANION.md) for
permissions, local bridge setup, privacy behavior, and testing.

## Testing

Run the project tests from the repository root:

```bash
python -m unittest discover -s tests
```
