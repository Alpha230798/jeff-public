# Jeff macOS app package

Jeff can be built as an Apple Silicon SwiftUI `.app` inside a compressed
`.dmg`. The app opens its own native window and starts a bundled Python
service bound to `127.0.0.1`; it does not start Streamlit or open a browser for
its interface. The service requires a per-launch random token and accepts
requests only from the native client.

## Requirements that stay separate

The DMG does not include Ollama, chat or embedding model weights, Firefox,
OpenVPN Connect, or user data. Install and run Ollama on this Mac, then download
the configured models. Jeff only accepts a local Ollama address in the native
app. Firefox Developer Edition and OpenVPN Connect are needed only for their
optional Browser and VPN features. The glossary and spelling memory continue
to use the existing `~/.jeff` locations.

## Build on Apple Silicon macOS

Install Xcode (including its command-line tools) and the project dependencies.
Then use the project virtual environment to install the build-only dependency:

```bash
.venv312/bin/python -m pip install -r requirements-build.txt
.venv312/bin/python packaging/macos/build_dmg.py
```

The build creates:

- `dist/Jeff.app`
- `dist/Jeff-macos-arm64.dmg`

## Install and first launch

Open the DMG, drag `Jeff.app` to Applications, and eject the mounted disk image.
Launch Jeff from Applications rather than from the mounted DMG. The app has its
own SwiftUI window and starts its bundled service; it does not open the
Streamlit development UI or a browser.

The repository build is ad-hoc signed, not signed or notarized with an Apple
Developer ID. Gatekeeper can reject a normal first launch. If macOS says it
cannot verify the developer or cannot check the app for malicious software,
and you trust that this DMG came from the Jeff repository, Control-click
`Jeff.app` in Applications, choose **Open**, and confirm the per-app prompt.
If **Open** is not offered there, try launching Jeff once, then look in System
Settings → Privacy & Security for **Open Anyway**. This approves Jeff only; it
does not disable Gatekeeper globally.

Do not use these steps for an alert that says the app contains malware or will
damage your computer. Cancel that launch, delete that copy, and obtain a fresh
DMG from the repository. For ordinary signature or launch failures, verify the
DMG and contact the maintainer with the exact macOS alert.

Ollama and its chat/embedding models are not bundled. Ollama is needed to chat,
but a running model is not required just to open Jeff. The bundled service is
local-only and is launched by the native app. Document indexes and chat
history stay in the app session; the glossary and confirmed spelling choices
are stored locally. Service logs are at
`~/Library/Logs/Jeff/native-service-launch.log`.

The sidebar footer shows whether Jeff's local service is ready and whether the
Mac can reach the internet. Internet connectivity is checked every 30 seconds;
an estimated download speed is measured at startup and every five minutes by
downloading a 1 MB test file from Cloudflare. The checks send no prompts or
personal content.

This build targets Apple Silicon and macOS 13 or later. A distribution build
that opens without a per-app Gatekeeper approval requires an Apple Developer ID
signature and notarization. An Intel Mac needs a separate x86_64 build.

## Troubleshooting

- **A verification window closes before Jeff opens:** copy the app to
  Applications and use the per-app approval above. This development build is
  not notarized, so normal Gatekeeper assessment can reject it.
- **Jeff opens but says its local service did not start:** check
  `~/Library/Logs/Jeff/native-service-launch.log`, then reinstall by copying the
  complete app from a freshly downloaded DMG.
- **The window opens but chat is unavailable:** start Ollama and make sure the
  selected chat and embedding models are downloaded.

## Verification

Run `python -m unittest discover -s tests` before packaging. Then mount the DMG,
copy Jeff to Applications, launch it, and check Chat, Documents, Glossary,
Settings, Browser, and VPN in the native window. Test Ollama, Firefox, and
OpenVPN separately if using those features. The DMG build script verifies the
image and app signature, but automated unit tests do not replace a fresh-install
launch test. Gatekeeper behavior also depends on the Mac and how the DMG was
downloaded.
