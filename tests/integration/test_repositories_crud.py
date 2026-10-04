"""Integration CRUD tests for typed repositories against a migrated temp DB."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

from koffer.domain import (
    Classification,
    ClassificationDimension,
    ClassificationSource,
    Collection,
    CollectionSortMode,
    EntityId,
    Job,
    JobState,
    JobType,
    Sample,
    SampleAvailability,
    Source,
    SourceStatus,
    Suggestion,
    SuggestionStatus,
    new_entity_id,
    utc_now_iso,
)
from koffer.persistence import ConnectionFactory, apply_migrations
from koffer.repositories import (
    ClassificationRepository,
    CollectionRepository,
    JobRepository,
    SampleRepository,
    SourceRepository,
    SuggestionRepository,
)


def _migrated_conn(tmp_path: Path) -> tuple[ConnectionFactory, sqlite3.Connection]:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    conn = factory.get_connection()
    apply_migrations(conn)
    return factory, conn


def _make_source(
    *,
    display_name: str = "Fixture Pack",
    status: SourceStatus = SourceStatus.ONLINE,
) -> Source:
    now = utc_now_iso()
    return Source(
        id=new_entity_id(),
        display_name=display_name,
        root_path="/tmp/koffer-fixtures/pack-a",
        enabled=True,
        recursive=True,
        status=status,
        created_at=now,
        updated_at=now,
    )


def _make_sample(
    *,
    source_id: EntityId | None = None,
    filename: str = "kick.wav",
    relative_path: str = "drums/kick.wav",
) -> Sample:
    now = utc_now_iso()
    return Sample(
        id=new_entity_id(),
        relative_path=relative_path,
        normalized_path_cache=relative_path,
        filename=filename,
        extension="wav",
        size_bytes=2048,
        mtime_ns=1_700_000_000_000_000_000,
        availability=SampleAvailability.ONLINE,
        favorite=False,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
        source_id=source_id,
    )


def _insert_analysis_run(conn: sqlite3.Connection, *, sample_id: EntityId) -> EntityId:
    run_id = new_entity_id()
    conn.execute(
        """
        INSERT INTO analysis_runs (
            id, sample_id, pipeline_version, source_fingerprint, state, started_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(run_id),
            str(sample_id),
            "test-pipeline-1",
            "fingerprint-test",
            "completed",
            utc_now_iso(),
        ),
    )
    return run_id


def test_source_crud(tmp_path: Path) -> None:
    factory, conn = _migrated_conn(tmp_path)
    try:
        repo = SourceRepository(conn)
        source = _make_source(display_name="Root A")
        repo.create(source)
        assert repo.get(source.id) == source

        updated = replace(
            source,
            display_name="Root A Renamed",
            status=SourceStatus.OFFLINE,
            enabled=False,
            updated_at=utc_now_iso(),
        )
        assert repo.update(updated) is True
        assert repo.get(source.id) == updated
        assert [item.id for item in repo.list_all()] == [source.id]

        assert repo.delete(source.id) is True
        assert repo.get(source.id) is None
        assert repo.update(updated) is False
        assert repo.delete(source.id) is False
    finally:
        factory.close_thread_connection()


def test_sample_crud(tmp_path: Path) -> None:
    factory, conn = _migrated_conn(tmp_path)
    try:
        sources = SourceRepository(conn)
        samples = SampleRepository(conn)
        source = _make_source()
        sources.create(source)

        sample = _make_sample(
            source_id=source.id,
            filename="snare.wav",
            relative_path="drums/snare.wav",
        )
        samples.create(sample)
        assert samples.get(sample.id) == sample
        assert [item.id for item in samples.list_by_source(source.id)] == [sample.id]

        updated = replace(
            sample,
            favorite=True,
            availability=SampleAvailability.CHANGED,
            size_bytes=4096,
            updated_at=utc_now_iso(),
        )
        assert samples.update(updated) is True
        assert samples.get(sample.id) == updated

        assert samples.delete(sample.id) is True
        assert samples.get(sample.id) is None
    finally:
        factory.close_thread_connection()


