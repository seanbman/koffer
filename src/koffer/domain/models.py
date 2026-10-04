"""Core domain value objects for Phase 1 persistence wiring."""

from __future__ import annotations

from dataclasses import dataclass

from koffer.domain.enums import (
    ClassificationDimension,
    ClassificationSource,
    ExclusionPatternType,
    JobState,
    JobType,
    SampleAvailability,
    SourceStatus,
    SuggestionStatus,
)
from koffer.domain.ids import EntityId


@dataclass(frozen=True, slots=True)
class ExclusionRule:
    """One exclusion pattern attached to a Source."""

    id: EntityId
    source_id: EntityId
    pattern: str
    pattern_type: ExclusionPatternType
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ExclusionPreview:
    """Dry-run effect of exclusion rules against the current Source tree."""

    rules: tuple[ExclusionRule, ...]
    matched_relative_paths: tuple[str, ...]
    excluded_count: int
    included_supported_count: int


@dataclass(frozen=True, slots=True)
class Source:
    """Authorized scan root."""

    id: EntityId
    display_name: str
    root_path: str
    enabled: bool
    recursive: bool
    status: SourceStatus
    created_at: str
    updated_at: str
    storage_fingerprint: str | None = None
    last_scan_started_at: str | None = None
    last_scan_completed_at: str | None = None
    last_seen_at: str | None = None


@dataclass(frozen=True, slots=True)
class Sample:
    """Indexed audio file identity."""

    id: EntityId
    relative_path: str
    normalized_path_cache: str
    filename: str
    extension: str
    size_bytes: int
    mtime_ns: int
    availability: SampleAvailability
    favorite: bool
    first_seen_at: str
    last_seen_at: str
    created_at: str
    updated_at: str
    source_id: EntityId | None = None
    device_id: int | None = None
    inode: int | None = None
    quick_hash: str | None = None
    content_hash: str | None = None
    last_previewed_at: str | None = None


@dataclass(frozen=True, slots=True)
class TechnicalMetadata:
    """One-to-one technical probe snapshot for a Sample (docs/17)."""

    sample_id: EntityId
    container_format: str
    codec: str
    duration_ms: int
    sample_rate_hz: int
    channels: int
    probe_version: str
    probed_at: str
    bit_depth: int | None = None
    channel_layout: str | None = None
    bitrate: int | None = None


@dataclass(frozen=True, slots=True)
class Collection:
    """User-curated Sample grouping (membership never deletes files)."""

    id: EntityId
    name: str
    sort_mode: str
    created_at: str
    updated_at: str
    description: str | None = None
    color: str | None = None
    artwork_path: str | None = None


@dataclass(frozen=True, slots=True)
class Classification:
    """User-confirmed library classification (never filesystem mutation)."""

    id: EntityId
    sample_id: EntityId
    dimension: ClassificationDimension
    value: str
    source: ClassificationSource
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Suggestion:
    """Machine-proposed classification awaiting user review."""

    id: EntityId
    sample_id: EntityId
    dimension: str
    proposed_value: str
    confidence: float
    status: SuggestionStatus
    evidence_json: str
    provider: str
    provider_version: str
    analysis_run_id: EntityId
    created_at: str
    reviewed_at: str | None = None


@dataclass(frozen=True, slots=True)
class Job:
    """Durable background work unit."""

    id: EntityId
    type: JobType
    state: JobState
    scope_json: str
    progress_current: int
    created_at: str
    progress_total: int | None = None
    stage: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_code: str | None = None
    summary_json: str | None = None
