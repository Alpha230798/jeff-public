from __future__ import annotations

import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from bridge.assistant import PAGE_LIMIT, answer
from jarvis.ollama import OllamaClient, OllamaError

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
BODY_LIMIT = 48_000
ALLOWED_LANGUAGES = {"Auto", "English", "French", "Mauritian Kreol (experimental)"}


class BridgeConfigError(RuntimeError):
    pass


def _loopback_ollama_url(value: str) -> bool:
    try:
        host = (urlsplit(value).hostname or "").lower()
    except ValueError:
        return False
    return host in {"localhost", "127.0.0.1", "::1"}


def _model_is_available(selected: str, models: list[str]) -> bool:
    installed = {model.casefold() for model in models}
    candidate = selected.strip().casefold()
    return candidate in installed or (":" not in candidate and f"{candidate}:latest" in installed)


def validate_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Send a JSON object.")
    message = value.get("message")
    if not isinstance(message, str) or not message.strip() or len(message) > 8_000:
        raise ValueError("The message must contain 1 to 8,000 characters.")
    settings = value.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("Settings must be an object.")
    language = settings.get("language", "Auto")
    if not isinstance(language, str) or language not in ALLOWED_LANGUAGES:
        raise ValueError("Choose Auto, English, French, or experimental Kreol.")
    if "name" in settings and (not isinstance(settings["name"], str) or len(settings["name"]) > 80):
        raise ValueError("The display name is too long.")
    history = value.get("history", [])
    if not isinstance(history, list) or len(history) > 40:
        raise ValueError("Conversation history is invalid.")
    page = value.get("page")
    if page is not None:
        if not isinstance(page, dict):
            raise ValueError("Page context is invalid.")
        if any(not isinstance(page.get(key, ""), str) for key in ("url", "title", "text")):
            raise ValueError("Page context fields must be text.")
        if len(page.get("text", "")) > PAGE_LIMIT:
            raise ValueError("Page text is too large. Reopen Jeff to capture a shorter excerpt.")
    return value


def _is_extension_origin(origin: str) -> bool:
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    return parsed.scheme == "moz-extension" and bool(parsed.hostname) and not parsed.path and not parsed.query and not parsed.fragment


def make_handler(token: str, origin: str | None, client: OllamaClient):
    if not token or (origin and not _is_extension_origin(origin)):
        raise BridgeConfigError("Set JEFF_BRIDGE_TOKEN and, optionally, a valid JEFF_EXTENSION_ORIGIN.")
    origin_lock = threading.Lock()
    pinned_origin = origin or None

    class Handler(BaseHTTPRequestHandler):
        server_version = "JeffBridge/1"

        def log_message(self, fmt: str, *args: Any) -> None:
            # Avoid logging prompts, page text, tokens, or user settings.
            return

        def _cors(self) -> bool:
            request_origin = self.headers.get("Origin", "")
            if not _is_extension_origin(request_origin):
                return False
            with origin_lock:
                return pinned_origin is None or hmac.compare_digest(request_origin, pinned_origin)

        def _cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", ""))
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        def _authorized(self) -> bool:
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {token}"
            if not hmac.compare_digest(supplied, expected):
                self.send_error(401, "Bridge token is missing or incorrect.")
                return False
            nonlocal pinned_origin
            request_origin = self.headers.get("Origin", "")
            with origin_lock:
                if pinned_origin is None:
                    pinned_origin = request_origin
                elif not hmac.compare_digest(request_origin, pinned_origin):
                    self.send_error(403, "This extension origin is not allowed.")
                    return False
            return True

        def _json(self, status: int, data: dict[str, Any]) -> None:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self) -> None:
            if not self._cors():
                self.send_error(403, "This extension origin is not allowed.")
                return
            self.send_response(204)
            self._cors_headers()
            self.end_headers()

        def do_GET(self) -> None:
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send_error(403, "Use the configured loopback address.")
                return
            if not self._cors():
                self.send_error(403, "This extension origin is not allowed.")
                return
            if not self._authorized():
                return
            if self.path != "/health":
                self.send_error(404, "Unknown bridge endpoint.")
                return
            if self.path == "/health":
                try:
                    models = client.available_models()
                    self._json(200, {
                        "ok": True,
                        "models": models,
                        "chat_model": client.chat_model,
                        "chat_model_available": _model_is_available(client.chat_model, models),
                        "ollama_url": client.base_url,
                        "ollama_local": _loopback_ollama_url(client.base_url),
                    })
                except OllamaError as exc:
                    self._json(503, {"ok": False, "error": str(exc)})

        def do_POST(self) -> None:
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send_error(403, "Use the configured loopback address.")
                return
            if not self._cors():
                self.send_error(403, "This extension origin is not allowed.")
                return
            if not self._authorized():
                return
            if self.path != "/chat":
                self.send_error(404, "Unknown bridge endpoint.")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error(400, "Invalid content length.")
                return
            if length <= 0 or length > BODY_LIMIT:
                self.send_error(413, "Request is empty or too large.")
                return
            try:
                payload = validate_payload(json.loads(self.rfile.read(length)))
                self._json(200, {"reply": answer(payload, client)})
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})
            except OllamaError as exc:
                self._json(503, {"error": str(exc)})

    return Handler


def main() -> None:
    token = os.environ.get("JEFF_BRIDGE_TOKEN", "")
    origin = os.environ.get("JEFF_EXTENSION_ORIGIN") or None
    ollama_url = os.environ.get("JEFF_OLLAMA_URL", "http://127.0.0.1:11434")
    if not _loopback_ollama_url(ollama_url):
        print("Privacy notice: Jeff will send chat and selected page text to remote Ollama:", ollama_url)
    client = OllamaClient(
        ollama_url,
        os.environ.get("JEFF_CHAT_MODEL", "qwen2.5:3b"),
        os.environ.get("JEFF_EMBEDDING_MODEL", "bge-m3"),
    )
    port = int(os.environ.get("JEFF_BRIDGE_PORT", DEFAULT_PORT))
    server = ThreadingHTTPServer((HOST, port), make_handler(token, origin, client))
    if origin is None:
        print("The first extension origin that authenticates with the bridge token will be pinned.")
    print(f"Jeff bridge listening on http://{HOST}:{port}; press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
