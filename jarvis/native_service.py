from __future__ import annotations

import argparse
import base64
import binascii
import hmac
import ipaddress
import json
import logging
import os
import signal
import threading
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path, PurePath
from typing import Any
from urllib.parse import urlsplit

from jarvis.browser import BrowserError, FirefoxBrowser
from jarvis.conversation import (
    DICTIONARY_ENTRIES,
    MOOD_OPTIONS,
    build_messages,
)
from jarvis.documents import Chunk, DocumentError, extract_chunks, extract_pdf_text
from jarvis.glossary import (
    GlossaryDraft,
    GlossaryError,
    add_entries,
    add_entry,
    delete_entry,
    list_entries,
    relevant_entries,
    update_entry,
)
from jarvis.glossary_import import (
    GlossaryImportError,
    build_extraction_messages,
    parse_glossary_candidates,
)
from jarvis.ollama import OllamaClient, OllamaError
from jarvis.retrieval import cosine_similarity
from jarvis.ui.spelling import uncertain_spelling_suggestions
from jarvis.vpn import (
    VpnError,
    connect as connect_vpn,
    disconnect as disconnect_vpn,
    list_connections,
    requested_vpn_action,
)
from phonetic import SpellingIndex, forget_variant, load_variants


MAX_REQUEST_BYTES = 48 * 1024 * 1024
MAX_FILE_BYTES = 24 * 1024 * 1024
MAX_DOCUMENTS = 20
DEFAULT_SETTINGS = {
    "ollama_url": "http://localhost:11434",
    "chat_model": "qwen2.5:3b",
    "embedding_model": "bge-m3",
    "mood": "😌 Calm",
    "reply_language": "Auto (match my message)",
}
REPLY_LANGUAGES = {"Auto (match my message)", "English", "French"}
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


