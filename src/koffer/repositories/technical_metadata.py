"""Typed technical_metadata repository. Caller owns the connection/transaction."""

from __future__ import annotations

import sqlite3

from koffer.domain.ids import EntityId
from koffer.domain.models import TechnicalMetadata
from koffer.repositories._sqlite import as_entity_id, optional_int, optional_str, row_count


def _from_row(row: sqlite3.Row) -> TechnicalMetadata:
    return TechnicalMetadata(
        sample_id=as_entity_id(row["sample_id"]),
        container_format=str(row["container_format"]),
        codec=str(row["codec"]),
        duration_ms=int(row["duration_ms"]),
        sample_rate_hz=int(row["sample_rate_hz"]),
        channels=int(row["channels"]),
        probe_version=str(row["probe_version"]),
        probed_at=str(row["probed_at"]),
        bit_depth=optional_int(row["bit_depth"]),
        channel_layout=optional_str(row["channel_layout"]),
        bitrate=optional_int(row["bitrate"]),
    )


class TechnicalMetadataRepository:
    """Upsert/get for Sample technical probe rows."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, meta: TechnicalMetadata) -> None:
        self._conn.execute(
            """
            INSERT INTO technical_metadata (
                sample_id, container_format, codec, duration_ms, sample_rate_hz,
                bit_depth, channels, channel_layout, bitrate, probe_version, probed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sample_id) DO UPDATE SET
                container_format = excluded.container_format,
                codec = excluded.codec,
                duration_ms = excluded.duration_ms,
                sample_rate_hz = excluded.sample_rate_hz,
                bit_depth = excluded.bit_depth,
                channels = excluded.channels,
                channel_layout = excluded.channel_layout,
                bitrate = excluded.bitrate,
                probe_version = excluded.probe_version,
                probed_at = excluded.probed_at
            """,
            (
                str(meta.sample_id),
                meta.container_format,
                meta.codec,
                meta.duration_ms,
                meta.sample_rate_hz,
                meta.bit_depth,
                meta.channels,
                meta.channel_layout,
                meta.bitrate,
                meta.probe_version,
                meta.probed_at,
            ),
        )

    def get(self, sample_id: EntityId) -> TechnicalMetadata | None:
        row = self._conn.execute(
            "SELECT * FROM technical_metadata WHERE sample_id = ?",
            (str(sample_id),),
        ).fetchone()
        return None if row is None else _from_row(row)

    def delete(self, sample_id: EntityId) -> bool:
        return (
            row_count(
                self._conn,
                "DELETE FROM technical_metadata WHERE sample_id = ?",
                (str(sample_id),),
            )
            > 0
        )
