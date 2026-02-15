"""Unit tests for adjudication prompt/flow behavior."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.core.adjudication import AdjudicationEngine
from app.core.protocols import LLMResponse, Message, RerankResult, VectorMatch


class QueueLLM:
    """LLM test double that returns queued responses and records calls."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

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
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format,
            }
        )
        content = self._responses.pop(0)
        return LLMResponse(content=content, model="mock-test")

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


class TinyEmbedder:
    """Embedder test double."""

    async def embed_query(self, text: str, *, model: str | None = None) -> list[float]:
        return [float(len(text))]

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> Any:
        return type("EmbeddingResult", (), {"vectors": [[float(len(t))] for t in texts]})()


class FixedVectorStore:
    """Vector store test double."""

    def __init__(self, matches: list[VectorMatch]) -> None:
        self._matches = matches

    async def query(
        self,
        vector: list[float],
        *,
        top_k: int = 10,
        namespace: str = "",
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        return self._matches


class FixedReranker:
    """Reranker test double."""

    def __init__(self, results: list[RerankResult]) -> None:
        self._results = results

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int = 10,
        model: str | None = None,
    ) -> list[RerankResult]:
        return self._results[:top_n]


@dataclass
class MatchData:
    vector_id: str
    score: float
    text: str
    page: int
    section: str
    source_type: str
    source_priority: int


def _mk_match(data: MatchData) -> VectorMatch:
    return VectorMatch(
        id=data.vector_id,
        score=data.score,
        metadata={
            "text": data.text,
            "page_number": data.page,
            "section_header": data.section,
            "source_type": data.source_type,
            "source_priority": data.source_priority,
            "game_name": "Test Game",
            "is_official": False,
            "ruleset_id": "ruleset-1",
        },
    )


@pytest.mark.anyio
async def test_adjudicate_uses_agent_prompt_and_chunk_index_citations() -> None:
    expansion_payload = json.dumps(
        {
            "expanded_query": "attack timing and override resolution",
            "keywords": ["attack", "timing"],
            "sub_queries": None,
        }
    )
    verdict_payload = json.dumps(
        {
            "verdict": "Errata allows the second attack in this edge case.",
            "reasoning_chain": "Errata modifies base timing window.",
            "confidence": 0.88,
            "confidence_reason": "Direct errata language.",
            "conflicts": None,
            "follow_up_hint": None,
            "citation_chunk_indexes": [2, 1],
        }
    )

    llm = QueueLLM([expansion_payload, verdict_payload])
    embedder = TinyEmbedder()
    matches = [
        _mk_match(
            MatchData(
                vector_id="base",
                score=0.91,
                text="Base rules: one attack during your action phase.",
                page=11,
                section="Combat Basics",
                source_type="BASE",
                source_priority=0,
            )
        ),
        _mk_match(
            MatchData(
                vector_id="errata",
                score=0.89,
                text="Errata: a bonus attack is allowed when condition X is met.",
                page=2,
                section="Official Errata",
                source_type="ERRATA",
                source_priority=100,
            )
        ),
    ]
    vector_store = FixedVectorStore(matches)
    reranker = FixedReranker(
        [
            RerankResult(index=0, score=0.96, text=matches[0].metadata["text"]),
            RerankResult(index=1, score=0.90, text=matches[1].metadata["text"]),
        ]
    )

    engine = AdjudicationEngine(
        llm=llm,
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
    )
    verdict = await engine.adjudicate(
        query="Can I attack twice this turn?",
        namespaces=["ns-test"],
        game_name="Test Game",
        persona="Rule Lawyer",
        system_prompt_override="Use terse numbered steps.",
    )

    # CHUNK_1 is errata after hierarchy sort; CHUNK_2 is base.
    assert [c.page for c in verdict.citations[:2]] == [11, 2]

    final_system_prompt = llm.calls[1]["messages"][0].content
    assert "Rule Lawyer" in final_system_prompt
    assert "Use terse numbered steps." in final_system_prompt
    assert "Primary game: Test Game" in final_system_prompt


@pytest.mark.anyio
async def test_adjudicate_parses_fenced_json_and_clamps_confidence() -> None:
    expansion_payload = json.dumps(
        {
            "expanded_query": "timing priority",
            "keywords": ["timing"],
            "sub_queries": [],
        }
    )
    verdict_payload = """```json
{
  "verdict": "Use timing priority from the highest-precedence source.",
  "reasoning_chain": null,
  "confidence": 1.4,
  "confidence_reason": "Clear priority chain in context.",
  "conflicts": null,
  "follow_up_hint": null,
  "citation_chunk_indexes": [99, 1, 1, -2]
}
```"""

    llm = QueueLLM([expansion_payload, verdict_payload])
    embedder = TinyEmbedder()
    matches = [
        _mk_match(
            MatchData(
                vector_id="v1",
                score=0.9,
                text="Priority: Errata overrides expansion and base.",
                page=4,
                section="Priority",
                source_type="ERRATA",
                source_priority=100,
            )
        )
    ]
    vector_store = FixedVectorStore(matches)
    reranker = FixedReranker([RerankResult(index=0, score=0.99, text=matches[0].metadata["text"])])

    engine = AdjudicationEngine(
        llm=llm,
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
    )
    verdict = await engine.adjudicate(
        query="Which timing rule wins?",
        namespaces=["ns-test"],
        game_name="Test Game",
    )

    assert verdict.confidence == 1.0
    assert len(verdict.citations) == 1
    assert verdict.citations[0].page == 4


@pytest.mark.anyio
async def test_expand_query_falls_back_to_original_when_payload_invalid() -> None:
    llm = QueueLLM(['{"foo":"bar"}'])
    engine = AdjudicationEngine(
        llm=llm,
        embedder=TinyEmbedder(),
        vector_store=FixedVectorStore([]),
        reranker=FixedReranker([]),
    )

    expansion = await engine._expand_query("How does initiative work?", game_name="Test Game")
    assert expansion["expanded_query"] == "How does initiative work?"
    assert expansion["keywords"] == []
    assert expansion["sub_queries"] == []