class APIError(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class UploadedDocument:
    name: str
    data: bytes

    def getvalue(self) -> bytes:
        return self.data


@dataclass
class DocumentIndex:
    chunks: list[Chunk]
    vectors: list[list[float]]


class NativeBackend:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._documents: DocumentIndex | None = None
        self._browser: FirefoxBrowser | None = None

    @staticmethod
    def settings(payload: Any) -> dict[str, str]:
        if not isinstance(payload, dict):
            raise APIError(HTTPStatus.BAD_REQUEST, "Settings must be an object.")
        settings = DEFAULT_SETTINGS | {
            key: value for key, value in payload.items() if key in DEFAULT_SETTINGS
        }
        for key in ("chat_model", "embedding_model"):
            value = settings[key]
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise APIError(
                    HTTPStatus.BAD_REQUEST,
                    f"Choose a valid {key.replace('_', ' ')} name.",
                )
            settings[key] = value.strip()
        if not isinstance(settings["mood"], str) or settings["mood"] not in MOOD_OPTIONS:
            raise APIError(HTTPStatus.BAD_REQUEST, "Choose one of Jeff's available moods.")
        if (
            not isinstance(settings["reply_language"], str)
            or settings["reply_language"] not in REPLY_LANGUAGES
        ):
            raise APIError(HTTPStatus.BAD_REQUEST, "Choose English, French, or automatic language.")
        settings["ollama_url"] = NativeBackend._local_ollama_url(settings["ollama_url"])
        return settings

    @staticmethod
    def _local_ollama_url(value: Any) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 2048:
            raise APIError(HTTPStatus.BAD_REQUEST, "Enter a valid local Ollama address.")
        candidate = value.strip().rstrip("/")
        try:
            parsed = urlsplit(candidate)
            host = parsed.hostname
            if (
                parsed.scheme not in {"http", "https"}
                or not host
                or parsed.path not in {"", "/"}
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError
            local = host.casefold() == "localhost" or ipaddress.ip_address(host).is_loopback
            if not local:
                raise ValueError
            parsed.port
        except ValueError as exc:
            raise APIError(
                HTTPStatus.BAD_REQUEST,
                "For privacy, Jeff only connects to an Ollama server on this Mac.",
            ) from exc
        return candidate

    @staticmethod
    def client(settings: dict[str, str]) -> OllamaClient:
        return OllamaClient(
            settings["ollama_url"],
            settings["chat_model"],
            settings["embedding_model"],
        )

    def handle(self, method: str, path: str, payload: Any) -> tuple[HTTPStatus, Any]:
        if method == "GET":
            return self._get(path)
        if method == "POST":
            if not isinstance(payload, dict):
                raise APIError(HTTPStatus.BAD_REQUEST, "Request body must be a JSON object.")
            return self._post(path, payload)
        if method == "PUT":
            if not isinstance(payload, dict):
                raise APIError(HTTPStatus.BAD_REQUEST, "Request body must be a JSON object.")
            return self._put(path, payload)
        if method == "DELETE":
            return self._delete(path)
        raise APIError(HTTPStatus.METHOD_NOT_ALLOWED, "That request method is not supported.")

    def _get(self, path: str) -> tuple[HTTPStatus, Any]:
        if path == "/api/health":
            return HTTPStatus.OK, {"ok": True}
        if path == "/api/documents":
            with self._lock:
                index = self._documents
                if index is None:
                    return HTTPStatus.OK, {"passages": 0, "sources": []}
                sources = sorted({chunk.source_label for chunk in index.chunks})
                return HTTPStatus.OK, {
                    "passages": len(index.chunks),
                    "sources": sources,
                }
        if path == "/api/glossary":
            return HTTPStatus.OK, [asdict(entry) for entry in list_entries()]
        if path == "/api/spellings":
            return HTTPStatus.OK, load_variants()
        if path == "/api/browser":
            with self._lock:
                return HTTPStatus.OK, {
                    "running": bool(self._browser and self._browser.running)
                }
        if path == "/api/browser/page":
            browser = self._require_browser()
            return HTTPStatus.OK, asdict(browser.read_current_page())
        if path == "/api/vpn":
            return HTTPStatus.OK, [asdict(connection) for connection in list_connections()]
        raise APIError(HTTPStatus.NOT_FOUND, "That Jeff service route was not found.")

    def _post(self, path: str, payload: dict[str, Any]) -> tuple[HTTPStatus, Any]:
        if path == "/api/models":
            settings = self.settings(payload.get("settings"))
            client = self.client(settings)
            models = client.available_models()
            return HTTPStatus.OK, {
                "reachable": True,
                "models": models,
                "chat_model_present": self._model_is_available(
                    settings["chat_model"], models
                ),
                "embedding_model_present": self._model_is_available(
                    settings["embedding_model"], models
                ),
            }
        if path == "/api/chat":
            return HTTPStatus.OK, self._chat(payload)
        if path == "/api/vpn/request":
            return HTTPStatus.OK, self._route_vpn_request(
                self._string(payload, "question", max_length=12000)
            )
        if path == "/api/documents":
            return HTTPStatus.OK, self._index_documents(payload)
        if path == "/api/documents/clear":
            with self._lock:
                self._documents = None
            return HTTPStatus.OK, {"cleared": True}
        if path == "/api/glossary":
            entry_id = add_entry(
                **self._glossary_fields(payload),
            )
            entry = next(item for item in list_entries() if item.id == entry_id)
            return HTTPStatus.CREATED, asdict(entry)
        if path == "/api/glossary/import":
            return HTTPStatus.OK, self._import_glossary_pdf(payload)
        if path == "/api/glossary/bulk":
            entries = payload.get("entries")
            if not isinstance(entries, list) or len(entries) > 40:
                raise APIError(HTTPStatus.BAD_REQUEST, "Provide up to 40 glossary candidates.")
            drafts = [
                GlossaryDraft(**self._glossary_fields(entry))
                for entry in entries
                if isinstance(entry, dict)
            ]
            if len(drafts) != len(entries):
                raise APIError(HTTPStatus.BAD_REQUEST, "Every glossary candidate must be an object.")
            added, skipped = add_entries(drafts)
            return HTTPStatus.OK, {"added": added, "skipped": skipped}
        if path == "/api/spellings/remember":
            variant = self._string(payload, "variant", max_length=100)
            canonical = self._string(payload, "canonical", max_length=100).lower()
            index = SpellingIndex(DICTIONARY_ENTRIES, load_variants())
            if canonical not in index.heads:
                raise APIError(HTTPStatus.BAD_REQUEST, "Choose one of Jeff's suggested dictionary words.")
            index.learn(variant, canonical)
            return HTTPStatus.OK, {"saved": True}
        if path == "/api/spellings/forget":
            variant = self._string(payload, "variant", max_length=100)
            return HTTPStatus.OK, {"forgotten": forget_variant(variant)}
        if path == "/api/browser/start":
            with self._lock:
                if self._browser is None or not self._browser.running:
                    self._browser = FirefoxBrowser()
                    self._browser.start()
                return HTTPStatus.OK, {"running": True}
        if path == "/api/browser/navigate":
            address = self._string(payload, "address", max_length=2048)
            current_url = self._require_browser().navigate(address)
            return HTTPStatus.OK, {"url": current_url}
        if path == "/api/browser/stop":
            with self._lock:
                browser, self._browser = self._browser, None
            if browser:
                browser.stop()
            return HTTPStatus.OK, {"running": False}
        if path.startswith("/api/vpn/"):
            parts = path.strip("/").split("/")
            if len(parts) != 4 or parts[1] != "vpn" or parts[3] not in {"connect", "disconnect"}:
                raise APIError(HTTPStatus.NOT_FOUND, "That Jeff service route was not found.")
            action = connect_vpn if parts[3] == "connect" else disconnect_vpn
            status = action(parts[2])
            return HTTPStatus.OK, {"status": status}
        raise APIError(HTTPStatus.NOT_FOUND, "That Jeff service route was not found.")

    def _put(self, path: str, payload: dict[str, Any]) -> tuple[HTTPStatus, Any]:
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[:2] != ["api", "glossary"]:
            raise APIError(HTTPStatus.NOT_FOUND, "That Jeff service route was not found.")
        try:
            entry_id = int(parts[2])
        except ValueError as exc:
            raise APIError(HTTPStatus.BAD_REQUEST, "Glossary entry ID must be a number.") from exc
        update_entry(entry_id, **self._glossary_fields(payload))
        entry = next((item for item in list_entries() if item.id == entry_id), None)
        if entry is None:
            raise APIError(HTTPStatus.NOT_FOUND, "That glossary entry no longer exists.")
        return HTTPStatus.OK, asdict(entry)

    def _delete(self, path: str) -> tuple[HTTPStatus, Any]:
        if path == "/api/documents":
            with self._lock:
                self._documents = None
            return HTTPStatus.OK, {"cleared": True}
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "glossary"]:
            try:
                entry_id = int(parts[2])
            except ValueError as exc:
                raise APIError(HTTPStatus.BAD_REQUEST, "Glossary entry ID must be a number.") from exc
            delete_entry(entry_id)
            return HTTPStatus.OK, {"deleted": True}
        raise APIError(HTTPStatus.NOT_FOUND, "That Jeff service route was not found.")

    def _chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self.settings(payload.get("settings"))
        question = self._string(payload, "question", max_length=12000)
        history = payload.get("history", [])
        if not isinstance(history, list) or len(history) > 8:
            raise APIError(HTTPStatus.BAD_REQUEST, "Chat history must contain at most 8 turns.")
        previous_turns: list[dict[str, str]] = []
        for turn in history:
            if (
                not isinstance(turn, dict)
                or turn.get("role") not in {"user", "assistant"}
                or not isinstance(turn.get("content"), str)
                or len(turn["content"]) > 12000
            ):
                raise APIError(HTTPStatus.BAD_REQUEST, "Chat history contains an invalid turn.")
            previous_turns.append({"role": turn["role"], "content": turn["content"]})

        passages: list[dict[str, str]] = []
        with self._lock:
            index = self._documents
        if index:
            query_vector = self.client(settings).embed([question])[0]
            ranked = sorted(
                zip(index.chunks, index.vectors),
                key=lambda pair: cosine_similarity(query_vector, pair[1]),
                reverse=True,
            )[:5]
            passages.extend(
                {
                    "citation": f"S{position}",
                    "source": chunk.source_label,
                    "text": chunk.text,
                }
                for position, (chunk, _) in enumerate(ranked, start=1)
            )
        browser_context = payload.get("browser_context")
        if browser_context is not None:
            if not isinstance(browser_context, dict):
                raise APIError(HTTPStatus.BAD_REQUEST, "Browser context must be an object.")
            title = self._string(browser_context, "title", max_length=500, allow_empty=True)
            url = self._string(browser_context, "url", max_length=2048, allow_empty=True)
            text = self._string(browser_context, "text", max_length=MAX_FILE_BYTES)
            passages.append(
                {
                    "citation": "B1",
                    "source": f"Firefox page: {title or url}",
                    "text": text,
                }
            )

        entries = relevant_entries(question, list_entries())
        client = self.client(settings)
        answer = client.chat(
            build_messages(
                question,
                passages,
                previous_turns,
                entries,
                mood=settings["mood"],
                reply_language=settings["reply_language"],
            )
        )
        return {
            "answer": answer,
            "passages": passages,
            "glossary_entries": [asdict(entry) for entry in entries],
            "spelling_suggestions": uncertain_spelling_suggestions(
                question,
                DICTIONARY_ENTRIES,
                load_variants(),
            ),
        }

    @staticmethod
    def _route_vpn_request(question: str) -> dict[str, Any]:
        request = requested_vpn_action(question)
        if request is None:
            return {"handled": False}
        action, target = request
        connections = list_connections()
        if action == "disconnect":
            active = [item for item in connections if item.status.casefold() == "connected"]
            if not active:
                return {
                    "handled": True,
                    "reply": "No OpenVPN profile appears to be connected, so I left the VPN unchanged.",
                }
            if len(active) > 1:
                return {
                    "handled": True,
                    "reply": "More than one VPN reports connected. Disconnect the extra connection in System Settings → VPN first.",
                }
            selected = active[0]
        else:
            if not target:
                return {
                    "handled": True,
                    "reply": "Which saved location would you like to use: Japan, Canada, or the United States?",
                }
            selected = next(
                (
                    item
                    for item in connections
                    if item.label.casefold().startswith(target.casefold())
                ),
                None,
            )
            if selected is None:
                return {
                    "handled": True,
                    "reply": f"I couldn't find a saved OpenVPN profile for {target}. No VPN change was made.",
                }
            if selected.status.casefold() == "connected":
                return {
                    "handled": True,
                    "reply": f"{selected.label} is already connected. Reload the webpage if you want it to check the VPN IP again.",
                }
            if selected.status.casefold() != "disconnected":
                return {
                    "handled": True,
                    "reply": f"{selected.label} is {selected.status.lower()}. Refresh the VPN page before trying again.",
                }
        return {
            "handled": True,
            "reply": f"I found {selected.label}. Please confirm before I {action} it.",
            "confirmation": {
                "action": action,
                "service_id": selected.service_id,
                "label": selected.label,
                "status": selected.status,
            },
        }

    def _index_documents(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self.settings(payload.get("settings"))
        files = payload.get("files")
        if not isinstance(files, list) or not files or len(files) > MAX_DOCUMENTS:
            raise APIError(
                HTTPStatus.BAD_REQUEST,
                f"Choose between 1 and {MAX_DOCUMENTS} documents.",
            )
        uploaded: list[UploadedDocument] = []
        for item in files:
            if not isinstance(item, dict):
                raise APIError(HTTPStatus.BAD_REQUEST, "Each document must have a name and data.")
            name = self._string(item, "name", max_length=255)
            if PurePath(name).name != name or PurePath(name).suffix.lower() not in ALLOWED_EXTENSIONS:
                raise APIError(HTTPStatus.BAD_REQUEST, f"{name}: unsupported document name or type.")
            encoded = self._string(item, "data", max_length=MAX_FILE_BYTES * 2)
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise APIError(HTTPStatus.BAD_REQUEST, f"{name}: invalid file data.") from exc
            if len(data) > MAX_FILE_BYTES:
                raise APIError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, f"{name}: file is too large.")
            uploaded.append(UploadedDocument(name, data))

        chunks, errors = extract_chunks(uploaded)
        if not chunks:
            details = " ".join(errors)
            raise APIError(
                HTTPStatus.BAD_REQUEST,
                "No readable text was found in the selected documents. " + details,
            )
        vectors = self.client(settings).embed([chunk.text for chunk in chunks])
        if len(vectors) != len(chunks):
            raise OllamaError("Ollama returned a different number of embeddings than requested.")
        with self._lock:
            self._documents = DocumentIndex(chunks, vectors)
        return {
            "passages": len(chunks),
            "sources": sorted({chunk.source_label for chunk in chunks}),
            "errors": errors,
        }

    def _import_glossary_pdf(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self.settings(payload.get("settings"))
        name = self._string(payload, "name", max_length=255)
        if PurePath(name).suffix.lower() != ".pdf":
            raise APIError(HTTPStatus.BAD_REQUEST, "Choose a PDF file.")
        encoded = self._string(payload, "data", max_length=MAX_FILE_BYTES * 2)
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise APIError(HTTPStatus.BAD_REQUEST, "The PDF data is invalid.") from exc
        if len(data) > MAX_FILE_BYTES:
            raise APIError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "The PDF is too large.")
        text, truncated = extract_pdf_text(UploadedDocument(name, data))
        response = self.client(settings).chat_json(build_extraction_messages(text))
        candidates = parse_glossary_candidates(response)
        return {
            "candidates": [asdict(candidate) for candidate in candidates],
            "truncated": truncated,
        }

    def _require_browser(self) -> FirefoxBrowser:
        with self._lock:
            browser = self._browser
        if browser is None or not browser.running:
            raise BrowserError("Start Jeff's Firefox browser before using it.")
        return browser

    @staticmethod
    def _glossary_fields(payload: Any) -> dict[str, str]:
        if not isinstance(payload, dict):
            raise APIError(HTTPStatus.BAD_REQUEST, "Glossary entry must be an object.")
        fields = (
            "kreol_phrase",
            "alternative_spellings",
            "english_meaning",
            "french_meaning",
            "example",
            "pronunciation_notes",
        )
        result: dict[str, str] = {}
        for field in fields:
            value = payload.get(field, "")
            if not isinstance(value, str) or len(value) > 4000:
                raise APIError(HTTPStatus.BAD_REQUEST, f"Glossary {field.replace('_', ' ')} must be text.")
            result[field] = value
        return result

    @staticmethod
    def _string(
        payload: dict[str, Any],
        key: str,
        *,
        max_length: int,
        allow_empty: bool = False,
    ) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or len(value) > max_length or (
            not allow_empty and not value.strip()
        ):
            raise APIError(HTTPStatus.BAD_REQUEST, f"Enter a valid {key.replace('_', ' ')}.")
        return value

    @staticmethod
    def _model_is_available(model: str, available: list[str]) -> bool:
        return model in available or (
            ":" not in model and f"{model}:latest" in available
        )

    def close(self) -> None:
        with self._lock:
            browser, self._browser = self._browser, None
        if browser:
            browser.stop()


class NativeServiceServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], token: str, backend: NativeBackend) -> None:
        self.token = token
        self.backend = backend
        super().__init__(address, NativeServiceHandler)


