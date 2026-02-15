"""mock_llm.py — Mock LLM provider for testing without API calls.

Implements the LLMProvider protocol with canned responses.
Returns realistic verdicts based on query keyword matching.
No external API calls, no API keys needed.

Called by: AdjudicationEngine (via registry) when LLM_PROVIDER=mock
Depends on: protocols.py (LLMProvider), factory.py (canned verdicts)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.config import Settings
from app.core.protocols import LLMResponse, Message
from app.core.registry import register_provider

logger = logging.getLogger(__name__)


class MockLLMProvider:
    """Fake LLM that returns canned verdicts — zero external calls.

    Matches query keywords to pre-written responses for realistic
    demo behavior. All calls are logged for debugging.

    Usage:
        Set LLM_PROVIDER=mock or APP_MODE=mock to activate.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the mock LLM provider.

        Args:
            settings: App settings (not used, but required by registry interface).
        """
        self._settings = settings
        logger.info("🎭 MockLLMProvider initialized — no API calls will be made")

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
        """Return a canned completion based on the last user message.

        Extracts the user's query from the message list, matches keywords
        to canned responses, and returns an LLMResponse.

        Args:
            messages: Conversation messages (system + user + assistant).
            model: Ignored — always uses 'mock-llm-v1'.
            temperature: Ignored.
            max_tokens: Ignored.
            response_format: If set, wraps response in JSON format.
            **kwargs: Additional args (ignored).

        Returns:
            LLMResponse with canned verdict content.
        """
        # WHY: Extract the last user message to determine the query type.
        # The adjudication engine puts the user's question in the last
        # user message, which we use for keyword matching.
        user_query = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_query = msg.content
                break

        logger.debug(
            "MockLLM.complete called: query='%s', model=%s",
            user_query[:100],
            model or "mock-llm-v1",
        )

        # WHY: Simulate a small delay to make the mock feel realistic.
        # Without this, the UI would snap instantly, which doesn't
        # match the real LLM experience and could mask timing bugs.
        await asyncio.sleep(0.1)

        # Build a realistic verdict response
        from app.mock.factory import create_mock_verdict
        verdict = create_mock_verdict(user_query)

        # WHY: If response_format asks for JSON, wrap the verdict in JSON.
        # The adjudication engine uses JSON mode to parse verdicts.
        content = json.dumps(verdict) if response_format else verdict["verdict"]

        return LLMResponse(
            content=content,
            model="mock-llm-v1",
            usage={"prompt_tokens": 100, "completion_tokens": 200},
            finish_reason="stop",
            raw={"mock": True, "query_preview": user_query[:50]},
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> Any:
        """Stream a canned response in chunks to simulate streaming LLM output.

        Yields the verdict content word-by-word with small delays to
        mimic real-time token generation.

        Args:
            messages: Conversation messages.
            model: Ignored.
            temperature: Ignored.
            max_tokens: Ignored.
            **kwargs: Additional args (ignored).

        Yields:
            String chunks of the verdict, one word at a time.
        """
        # Get the complete response first, then stream it
        response = await self.complete(messages, model=model)
        words = response.content.split()

        async def _stream():
            for word in words:
                # WHY: 30ms delay per word ≈ ~200ms for a short sentence.
                # Fast enough to not be annoying, slow enough to see streaming.
                await asyncio.sleep(0.03)
                yield word + " "

        return _stream()


# ─── Provider Registration ────────────────────────────────────────────────────
# WHY: Self-registering on import — same pattern as all other providers.
# The registry picks this up when it imports the module.

register_provider("llm", "mock", MockLLMProvider)
