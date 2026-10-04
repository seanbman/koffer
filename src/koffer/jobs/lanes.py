"""Job type -> scheduler lane mapping (docs/18)."""

from __future__ import annotations

from koffer.domain.enums import JobLane, JobType

_LANE_BY_TYPE: dict[JobType, JobLane] = {
    JobType.SOURCE_SCAN: JobLane.IO,
    JobType.TECHNICAL_PROBE: JobLane.IO,
    JobType.BACKUP: JobLane.IO,
    JobType.RESTORE: JobLane.IO,
    JobType.REBUILD_FILESYSTEM_INDEX: JobLane.IO,
    JobType.CACHE_CLEAR: JobLane.IO,
    JobType.SYNTHETIC_ITEMS: JobLane.IO,
    JobType.REFERENCE_SAMPLES: JobLane.IO,
    JobType.WAVEFORM_BUILD: JobLane.ANALYSIS,
    JobType.DETERMINISTIC_ANALYSIS: JobLane.ANALYSIS,
    JobType.SEMANTIC_ANALYSIS: JobLane.ANALYSIS,
    JobType.SIMILARITY_INDEX_BUILD: JobLane.ANALYSIS,
    JobType.REBUILD_WAVEFORMS: JobLane.ANALYSIS,
    JobType.REBUILD_ANALYSIS: JobLane.ANALYSIS,
    JobType.REBUILD_SIMILARITY: JobLane.ANALYSIS,
    JobType.COPY_FILES: JobLane.MUTATION,
    JobType.MOVE_FILES: JobLane.MUTATION,
    JobType.METADATA_WRITE: JobLane.MUTATION,
    JobType.RENDER: JobLane.RENDER,
    JobType.DATABASE_VERIFY: JobLane.MAINTENANCE,
}


def lane_for_job_type(job_type: JobType) -> JobLane:
    """Return the executor lane for ``job_type`` (defaults to IO)."""
    return _LANE_BY_TYPE.get(job_type, JobLane.IO)


def default_analysis_workers() -> int:
    """min(2, max(1, CPU/2)) per docs/18."""
    import os

    cpu = os.cpu_count() or 2
    return min(2, max(1, cpu // 2))
