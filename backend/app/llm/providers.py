"""Provider adapters.

Each adapter takes a prompt and returns text plus token counts. Adding a
provider means adding one class here; no caller changes. The null provider
exists so the whole app runs, tests pass, and the demo degrades gracefully
when no key is configured.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.exceptions import LLMUnavailable
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class Completion:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = ""


class Provider(Protocol):
    name: str

    async def complete(
        self, *, system: str, prompt: str, model: str, max_tokens: int, json_mode: bool
    ) -> Completion: ...


class AnthropicProvider:
    name = "anthropic"
    endpoint = "https://api.anthropic.com/v1/messages"

    async def complete(self, *, system, prompt, model, max_tokens, json_mode):
        key = settings.anthropic_api_key
        if not key:
            raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if json_mode:
            # Prefilling the assistant turn is the cheapest way to force JSON.
            payload["messages"].append({"role": "assistant", "content": "{"})
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        text = "".join(b.get("text", "") for b in data.get("content", []))
        if json_mode:
            text = "{" + text
        usage = data.get("usage", {})
        return Completion(
            text=text,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            model=model,
            provider=self.name,
        )


class GeminiProvider:
    name = "gemini"
    base = "https://generativelanguage.googleapis.com/v1beta/models"

    async def complete(self, *, system, prompt, model, max_tokens, json_mode):
        key = settings.google_api_key
        if not key:
            raise LLMUnavailable("GOOGLE_API_KEY is not set")
        generation: dict = {"maxOutputTokens": max_tokens, "temperature": 0.1}
        if json_mode:
            generation["responseMimeType"] = "application/json"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation,
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base}/{model}:generateContent",
                headers={"x-goog-api-key": key, "content-type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        candidates = data.get("candidates") or []
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {})
        return Completion(
            text=text,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            model=model,
            provider=self.name,
        )


class OpenAICompatibleProvider:
    """Covers OpenAI, Groq, Together and anything else speaking the same
    schema. Base URL and key are injected so one class serves several."""

    def __init__(self, name: str, base_url: str, api_key: str | None) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def complete(self, *, system, prompt, model, max_tokens, json_mode):
        if not self.api_key:
            raise LLMUnavailable(f"{self.name} API key is not set")
        payload: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        choices = data.get("choices") or [{}]
        text = choices[0].get("message", {}).get("content", "") or ""
        usage = data.get("usage", {})
        return Completion(
            text=text,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=model,
            provider=self.name,
        )


class NullProvider:
    """No key configured. Returns an empty JSON object so every downstream
    parser takes its 'nothing extracted' path instead of exploding."""

    name = "null"

    async def complete(self, *, system, prompt, model, max_tokens, json_mode):
        log.warning("no LLM provider configured; returning empty completion")
        return Completion(text="{}" if json_mode else "", model="null", provider="null")


def build_provider(name: str | None = None) -> Provider:
    name = (name or settings.llm_provider or "null").lower()
    if name == "anthropic":
        return AnthropicProvider()
    if name in {"gemini", "google"}:
        return GeminiProvider()
    if name == "openai":
        return OpenAICompatibleProvider(
            "openai", "https://api.openai.com/v1", settings.openai_api_key
        )
    if name == "groq":
        return OpenAICompatibleProvider(
            "groq", "https://api.groq.com/openai/v1", settings.groq_api_key
        )
    return NullProvider()
