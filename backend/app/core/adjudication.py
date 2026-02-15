"""Adjudication engine — The Judge.

Processes user queries through the RAG pipeline:
    Query Expansion → Hybrid Retrieval → Reranking →
    Hierarchy Re-sort → Conflict Detection → Verdict Generation

All external dependencies injected via protocols.
"""

from __future__ import annotations

import json
import logging
import re
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

# ─── Prompt Templates ────────────────────────────────────────────────────────

BASE_JUDGE_SYSTEM_PROMPT = """You are Arbiter, an elite tabletop tournament judge.

Your job is to issue accurate rulings grounded ONLY in supplied RULE_CONTEXT.

NON-NEGOTIABLE CONSTRAINTS:
1. Use only provided context chunks. Never rely on outside knowledge.
2. Do not invent page numbers, sections, or missing rules text.
3. Resolve precedence as: ERRATA > EXPANSION > BASE.
4. If context is insufficient, explicitly say so and provide a targeted next step.
5. Keep rulings concise but complete; use bullets for multi-part outcomes.
6. If RECENT_CHAT_CONTEXT is provided, use it only for pronoun/follow-up
   disambiguation; rules authority still comes from RULE_CONTEXT.

CONFIDENCE CALIBRATION:
- 0.90-1.00: Direct rule text clearly answers the question.
- 0.70-0.89: Strong support across multiple rules with light inference.
- 0.50-0.69: Material ambiguity or interpretation required.
- 0.00-0.49: Insufficient evidence in provided context.

OUTPUT CONTRACT:
Return ONLY valid JSON with this exact shape:
{
  "verdict": "string",
  "reasoning_chain": "string or null",
  "confidence": 0.0,
  "confidence_reason": "string",
  "conflicts": [{"description":"string","resolution":"string"}] or null,
  "follow_up_hint": "string or null",
  "citation_chunk_indexes": [1,2]
}

`citation_chunk_indexes` MUST reference the CHUNK_N labels in RULE_CONTEXT.
Use 1-based indexes. Include 1-5 indexes when evidence exists.
"""

QUERY_EXPANSION_PROMPT = """You optimize retrieval queries for tabletop rulebooks.

Given a player question, output JSON with:
- expanded_query: clear, retrieval-optimized rewrite preserving user intent
- keywords: up to 8 high-signal terms (card names, phases, keywords, actions)
- sub_queries: null or up to 3 targeted sub-queries only when the question is multi-step

Rules:
1. Preserve game terminology exactly when present.
2. Add concise synonyms only when they improve recall.
3. Avoid verbosity, speculation, and duplicate terms.

Return ONLY valid JSON:
{
  "expanded_query": "string",
  "keywords": ["term1", "term2"],
  "sub_queries": ["q1", "q2"] or null
}
"""


# ─── Data Structures ────────────────────────────────────────────────────────


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
    model: str = "unknown"


# ─── The Judge ───────────────────────────────────────────────────────────────


