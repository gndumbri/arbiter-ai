"""Adjudication engine — The Judge.

Processes user queries through the RAG pipeline:
    Query Expansion → Hybrid Retrieval → Reranking →
    Hierarchy Re-sort → Conflict Detection → Verdict Generation

All external dependencies injected via protocols.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.protocols import (
    EmbeddingProvider,
    LLMProvider,
    Message,
    RerankerProvider,
    VectorMatch,
    VectorStoreProvider,
)

logger = logging.getLogger(__name__)

# ─── System Prompt ─────────────────────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """You are an impartial board game tournament judge. Your role is to deliver
accurate, authoritative rulings based EXCLUSIVELY on the provided rule excerpts.

REASONING PROTOCOL:
- Think step-by-step. For complex questions, identify ALL relevant rules
  before forming a verdict.
- If multiple rules interact (e.g., a spell + a status effect + terrain),
  chain them explicitly: "Rule A says X → Rule B modifies X under condition Y → Therefore Z."
- Consider edge cases: timing conflicts, simultaneous effects, and rule
  precedence (Errata > Expansion > Base).

STRICT RULES:
1. Answer ONLY using the provided context chunks. Never use outside knowledge.
2. If the context is insufficient, respond: "I cannot find a specific rule
   covering this situation in the uploaded rulebook(s). I recommend checking
   [specific section/topic] in your rulebook."
3. When rules from an EXPANSION or ERRATA override BASE rules, explicitly
   state: "The [Expansion Name] overrides the base rule here."
4. Always cite the specific page number and section for every claim.
5. If rules conflict and priority is unclear, present BOTH interpretations
   and note the ambiguity. Never guess.
6. Keep your verdict concise but complete. Use bullet points for multi-part answers.
7. For complex interactions, show your reasoning chain before the final verdict.

CONFIDENCE CALIBRATION:
- 0.9-1.0: Rule text directly and unambiguously answers the question.
- 0.7-0.89: Answer requires inference from multiple rules, but is well-supported.
- 0.5-0.69: Answer involves interpretation; some ambiguity exists.
- Below 0.5: Insufficient context. Respond with uncertainty disclaimer.

You MUST respond with valid JSON matching this schema:
{
  "verdict": "string — the ruling in natural language",
  "reasoning_chain": "string — step-by-step logic (for complex queries)",
  "confidence": 0.0-1.0,
  "confidence_reason": "string — why this confidence level",
  "citations": [
    {"source": "...", "page": N, "section": "...",
     "snippet": "...", "is_official": bool}
  ],
  "conflicts": [{"description": "...", "resolution": "..."}] or null,
  "follow_up_hint": "string or null"
}"""

QUERY_EXPANSION_PROMPT = """You are a search query optimizer for board game rulebooks.

Given a user's natural-language question, produce:
1. An expanded, precise search query optimized for semantic retrieval
2. Key game-specific terms for keyword matching
3. If the query involves multiple rules interacting, decompose into sub-queries

