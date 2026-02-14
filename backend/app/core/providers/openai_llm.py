"""OpenAI LLM provider — GPT-4o / GPT-4o-mini implementation."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.config import Settings
from app.core.protocols import LLMResponse, Message
from app.core.registry import register_provider

logger = logging.getLogger(__name__)


class OpenAILLMProvider:
    """OpenAI chat completion provider.

    Supports both standard completions and streaming.
    """

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._default_model = settings.llm_model
        self._fast_model = settings.llm_model_fast

    def _to_openai_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert protocol Messages to OpenAI format."""
        result = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            result.append(entry)
        return result

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        response_format: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a chat completion."""
        target_model = model or self._default_model

        params: dict[str, Any] = {
            "model": target_model,
            "messages": self._to_openai_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            params["response_format"] = response_format

        response = await self._client.chat.completions.create(**params)
        choice = response.choices[0]

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason or "stop",
            raw=response.model_dump(),
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a chat completion, yielding content chunks."""
        target_model = model or self._default_model

        stream = await self._client.chat.completions.create(
            model=target_model,
            messages=self._to_openai_messages(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


# Self-register on import
register_provider("llm", "openai", OpenAILLMProvider)
