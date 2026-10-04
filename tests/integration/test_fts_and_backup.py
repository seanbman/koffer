"""Integration tests for FTS5 projection maintenance and backup/restore."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from koffer.domain import (
    Classification,
    ClassificationDimension,
    ClassificationSource,
    EntityId,
    Sample,
    SampleAvailability,
    Source,
    SourceStatus,
    new_entity_id,
    utc_now_iso,
)
from koffer.persistence import (
    ConnectionFactory,
    SearchIndexService,
    apply_migrations,
    backup_database,
    restore_database,
)
from koffer.repositories import ClassificationRepository, SampleRepository, SourceRepository


def _migrated_conn(db_path: Path) -> tuple[ConnectionFactory, sqlite3.Connection]:
    factory = ConnectionFactory(db_path)
    conn = factory.get_connection()
    apply_migrations(conn)
    return factory, conn


def _make_source() -> Source:
    now = utc_now_iso()
    return Source(
        id=new_entity_id(),
        display_name="Fixture Pack",
        root_path="/tmp/koffer-fixtures/pack-a",
        enabled=True,
        recursive=True,
        status=SourceStatus.ONLINE,
        created_at=now,
        updated_at=now,
    )


def _make_sample(
    *,
    source_id: EntityId | None,
    filename: str,
    relative_path: str,
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


def _seed_embedded_metadata(
    conn: sqlite3.Connection,
    *,
    sample_id: EntityId,
    title: str,
    artist: str,
    album: str,
    genre: str,
) -> None:
    conn.execute(
        """
        INSERT INTO embedded_metadata (
            sample_id, title, artist, album, album_artist, genre, date_text,
            track_number, composer, copyright, comment, artwork_present,
            artwork_mime, raw_capability_json, reader_version, read_at
        ) VALUES (?, ?, ?, ?, NULL, ?, NULL, NULL, NULL, NULL, NULL, 0, NULL, '{}', 'test', ?)
        """,
        (str(sample_id), title, artist, album, genre, utc_now_iso()),
    )


def test_fts_projection_update_and_query_for_seeded_sample(tmp_path: Path) -> None:
    factory, conn = _migrated_conn(tmp_path / "library.sqlite3")
    try:
        sources = SourceRepository(conn)
        samples = SampleRepository(conn)
        classifications = ClassificationRepository(conn)
        index = SearchIndexService(conn)

        source = _make_source()
        sources.create(source)
        sample = _make_sample(
            source_id=source.id,
            filename="punchy-kick.wav",
            relative_path="drums/kicks/punchy-kick.wav",
        )
        samples.create(sample)
        _seed_embedded_metadata(
            conn,
            sample_id=sample.id,
            title="Punchy Kick",
            artist="Studio One",
            album="Drum Kit",
            genre="Electronic",
        )
        now = utc_now_iso()
        classifications.create(
            Classification(
                id=new_entity_id(),
                sample_id=sample.id,
                dimension=ClassificationDimension.SAMPLE_TYPE,
                value="one-shot",
                source=ClassificationSource.USER,
                created_at=now,
                updated_at=now,
            )
        )
        tag_id = new_entity_id()
        conn.execute(
            """
            INSERT INTO user_tags (id, normalized_name, display_name, created_at)
            VALUES (?, 'boom', 'Boom', ?)
            """,
            (str(tag_id), now),
        )
        conn.execute(
            """
            INSERT INTO sample_tags (sample_id, tag_id, created_at)
            VALUES (?, ?, ?)
            """,
            (str(sample.id), str(tag_id), now),
        )

        index.refresh_sample(sample.id)

        by_filename = index.search("punchy")
        assert sample.id in by_filename

        by_path = index.search("drums")
        assert sample.id in by_path

        by_classification = index.search("one-shot")
        assert sample.id in by_classification

        by_tag = index.search("Boom")
        assert sample.id in by_tag

        by_title = index.search("Punchy Kick")
        assert sample.id in by_title

        other = _make_sample(
            source_id=source.id,
            filename="hat.wav",
            relative_path="drums/hats/hat.wav",
        )
        samples.create(other)
        index.refresh_sample(other.id)
        assert other.id not in index.search("punchy")

        index.delete_sample(sample.id)
        assert sample.id not in index.search("punchy")
    finally:
        factory.close_thread_connection()


def test_backup_restore_roundtrip_preserves_user_authored_rows(tmp_path: Path) -> None:
    source_db = tmp_path / "live" / "library.sqlite3"
    backup_parent = tmp_path / "backups"
    restore_db = tmp_path / "restored" / "library.sqlite3"

    factory, conn = _migrated_conn(source_db)
    try:
        sources = SourceRepository(conn)
        samples = SampleRepository(conn)
        classifications = ClassificationRepository(conn)

        source = _make_source()
        sources.create(source)
        sample = _make_sample(
            source_id=source.id,
            filename="snare.wav",
            relative_path="drums/snare.wav",
        )
        samples.create(sample)
        now = utc_now_iso()
        classification = Classification(
            id=new_entity_id(),
            sample_id=sample.id,
            dimension=ClassificationDimension.INSTRUMENT_SOURCE,
            value="acoustic-kit",
            source=ClassificationSource.USER,
            created_at=now,
            updated_at=now,
        )
        classifications.create(classification)

        collection_id = new_entity_id()
        conn.execute(
            """
            INSERT INTO collections (
                id, name, description, color, artwork_path, sort_mode, created_at, updated_at
            ) VALUES (?, 'Favorites', 'user pack', NULL, NULL, 'manual', ?, ?)
            """,
            (str(collection_id), now, now),
        )
        conn.execute(
            """
            INSERT INTO collection_samples (collection_id, sample_id, manual_position, added_at)
            VALUES (?, ?, 0, ?)
            """,
            (str(collection_id), str(sample.id), now),
        )

        SearchIndexService(conn).refresh_sample(sample.id)
        backup_dir = backup_database(conn, backup_parent, stamp="roundtrip-1")
        assert (backup_dir / "manifest.json").is_file()
        assert (backup_dir / "library.sqlite3").is_file()
    finally:
        factory.close_thread_connection()

    manifest = restore_database(backup_dir, restore_db)
    assert manifest.schema_version >= 2
    assert manifest.koffer_version

    restore_factory, restore_conn = _migrated_conn(restore_db)
    try:
        restored_source = SourceRepository(restore_conn).get(source.id)
        restored_sample = SampleRepository(restore_conn).get(sample.id)
        restored_classification = ClassificationRepository(restore_conn).get(classification.id)
        assert restored_source == source
        assert restored_sample == sample
        assert restored_classification == classification

        membership = restore_conn.execute(
            """
            SELECT collection_id, sample_id FROM collection_samples
            WHERE collection_id = ? AND sample_id = ?
            """,
            (str(collection_id), str(sample.id)),
        ).fetchone()
        assert membership is not None

        hits = SearchIndexService(restore_conn).search("snare")
        assert sample.id in hits
    finally:
        restore_factory.close_thread_connection()