Respond with valid JSON:
{
  "expanded_query": "string — rewritten for retrieval precision",
  "keywords": ["term1", "term2"],
  "sub_queries": ["query1", "query2"] or null
}"""


# ─── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class Citation:
    """A citation from a retrieved chunk."""

    source: str
    page: int | None
    section: str | None
    snippet: str
    is_official: bool = False


@dataclass
class Conflict:
    """A detected conflict between rules."""

    description: str
    resolution: str


@dataclass
class Verdict:
    """A complete adjudication verdict."""

    verdict: str
    reasoning_chain: str | None
    confidence: float
    confidence_reason: str | None
    citations: list[Citation]
    conflicts: list[Conflict] | None
    follow_up_hint: str | None
    query_id: str
    latency_ms: int = 0
    expanded_query: str = ""


# ─── The Judge ─────────────────────────────────────────────────────────────────


class AdjudicationEngine:
    """The Judge — processes queries through the full RAG pipeline.

    All dependencies are protocol-typed and injected via constructor.
    Swap LLM, embedder, vector store, or reranker without changing this code.
    """

    def __init__(
        self,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        vector_store: VectorStoreProvider,
        reranker: RerankerProvider,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._vector_store = vector_store
        self._reranker = reranker

    async def adjudicate(
        self,
        query: str,
        *,
        namespaces: list[str],
        game_name: str | None = None,
    ) -> Verdict:
        """Process a user query through the full adjudication pipeline."""
        start = time.perf_counter()
        query_id = str(uuid.uuid4())

        # Step 1: Query Expansion
        expansion = await self._expand_query(query)
        expanded_query = expansion.get("expanded_query", query)
        sub_queries = expansion.get("sub_queries") or []
        # keywords reserved for future BM25 boost

        logger.info(
            "Query expanded",
            extra={
                "original": query,
                "expanded": expanded_query,
                "sub_queries": len(sub_queries),
            },
        )

        # Step 2: Hybrid Retrieval (fan-out across namespaces)
        all_queries = [expanded_query, *sub_queries]
        all_matches: list[VectorMatch] = []

        for q in all_queries:
            query_vector = await self._embedder.embed_query(q)
            for ns in namespaces:
                matches = await self._vector_store.query(
                    query_vector, top_k=50, namespace=ns
                )
                all_matches.extend(matches)

        # Deduplicate by vector ID, keeping highest score
        unique_matches = self._deduplicate_matches(all_matches)
        logger.info("Retrieved %d unique chunks", len(unique_matches))

        if not unique_matches:
            return Verdict(
                verdict="I cannot find any relevant rules in the uploaded rulebook(s).",
                reasoning_chain=None,
                confidence=0.0,
                confidence_reason="No matching chunks found in vector store",
                citations=[],
                conflicts=None,
                follow_up_hint="Try uploading the relevant rulebook first.",
                query_id=query_id,
                latency_ms=self._elapsed_ms(start),
                expanded_query=expanded_query,
            )

        # Step 3: Cross-Encoder Reranking (top 50 → top 10)
        doc_texts = [m.metadata.get("text", "") for m in unique_matches]
        reranked = await self._reranker.rerank(
            expanded_query, doc_texts, top_n=10
        )

        # Step 4: Hierarchy Re-sort (source priority override)
        sorted_chunks = self._hierarchy_resort(reranked, unique_matches)

        # Step 5: Conflict Detection
        conflicts = self._detect_conflicts(sorted_chunks, unique_matches)

        # Step 6: Verdict Generation
        context = self._build_context(sorted_chunks, unique_matches, conflicts)
        verdict = await self._generate_verdict(query, context)

        # Build citations from top chunks
        citations = self._extract_citations(sorted_chunks, unique_matches)

        latency_ms = self._elapsed_ms(start)

        return Verdict(
            verdict=verdict.get("verdict", ""),
            reasoning_chain=verdict.get("reasoning_chain"),
            confidence=float(verdict.get("confidence", 0.5)),
            confidence_reason=verdict.get("confidence_reason"),
            citations=citations,
            conflicts=[
                Conflict(description=c["description"], resolution=c["resolution"])
                for c in (verdict.get("conflicts") or [])
            ] or (conflicts if conflicts else None),
            follow_up_hint=verdict.get("follow_up_hint"),
            query_id=query_id,
            latency_ms=latency_ms,
            expanded_query=expanded_query,
        )

    # ─── Step 1: Query Expansion ──────────────────────────────────────────────

    async def _expand_query(self, query: str) -> dict[str, Any]:
        """Expand and decompose the user query for better retrieval."""
        try:
            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=QUERY_EXPANSION_PROMPT),
                    Message(role="user", content=query),
                ],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            return json.loads(response.content)
        except Exception as exc:
            logger.warning("Query expansion failed, using original: %s", exc)
            return {"expanded_query": query, "keywords": [], "sub_queries": None}

    # ─── Step 4: Hierarchy Re-sort ────────────────────────────────────────────

    def _hierarchy_resort(
        self,
        reranked: list,
        original_matches: list[VectorMatch],
    ) -> list:
        """Re-sort reranked results by source priority (Errata > Expansion > Base)."""
        # Map original match index to metadata
        match_map = {i: m for i, m in enumerate(original_matches)}

        sorted_results = sorted(
            reranked,
            key=lambda r: (
                -match_map.get(r.index, VectorMatch(id="", score=0))
                .metadata.get("source_priority", 0),
                -r.score,
            ),
        )
        return sorted_results[:8]  # Dynamic context window: top 5-8

    # ─── Step 5: Conflict Detection ───────────────────────────────────────────

    def _detect_conflicts(
        self,
        sorted_chunks: list,
        original_matches: list[VectorMatch],
    ) -> list[Conflict] | None:
        """Detect conflicts between BASE and EXPANSION/ERRATA rules."""
        conflicts = []
        seen_topics: dict[str, list[dict[str, Any]]] = {}

        for chunk in sorted_chunks:
            idx = chunk.index
            if idx >= len(original_matches):
                continue
            meta = original_matches[idx].metadata
            section = meta.get("section_header", "")
            source_type = meta.get("source_type", "BASE")

            if section not in seen_topics:
                seen_topics[section] = []
            seen_topics[section].append(
                {"source_type": source_type, "text": chunk.text[:200]}
            )

        for section, entries in seen_topics.items():
            source_types = {e["source_type"] for e in entries}
            if len(source_types) > 1 and "BASE" in source_types:
                conflicts.append(
                    Conflict(
                        description=f"Conflicting rules in '{section}': "
                        f"found {', '.join(source_types)}",
                        resolution="Higher-priority source takes precedence "
                        "(Errata > Expansion > Base)",
                    )
                )

        return conflicts or None

    # ─── Step 6: Verdict Generation ───────────────────────────────────────────

    async def _generate_verdict(
        self,
        query: str,
        context: str,
    ) -> dict[str, Any]:
        """Generate the final verdict using the LLM."""
        try:
            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=JUDGE_SYSTEM_PROMPT),
                    Message(
                        role="user",
                        content=f"CONTEXT:\n{context}\n\nQUESTION:\n{query}",
                    ),
                ],
                temperature=0.0,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse verdict JSON, returning raw")
            return {
                "verdict": response.content if 'response' in dir() else "Error generating verdict",
                "confidence": 0.3,
                "confidence_reason": "Failed to parse structured response",
                "citations": [],
            }
        except Exception as exc:
            logger.exception("Verdict generation failed")
            return {
                "verdict": f"An error occurred while generating the verdict: {exc}",
                "confidence": 0.0,
                "confidence_reason": "Internal error",
                "citations": [],
            }

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _deduplicate_matches(matches: list[VectorMatch]) -> list[VectorMatch]:
        """Deduplicate by vector ID, keeping highest score."""
        seen: dict[str, VectorMatch] = {}
        for m in matches:
            if m.id not in seen or m.score > seen[m.id].score:
                seen[m.id] = m
        return sorted(seen.values(), key=lambda x: -x.score)

    @staticmethod
    def _build_context(
        sorted_chunks: list,
        original_matches: list[VectorMatch],
        conflicts: list[Conflict] | None,
    ) -> str:
        """Build the context string for the LLM from retrieved chunks."""
        lines = []
        for i, chunk in enumerate(sorted_chunks):
            idx = chunk.index
            if idx >= len(original_matches):
                continue
            meta = original_matches[idx].metadata
            source_type = meta.get("source_type", "BASE")
            label = f"[{source_type}]"
            if source_type in ("EXPANSION", "ERRATA"):
                label = f"[{source_type} OVERRIDE]"

            page = meta.get("page_number", "?")
            section = meta.get("section_header", "")
            lines.append(
                f"--- Chunk {i + 1} {label} (p.{page}, {section}) ---\n{chunk.text}"
            )

        if conflicts:
            lines.append("\n⚠️ CONFLICT DETECTED:")
            for c in conflicts:
                lines.append(f"  - {c.description} → {c.resolution}")

        return "\n\n".join(lines)

    @staticmethod
    def _extract_citations(
        sorted_chunks: list,
        original_matches: list[VectorMatch],
    ) -> list[Citation]:
        """Extract citations from the top chunks."""
        citations = []
        for chunk in sorted_chunks[:5]:  # Top 5 citations
            idx = chunk.index
            if idx >= len(original_matches):
                continue
            meta = original_matches[idx].metadata
            citations.append(
                Citation(
                    source=meta.get("game_name", "Unknown"),
                    page=meta.get("page_number"),
                    section=meta.get("section_header"),
                    snippet=chunk.text[:300],
                    is_official=meta.get("is_official", False),
                )
            )
        return citations

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        """Calculate elapsed milliseconds."""
        return round((time.perf_counter() - start) * 1000)
