"""Application composition root: paths, DB, scheduler, and Phase 5 services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from koffer.audio.waveform import WaveformCache
from koffer.config.paths import AppPaths, resolve_app_paths
from koffer.domain.ids import EntityId
from koffer.jobs.scheduler import JobScheduler
from koffer.persistence.connection import ConnectionFactory
from koffer.persistence.migrations import apply_migrations
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.services.analysis import AnalysisService
from koffer.services.collections import CollectionService
from koffer.services.file_operations import FileOperationService
from koffer.services.metadata import MetadataService
from koffer.services.playback import PlaybackService
from koffer.services.preparation import PreparationService
from koffer.services.samples import SampleService
from koffer.services.search import SearchService
from koffer.services.similarity import SimilarityService
from koffer.services.sources import SourceService


@dataclass
class AppContext:
    """Owns durable infrastructure for the UI shell.

    UI widgets receive this context and must not open SQL connections themselves.
    UI must not touch QMediaPlayer outside ``playback_service``.
    """

    paths: AppPaths
    connection_factory: ConnectionFactory
    scheduler: JobScheduler
    source_service: SourceService
    search_service: SearchService
    playback_service: PlaybackService
    waveform_cache: WaveformCache
    collection_service: CollectionService
    metadata_service: MetadataService
    sample_service: SampleService
    file_operation_service: FileOperationService
    preparation_service: PreparationService
    analysis_service: AnalysisService
    similarity_service: SimilarityService
    _owns_scheduler: bool = True

    @classmethod
    def open(
        cls,
        paths: AppPaths,
        *,
        database_name: str = "library.sqlite3",
        io_workers: int = 4,
    ) -> AppContext:
        """Create directories, migrate SQLite, and wire application services."""
        paths.ensure()
        factory = ConnectionFactory(paths.data_dir / database_name)
        apply_migrations(factory.get_connection())
        # recover_on_start marks abandoned running Jobs interrupted (docs/24).
        scheduler = JobScheduler(factory, io_workers=io_workers, recover_on_start=True)
        source_service = SourceService(factory, scheduler)
        search_service = SearchService(factory)
        playback_service = PlaybackService()
        waveform_cache = WaveformCache(paths.cache_dir)
        collection_service = CollectionService(factory)
        metadata_service = MetadataService(factory, scheduler)
        sample_service = SampleService(factory, metadata_service)
        file_operation_service = FileOperationService(factory, scheduler)
        preparation_service = PreparationService(factory, scheduler)
        analysis_service = AnalysisService(factory, scheduler)
        # Default PANNs provider stays unavailable without out-of-git weights.
        similarity_service = SimilarityService(factory, paths.cache_dir, scheduler=scheduler)
        return cls(
            paths=paths,
            connection_factory=factory,
            scheduler=scheduler,
            source_service=source_service,
            search_service=search_service,
            playback_service=playback_service,
            waveform_cache=waveform_cache,
            collection_service=collection_service,
            metadata_service=metadata_service,
            sample_service=sample_service,
            file_operation_service=file_operation_service,
            preparation_service=preparation_service,
            analysis_service=analysis_service,
            similarity_service=similarity_service,
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

    def resolve_sample_media_path(self, sample_id: EntityId) -> Path | None:
        """Resolve indexed Sample -> absolute media path (read-only; never mutates files)."""
        conn = self.connection_factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None or sample.source_id is None:
            return None
        source = SourceRepository(conn).get(sample.source_id)
        if source is None:
            return None
        return Path(source.root_path) / sample.relative_path

    def close(self) -> None:
        if self._owns_scheduler:
            self.scheduler.shutdown(wait=False)
        self.playback_service.stop()
        self.connection_factory.close_thread_connection()