def test_collection_crud_and_membership_does_not_delete_samples(tmp_path: Path) -> None:
    factory, conn = _migrated_conn(tmp_path)
    try:
        sources = SourceRepository(conn)
        samples = SampleRepository(conn)
        collections = CollectionRepository(conn)

        source = _make_source()
        sources.create(source)
        sample = _make_sample(source_id=source.id)
        samples.create(sample)

        now = utc_now_iso()
        collection = Collection(
            id=new_entity_id(),
            name="Favorites",
            sort_mode=str(CollectionSortMode.ADDED_AT_DESC),
            created_at=now,
            updated_at=now,
            description="logical grouping only",
        )
        collections.create(collection)
        assert collections.get(collection.id) == collection

        renamed = replace(collection, name="Session A", updated_at=utc_now_iso())
        assert collections.update(renamed) is True
        assert collections.get(collection.id) == renamed

        collections.add_sample(collection.id, sample.id, manual_position=1)
        memberships = collections.list_memberships(collection.id)
        assert len(memberships) == 1
        assert memberships[0].sample_id == sample.id
        assert memberships[0].manual_position == 1
        assert collections.list_sample_ids(collection.id) == [sample.id]

        assert collections.remove_sample(collection.id, sample.id) is True
        assert collections.list_sample_ids(collection.id) == []
        # Membership removal is DB-only: Sample row remains.
        assert samples.get(sample.id) == sample

        collections.add_sample(collection.id, sample.id)
        assert collections.delete(collection.id) is True
        assert collections.get(collection.id) is None
        # Deleting a Collection cascades membership only, never Samples/files.
        assert samples.get(sample.id) == sample
        remaining = conn.execute(
            "SELECT COUNT(*) FROM collection_samples WHERE sample_id = ?",
            (str(sample.id),),
        ).fetchone()
        assert remaining is not None
        assert int(remaining[0]) == 0
    finally:
        factory.close_thread_connection()


def test_classification_crud(tmp_path: Path) -> None:
    factory, conn = _migrated_conn(tmp_path)
    try:
        sources = SourceRepository(conn)
        samples = SampleRepository(conn)
        classifications = ClassificationRepository(conn)

        source = _make_source()
        sources.create(source)
        sample = _make_sample(source_id=source.id)
        samples.create(sample)

        now = utc_now_iso()
        classification = Classification(
            id=new_entity_id(),
            sample_id=sample.id,
            dimension=ClassificationDimension.SAMPLE_TYPE,
            value="One-shot",
            source=ClassificationSource.USER,
            created_at=now,
            updated_at=now,
        )
        classifications.create(classification)
        assert classifications.get(classification.id) == classification
        assert classifications.list_for_sample(sample.id) == [classification]

        updated = replace(
            classification,
            value="Loop",
            source=ClassificationSource.IMPORT,
            updated_at=utc_now_iso(),
        )
        assert classifications.update(updated) is True
        assert classifications.get(classification.id) == updated

        assert classifications.delete(classification.id) is True
        assert classifications.get(classification.id) is None
        assert classifications.list_for_sample(sample.id) == []
    finally:
        factory.close_thread_connection()


def test_suggestion_crud(tmp_path: Path) -> None:
    factory, conn = _migrated_conn(tmp_path)
    try:
        sources = SourceRepository(conn)
        samples = SampleRepository(conn)
        suggestions = SuggestionRepository(conn)

        source = _make_source()
        sources.create(source)
        sample = _make_sample(source_id=source.id)
        samples.create(sample)
        run_id = _insert_analysis_run(conn, sample_id=sample.id)

        suggestion = Suggestion(
            id=new_entity_id(),
            sample_id=sample.id,
            dimension="sample_type",
            proposed_value="One-shot",
            confidence=0.91,
            status=SuggestionStatus.PENDING,
            evidence_json='{"signals":["filename"]}',
            provider="test-provider",
            provider_version="1.0.0",
            analysis_run_id=run_id,
            created_at=utc_now_iso(),
        )
        suggestions.create(suggestion)
        assert suggestions.get(suggestion.id) == suggestion
        assert suggestions.list_for_sample(sample.id, status=SuggestionStatus.PENDING) == [
            suggestion
        ]

        reviewed = replace(
            suggestion,
            status=SuggestionStatus.ACCEPTED,
            reviewed_at=utc_now_iso(),
            confidence=0.95,
        )
        assert suggestions.update(reviewed) is True
        assert suggestions.get(suggestion.id) == reviewed
        assert suggestions.list_for_sample(sample.id, status=SuggestionStatus.PENDING) == []

        assert suggestions.delete(suggestion.id) is True
        assert suggestions.get(suggestion.id) is None
    finally:
        factory.close_thread_connection()


def test_job_crud(tmp_path: Path) -> None:
    factory, conn = _migrated_conn(tmp_path)
    try:
        jobs = JobRepository(conn)
        job = Job(
            id=new_entity_id(),
            type=JobType.SOURCE_SCAN,
            state=JobState.QUEUED,
            scope_json='{"source_id":"x"}',
            progress_current=0,
            created_at=utc_now_iso(),
            progress_total=100,
            stage="queued",
        )
        jobs.create(job)
        assert jobs.get(job.id) == job
        assert [item.id for item in jobs.list_by_state(JobState.QUEUED)] == [job.id]

        running = replace(
            job,
            state=JobState.RUNNING,
            progress_current=40,
            stage="walk",
            started_at=utc_now_iso(),
        )
        assert jobs.update(running) is True
        assert jobs.get(job.id) == running
        assert jobs.list_by_state(JobState.QUEUED) == []
        assert [item.id for item in jobs.list_by_state(JobState.RUNNING)] == [job.id]

        assert jobs.delete(job.id) is True
        assert jobs.get(job.id) is None
    finally:
        factory.close_thread_connection()
