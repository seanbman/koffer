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
    SourceStatus,
    SuggestionStatus,
)
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.models import (
    Collection,
    Job,
    Sample,
    Source,
    Suggestion,
)
from koffer.domain.timestamps import TIMESTAMP_CONVENTION, utc_now_iso

__all__ = [
    "TIMESTAMP_CONVENTION",
    "AnalysisRunState",
    "ClassificationDimension",
    "ClassificationSource",
    "Collection",
    "CollectionSortMode",
    "EntityId",
    "ExclusionPatternType",
    "Job",
    "JobItemState",
    "JobState",
    "JobType",
    "Sample",
    "SampleAvailability",
    "Source",
    "SourceStatus",
    "Suggestion",
    "SuggestionStatus",
    "new_entity_id",
    "utc_now_iso",
]
