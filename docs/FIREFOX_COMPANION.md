# Jeff Firefox Companion

This guide covers the separate Firefox extension, its local Python bridge,
installation and packaging, privacy behavior, supported actions, and
troubleshooting. The companion is separate from the Streamlit app's **Browser**
page. It does not give Jeff general control of your computer or other apps.

## What was built

The feature has two parts:

1. A Firefox WebExtension that opens a floating Jeff panel on the current tab.
   It reads page text only after you request it, and only offers a small set of
   fixed browser actions.
2. A Python HTTP bridge on `127.0.0.1:8765`. It authenticates extension
   requests and forwards chat to the configured Ollama server.

The request path is:

```text
Firefox toolbar click
  └─ background.js injects content.js into the active tab
       ├─ content.js displays chat, settings, previews, and action confirmations
       ├─ logic.js filters page text and recognizes supported action phrases
       └─ background.js sends authenticated requests to
            http://127.0.0.1:8765
              └─ bridge/server.py validates requests and calls bridge/assistant.py
                    └─ Ollama chat model
```

The extension uses Manifest V3 and a Firefox event page. Firefox may suspend
the background page, so alarms are used for refresh and monitoring tasks. Task
records and extension settings are stored in Firefox's local extension
storage.

## Project files

```text
bridge/
  __init__.py                 Python bridge package
  assistant.py                Builds Jeff's prompt and adds relevant local references
  server.py                   Authenticated loopback HTTP API and Ollama connection

browser_extension/
  manifest.json               Extension ID, permissions, and Firefox requirements
  background.js                Toolbar action, settings, bridge requests, and tasks
  content.js                   Floating panel, page capture, chat, confirmations
  logic.js                     Page-text filtering and constrained action parsing
  logic.test.js                JavaScript behavior tests
  options.html                 Extension origin and connection-status page
  options.js                   Options-page status and extension-origin display
  icons/
    jeff-icon.svg               Shared top-hat/bow-tie artwork for the widget
    icon-16.png … icon-512.png  Toolbar, install, and notification icon sizes
  test_pages/
    prompt_injection.html       Harmless local privacy and prompt-injection fixture

assets/
  jeff-icon.svg                 Streamlit favicon and sidebar brand mark

tests/
  test_bridge.py                Bridge authentication, validation, and prompt tests
  test_ui.py                    Streamlit page, state, privacy, and UI smoke tests

scripts/
  build_firefox_companion.py   Creates a curated unsigned XPI

dist/
  jeff-browser-companion.xpi   Generated extension package for import/testing

docs/
  FIREFOX_COMPANION.md         This guide
```

## Firefox profile and installation choices

Firefox keeps add-ons and their local settings inside a browser profile. A
Firefox Developer Edition window launched by `web-ext run` uses a temporary
development profile by default. That window is a different profile from your
usual Firefox window, even if both windows say **Firefox Developer Edition**.
The extension's token and preferences do not carry between those profiles.

### Load the XPI temporarily