class NativeServiceHandler(BaseHTTPRequestHandler):
    server: NativeServiceServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        if not hmac.compare_digest(
            self.headers.get("Authorization", ""),
            f"Bearer {self.server.token}",
        ):
            self._respond(HTTPStatus.UNAUTHORIZED, {"error": "Jeff service authorization failed."})
            return
        try:
            payload = self._read_json() if method in {"POST", "PUT"} else None
            route = urlsplit(self.path).path
            status, response = self.server.backend.handle(method, route, payload)
        except APIError as exc:
            status, response = exc.status, {"error": str(exc)}
        except OllamaError as exc:
            status, response = HTTPStatus.BAD_GATEWAY, {"error": str(exc)}
        except (
            BrowserError,
            DocumentError,
            GlossaryError,
            GlossaryImportError,
            VpnError,
            ValueError,
        ) as exc:
            status, response = HTTPStatus.BAD_REQUEST, {"error": str(exc)}
        except Exception:
            logging.exception("Unexpected error handling %s %s", method, self.path)
            status, response = HTTPStatus.INTERNAL_SERVER_ERROR, {
                "error": "Jeff could not complete that request. Check the app log for details."
            }
        self._respond(status, response)

    def _read_json(self) -> Any:
        if self.headers.get("Transfer-Encoding"):
            raise APIError(HTTPStatus.BAD_REQUEST, "Chunked requests are not supported.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise APIError(HTTPStatus.BAD_REQUEST, "Invalid request size.") from exc
        if length < 0:
            raise APIError(HTTPStatus.BAD_REQUEST, "Invalid request size.")
        if length > MAX_REQUEST_BYTES:
            raise APIError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request is too large.")
        if length == 0:
            return {}
        if self.headers.get_content_type() != "application/json":
            raise APIError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Send JSON to Jeff's local service.")
        try:
            result = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise APIError(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON.") from exc
        return result

    def _respond(self, status: HTTPStatus, payload: Any) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_string: str, *args: Any) -> None:
        logging.info("%s - %s", self.client_address[0], format_string % args)


def _configure_logging() -> None:
    log_path = Path.home() / "Library" / "Logs" / "Jeff" / "native-service.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    logging.basicConfig(
        handlers=[handler],
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Jeff's authenticated local native-app service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    arguments = parser.parse_args()
    if arguments.host != "127.0.0.1":
        raise SystemExit("Jeff's native service must bind to 127.0.0.1.")
    if not 0 < arguments.port < 65536:
        raise SystemExit("Choose a valid local service port.")
    token = os.environ.get("JEFF_SERVICE_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("The local service token must be at least 32 characters.")

    _configure_logging()
    backend = NativeBackend()
    server = NativeServiceServer(
        (arguments.host, arguments.port),
        token,
        backend,
    )

    def request_shutdown(_signal_number: int, _frame: Any) -> None:
        del _signal_number, _frame
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    logging.info("Jeff local service listening on %s:%s", arguments.host, arguments.port)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        backend.close()


if __name__ == "__main__":
    main()
