"""SimilarityService: embeddings + Find Similar (docs/27, docs/19)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from koffer.analysis.embeddings import EmbeddingStore
from koffer.analysis.panns import PannsSemanticProvider
from koffer.analysis.semantic import FakeSemanticProvider, SemanticProvider
from koffer.analysis.similarity_index import SimilarityIndex
from koffer.domain.enums import JobType, SampleAvailability
from koffer.domain.errors import ModelUnavailableError, NotFoundError, ValidationError
from koffer.domain.ids import EntityId
from koffer.domain.models import Sample
from koffer.domain.query import SampleFilters, SampleQuery
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.operations import path_fingerprint
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository

if TYPE_CHECKING:
    from koffer.jobs.scheduler import JobScheduler

MediaResolver = Callable[[EntityId], Path | None]

__all__ = [
    "SimilarityService",
    "SimilarityResult",
    "SimilarityStatus",
    "SimilarityStatusKind",
]


class SimilarityStatusKind(StrEnum):
    READY = "ready"
    MODEL_UNAVAILABLE = "model_unavailable"
    EMPTY = "empty"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class SimilarityResult:
    """One Find Similar row (score is similarity, not a metadata filter rank)."""

    sample_id: EntityId
    score: float
    filename: str
    availability: SampleAvailability
    relative_path: str


@dataclass(frozen=True, slots=True)
class SimilarityStatus:
    kind: SimilarityStatusKind
    model_version: str | None
    provider: str | None
    index_size: int
    backend: str
    detail: str = ""


class SimilarityService:
    """Owns embedding cache + HNSW/numpy cosine index lifecycle."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        cache_dir: Path,
        *,
        provider: SemanticProvider | None = None,
        scheduler: JobScheduler | None = None,
        media_resolver: MediaResolver | None = None,
    ) -> None:
        self._factory = connection_factory
        self._cache_dir = Path(cache_dir)
        self._scheduler = scheduler
        self._media_resolver = media_resolver
        self._store = EmbeddingStore(self._cache_dir)
        if provider is not None:
            self._provider: SemanticProvider = provider
        else:
            # Default production adapter; unavailable without weights/torch.
            self._provider = PannsSemanticProvider(self._cache_dir)
        self._index: SimilarityIndex | None = None

    @property
    def provider(self) -> SemanticProvider:
        return self._provider

    @property
    def embedding_store(self) -> EmbeddingStore:
        return self._store

    def status(self) -> SimilarityStatus:
        if not self._provider.is_available():
            return SimilarityStatus(
                kind=SimilarityStatusKind.MODEL_UNAVAILABLE,
                model_version=self._provider.model_version,
                provider=self._provider.provider_id,
                index_size=0,
                backend="none",
                detail=self._provider.unavailable_reason() or "model unavailable",
            )
        index = self._ensure_index_loaded()
        if index.size == 0:
            return SimilarityStatus(
                kind=SimilarityStatusKind.EMPTY,
                model_version=self._provider.model_version,
                provider=self._provider.provider_id,
                index_size=0,
                backend=index.backend,
                detail="No embeddings indexed yet",
            )
        return SimilarityStatus(
            kind=SimilarityStatusKind.READY,
            model_version=self._provider.model_version,
            provider=self._provider.provider_id,
            index_size=index.size,
            backend=index.backend,
        )

    def ensure_embedding(self, sample_id: EntityId) -> EntityId | None:
        """Ensure a cached embedding exists.

        Foundations compute synchronously and return ``None`` (already present or
        just computed). Returns ``None`` immediately when the model is absent so
        callers can keep library UX usable.
        """
        if not self._provider.is_available():
            return None
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        existing = self._store.get(sample_id, self._provider.model_version)
        media = self._resolve_media(sample_id)
        fingerprint = self._fingerprint(media)
        if existing is not None and existing.source_fingerprint == fingerprint:
            return None
        self._compute_and_store(sample_id)
        return None

    def compute_embedding(self, sample_id: EntityId) -> None:
        """Synchronously compute and cache an embedding (tests / job runners)."""
        if not self._provider.is_available():
            raise ModelUnavailableError(
                "Semantic model is unavailable",
                detail=self._provider.unavailable_reason() or "",
            )
        self._compute_and_store(sample_id)

    def find_similar(
        self,
        sample_id: EntityId,
        limit: int,
        filters: SampleQuery | None = None,
    ) -> list[SimilarityResult]:
        if limit < 1:
            raise ValidationError("limit must be >= 1", detail=str(limit))
        if not self._provider.is_available():
            raise ModelUnavailableError(
                "Semantic embeddings are unavailable",
                detail=self._provider.unavailable_reason() or "",
            )
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")

        record = self._store.get(sample_id, self._provider.model_version)
        if record is None:
            # Best-effort compute for the seed when provider is present.
            self._compute_and_store(sample_id)
            record = self._store.get(sample_id, self._provider.model_version)
        if record is None:
            raise ValidationError("Seed embedding could not be produced", detail=str(sample_id))

        index = self._ensure_index_loaded()
        if index.size == 0:
            self.rebuild_index_sync()
            index = self._ensure_index_loaded()

        # Over-fetch before metadata filters so ranking stays similarity-first.
        fetch = max(limit * 4, limit + 8)
        hits = index.query(record.vector, limit=fetch, exclude=sample_id)
        samples = SampleRepository(conn)
        results: list[SimilarityResult] = []
        for hit in hits:
            candidate = samples.get(hit.sample_id)
            if candidate is None:
                continue
            if filters is not None and not _passes_filters(candidate, filters.filters):
                continue
            results.append(
                SimilarityResult(
                    sample_id=candidate.id,
                    score=hit.score,
                    filename=candidate.filename,
                    availability=candidate.availability,
                    relative_path=candidate.relative_path,
                )
            )
            if len(results) >= limit:
                break
        return results

    def rebuild_index(self) -> EntityId:
        """Rebuild the similarity index; returns a Job id when scheduled."""
        self.rebuild_index_sync()
        if self._scheduler is None:
            raise ValidationError("JobScheduler is required to queue rebuild_index")
        from koffer.jobs.scheduler import JobSpec

        return self._scheduler.submit(
            JobSpec(
                type=JobType.REBUILD_SIMILARITY,
                scope={
                    "model_version": self._provider.model_version,
                    "cache_dir": str(self._cache_dir),
                },
            )
        )

    def rebuild_index_sync(self) -> int:
        """Synchronously rebuild the on-disk/in-memory index from cached embeddings."""
        model_version = self._provider.model_version
        records = self._store.list_for_model(model_version)
        index = SimilarityIndex(
            self._cache_dir,
            model_version=model_version,
            embedding_dim=self._provider.embedding_dim,
        )
        index.build([(item.sample_id, item.vector) for item in records])
        self._index = index
        return index.size

    def _compute_and_store(self, sample_id: EntityId) -> None:
        media = self._resolve_media(sample_id)
        if media is None or not media.is_file():
            raise ValidationError(
                "Sample media is unavailable for embedding",
                detail=str(sample_id),
            )
        result = self._provider.infer(media)
        self._store.put(
            sample_id,
            model_version=result.model_version,
            source_fingerprint=self._fingerprint(media),
            vector=result.embedding,
        )
        # Keep index membership fresh for interactive Find Similar.
        self.rebuild_index_sync()

    def _ensure_index_loaded(self) -> SimilarityIndex:
        if self._index is not None:
            return self._index
        index = SimilarityIndex(
            self._cache_dir,
            model_version=self._provider.model_version,
            embedding_dim=self._provider.embedding_dim,
        )
        if not index.load():
            index.build([])
        self._index = index
        return index

    def _resolve_media(self, sample_id: EntityId) -> Path | None:
        if self._media_resolver is not None:
            return self._media_resolver(sample_id)
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None or sample.source_id is None:
            return None
        source = SourceRepository(conn).get(sample.source_id)
        if source is None:
            return None
        return Path(source.root_path) / sample.relative_path

    @staticmethod
    def _fingerprint(media: Path | None) -> str:
        if media is None or not media.is_file():
            return "missing"
        return f"{path_fingerprint(media)}:{content_fingerprint(media)}"


def _passes_filters(sample: Sample, filters: SampleFilters) -> bool:
    """Apply a minimal subset of SampleFilters for post-similarity narrowing."""
    if filters.availability and sample.availability not in filters.availability:
        return False
    if filters.extensions and sample.extension not in filters.extensions:
        return False
    if filters.source_ids and sample.source_id not in filters.source_ids:
        return False
    return not (filters.favorite is not None and sample.favorite is not filters.favorite)


def build_default_similarity_service(
    connection_factory: ConnectionFactory,
    cache_dir: Path,
    *,
    scheduler: JobScheduler | None = None,
    prefer_fake: bool = False,
    media_resolver: MediaResolver | None = None,
) -> SimilarityService:
    """Factory used by AppContext. Prefer fake only for explicit test wiring."""
    provider: SemanticProvider = (
        FakeSemanticProvider() if prefer_fake else PannsSemanticProvider(cache_dir)
    )
    return SimilarityService(
        connection_factory,
        cache_dir,
        provider=provider,
        scheduler=scheduler,
        media_resolver=media_resolver,
    )
