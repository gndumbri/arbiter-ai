"""Judge routes — adjudication query and feedback endpoints."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import update

from app.api.deps import DbSession, GetSettings
from app.core.adjudication import AdjudicationEngine
from app.core.registry import get_provider_registry
from app.models.schemas import (
    FeedbackRequest,
    JudgeQuery,
    JudgeVerdict,
    VerdictCitation,
    VerdictConflict,
)
from app.models.tables import QueryAuditLog

router = APIRouter(prefix="/api/v1", tags=["judge"])
logger = structlog.get_logger()


@router.post("/judge", response_model=JudgeVerdict)
async def submit_query(
    body: JudgeQuery,
    db: DbSession,
    settings: GetSettings,
) -> JudgeVerdict:
    """Submit a rules question for adjudication.

    The Judge processes the query through:
    1. Query expansion (LLM rewrites for retrieval precision)
    2. Hybrid search (dense + sparse across namespaces)
    3. Cross-encoder reranking (top 50 → top 10)
    4. Conflict detection (BASE vs EXPANSION)
    5. Verdict generation (chain-of-thought reasoning)
    """
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
