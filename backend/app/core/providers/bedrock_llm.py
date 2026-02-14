"""AWS Bedrock LLM Provider implementation."""

from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings
from app.core.protocols import LLMProvider, LLMResponse, Message
from app.core.registry import register_provider

logger = logging.getLogger(__name__)


class BedrockLLMProvider(LLMProvider):
    """LLM provider using AWS Bedrock Converse API (Claude 3.5 Sonnet)."""

    def __init__(self, settings: Settings) -> None:
        self.client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        self.model_id = settings.bedrock_llm_model_id

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
        """Generate a completion using Bedrock Converse API."""
        target_model = model or self.model_id

        # 1. Format System Prompts and Messages
        # Bedrock Converse API expects system prompts in a separate field, not in messages list
        system_prompts = []
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompts.append({"text": msg.content})
            elif msg.role == "tool":
                # Handle tool results (future proofing)
                conversation_messages.append({
                    "role": "user",
                    "content": [{"toolResult": {"toolUseId": msg.tool_call_id, "content": [{"text": msg.content}]}}]
                })
            else:
                # User or Assistant messages
                content_block = {"text": msg.content}
                # If content is complex (image etc), handle here (omitted for now)
                
                conversation_messages.append({
                    "role": msg.role,
                    "content": [content_block]
                })

        try:
            # 2. Call Bedrock
            response = self.client.converse(
                modelId=target_model,
                messages=conversation_messages,
                system=system_prompts,
                inferenceConfig={
                    "temperature": temperature,
                    "maxTokens": max_tokens,
                },
                # toolConfig=... (if tools needed)
            )

            # 3. Parse Response
            output_message = response["output"]["message"]
            content_text = output_message["content"][0]["text"]
            usage = response.get("usage", {})

            return LLMResponse(
                content=content_text,
                model=target_model,
                usage={
                    "prompt_tokens": usage.get("inputTokens", 0),
                    "completion_tokens": usage.get("outputTokens", 0),
                },
                finish_reason=response.get("stopReason", "stop"),
                raw=response,
            )

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Bedrock API error: {e}", exc_info=True)
            raise

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> Any:
        """Stream a completion (Not implemented yet)."""
        raise NotImplementedError("Streaming not yet implemented for Bedrock provider.")


register_provider("llm", "bedrock", BedrockLLMProvider)
