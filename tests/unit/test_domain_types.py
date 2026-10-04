"""Unit coverage for Phase 1 domain enums/types."""

from __future__ import annotations

import uuid

from koffer.domain import (
    TIMESTAMP_CONVENTION,
    ClassificationDimension,
    JobState,
    JobType,
    SampleAvailability,
    ScanMode,
    SourceStatus,
    SuggestionStatus,
    new_entity_id,
    utc_now_iso,
)


def test_core_enums_expose_documented_values() -> None:
    assert SourceStatus.ONLINE == "online"
    assert SampleAvailability.SOURCE_OFFLINE == "source_offline"
    assert ClassificationDimension.SAMPLE_TYPE == "sample_type"
    assert SuggestionStatus.PENDING == "pending"
    assert JobState.QUEUED == "queued"
    assert JobType.SOURCE_SCAN == "source_scan"
    assert ScanMode.INCREMENTAL == "incremental"


def test_new_entity_id_is_uuid_v4_text() -> None:
    entity_id = new_entity_id()
    parsed = uuid.UUID(str(entity_id))
    assert parsed.version == 4


def test_timestamp_convention_is_utc_iso8601_text() -> None:
    assert TIMESTAMP_CONVENTION == "utc_iso8601_text"
    stamp = utc_now_iso()
    assert stamp.endswith("+00:00")
    assert "T" in stamp
