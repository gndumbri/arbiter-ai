"""Judge routes — adjudication query and feedback endpoints."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, DbSession, GetSettings
from app.core.adjudication import AdjudicationEngine
from app.core.registry import get_provider_registry
from app.models.schemas import (
    FeedbackRequest,
    JudgeQuery,
    JudgeVerdict,
    VerdictCitation,
    VerdictConflict,
)
from app.models.tables import QueryAuditLog, Subscription, SubscriptionTier

router = APIRouter(prefix="/api/v1", tags=["judge"])
logger = structlog.get_logger()


@router.post("/judge", response_model=JudgeVerdict)
async def submit_query(
    body: JudgeQuery,
    user: CurrentUser,
    db: DbSession,
    settings: GetSettings,
) -> JudgeVerdict:
    """Submit a rules question for adjudication.

    Enforces billing limits based on user's subscription tier.
    """
    # 1. Resolve User Tier
    # Check for active subscription
    stmt = select(Subscription).where(Subscription.user_id == user["id"])
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()
    
    tier_name = subscription.plan_tier if subscription else "FREE"
    
    # 2. Get Tier Limits
    tier_stmt = select(SubscriptionTier).where(SubscriptionTier.name == tier_name)
    tier_result = await db.execute(tier_stmt)
    tier_config = tier_result.scalar_one_or_none()
    
    # Fallback if tier config missing (should include seed data)
    daily_limit = tier_config.daily_query_limit if tier_config else 5
    
    # 3. Check Usage (if not unlimited)
    if daily_limit != -1:
        start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        usage_stmt = (
            select(func.count(QueryAuditLog.id))
            .where(QueryAuditLog.user_id == user["id"])
            .where(QueryAuditLog.created_at >= start_of_day)
        )
        usage_result = await db.execute(usage_stmt)
        usage_count = usage_result.scalar_one() or 0
        
        if usage_count >= daily_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Daily query limit reached ({usage_count}/{daily_limit}). Upgrade to Pro for unlimited queries.",
            )

    # 4. Proceed with Adjudication...
    registry = get_provider_registry()

    engine = AdjudicationEngine(
        llm=registry.get_llm(),
        embedder=registry.get_embedder(),
        vector_store=registry.get_vector_store(),
        reranker=registry.get_reranker(),
    )

    # Build namespace list from session
    # TODO: resolve actual namespaces from session's rulesets + official catalog
    namespaces = ["user_anonymous"]  # Placeholder
    if body.session_id:
        namespaces = [f"session_{body.session_id}"]

    try:
        verdict = await engine.adjudicate(
            query=body.query,
            namespaces=namespaces,
            game_name=body.game_name,
        )
    except Exception as exc:
        logger.exception("adjudication_failed", query=body.query[:100])
        raise HTTPException(
            status_code=500,
            detail=f"Adjudication failed: {exc}",
        ) from exc

    # Persist to audit log
    audit = QueryAuditLog(
        id=uuid.UUID(verdict.query_id),
        session_id=body.session_id,
        user_id=user["id"],
        query_text=body.query,
        expanded_query=verdict.expanded_query,
        verdict_summary=verdict.verdict[:500] if verdict.verdict else None,
        confidence=verdict.confidence,
        latency_ms=verdict.latency_ms,
    )
    db.add(audit)

    logger.info(
        "adjudication_complete",
        query_id=verdict.query_id,
        confidence=verdict.confidence,
        latency_ms=verdict.latency_ms,
    )

    return JudgeVerdict(
        query_id=uuid.UUID(verdict.query_id),
        verdict=verdict.verdict,
        confidence=verdict.confidence,
        reasoning_chain=verdict.reasoning_chain,
        citations=[
            VerdictCitation(
                source=c.source,
                page=c.page,
                section=c.section,
                snippet=c.snippet,
                is_official=c.is_official,
            )
            for c in verdict.citations
        ],
        conflicts=[
            VerdictConflict(
                description=c.description,
                resolution=c.resolution,
            )
            for c in verdict.conflicts
        ] if verdict.conflicts else None,
        follow_up_hint=verdict.follow_up_hint,
    )


@router.post("/judge/{query_id}/feedback", status_code=204)
async def submit_feedback(
    query_id: uuid.UUID,
    body: FeedbackRequest,
    db: DbSession,
) -> None:
    """Submit feedback (thumbs up/down) for a verdict."""
    result = await db.execute(
        update(QueryAuditLog)
        .where(QueryAuditLog.id == query_id)
        .values(feedback=body.feedback)
    )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Query not found")

    logger.info("feedback_received", query_id=str(query_id), feedback=body.feedback)
