from __future__ import annotations

from typing import Any

import requests


class OllamaError(Exception):
    """Raised when Ollama cannot fulfill a request."""


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        timeout: int = 180,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model.strip()
        self.embedding_model = embedding_model.strip()
        self.timeout = timeout

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(
                f"{self.base_url}/api/{endpoint}",
                json=payload,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise OllamaError(
                f"Ollama did not return a response from /api/{endpoint} within "
                f"{self.timeout} seconds. The server is reachable, but the model may "
                "be taking too long to generate."
            ) from exc
        except requests.RequestException as exc:
            raise OllamaError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc

        if not response.ok:
            detail = response.text.strip() or response.reason
            raise OllamaError(f"Ollama returned HTTP {response.status_code}: {detail}")
        try:
            result = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise OllamaError("Ollama returned an invalid JSON response.") from exc
        if not isinstance(result, dict):
            raise OllamaError("Ollama returned an unexpected response.")
        return result

    def check_connection(self) -> None:
        self.available_models()

    def available_models(self) -> list[str]:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
        except requests.RequestException as exc:
            raise OllamaError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        if not response.ok:
            detail = response.text.strip() or response.reason
            raise OllamaError(f"Ollama returned HTTP {response.status_code}: {detail}")
        try:
            payload = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise OllamaError("Ollama returned an invalid model list.") from exc
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise OllamaError("Ollama returned an unexpected model list.")
        return [
            model["name"]
            for model in models
            if isinstance(model, dict) and isinstance(model.get("name"), str)
        ]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embedding_model:
            raise OllamaError("Choose an embedding model in the sidebar.")
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), 32):
            response = self._post(
                "embed",
                {"model": self.embedding_model, "input": texts[offset : offset + 32]},
            )
            batch = response.get("embeddings")
            if not isinstance(batch, list) or not all(
                isinstance(vector, list)
                and vector
                and all(isinstance(value, (int, float)) for value in vector)
                for vector in batch
            ):
                raise OllamaError("Ollama's embedding response did not contain valid vectors.")
            if len(batch) != min(32, len(texts) - offset):
                raise OllamaError("Ollama returned a different number of embeddings than requested.")
            vectors.extend([[float(value) for value in vector] for vector in batch])
        return vectors

    def chat(self, messages: list[dict[str, str]]) -> str:
        if not self.chat_model:
            raise OllamaError("Choose a chat model in the sidebar.")
        response = self._post(
            "chat",
            {
                "model": self.chat_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.25,
                    "num_predict": 128,
                    "repeat_penalty": 1.15,
                    "repeat_last_n": 64,
                },
            },
        )
        message = response.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama's chat response did not contain an answer.")
        return content.strip()

    def chat_json(self, messages: list[dict[str, str]], max_tokens: int = 2048) -> str:
        if not self.chat_model:
            raise OllamaError("Choose a chat model in the sidebar.")
        if max_tokens <= 0:
            raise ValueError("Maximum output tokens must be positive.")
        response = self._post(
            "chat",
            {
                "model": self.chat_model,
                "messages": messages,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": max_tokens},
            },
        )
        message = response.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama's structured response did not contain JSON.")
        return content.strip()
