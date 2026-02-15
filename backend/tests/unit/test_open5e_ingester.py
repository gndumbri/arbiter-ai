"""Unit tests for Open5e ingestion helpers."""

from __future__ import annotations

from app.services.catalog.open5e_ingester import (
    _is_allowed_license,
    _normalize_license,
    _ruleset_slug_for_document,
)


def test_normalize_license_maps_known_values() -> None:
    assert _normalize_license("Creative Commons Attribution 4.0 International License") == "CC-BY-4.0"
    assert _normalize_license("Open Gaming License") == "OGL-1.0a"
    assert _normalize_license("ORC License") == "ORC"


def test_allowed_license_keyword_matching_is_case_insensitive() -> None:
    keywords = ("creative commons", "open gaming license", "orc")
    assert _is_allowed_license("Creative Commons Attribution 4.0", keywords) is True
    assert _is_allowed_license("OPEN GAME LICENSE Version 1.0a", keywords) is True
    assert _is_allowed_license("ORC License", keywords) is True
    assert _is_allowed_license("Proprietary", keywords) is False


def test_ruleset_slug_preserves_legacy_srd_identity() -> None:
    assert _ruleset_slug_for_document("wotc-srd") == "srd-dnd-5e"
    assert _ruleset_slug_for_document("a5e") == "open5e-a5e"

