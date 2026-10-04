"""Integration tests for SearchService FTS, filters, sort, and paging."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from koffer.domain import (
    Classification,
    ClassificationDimension,
    ClassificationSource,
    EntityId,
    NumericRange,
    PageRequest,
    Sample,
    SampleAvailability,
    SampleFilters,
    SampleQuery,
    SortDirection,
    SortField,
    SortSpec,
    Source,
    SourceStatus,
    TechnicalMetadata,
    new_entity_id,
    utc_now_iso,
)
from koffer.persistence import ConnectionFactory, SearchIndexService, apply_migrations
from koffer.repositories import (
    ClassificationRepository,
    SampleRepository,
    SourceRepository,
    TechnicalMetadataRepository,
)
from koffer.services.search import SearchService
from koffer.ui.models.sample_table import SampleTableModel


def _migrated_factory(db_path: Path) -> ConnectionFactory:
    factory = ConnectionFactory(db_path)
    apply_migrations(factory.get_connection())
    return factory


def _make_source(name: str = "Pack") -> Source:
    now = utc_now_iso()
    return Source(
        id=new_entity_id(),
        display_name=name,
        root_path=f"/tmp/koffer-fixtures/{name}",
        enabled=True,
        recursive=True,
        status=SourceStatus.ONLINE,
        created_at=now,
        updated_at=now,
    )


def _make_sample(
    *,
    source_id: EntityId,
    filename: str,
    relative_path: str,
    size_bytes: int = 2048,
    favorite: bool = False,
) -> Sample:
    now = utc_now_iso()
    return Sample(
        id=new_entity_id(),
        relative_path=relative_path,
        normalized_path_cache=relative_path,
        filename=filename,
        extension="wav",
        size_bytes=size_bytes,
        mtime_ns=1_700_000_000_000_000_000,
        availability=SampleAvailability.ONLINE,
        favorite=favorite,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
        source_id=source_id,
    )


def _seed_classification(
    repo: ClassificationRepository,
    sample_id: EntityId,
    dimension: ClassificationDimension,
    value: str,
) -> None:
    now = utc_now_iso()
    repo.create(
        Classification(
            id=new_entity_id(),
            sample_id=sample_id,
            dimension=dimension,
            value=value,
            source=ClassificationSource.USER,
            created_at=now,
            updated_at=now,
        )
    )


def _seed_tech(
    repo: TechnicalMetadataRepository,
    sample_id: EntityId,
    *,
    duration_ms: int,
    channels: int = 2,
) -> None:
    repo.upsert(
        TechnicalMetadata(
            sample_id=sample_id,
            container_format="wav",
            codec="pcm_s16le",
            duration_ms=duration_ms,
            sample_rate_hz=44100,
            channels=channels,
            probe_version="test",
            probed_at=utc_now_iso(),
        )
    )


def _seed_feature(
    conn: sqlite3.Connection,
    sample_id: EntityId,
    *,
    name: str,
    value_json: str,
) -> None:
    run_id = new_entity_id()
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO analysis_runs (
            id, sample_id, pipeline_version, source_fingerprint, state,
            started_at, completed_at, error_code
        ) VALUES (?, ?, 'test', 'fp', 'completed', ?, ?, NULL)
        """,
        (str(run_id), str(sample_id), now, now),
    )
    conn.execute(
        """
        INSERT INTO analysis_features (id, analysis_run_id, name, value_json, provider_version)
        VALUES (?, ?, ?, ?, 'test')
        """,
        (str(new_entity_id()), str(run_id), name, value_json),
    )


def _seed_library(factory: ConnectionFactory) -> dict[str, Sample]:
    conn = factory.get_connection()
    sources = SourceRepository(conn)
    samples = SampleRepository(conn)
    classifications = ClassificationRepository(conn)
    tech = TechnicalMetadataRepository(conn)
    index = SearchIndexService(conn)

    source = _make_source()
    sources.create(source)

    kick = _make_sample(
        source_id=source.id,
        filename="punchy-kick.wav",
        relative_path="drums/punchy-kick.wav",
        size_bytes=1000,
    )
    snare = _make_sample(
        source_id=source.id,
        filename="crisp-snare.wav",
        relative_path="drums/crisp-snare.wav",
        size_bytes=2000,
        favorite=True,
    )
    loop = _make_sample(
        source_id=source.id,
        filename="ambient-loop.wav",
        relative_path="loops/ambient-loop.wav",
        size_bytes=3000,
    )
    for sample in (kick, snare, loop):
        samples.create(sample)

    _seed_classification(classifications, kick.id, ClassificationDimension.SAMPLE_TYPE, "One-shot")
    _seed_classification(
        classifications, kick.id, ClassificationDimension.INSTRUMENT_SOURCE, "Kick"
    )
    _seed_classification(classifications, snare.id, ClassificationDimension.SAMPLE_TYPE, "One-shot")
    _seed_classification(
        classifications, snare.id, ClassificationDimension.INSTRUMENT_SOURCE, "Snare"
    )
    _seed_classification(classifications, loop.id, ClassificationDimension.SAMPLE_TYPE, "Loop")

    _seed_tech(tech, kick.id, duration_ms=250, channels=1)
    _seed_tech(tech, snare.id, duration_ms=400, channels=2)
    _seed_tech(tech, loop.id, duration_ms=4000, channels=2)

    _seed_feature(conn, kick.id, name="bpm", value_json="90")
    _seed_feature(conn, snare.id, name="bpm", value_json="120")
    _seed_feature(conn, loop.id, name="bpm", value_json="85")
    _seed_feature(conn, loop.id, name="key", value_json='"Am"')

    for sample in (kick, snare, loop):
        index.refresh_sample(sample.id)

    return {"kick": kick, "snare": snare, "loop": loop}