Build the unsigned development package locally using the command in
[Build or lint the package](#build-or-lint-the-package). In Firefox Developer Edition:

1. Open `about:debugging#/runtime/this-firefox` in the profile you intend to use.
2. Choose **This Firefox**, then **Load Temporary Add-on…**.
3. Select the generated `dist/jeff-browser-companion.xpi` (or
   `browser_extension/manifest.json`).
4. On a normal website tab, click the Jeff action in the toolbar. If Firefox
   hides it, look in the Extensions menu.

A temporary add-on is removed when that Firefox profile closes or restarts.
Load it into the everyday profile you intend to use; loading it in a
`web-ext run` test window will not install it in another profile.
After rebuilding the XPI, open `about:debugging#/runtime/this-firefox` and use
the add-on's **Reload** action to load the updated package into the current
temporary installation.

### Install permanently or sync it

Firefox may reject the unsigned XPI with a message that the add-on has not been
verified. That is expected. A persistent install requires Mozilla to sign the
extension, usually by submitting it through the Add-on Developer Hub. This
project has not been submitted or published. After a signed version is
installed, desktop Firefox Sync can sync add-ons when **Add-ons** is selected
in Sync settings. Jeff's bridge token and extension preferences use
`browser.storage.local`; they remain local to each Firefox profile and must be
configured separately. See Mozilla's [temporary installation guide](https://extensionworkshop.com/documentation/develop/temporary-installation-in-firefox/),
[signing overview](https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/),
and [Firefox Sync options](https://support.mozilla.org/en-US/kb/how-do-i-choose-what-information-sync-firefox).

## Build or lint the package

The XPI contains the runtime extension files only. Tests and the local test
page are deliberately excluded. From the project root, rebuild it with:

```bash
python scripts/build_firefox_companion.py
```

The default output overwrites `dist/jeff-browser-companion.xpi`. To write it
somewhere else:

```bash
python scripts/build_firefox_companion.py --output /path/to/jeff-browser-companion.xpi
```

The XPI is a ZIP package, not a signed installer. To run the unpacked extension
in an isolated development profile, install `web-ext` and run:

```bash
npm install --global web-ext
web-ext lint --source-dir browser_extension
web-ext run \
  --source-dir browser_extension \
  --firefox "/Applications/Firefox Developer Edition.app/Contents/MacOS/firefox" \
  --start-url "http://127.0.0.1:8000/browser_extension/test_pages/prompt_injection.html"
```

`web-ext run` is useful for testing, but it opens a separate temporary
Firefox profile. Do not mistake its extension settings for the settings in your
everyday browser profile.

## Visual design

The Streamlit app uses the supported `[theme.light]` and `[theme.dark]`
sections in `.streamlit/config.toml`. The theme uses a warm off-white and
charcoal, readable system sans-serif text, system serif headings, a 16 px base
size, and rounded widgets. Light mode uses background `#FBF7F0`, surface
`#F1EAE0`, and text `#292722`; dark mode uses background `#211F1B`, surface
`#2B2924`, and text `#F4EFE6`. Jeff's teal is `#1F6F78`; the icon's gold is
`#E0B25F` and is reserved for small highlights. No web fonts, external CSS, or
remote images are loaded.

The Firefox widget defines its palette with CSS variables inside a closed
Shadow DOM, follows the widget's **Match Firefox / Light / Dark** setting,
respects reduced-motion and forced-colors preferences, and provides a visible
focus ring. The icon SVG is declared as a web-accessible extension resource
because the page-injected widget displays it; no other extension assets are
exposed to websites. The extension action and notifications use the supplied
PNG sizes.

## Start Ollama and the bridge

Keep the bridge terminal open while using the companion. Start Ollama first and
make sure the selected chat model is installed. The default configuration is
`qwen2.5:3b` for chat and `bge-m3` for embeddings.

From the project root, create a random token and start the bridge in the same
terminal:

```bash
export JEFF_BRIDGE_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export JEFF_OLLAMA_URL="http://127.0.0.1:11434"
export JEFF_CHAT_MODEL="qwen2.5:3b"
export JEFF_EMBEDDING_MODEL="bge-m3"
printf '%s' "$JEFF_BRIDGE_TOKEN" | pbcopy
python -m bridge.server
```

On macOS, `pbcopy` copies the token to the clipboard so it can be pasted into
the widget. If clipboard tools are unavailable, print the token with
`printf '%s\\n' "$JEFF_BRIDGE_TOKEN"` and copy it manually. Keep the bridge
terminal open; its environment variables last only for that process/terminal.
The bridge binds to loopback (`127.0.0.1`), not to the network.

Open Jeff on a regular website tab, expand **Jeff settings and privacy**, paste
the token in the password field, and click **Save settings**. The field clears
after saving by design; it does not display stored secrets back to the screen.
The status message should report whether the bridge and Ollama connected. The
token is stored in Firefox local extension storage, which is not encrypted by
Firefox. Protect the profile that stores it.

### Extension origin pinning

The bridge requires the token and validates the Firefox extension `Origin`.
Without `JEFF_EXTENSION_ORIGIN`, it pins the first Firefox extension origin
that successfully authenticates with the token. This avoids having to copy a
profile-specific UUID from the Options page. You can instead pin an origin
before startup by setting `JEFF_EXTENSION_ORIGIN` to the exact
`moz-extension://…` value shown on that profile's extension Options page.

Only one origin is accepted at a time. If you authenticate a different Firefox
profile, it will be rejected until the bridge restarts and pins that profile,
or you configure that profile's origin explicitly. A request from an
unauthenticated origin does not pin it. The bridge compares bearer tokens in
constant time and does not log prompts, page text, or tokens.

## Configuration and connection status

The bridge accepts these environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `JEFF_BRIDGE_TOKEN` | none; required | Shared bearer token for extension-to-bridge requests |
| `JEFF_EXTENSION_ORIGIN` | first authenticated extension origin | Optional exact origin pin |
| `JEFF_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama server URL |
| `JEFF_CHAT_MODEL` | `qwen2.5:3b` | Chat model name checked and used by the bridge |
| `JEFF_EMBEDDING_MODEL` | `bge-m3` | Embedding-model configuration passed to the Ollama client |
| `JEFF_BRIDGE_PORT` | `8765` | Local bridge port |

The widget checks the bridge when settings are saved and shows a local
connection status or a remote-server privacy warning. The Options page shows
the extension origin and a short connection status. If the Ollama URL is not
loopback, the bridge prints a privacy notice and chat plus selected page text
goes to that configured server. Use only a remote endpoint you trust.

## How to use Jeff

### Chat and page reading

- Click the toolbar action on a regular page to inject/open the floating Jeff
  panel. The panel's **Ask Jeff** button toggles the panel on that tab.
- Type a normal question for chat. Jeff displays a thinking state while the
  local bridge calls Ollama.
- Choose **Read this page** or **Read my selection** to capture context. Review
  the preview, then send a message if you want that text included in the chat.
- Captured page text stays in the current tab until you send it. A capture is
  capped at 12,000 characters. The extension omits form controls and values,
  buttons, scripts, hidden/aria-hidden text, embedded frames, and editable
  regions. It does not read password or card values.
- Chat history is held in the widget's current page session. The extension
  sends up to eight prior turns; the bridge keeps at most twelve when building
  the prompt. The bridge rejects messages over
  8,000 characters and page context over 12,000 characters.
- Language choices are Auto, English, French, and explicitly selected
  experimental Mauritian Kreol. Auto uses a lightweight language estimate;
  neither language detection nor model output is guaranteed accurate.

### Settings and site restrictions

Open **Jeff settings and privacy** to change the display name, reply language,
appearance, bridge token, blocked hosts, or optional allowed-host list. The
default block list covers common financial, email, account-login, and password
manager sites. A blocked match always takes precedence over the allow list.
When an allow list is non-empty, Jeff is enabled only on listed hosts.

Settings, the token, task records, and saved widget position are local to the
Firefox profile. Jeff is disabled in private windows. **Pause Jeff everywhere**
stops running tasks and disables chat/page actions until resumed.

### Supported browser actions

The extension implements fixed actions; it does not give the model arbitrary
browser or computer control. Supported requests include:

- `scroll to <literal text>` and `highlight <literal text>`: Jeff shows the
  proposed text and requires **Allow**. Highlights are temporary. Targets must
  be 2–120 characters and are matched as literal visible page text.
- `refresh every <number> seconds/minutes`: Jeff asks for confirmation first.
  Intervals below 30 seconds or above one day are rejected.
- `monitor this page for changes` / `watch this page for changes`, optionally
  with an interval or a literal target element: Jeff asks for confirmation.
  Monitoring checks visible page text locally, with a 30-second minimum
  interval.
- `stop monitoring`, `stop refreshing`, or `stop all tasks`: stops matching
  tasks in the current tab.

There is no general-purpose button clicking, form filling/submission, login,
purchase, app launching, shell command execution, or unrestricted access to
other apps. Page actions require confirmation. At most five tasks can run
across tabs in one Firefox profile. Task durations are selected from 15 minutes
through 24 hours; the default is two hours. Refresh tasks stop when their tab closes or changes
origin. Monitor tasks stop when their tab closes or navigates. Tasks do not
resume after Firefox restarts. Firefox and operating-system scheduling can
delay alarms, so intervals are not exact timing guarantees.

### Monitoring changes

Monitoring samples visible text locally and normalizes whitespace, common ad
labels, and timestamps to reduce noise. When it detects a change, it stores at
most a 600-character excerpt in Firefox local storage and sends a notification
without that excerpt. The excerpt is sent to Ollama only if you choose **Ask
Jeff to summarize this change**. Stop or clear a task to discard its stored
change excerpt.

## Data flow and privacy

The extension has no general website host permission. The toolbar click grants
temporary access to the active tab for script injection. Its standing network
permission is limited to `http://127.0.0.1:8765/*` for the local bridge. The
bridge only binds to `127.0.0.1`, requires a bearer token, validates the
extension origin, and suppresses HTTP request logging.

Data handling:

| Data | When it is used | Where it is stored or sent |
| --- | --- | --- |
| Chat text and recent chat history | When you send a chat message | Sent to the Ollama endpoint configured for the bridge |
| Visible/selected page excerpt | Only after you request capture and then send a message | Previewed in the tab; included in Ollama request only when submitted |
| Relevant local glossary, dictionary, or spelling references | When bridge prompt construction finds relevant references | Included in the Ollama chat request; not bulk-uploaded |
| Name, language, theme, site lists, token, task state, widget position | Settings or browser tasks | Firefox local extension storage; the name is not sent to Ollama |
| Monitor change excerpt | After a local monitor detects a change | Up to 600 characters stored locally; sent only after you choose to summarize |

Page content is JSON-encoded in an untrusted-data block in Jeff's prompt. The
prompt instructs the model to treat page content as reference data and not
instructions. This is a mitigation, not a guarantee against prompt injection.
Firefox's installation disclosure lists conversation and website-content data
types because the extension can send them to the configured Ollama server.
The companion does not search documents indexed by the Streamlit app or run
document retrieval. It uses only the submitted conversation/page context and
relevant local glossary, dictionary, or spelling references described above.

## Troubleshooting

### The widget is not visible

1. Confirm Jeff Browser Companion appears in `about:addons` for the profile
   currently showing your website.
2. If it was loaded temporarily, load it again after restarting Firefox.
3. Check the toolbar's Extensions menu if the Jeff action is not pinned.
4. Click the Jeff action on a regular website tab. Firefox internal pages,
   extension pages, and some protected pages do not allow injection.
5. Check whether the site is blocked or whether Jeff is paused.

### The token field clears after saving

This is intentional: the password field does not reveal a saved token. The
extension stores it in the current Firefox profile. Check the status message
below Jeff's privacy status. A different Firefox profile has separate settings
and will require its own token entry.

### Token or origin error

- Confirm the bridge process is still running in its terminal and uses the
  same token pasted into this Firefox profile.
- A `401` usually means missing or mismatched token.
- A `403` from the bridge can mean the origin is not a Firefox extension
  origin, or the bridge already pinned a different profile. Restart the bridge
  to clear a dynamic pin, then authenticate from the intended profile first;
  alternatively set `JEFF_EXTENSION_ORIGIN` explicitly.
- Do not send the token to anyone or paste it into a web page. It is a secret
  credential for the local bridge.

### Ollama or model error

- Start Ollama and check `ollama list`.
- Confirm `JEFF_OLLAMA_URL` points to the intended server and
  `JEFF_CHAT_MODEL` matches an installed model, such as `qwen2.5:3b`.
- Read **Technical details** in the widget for the underlying error.
- If Ollama is remote, confirm the address is trusted; message and submitted
  page context will be sent there.

### Firefox says the add-on is unverified

The repository XPI is unsigned. Load it as a temporary add-on in Developer
Edition for local testing. Permanent installation requires Mozilla signing.
Do not disable signature checks in a regular browsing profile.

## Local test fixture

The fixture contains fake sensitive form values and hostile prompt-injection
text. It contains no real credentials or personal information. Serve it from
the project root:

```bash
python -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/browser_extension/test_pages/prompt_injection.html`,
open Jeff, choose **Read this page**, and inspect the preview. The fake
password, card number, regular form value, and hidden text should not appear.
Ask Jeff to summarize the visible page; the hostile text should remain page
content and Jeff must not reveal the bridge token or claim to have sent it.
Also test Cancel and Allow on action/task proposals, Stop, global pause, a
blocked host, and private-window behavior.

## Automated checks

From the project root:

```bash
python -m unittest discover -s tests
node --test browser_extension/logic.test.js
web-ext lint --source-dir browser_extension
python scripts/build_firefox_companion.py
```

The Python tests cover bridge validation, authentication/origin pinning,
unreachable Ollama handling, and prompt construction. JavaScript tests cover
page filtering, supported action parsing, task validation, and monitor-text
normalization. The XPI build script verifies the ZIP archive and packages only
runtime extension files; signing is a separate Mozilla process.

## Implementation milestones

The feature was developed in these steps on the `feat/jeff-firefox-companion`
branch:

1. `1e54a1c` — authenticated local bridge and API foundation.
2. `798c0d1` — Firefox companion widget and settings.
3. `2e2cdd5` — opt-in page capture and companion chat.
4. `f614bc1` — confirmed page actions and monitor tasks.
5. `5387d36` — setup and privacy documentation.
6. `c9333cb` — easier first-run origin pairing and immediate connection check
   after saving settings.

The initial extension was tested in an isolated Firefox profile against the
local bridge and Ollama. The repository XPI is for local temporary installation
and review; it is not an AMO-signed release.
