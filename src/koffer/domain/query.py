"""Typed SampleQuery / SampleRow / paging contracts for SearchService (docs/17, docs/27)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeVar

from koffer.domain.enums import SampleAvailability
from koffer.domain.ids import EntityId

DEFAULT_PAGE_LIMIT = 200


class SortField(StrEnum):
    """Sortable Sample browser columns (docs/04, docs/28)."""

    NAME = "name"
    SAMPLE_TYPE = "sample_type"
    INSTRUMENT_SOURCE = "instrument_source"
    BPM = "bpm"
    KEY = "key"
    DURATION = "duration"
    EXTENSION = "extension"
    AVAILABILITY = "availability"
    DATE_DISCOVERED = "date_discovered"
    LAST_USED = "last_used"
    FILE_SIZE = "file_size"
    ANALYSIS_CONFIDENCE = "analysis_confidence"


class SortDirection(StrEnum):
    """Sort direction."""

    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class NumericRange:
    """Inclusive numeric range filter; either bound may be omitted."""

    min: float | None = None
    max: float | None = None

    def is_empty(self) -> bool:
        return self.min is None and self.max is None


@dataclass(frozen=True, slots=True)
class SortSpec:
    """Sort field + direction. Default: Name ascending (docs/28)."""

    field: SortField = SortField.NAME
    direction: SortDirection = SortDirection.ASC


@dataclass(frozen=True, slots=True)
class SampleFilters:
    """Structured S02 filters. Groups AND together; multi-select OR within a group."""

    sample_type: tuple[str, ...] = ()
    instrument_source: tuple[str, ...] = ()
    musical_role: tuple[str, ...] = ()
    genre_style: tuple[str, ...] = ()
    character: tuple[str, ...] = ()
    bpm: NumericRange = field(default_factory=NumericRange)
    duration_ms: NumericRange = field(default_factory=NumericRange)
    extensions: tuple[str, ...] = ()
    availability: tuple[SampleAvailability, ...] = ()
    source_ids: tuple[EntityId, ...] = ()
    collection_ids: tuple[EntityId, ...] = ()
    favorite: bool | None = None
    channels: tuple[int, ...] = ()
    keys: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return (
            not self.sample_type
            and not self.instrument_source
            and not self.musical_role
            and not self.genre_style
            and not self.character
            and self.bpm.is_empty()
            and self.duration_ms.is_empty()
            and not self.extensions
            and not self.availability
            and not self.source_ids
            and not self.collection_ids
            and self.favorite is None
            and not self.channels
            and not self.keys
        )


@dataclass(frozen=True, slots=True)
class SampleQuery:
    """Versioned typed query (docs/17 saved_searches.query_json)."""

    version: int = 1
    text: str = ""
    filters: SampleFilters = field(default_factory=SampleFilters)
    sort: SortSpec = field(default_factory=SortSpec)


@dataclass(frozen=True, slots=True)
class PageRequest:
    """Bounded offset pagination for browser fetches (docs/17)."""

    offset: int = 0
    limit: int = DEFAULT_PAGE_LIMIT

    def __post_init__(self) -> None:
        if self.offset < 0:
            msg = "PageRequest.offset must be >= 0"
            raise ValueError(msg)
        if self.limit < 1:
            msg = "PageRequest.limit must be >= 1"
            raise ValueError(msg)


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page[T]:
    """One page of results plus total matching count."""

    items: tuple[T, ...]
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


@dataclass(frozen=True, slots=True)
class SampleRow:
    """Lightweight browser row — not a full Sample aggregate."""

    id: EntityId
    name: str
    extension: str
    availability: SampleAvailability
    favorite: bool
    size_bytes: int
    first_seen_at: str
    sample_type: str | None = None
    instrument_source: str | None = None
    bpm: float | None = None
    key: str | None = None
    duration_ms: int | None = None
    source_id: EntityId | None = None
    last_previewed_at: str | None = None
    collection_count: int = 0
    pending_suggestion_count: int = 0
    analysis_confidence: float | None = None


@dataclass(frozen=True, slots=True)
class SavedSearch:
    """Persisted named SampleQuery view (docs/17 saved_searches)."""

    id: EntityId
    name: str
    query: SampleQuery
    created_at: str
    updated_at: str
