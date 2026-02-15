"""judge.py — Adjudication query and feedback endpoints (The Judge).

The core adjudication route: accepts a rules question, resolves the
appropriate vector namespaces from the session's rulesets, enforces
billing limits, runs the RAG pipeline, and returns a structured verdict.

Endpoints:
    POST /api/v1/judge              → Submit a rules question
    POST /api/v1/judge/{id}/feedback → Submit feedback on a verdict

Called by: Frontend ChatInterface component via api.ts (submitQuery).
Depends on: deps.py (CurrentUser, DbSession, GetSettings),
            core/adjudication.py (AdjudicationEngine),
            core/registry.py (provider factory),
            tables.py (QueryAuditLog, Session, RulesetMetadata, Subscription, SubscriptionTier)

Architecture note for AI agents:
    Namespace resolution is CRITICAL. Each uploaded ruleset uses its
    UUID as the vector namespace in pgvector. The judge resolves these
    namespaces from session rulesets and queries only indexed ones.

    Session expiry is enforced here — expired sessions return 410 Gone.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException
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
from app.models.tables import QueryAuditLog, RulesetMetadata, Session, Subscription, SubscriptionTier

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

    Auth: JWT required.
    Rate limit: Tier-based (FREE=5/day, PRO=unlimited).
    Tier: All tiers (with limits).

    Flow:
        1. Validate session exists and is not expired
        2. Resolve vector namespaces from session's rulesets
        3. Check daily query limit based on subscription tier
        4. Run RAG adjudication pipeline
        5. Persist query + verdict to audit log
        6. Return structured verdict with citations

    Args:
        body: JudgeQuery with session_id, query text, optional ruleset_ids filter.

    Returns:
        JudgeVerdict with verdict text, confidence, citations, and conflicts.

    Raises:
        HTTPException: 404 if session not found, 410 if expired,
                       429 if rate limited, 500 if adjudication fails.
    """
    # ── 1. Validate session exists and is not expired ─────────────────────
    if body.session_id:
        session_result = await db.execute(
            select(Session).where(
                Session.id == body.session_id,
                Session.user_id == user["id"],
            )
        )
        session_record = session_result.scalar_one_or_none()

        if not session_record:
            raise HTTPException(status_code=404, detail="Session not found.")

        # WHY: Sessions have expiry dates (24h FREE, 30d PRO) set at creation.
        # Enforcing expiry here prevents queries against stale sessions.
        if session_record.expires_at and session_record.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=410,
                detail="Session has expired. Create a new session to continue.",
            )

    # ── 2. Resolve vector namespaces from session's rulesets ───────────────
    # WHY: In pgvector, namespace is the ruleset UUID string.
    namespaces: list[str] = []

    if body.session_id:
        # Build query to find indexed rulesets for this session
        ns_stmt = (
            select(RulesetMetadata.id)
            .where(
                RulesetMetadata.session_id == body.session_id,
                RulesetMetadata.status == "INDEXED",
            )
        )

        # If the frontend sent specific ruleset_ids, filter to only those
        if body.ruleset_ids:
            ns_stmt = ns_stmt.where(RulesetMetadata.id.in_(body.ruleset_ids))

        ns_result = await db.execute(ns_stmt)
        namespaces = [str(row[0]) for row in ns_result.all()]

    if not namespaces:
        raise HTTPException(
            status_code=409,
            detail=(
                "No indexed rulesets available for this session. "
                "Upload and finish indexing a ruleset first."
            ),
        )

    # ── 3. Resolve tier and check daily query limits ──────────────────────
    stmt = select(Subscription).where(Subscription.user_id == user["id"])
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    tier_name = subscription.plan_tier if subscription else "FREE"

    tier_stmt = select(SubscriptionTier).where(SubscriptionTier.name == tier_name)
    tier_result = await db.execute(tier_stmt)
    tier_config = tier_result.scalar_one_or_none()

    # Fallback if tier config missing (should include seed data)
    daily_limit = tier_config.daily_query_limit if tier_config else 5

    if daily_limit != -1:
        start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

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
                detail=(
                    f"Daily query limit reached ({usage_count}/{daily_limit}). "
                    "Upgrade to Pro for unlimited queries."
                ),
            )

    # ── 4. Run RAG adjudication pipeline ──────────────────────────────────
    registry = get_provider_registry()

    engine = AdjudicationEngine(
        llm=registry.get_llm(),
        embedder=registry.get_embedder(),
        vector_store=registry.get_vector_store(),
        reranker=registry.get_reranker(),
    )

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
            detail="An error occurred during adjudication. Please try again.",
        ) from exc

    # ── 5. Persist to audit log ───────────────────────────────────────────
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
        namespaces=namespaces,
    )

    # ── 6. Return structured verdict ──────────────────────────────────────
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
        model=verdict.model,
    )


@router.post("/judge/{query_id}/feedback", status_code=204)
async def submit_feedback(
    query_id: uuid.UUID,
    body: FeedbackRequest,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Submit feedback (thumbs up/down) for a verdict.

    Auth: JWT required (users can only rate their own queries).
    Rate limit: None.
    Tier: All tiers.

    Args:
        query_id: UUID of the query to leave feedback on.
        body: FeedbackRequest with feedback string ('up' or 'down').

    Raises:
        HTTPException: 404 if query not found.
    """
    result = await db.execute(
        update(QueryAuditLog)
        .where(
            QueryAuditLog.id == query_id,
            QueryAuditLog.user_id == user["id"],
        )
        .values(feedback=body.feedback)
    )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Query not found")

    logger.info("feedback_received", query_id=str(query_id), feedback=body.feedback)
