"""Unit tests for ingestion rulebook-classifier parsing."""

from app.core.ingestion import IngestionPipeline


def test_parse_rulebook_classification_json_payload() -> None:
    parsed = IngestionPipeline._parse_rulebook_classification(
        '{"is_rulebook": true, "confidence": 0.92, "reason": "Has setup and turn order"}'
    )

    assert parsed["is_rulebook"] is True
    assert parsed["confidence"] == 0.92
    assert parsed["reason"] == "Has setup and turn order"


def test_parse_rulebook_classification_non_json_fallback() -> None:
    parsed = IngestionPipeline._parse_rulebook_classification(
        "YES - Contains setup, turn order, and victory conditions."
    )

    assert parsed["is_rulebook"] is True
    assert parsed["confidence"] == 0.6