class AdjudicationEngine:
    """The Judge — processes queries through the full RAG pipeline."""

    _MAX_OVERRIDE_CHARS = 2000
    _MAX_KEYWORDS = 8
    _MAX_SUB_QUERIES = 3
    _MAX_CITATIONS = 5

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
        persona: str | None = None,
        system_prompt_override: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> Verdict:
        """Process a user query through the full adjudication pipeline."""
        start = time.perf_counter()
        query_id = str(uuid.uuid4())

        # Step 1: Query Expansion
        expansion = await self._expand_query(query, game_name=game_name)
        expanded_query = expansion["expanded_query"]
        sub_queries = expansion["sub_queries"]

        logger.info(
            "Query expanded",
            extra={
                "original": query,
                "expanded": expanded_query,
                "sub_queries": len(sub_queries),
            },
        )

        # Step 2: Hybrid Retrieval (fan-out across namespaces)
        retrieval_queries = self._dedupe_query_variants([query, expanded_query, *sub_queries])
        all_matches: list[VectorMatch] = []

        for retrieval_query in retrieval_queries:
            query_vector = await self._embedder.embed_query(retrieval_query)
            for ns in namespaces:
                matches = await self._vector_store.query(query_vector, top_k=50, namespace=ns)
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

        # Step 3: Cross-Encoder Reranking
        doc_texts = [m.metadata.get("text", "") for m in unique_matches]
        rerank_query = query if expanded_query == query else f"{query}\n\nExpanded query: {expanded_query}"
        reranked = await self._reranker.rerank(rerank_query, doc_texts, top_n=12)

        # Step 4: Hierarchy Re-sort (source priority override)
        sorted_chunks = self._hierarchy_resort(reranked, unique_matches)

        # Step 5: Conflict Detection
        conflicts = self._detect_conflicts(sorted_chunks, unique_matches)

        # Step 6: Verdict Generation
        context = self._build_context(sorted_chunks, unique_matches, conflicts)
        verdict_data, model_name = await self._generate_verdict(
            query=query,
            context=context,
            game_name=game_name,
            persona=persona,
            system_prompt_override=system_prompt_override,
            conversation_history=conversation_history or [],
        )
        normalized_verdict = self._normalize_verdict_payload(verdict_data)

        citations = self._extract_citations(
            sorted_chunks=sorted_chunks,
            original_matches=unique_matches,
            citation_chunk_indexes=normalized_verdict.get("citation_chunk_indexes"),
        )

        latency_ms = self._elapsed_ms(start)

        return Verdict(
            verdict=normalized_verdict["verdict"],
            reasoning_chain=normalized_verdict.get("reasoning_chain"),
            confidence=normalized_verdict["confidence"],
            confidence_reason=normalized_verdict.get("confidence_reason"),
            citations=citations,
            conflicts=[
                Conflict(description=c["description"], resolution=c["resolution"])
                for c in (normalized_verdict.get("conflicts") or [])
            ]
            or (conflicts if conflicts else None),
            follow_up_hint=normalized_verdict.get("follow_up_hint"),
            query_id=query_id,
            latency_ms=latency_ms,
            expanded_query=expanded_query,
            model=model_name,
        )

    # ─── Step 1: Query Expansion ────────────────────────────────────────────

    async def _expand_query(self, query: str, *, game_name: str | None = None) -> dict[str, Any]:
        """Expand and decompose the user query for better retrieval."""
        user_payload = f"GAME: {game_name or 'Unknown'}\nQUESTION: {query}"
        try:
            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=QUERY_EXPANSION_PROMPT),
                    Message(role="user", content=user_payload),
                ],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            parsed = self._safe_json_loads(response.content)
            return self._normalize_expansion_payload(parsed, fallback_query=query)
        except Exception as exc:
            logger.warning("Query expansion failed, using original: %s", exc)
            return {"expanded_query": query, "keywords": [], "sub_queries": []}

    # ─── Step 4: Hierarchy Re-sort ──────────────────────────────────────────

    def _hierarchy_resort(
        self,
        reranked: list,
        original_matches: list[VectorMatch],
    ) -> list:
        """Re-sort reranked results by source priority (Errata > Expansion > Base)."""
        match_map = {i: m for i, m in enumerate(original_matches)}

        sorted_results = sorted(
            reranked,
            key=lambda r: (
                -match_map.get(r.index, VectorMatch(id="", score=0)).metadata.get(
                    "source_priority", 0
                ),
                -r.score,
            ),
        )
        return sorted_results[:8]

    # ─── Step 5: Conflict Detection ─────────────────────────────────────────

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
            seen_topics[section].append({"source_type": source_type, "text": chunk.text[:200]})

        for section, entries in seen_topics.items():
            source_types = {e["source_type"] for e in entries}
            if len(source_types) > 1 and "BASE" in source_types:
                conflicts.append(
                    Conflict(
                        description=f"Conflicting rules in '{section}': found {', '.join(source_types)}",
                        resolution="Higher-priority source takes precedence (Errata > Expansion > Base)",
                    )
                )

        return conflicts or None

    # ─── Step 6: Verdict Generation ─────────────────────────────────────────

    async def _generate_verdict(
        self,
        *,
        query: str,
        context: str,
        game_name: str | None,
        persona: str | None,
        system_prompt_override: str | None,
        conversation_history: list[dict[str, str]],
    ) -> tuple[dict[str, Any], str]:
        """Generate the final verdict using the LLM."""
        system_prompt = self._build_judge_system_prompt(
            game_name=game_name,
            persona=persona,
            system_prompt_override=system_prompt_override,
        )
        history_context = self._format_history_context(conversation_history)
        history_block = (
            f"RECENT_CHAT_CONTEXT:\n{history_context}\n\n"
            if history_context
            else ""
        )
        user_prompt = (
            f"GAME: {game_name or 'Unknown'}\n\n"
            f"{history_block}"
            f"RULE_CONTEXT:\n{context}\n\n"
            f"PLAYER_QUESTION:\n{query}"
        )
        try:
            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=user_prompt),
                ],
                temperature=0.0,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            parsed = self._safe_json_loads(response.content)
            if not isinstance(parsed, dict):
                raise json.JSONDecodeError("No JSON object found", response.content, 0)
            return parsed, response.model
        except json.JSONDecodeError:
            logger.warning("Failed to parse verdict JSON, returning raw")
            return {
                "verdict": "I could not generate a reliably structured ruling for this query.",
                "reasoning_chain": None,
                "confidence": 0.2,
                "confidence_reason": "Model response was not valid JSON",
                "conflicts": None,
                "follow_up_hint": "Rephrase the question with specific phase and card/rule names.",
                "citation_chunk_indexes": [1],
            }, "unknown"
        except Exception:
            logger.exception("Verdict generation failed")
            return {
                "verdict": "An internal error occurred while generating the verdict.",
                "reasoning_chain": None,
                "confidence": 0.0,
                "confidence_reason": "Internal error",
                "conflicts": None,
                "follow_up_hint": "Please try again in a few seconds.",
                "citation_chunk_indexes": [],
            }, "unknown"

    # ─── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _deduplicate_matches(matches: list[VectorMatch]) -> list[VectorMatch]:
        """Deduplicate by vector ID, keeping highest score."""
        seen: dict[str, VectorMatch] = {}
        for match in matches:
            if match.id not in seen or match.score > seen[match.id].score:
                seen[match.id] = match
        return sorted(seen.values(), key=lambda item: -item.score)

    @staticmethod
    def _dedupe_query_variants(queries: list[str]) -> list[str]:
        """Deduplicate normalized query variants while preserving order."""
        deduped: list[str] = []
        seen: set[str] = set()
        for query in queries:
            clean = query.strip()
            if not clean:
                continue
            key = clean.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(clean)
        return deduped

    def _build_judge_system_prompt(
        self,
        *,
        game_name: str | None,
        persona: str | None,
        system_prompt_override: str | None,
    ) -> str:
        """Build the final judge system prompt with agent-specific context."""
        segments = [BASE_JUDGE_SYSTEM_PROMPT]

        if game_name:
            segments.append(f"GAME CONTEXT:\n- Primary game: {game_name}")

        persona_clean = (persona or "").strip()
        if persona_clean:
            segments.append(
                "AGENT STYLE PROFILE:\n"
                f"- Persona: {persona_clean}\n"
                "- Adapt tone/style to this persona while preserving all non-negotiable constraints."
            )

        override_clean = (system_prompt_override or "").strip()
        if override_clean:
            clipped_override = override_clean[: self._MAX_OVERRIDE_CHARS]
            segments.append(
                "AGENT INSTRUCTIONS (LOWER PRIORITY THAN NON-NEGOTIABLE CONSTRAINTS):\n"
                f"{clipped_override}"
            )

        return "\n\n".join(segments)

    @staticmethod
    def _build_context(
        sorted_chunks: list,
        original_matches: list[VectorMatch],
        conflicts: list[Conflict] | None,
    ) -> str:
        """Build the context string for the LLM from retrieved chunks."""
        lines: list[str] = []
        for i, chunk in enumerate(sorted_chunks):
            idx = chunk.index
            if idx >= len(original_matches):
                continue
            meta = original_matches[idx].metadata
            source_type = meta.get("source_type", "BASE")
            source_priority = meta.get("source_priority", 0)
            page = meta.get("page_number", "?")
            section = meta.get("section_header") or "Unknown section"
            ruleset_id = meta.get("ruleset_id") or "unknown_ruleset"
            game_name = meta.get("game_name") or "Unknown game"

            lines.append(
                f"CHUNK_{i + 1}\n"
                f"- source_type: {source_type}\n"
                f"- source_priority: {source_priority}\n"
                f"- game_name: {game_name}\n"
                f"- ruleset_id: {ruleset_id}\n"
                f"- page: {page}\n"
                f"- section: {section}\n"
                f"- text: {chunk.text}"
            )

        if conflicts:
            lines.append("DETECTED_CONFLICTS:")
            for conflict in conflicts:
                lines.append(f"- {conflict.description} => {conflict.resolution}")

        return "\n\n".join(lines)

    @staticmethod
    def _format_history_context(history: list[dict[str, str]]) -> str:
        """Format recent chat turns into a compact context block."""
        if not history:
            return ""

        normalized: list[str] = []
        for turn in history[-6:]:
            role = str(turn.get("role", "")).strip().lower()
            content = str(turn.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            clipped = content.replace("\n", " ")[:500]
            normalized.append(f"{role.upper()}: {clipped}")

        return "\n".join(normalized)

    def _extract_citations(
        self,
        sorted_chunks: list,
        original_matches: list[VectorMatch],
        *,
        citation_chunk_indexes: list[int] | None = None,
    ) -> list[Citation]:
        """Extract citations from model-chosen chunk indices or top chunks."""
        citations: list[Citation] = []

        requested = self._normalize_citation_chunk_indexes(citation_chunk_indexes)
        if not requested:
            requested = list(range(1, min(len(sorted_chunks), self._MAX_CITATIONS) + 1))

        for chunk_number in requested[: self._MAX_CITATIONS]:
            chunk_position = chunk_number - 1
            if chunk_position < 0 or chunk_position >= len(sorted_chunks):
                continue

            chunk = sorted_chunks[chunk_position]
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
    def _safe_json_loads(raw_text: str) -> dict[str, Any] | list[Any] | None:
        """Parse JSON robustly, including fenced markdown payloads."""
        text = raw_text.strip()
        if not text:
            return None

        try:
            parsed = json.loads(text)
            if isinstance(parsed, (dict, list)):
                return parsed
            return None
        except json.JSONDecodeError:
            pass

        fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL)
        candidate = fenced.group(1).strip() if fenced else ""
        if candidate:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except json.JSONDecodeError:
                pass

        first_curly = text.find("{")
        last_curly = text.rfind("}")
        if 0 <= first_curly < last_curly:
            candidate = text[first_curly : last_curly + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        first_square = text.find("[")
        last_square = text.rfind("]")
        if 0 <= first_square < last_square:
            candidate = text[first_square : last_square + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        return None

    def _normalize_expansion_payload(
        self,
        payload: Any,
        *,
        fallback_query: str,
    ) -> dict[str, Any]:
        """Normalize expansion payload into a stable shape."""
        if not isinstance(payload, dict):
            return {"expanded_query": fallback_query, "keywords": [], "sub_queries": []}

        expanded_query = str(payload.get("expanded_query") or "").strip() or fallback_query

        raw_keywords = payload.get("keywords")
        keywords: list[str] = []
        if isinstance(raw_keywords, list):
            for item in raw_keywords:
                if not isinstance(item, str):
                    continue
                keyword = item.strip()
                if keyword:
                    keywords.append(keyword)
        keywords = self._dedupe_query_variants(keywords)[: self._MAX_KEYWORDS]

        raw_sub_queries = payload.get("sub_queries")
        sub_queries: list[str] = []
        if isinstance(raw_sub_queries, list):
            for item in raw_sub_queries:
                if not isinstance(item, str):
                    continue
                sub_query = item.strip()
                if sub_query:
                    sub_queries.append(sub_query)
        sub_queries = self._dedupe_query_variants(sub_queries)[: self._MAX_SUB_QUERIES]

        return {
            "expanded_query": expanded_query,
            "keywords": keywords,
            "sub_queries": sub_queries,
        }

    def _normalize_verdict_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize verdict payload into a stable, API-safe shape."""
        verdict = str(payload.get("verdict") or "").strip()
        if not verdict:
            verdict = "I cannot determine a reliable ruling from the available context."

        reasoning_chain = payload.get("reasoning_chain")
        if reasoning_chain is not None:
            reasoning_chain = str(reasoning_chain).strip() or None

        confidence = self._coerce_confidence(payload.get("confidence"), default=0.45)
        confidence_reason = str(payload.get("confidence_reason") or "").strip() or None
        if not confidence_reason:
            confidence_reason = "Confidence estimated from evidence strength and ambiguity."

        conflicts = self._normalize_conflicts(payload.get("conflicts"))
        follow_up_hint = payload.get("follow_up_hint")
        if follow_up_hint is not None:
            follow_up_hint = str(follow_up_hint).strip() or None
        if confidence < 0.6 and not follow_up_hint:
            follow_up_hint = (
                "Ask a narrower follow-up with specific phase/timing and card/ability names."
            )

        citation_chunk_indexes = self._normalize_citation_chunk_indexes(
            payload.get("citation_chunk_indexes")
        )

        return {
            "verdict": verdict,
            "reasoning_chain": reasoning_chain,
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "conflicts": conflicts,
            "follow_up_hint": follow_up_hint,
            "citation_chunk_indexes": citation_chunk_indexes,
        }

    def _normalize_citation_chunk_indexes(self, raw: Any) -> list[int]:
        """Normalize model-selected citation indexes to valid, deduped ints."""
        if not isinstance(raw, list):
            return []
        cleaned: list[int] = []
        for value in raw:
            if isinstance(value, bool):
                continue
            if not isinstance(value, int):
                continue
            if value < 1:
                continue
            cleaned.append(value)
        return self._dedupe_ints(cleaned)

    @staticmethod
    def _normalize_conflicts(raw: Any) -> list[dict[str, str]] | None:
        """Normalize conflict list."""
        if not isinstance(raw, list):
            return None

        conflicts: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            description = str(item.get("description") or "").strip()
            resolution = str(item.get("resolution") or "").strip()
            if not description or not resolution:
                continue
            conflicts.append({"description": description, "resolution": resolution})
        return conflicts or None

    @staticmethod
    def _coerce_confidence(value: Any, *, default: float) -> float:
        """Coerce confidence into [0.0, 1.0]."""
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _dedupe_ints(values: list[int]) -> list[int]:
        """Deduplicate integers while preserving order."""
        deduped: list[int] = []
        seen: set[int] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        """Calculate elapsed milliseconds."""
        return round((time.perf_counter() - start) * 1000)
