"""Domain enumerations for Source/Sample/Job/classification dimensions."""

from __future__ import annotations

from enum import StrEnum


class SourceStatus(StrEnum):
    """Operational status of an authorized scan root."""

    ONLINE = "online"
    OFFLINE = "offline"
    PERMISSION_DENIED = "permission_denied"
    DISABLED = "disabled"
    SCANNING = "scanning"
    ERROR = "error"


class SampleAvailability(StrEnum):
    """Filesystem availability of an indexed Sample."""

    ONLINE = "online"
    SOURCE_OFFLINE = "source_offline"
    MISSING = "missing"
    CHANGED = "changed"
    PERMISSION_DENIED = "permission_denied"
    UNSUPPORTED = "unsupported"


class ExclusionPatternType(StrEnum):
    """How a Source exclusion pattern is interpreted."""

    GLOB = "glob"
    RELATIVE_PATH = "relative_path"
    HIDDEN_POLICY = "hidden_policy"


class ScanMode(StrEnum):
    """How a Source scan compares discovered files to known state."""

    INCREMENTAL = "incremental"
    FULL = "full"


class ClassificationDimension(StrEnum):
    """Confirmed library classification axes (docs/05, docs/17)."""

    SAMPLE_TYPE = "sample_type"
    INSTRUMENT_SOURCE = "instrument_source"
    MUSICAL_ROLE = "musical_role"
    GENRE_STYLE = "genre_style"
    CHARACTER = "character"


class ClassificationSource(StrEnum):
    """Provenance of a confirmed classification row."""

    USER = "user"
    ACCEPTED_SUGGESTION = "accepted_suggestion"
    IMPORT = "import"


class SuggestionStatus(StrEnum):
    """Lifecycle of an analysis Suggestion."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class JobState(StrEnum):
    """Persisted Job scheduler states (docs/18)."""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSE_REQUESTED = "pause_requested"
    PAUSED = "paused"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class JobType(StrEnum):
    """Supported Job kinds (docs/18)."""

    SOURCE_SCAN = "source_scan"
    TECHNICAL_PROBE = "technical_probe"
    WAVEFORM_BUILD = "waveform_build"
    DETERMINISTIC_ANALYSIS = "deterministic_analysis"
    SEMANTIC_ANALYSIS = "semantic_analysis"
    SIMILARITY_INDEX_BUILD = "similarity_index_build"
    COPY_FILES = "copy_files"
    MOVE_FILES = "move_files"
    METADATA_WRITE = "metadata_write"
    RENDER = "render"
    BACKUP = "backup"
    RESTORE = "restore"
    REBUILD_FILESYSTEM_INDEX = "rebuild_filesystem_index"
    REBUILD_WAVEFORMS = "rebuild_waveforms"
    REBUILD_ANALYSIS = "rebuild_analysis"
    REBUILD_SIMILARITY = "rebuild_similarity"
    CACHE_CLEAR = "cache_clear"
    DATABASE_VERIFY = "database_verify"
    # Harness Job: cooperative cancel / interrupted-recovery tests (no filesystem mutation).
    SYNTHETIC_ITEMS = "synthetic_items"


class JobLane(StrEnum):
    """Bounded scheduler executor lanes (docs/18)."""

    IO = "io"
    ANALYSIS = "analysis"
    MUTATION = "mutation"
    RENDER = "render"
    MAINTENANCE = "maintenance"


class ActivityGroup(StrEnum):
    """Activity Center grouping buckets (S16)."""

    RUNNING = "running"
    QUEUED = "queued"
    COMPLETED = "completed"
    NEEDS_ATTENTION = "needs_attention"


class JobItemState(StrEnum):
    """Per-item outcome within a batch Job."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class AnalysisRunState(StrEnum):
    """Lifecycle of an analysis_runs row."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CollectionSortMode(StrEnum):
    """Ordering policy inside a Collection."""

    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    ADDED_AT_ASC = "added_at_asc"
    ADDED_AT_DESC = "added_at_desc"
    MANUAL = "manual"
