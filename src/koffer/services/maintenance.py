"""MaintenanceService: backup/restore/verify/rebuild/cache (docs/27, docs/24)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from koffer.config.paths import AppPaths
from koffer.domain.enums import CacheCategory, JobType
from koffer.domain.errors import ValidationError
from koffer.domain.ids import EntityId
from koffer.jobs.scheduler import JobScheduler, JobSpec
from koffer.persistence.connection import ConnectionFactory

if TYPE_CHECKING:
    pass

__all__ = ["MaintenanceService", "PRESERVE_NOTES"]

# User-facing preserve/rebuild statements for S20 (docs/15 S20 acceptance).
PRESERVE_NOTES: dict[str, str] = {
    "backup": "Creates a versioned library database backup. Audio files are not copied.",
    "restore": (
        "Replaces the library database from a backup after automatic safety backup. "
        "Collections, classifications, recipes, and Sources are restored; audio files "
        "remain on disk where they already were."
    ),
    "verify": "Non-destructive database integrity check. No user organization is modified.",
    "rebuild_filesystem_index": (
        "Preserves Collections, classifications, tags, and recipes. "
        "Rebuilds filesystem-derived Sample availability and scan state."
    ),
    "rebuild_waveforms": ("Preserves all user organization. Clears/rebuilds waveform cache only."),
    "rebuild_analysis": (
        "Preserves confirmed Classifications, Collections, and recipes. "
        "Rebuilds deterministic/semantic derived analysis."
    ),
    "rebuild_similarity": (
        "Preserves user organization. Rebuilds embedding similarity index only."
    ),
    "clear_cache": (
        "Clears selected rebuildable caches only. Never removes Collections, "
        "classifications, Sources, or preparation recipes."
    ),
}


class MaintenanceService:
    """Orchestrates maintenance Jobs; never mutates user audio files."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        scheduler: JobScheduler,
        paths: AppPaths,
    ) -> None:
        self._factory = connection_factory
        self._scheduler = scheduler
        self._paths = paths

    @property
    def paths(self) -> AppPaths:
        return self._paths

    def preserve_note(self, action: str) -> str:
        return PRESERVE_NOTES.get(action, "")

    def backup(self, destination: Path) -> EntityId:
        dest = Path(destination)
        if dest.exists() and not dest.is_dir():
            raise ValidationError(
                "Backup destination must be a directory",
                detail=str(dest),
            )
        return self._scheduler.submit(
            JobSpec(
                type=JobType.BACKUP,
                scope={
                    "destination": str(dest),
                    "database_path": str(self._factory.database_path),
                    "preserve_note": PRESERVE_NOTES["backup"],
                },
            )
        )

    def restore(self, backup_path: Path) -> EntityId:
        backup_dir = Path(backup_path)
        if not backup_dir.is_dir():
            raise ValidationError(
                "Restore path must be a backup directory",
                detail=str(backup_dir),
            )
        if not (backup_dir / "manifest.json").is_file():
            raise ValidationError(
                "Backup directory is missing manifest.json",
                detail=str(backup_dir),
            )
        return self._scheduler.submit(
            JobSpec(
                type=JobType.RESTORE,
                scope={
                    "backup_path": str(backup_dir),
                    "database_path": str(self._factory.database_path),
                    "safety_backup_parent": str(self._paths.data_dir / "safety-backups"),
                    "preserve_note": PRESERVE_NOTES["restore"],
                },
            )
        )

    def verify_database(self, *, deep: bool = False) -> EntityId:
        return self._scheduler.submit(
            JobSpec(
                type=JobType.DATABASE_VERIFY,
                scope={
                    "deep": deep,
                    "database_path": str(self._factory.database_path),
                    "preserve_note": PRESERVE_NOTES["verify"],
                },
            )
        )

    def rebuild_filesystem_index(self) -> EntityId:
        return self._scheduler.submit(
            JobSpec(
                type=JobType.REBUILD_FILESYSTEM_INDEX,
                scope={
                    "database_path": str(self._factory.database_path),
                    "preserve_note": PRESERVE_NOTES["rebuild_filesystem_index"],
                },
            )
        )

    def rebuild_waveforms(self) -> EntityId:
        return self._scheduler.submit(
            JobSpec(
                type=JobType.REBUILD_WAVEFORMS,
                scope={
                    "cache_dir": str(self._paths.cache_dir),
                    "preserve_note": PRESERVE_NOTES["rebuild_waveforms"],
                },
            )
        )

    def rebuild_analysis(self) -> EntityId:
        return self._scheduler.submit(
            JobSpec(
                type=JobType.REBUILD_ANALYSIS,
                scope={
                    "cache_dir": str(self._paths.cache_dir),
                    "preserve_note": PRESERVE_NOTES["rebuild_analysis"],
                },
            )
        )

    def rebuild_similarity(self) -> EntityId:
        return self._scheduler.submit(
            JobSpec(
                type=JobType.REBUILD_SIMILARITY,
                scope={
                    "cache_dir": str(self._paths.cache_dir),
                    "preserve_note": PRESERVE_NOTES["rebuild_similarity"],
                },
            )
        )

    def clear_cache(self, categories: set[CacheCategory]) -> EntityId:
        if not categories:
            raise ValidationError("At least one cache category is required")
        return self._scheduler.submit(
            JobSpec(
                type=JobType.CACHE_CLEAR,
                scope={
                    "cache_dir": str(self._paths.cache_dir),
                    "categories": sorted(str(item) for item in categories),
                    "preserve_note": PRESERVE_NOTES["clear_cache"],
                },
            )
        )

    def storage_usage(self) -> dict[str, int]:
        """Return approximate byte sizes for data/cache locations (S20)."""
        return {
            "database_bytes": _path_size(self._factory.database_path),
            "data_dir_bytes": _dir_size(self._paths.data_dir),
            "cache_dir_bytes": _dir_size(self._paths.cache_dir),
        }


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        total = path.stat().st_size
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(path) + suffix)
            if sidecar.is_file():
                total += sidecar.stat().st_size
        return total
    return _dir_size(path)


def _dir_size(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total
