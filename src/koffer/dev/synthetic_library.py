"""Deterministic synthetic library fixture (docs/20 performance fixture).

Builds a SQLite library + filesystem *manifest* representing N Samples without
materializing N audio files. Paths in the DB are virtual; audio_files_materialized
is always false for the default 100k corpus.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from koffer.persistence.connection import ConnectionFactory
from koffer.persistence.migrations import apply_migrations
from koffer.persistence.search_index import path_terms_from_paths

# Stable namespace so sample/source IDs are deterministic across runs.
_FIXTURE_NAMESPACE = uuid.UUID("8f3c6e2a-4b91-5d70-9e18-2a7c4f6b1d03")

DEFAULT_SAMPLE_COUNT = 100_000
DEFAULT_SEED = "koffer-100k-v1"
MANIFEST_NAME = "manifest.json"
DATABASE_NAME = "library.sqlite3"

_STEMS: tuple[str, ...] = (
    "kick",
    "snare",
    "hat",
    "clap",
    "bass",
    "pad",
    "lead",
    "perc",
    "fx",
    "loop",
)
_SAMPLE_TYPES: tuple[str, ...] = (
    "One-shot",
    "Loop",
    "Texture",
    "Ambience",
    "SFX",
)
_INSTRUMENTS: tuple[str, ...] = (
    "Kick",
    "Snare",
    "Hat",
    "Bass",
    "Synth",
    "Pad",
    "Vocal",
    "Guitar",
)
_EXTENSIONS: tuple[str, ...] = ("wav", "flac", "aiff", "mp3")
_NOW = "2024-01-15T12:00:00+00:00"


@dataclass(frozen=True)
class SyntheticLibraryPaths:
    """Output layout for a generated synthetic library fixture."""

    root: Path
    database_path: Path
    manifest_path: Path
    virtual_media_root: str


@dataclass(frozen=True)
class SyntheticLibraryResult:
    """Result of building a synthetic library fixture."""

    paths: SyntheticLibraryPaths
    sample_count: int
    source_id: str
    database_sha256: str
    audio_files_created: int
    manifest: dict[str, Any]


def deterministic_id(kind: str, key: str) -> str:
    """Return a stable UUIDv5 text id for fixture entities."""
    return str(uuid.uuid5(_FIXTURE_NAMESPACE, f"{kind}:{key}"))


def fixture_paths(root: Path) -> SyntheticLibraryPaths:
    """Resolve standard fixture file locations under ``root``."""
    root = Path(root)
    return SyntheticLibraryPaths(
        root=root,
        database_path=root / DATABASE_NAME,
        manifest_path=root / MANIFEST_NAME,
        virtual_media_root="/synthetic/koffer-perf-library",
    )


def build_synthetic_library(
    output_dir: Path,
    *,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    seed: str = DEFAULT_SEED,
    force: bool = False,
) -> SyntheticLibraryResult:
    """Create a migrated SQLite DB + manifest for ``sample_count`` Samples.

    Does not create per-sample audio files. Optionally writes zero audio files
    (default); ``audio_files_created`` remains 0.
    """
    if sample_count < 1:
        msg = "sample_count must be >= 1"
        raise ValueError(msg)

    paths = fixture_paths(output_dir)
    paths.root.mkdir(parents=True, exist_ok=True)

    if paths.database_path.exists() or paths.manifest_path.exists():
        if not force:
            if paths.database_path.exists() and paths.manifest_path.exists():
                existing = json.loads(paths.manifest_path.read_text(encoding="utf-8"))
                if (
                    int(existing.get("sample_count", -1)) == sample_count
                    and str(existing.get("seed", "")) == seed
                ):
                    return SyntheticLibraryResult(
                        paths=paths,
                        sample_count=sample_count,
                        source_id=str(existing["source_id"]),
                        database_sha256=str(existing["database_sha256"]),
                        audio_files_created=int(existing.get("audio_files_created", 0)),
                        manifest=existing,
                    )
            msg = f"fixture already exists at {paths.root}; pass force=True to rebuild"
            raise FileExistsError(msg)
        if paths.database_path.exists():
            paths.database_path.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(paths.database_path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        if paths.manifest_path.exists():
            paths.manifest_path.unlink()

    factory = ConnectionFactory(paths.database_path)
    conn = factory.get_connection()
    try:
        apply_migrations(conn)
        source_id = _insert_corpus(conn, sample_count=sample_count, seed=seed, paths=paths)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        factory.close_thread_connection()

    digest = _sha256_file(paths.database_path)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "seed": seed,
        "sample_count": sample_count,
        "source_id": source_id,
        "database": DATABASE_NAME,
        "database_sha256": digest,
        "virtual_media_root": paths.virtual_media_root,
        "audio_files_materialized": False,
        "audio_files_created": 0,
        "notes": (
            "Synthetic performance corpus: Sample rows and FTS projection only. "
            "No per-sample audio files are stored; relative_path values are virtual."
        ),
        "targets_docs_20": {
            "app_shell_ms": 2000,
            "common_query_p95_ms": 250,
            "first_200_rows_ms": 400,
        },
    }
    paths.manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return SyntheticLibraryResult(
        paths=paths,
        sample_count=sample_count,
        source_id=source_id,
        database_sha256=digest,
        audio_files_created=0,
        manifest=manifest,
    )


def _insert_corpus(
    conn: sqlite3.Connection,
    *,
    sample_count: int,
    seed: str,
    paths: SyntheticLibraryPaths,
) -> str:
    source_id = deterministic_id("source", seed)
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """
            INSERT INTO sources (
                id, display_name, root_path, storage_fingerprint, enabled, recursive,
                status, last_scan_started_at, last_scan_completed_at, last_seen_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, 1, 'online', ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                "Synthetic 100k Performance Library",
                paths.virtual_media_root,
                f"synth:{seed}",
                _NOW,
                _NOW,
                _NOW,
                _NOW,
                _NOW,
            ),
        )

        sample_rows: list[tuple[Any, ...]] = []
        tech_rows: list[tuple[Any, ...]] = []
        class_rows: list[tuple[Any, ...]] = []
        fts_rows: list[tuple[Any, ...]] = []

        batch = 2_000
        for index in range(sample_count):
            sample_id = deterministic_id("sample", f"{seed}:{index}")
            stem = _STEMS[index % len(_STEMS)]
            ext = _EXTENSIONS[index % len(_EXTENSIONS)]
            folder = f"pack{(index // 1000) % 100:02d}/{stem}"
            filename = f"{stem}_{index:06d}.{ext}"
            relative_path = f"{folder}/{filename}"
            size_bytes = 1024 + (index % 50_000)
            mtime_ns = 1_700_000_000_000_000_000 + index
            favorite = 1 if index % 97 == 0 else 0

            sample_rows.append(
                (
                    sample_id,
                    source_id,
                    relative_path,
                    relative_path.lower(),
                    filename,
                    ext,
                    size_bytes,
                    mtime_ns,
                    None,
                    None,
                    f"qh{index:08x}",
                    f"ch{index:08x}",
                    "online",
                    favorite,
                    _NOW,
                    _NOW,
                    None,
                    _NOW,
                    _NOW,
                )
            )

            duration_ms = 100 + (index % 8_000)
            tech_rows.append(
                (
                    sample_id,
                    ext,
                    "pcm_s16le" if ext in {"wav", "aiff"} else "flac",
                    duration_ms,
                    44100 if index % 2 == 0 else 48000,
                    16,
                    1 if index % 3 else 2,
                    "mono" if index % 3 else "stereo",
                    None,
                    "synthetic-1",
                    _NOW,
                )
            )

            sample_type = _SAMPLE_TYPES[index % len(_SAMPLE_TYPES)]
            instrument = _INSTRUMENTS[index % len(_INSTRUMENTS)]
            class_rows.append(
                (
                    deterministic_id("class", f"{seed}:{index}:sample_type"),
                    sample_id,
                    "sample_type",
                    sample_type,
                    "user",
                    _NOW,
                    _NOW,
                )
            )
            class_rows.append(
                (
                    deterministic_id("class", f"{seed}:{index}:instrument_source"),
                    sample_id,
                    "instrument_source",
                    instrument,
                    "user",
                    _NOW,
                    _NOW,
                )
            )

            path_terms = path_terms_from_paths(relative_path, relative_path.lower())
            fts_rows.append(
                (
                    sample_id,
                    filename.replace(".", " "),
                    path_terms,
                    "",
                    "",
                    "",
                    "",
                    f"{sample_type} {instrument}",
                    "",
                )
            )

            if len(sample_rows) >= batch:
                _flush_batch(conn, sample_rows, tech_rows, class_rows, fts_rows)
                sample_rows.clear()
                tech_rows.clear()
                class_rows.clear()
                fts_rows.clear()

        if sample_rows:
            _flush_batch(conn, sample_rows, tech_rows, class_rows, fts_rows)

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return source_id


