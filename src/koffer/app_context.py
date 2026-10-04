"""Application composition root: paths, DB, scheduler, SourceService."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from koffer.config.paths import AppPaths, resolve_app_paths
from koffer.jobs.scheduler import JobScheduler
from koffer.persistence.connection import ConnectionFactory
from koffer.persistence.migrations import apply_migrations
from koffer.services.sources import SourceService


@dataclass
class AppContext:
    """Owns durable infrastructure for the UI shell.

    UI widgets receive this context and must not open SQL connections themselves.
    """

    paths: AppPaths
    connection_factory: ConnectionFactory
    scheduler: JobScheduler
    source_service: SourceService
    _owns_scheduler: bool = True

    @classmethod
    def open(
        cls,
        paths: AppPaths,
        *,
        database_name: str = "library.sqlite3",
        io_workers: int = 4,
    ) -> AppContext:
        """Create directories, migrate SQLite, and wire SourceService."""
        paths.ensure()
        factory = ConnectionFactory(paths.data_dir / database_name)
        apply_migrations(factory.get_connection())
        scheduler = JobScheduler(factory, io_workers=io_workers)
        source_service = SourceService(factory, scheduler)
        return cls(
            paths=paths,
            connection_factory=factory,
            scheduler=scheduler,
            source_service=source_service,
        )

    @classmethod
    def open_default(cls) -> AppContext:
        return cls.open(resolve_app_paths())

    @classmethod
    def open_temp(cls, root: Path, *, io_workers: int = 2) -> AppContext:
        """Test/helper composition under an isolated directory tree."""
        paths = AppPaths(
            config_dir=root / "config",
            data_dir=root / "data",
            cache_dir=root / "cache",
            state_dir=root / "state",
            log_dir=root / "state" / "logs",
        )
        return cls.open(paths, io_workers=io_workers)

    def close(self) -> None:
        if self._owns_scheduler:
            self.scheduler.shutdown(wait=False)
        self.connection_factory.close_thread_connection()
