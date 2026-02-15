"""Tests for Pydantic schemas — validation rules."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    FeedbackSubmit,
    JudgeQuery,
    SessionCreate,
)


def test_session_create_valid():
    """Valid session creation should pass."""
    session = SessionCreate(game_name="Root")
    assert session.game_name == "Root"


def test_session_create_empty_name_rejected():
    """Empty game name should be rejected."""
    with pytest.raises(ValidationError):
        SessionCreate(game_name="")


def test_judge_query_valid():
    """Valid judge query should pass."""
    query = JudgeQuery(session_id=uuid.uuid4(), query="Can I attack?")
    assert len(query.query) > 0


def test_judge_query_too_long():
    """Query exceeding 500 chars should be rejected."""
    with pytest.raises(ValidationError):
        JudgeQuery(session_id=uuid.uuid4(), query="x" * 501)


def test_judge_query_history_too_many_turns_rejected():
    """History exceeding max turn count should be rejected."""
    with pytest.raises(ValidationError):
        JudgeQuery(
            session_id=uuid.uuid4(),
            query="Follow-up question",
            history=[{"role": "user", "content": "x"}] * 9,
        )


def test_feedback_valid_values():
    """Feedback must be 'up' or 'down'."""
    assert FeedbackSubmit(feedback="up").feedback == "up"
    assert FeedbackSubmit(feedback="down").feedback == "down"


def test_feedback_invalid_value():
    """Invalid feedback value should be rejected."""
    with pytest.raises(ValidationError):
        FeedbackSubmit(feedback="maybe")