def _flush_batch(
    conn: sqlite3.Connection,
    sample_rows: list[tuple[Any, ...]],
    tech_rows: list[tuple[Any, ...]],
    class_rows: list[tuple[Any, ...]],
    fts_rows: list[tuple[Any, ...]],
) -> None:
    conn.executemany(
        """
        INSERT INTO samples (
            id, source_id, relative_path, normalized_path_cache, filename, extension,
            size_bytes, mtime_ns, device_id, inode, quick_hash, content_hash,
            availability, favorite, first_seen_at, last_seen_at, last_previewed_at,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sample_rows,
    )
    conn.executemany(
        """
        INSERT INTO technical_metadata (
            sample_id, container_format, codec, duration_ms, sample_rate_hz, bit_depth,
            channels, channel_layout, bitrate, probe_version, probed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tech_rows,
    )
    conn.executemany(
        """
        INSERT INTO classifications (
            id, sample_id, dimension, value, source, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        class_rows,
    )
    conn.executemany(
        """
        INSERT INTO sample_search_fts (
            sample_id, filename, path_terms, title, artist, album, genre,
            classification_terms, tag_terms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        fts_rows,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "DATABASE_NAME",
    "DEFAULT_SAMPLE_COUNT",
    "DEFAULT_SEED",
    "MANIFEST_NAME",
    "SyntheticLibraryPaths",
    "SyntheticLibraryResult",
    "build_synthetic_library",
    "deterministic_id",
    "fixture_paths",
]
