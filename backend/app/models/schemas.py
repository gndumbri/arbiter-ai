"""Pydantic v2 schemas for API request/response bodies."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ─── Health ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "healthy"
    database: str = "connected"
    redis: str = "connected"
    version: str = "0.1.0"


# ─── Users ─────────────────────────────────────────────────────────────────────


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    tier: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Sessions ──────────────────────────────────────────────────────────────────


class SessionCreate(BaseModel):
    game_name: str = Field(..., min_length=1, max_length=200)
    persona: str | None = None
    system_prompt_override: str | None = None
    # Optional ready-to-use official ruleset namespaces for immediate judge access.
    active_ruleset_ids: list[uuid.UUID] | None = None


class SessionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    game_name: str
    persona: str | None = None
    system_prompt_override: str | None = None
    active_ruleset_ids: list[uuid.UUID] | None = None
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


# ─── Rulesets ──────────────────────────────────────────────────────────────────


class RulesetStatusRead(BaseModel):
    id: uuid.UUID
    filename: str
    game_name: str
    source_type: str
    status: str
    chunk_count: int
    error_message: str | None = None

    model_config = {"from_attributes": True}


# ─── Judge ─────────────────────────────────────────────────────────────────────


class JudgeHistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class JudgeQuery(BaseModel):
    session_id: uuid.UUID
    query: str = Field(..., min_length=1, max_length=500)
    game_name: str | None = None
    ruleset_ids: list[uuid.UUID] | None = None
    history: list[JudgeHistoryTurn] | None = Field(default=None, max_length=8)


class VerdictCitation(BaseModel):
    source: str
    page: int | None = None
    section: str | None = None
    snippet: str
    is_official: bool = False


# Alias for backward compatibility
Citation = VerdictCitation


class VerdictConflict(BaseModel):
    description: str
    resolution: str


# Alias for backward compatibility
Conflict = VerdictConflict


class JudgeVerdict(BaseModel):
    verdict: str
    reasoning_chain: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_reason: str | None = None
    citations: list[VerdictCitation]
    conflicts: list[VerdictConflict] | None = None
    follow_up_hint: str | None = None
    query_id: uuid.UUID
    model: str = "unknown"


class FeedbackRequest(BaseModel):
    feedback: str = Field(..., pattern="^(up|down)$")


# Alias for backward compatibility
FeedbackSubmit = FeedbackRequest


# ─── Library ───────────────────────────────────────────────────────────────────


class LibraryGameRead(BaseModel):
    id: uuid.UUID
    game_name: str
    is_favorite: bool
    official_ruleset_ids: list[uuid.UUID] | None = None
    personal_ruleset_ids: list[uuid.UUID] | None = None
    last_queried: datetime | None = None

    model_config = {"from_attributes": True}


class LibraryAddGame(BaseModel):
    game_name: str = Field(..., min_length=1, max_length=200)
    official_ruleset_ids: list[uuid.UUID] | None = None


# ─── Catalog ───────────────────────────────────────────────────────────────────


class CatalogGameRead(BaseModel):
    id: uuid.UUID
    game_name: str
    game_slug: str
    publisher_name: str
    source_type: str
    version: str

    model_config = {"from_attributes": True}


# ─── Errors ────────────────────────────────────────────────────────────────────


class ErrorDetail(BaseModel):
    code: str
    message: str
    retry_after_seconds: int | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