def test_search_service_fts_paged_results(tmp_path: Path) -> None:
    factory = _migrated_factory(tmp_path / "search.sqlite3")
    seeded = _seed_library(factory)
    service = SearchService(factory)

    page = service.search(SampleQuery(text="kick"), PageRequest(offset=0, limit=10))
    assert page.total == 1
    assert len(page.items) == 1
    assert page.items[0].id == seeded["kick"].id
    assert page.items[0].name == "punchy-kick.wav"
    assert page.items[0].sample_type == "One-shot"


def test_structured_filter_and_sort(tmp_path: Path) -> None:
    factory = _migrated_factory(tmp_path / "filters.sqlite3")
    seeded = _seed_library(factory)
    service = SearchService(factory)

    query = SampleQuery(
        filters=SampleFilters(
            sample_type=("One-shot",),
            bpm=NumericRange(min=100, max=140),
        ),
        sort=SortSpec(field=SortField.DURATION, direction=SortDirection.ASC),
    )
    page = service.search(query, PageRequest(offset=0, limit=50))
    assert page.total == 1
    assert page.items[0].id == seeded["snare"].id
    assert page.items[0].bpm == 120.0

    by_name = service.search(
        SampleQuery(sort=SortSpec(field=SortField.NAME, direction=SortDirection.ASC)),
        PageRequest(offset=0, limit=50),
    )
    names = [row.name for row in by_name.items]
    assert names == sorted(names)
    assert names[0] == "ambient-loop.wav"

    by_duration_desc = service.search(
        SampleQuery(sort=SortSpec(field=SortField.DURATION, direction=SortDirection.DESC)),
        PageRequest(offset=0, limit=50),
    )
    durations = [row.duration_ms for row in by_duration_desc.items]
    assert durations == sorted((d for d in durations if d is not None), reverse=True)


def test_table_model_pages_without_loading_all_rows(tmp_path: Path) -> None:
    factory = _migrated_factory(tmp_path / "paging.sqlite3")
    conn = factory.get_connection()
    sources = SourceRepository(conn)
    samples = SampleRepository(conn)
    index = SearchIndexService(conn)
    source = _make_source("Bulk")
    sources.create(source)

    total = 250
    for i in range(total):
        sample = _make_sample(
            source_id=source.id,
            filename=f"sample-{i:04d}.wav",
            relative_path=f"bulk/sample-{i:04d}.wav",
            size_bytes=1000 + i,
        )
        samples.create(sample)
        index.refresh_sample(sample.id)

    service = SearchService(factory)
    model = SampleTableModel(service, page_size=50)
    model.set_query(SampleQuery())
    assert model.rowCount() == total

    # Touch first and last rows only — cache must stay bounded.
    assert model.data(model.index(0, 0)) == "sample-0000.wav"
    assert model.data(model.index(total - 1, 0)) == "sample-0249.wav"
    assert model.cached_row_count <= 150  # at most 3 pages of 50
    assert model.cached_row_count < total
    assert model.fetch_count >= 2
    assert model.fetch_count < total  # never one-row-at-a-time full scan


def test_save_search_persists_query(tmp_path: Path) -> None:
    factory = _migrated_factory(tmp_path / "saved.sqlite3")
    _seed_library(factory)
    service = SearchService(factory)
    query = SampleQuery(
        text="snare",
        filters=SampleFilters(sample_type=("One-shot",)),
        sort=SortSpec(field=SortField.NAME, direction=SortDirection.ASC),
    )
    saved = service.save_search("One-shot snares", query)
    assert saved.name == "One-shot snares"
    assert saved.query.text == "snare"
    assert saved.query.filters.sample_type == ("One-shot",)

    page = service.search(saved.query, PageRequest(offset=0, limit=10))
    assert page.total == 1
    assert page.items[0].name == "crisp-snare.wav"
