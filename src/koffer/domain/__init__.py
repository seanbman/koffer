"""Pure domain types and enums (no Qt/SQLite/filesystem side effects)."""

from koffer.domain.enums import (
    AnalysisRunState,
    ClassificationDimension,
    ClassificationSource,
    CollectionSortMode,
    ExclusionPatternType,
    JobItemState,
    JobState,
    JobType,
    SampleAvailability,
    ScanMode,
    SourceStatus,
    SuggestionStatus,
)
from koffer.domain.errors import (
    ApplicationError,
    NotFoundError,
    PathUnavailableError,
    UnsupportedOperationError,
    ValidationError,
)
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.models import (
    Classification,
    Collection,
    ExclusionPreview,
    ExclusionRule,
    Job,
    Sample,
    Source,
    Suggestion,
)
from koffer.domain.timestamps import TIMESTAMP_CONVENTION, utc_now_iso

__all__ = [
    "TIMESTAMP_CONVENTION",
    "AnalysisRunState",
    "ApplicationError",
    "Classification",
    "ClassificationDimension",
    "ClassificationSource",
    "Collection",
    "CollectionSortMode",
    "EntityId",
    "ExclusionPatternType",
    "ExclusionPreview",
    "ExclusionRule",
    "Job",
    "JobItemState",
    "JobState",
    "JobType",
    "NotFoundError",
    "PathUnavailableError",
    "Sample",
    "SampleAvailability",
    "ScanMode",
    "Source",
    "SourceStatus",
    "Suggestion",
    "SuggestionStatus",
    "UnsupportedOperationError",
    "ValidationError",
    "new_entity_id",
    "utc_now_iso",
]
