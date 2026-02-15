"""Unit tests for invite-link join flow in parties routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
from fastapi import HTTPException

from app.api.routes.parties import JoinViaLinkRequest, join_via_invite_link


@pytest.mark.asyncio
async def test_join_via_invite_link_passes_limiter_to_join_party() -> None:
    secret = "test-secret-at-least-32-bytes-long"
    party_id = uuid.uuid4()
    token = pyjwt.encode(
        {
            "sub": "party_invite",
            "party_id": str(party_id),
            "invited_by": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )
    body = JoinViaLinkRequest(token=token)
    user = {"id": uuid.uuid4(), "tier": "FREE"}
    db = object()
    limiter = object()
    join_party_mock = AsyncMock(return_value={"party_id": str(party_id), "status": "joined"})

    with patch(
        "app.api.routes.parties.get_settings",
        return_value=SimpleNamespace(nextauth_secret=secret),
    ):
        with patch("app.api.routes.parties.join_party", join_party_mock):
            result = await join_via_invite_link(body=body, user=user, db=db, limiter=limiter)

    assert result == {"party_id": str(party_id), "status": "joined"}
    join_party_mock.assert_awaited_once_with(party_id, user, db, limiter)


@pytest.mark.asyncio
async def test_join_via_invite_link_rejects_invalid_payload() -> None:
    secret = "test-secret-at-least-32-bytes-long"
    token = pyjwt.encode(
        {
            "sub": "party_invite",
            # Missing party_id on purpose
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )
    body = JoinViaLinkRequest(token=token)

    with patch(
        "app.api.routes.parties.get_settings",
        return_value=SimpleNamespace(nextauth_secret=secret),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await join_via_invite_link(
                body=body,
                user={"id": uuid.uuid4(), "tier": "FREE"},
                db=object(),
                limiter=object(),
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid invite link"
