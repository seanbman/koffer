"""Typed saved_searches repository. Caller owns the connection/transaction."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from koffer.domain.enums import SampleAvailability
from koffer.domain.ids import EntityId
from koffer.domain.query import (
    NumericRange,
    SampleFilters,
    SampleQuery,
    SavedSearch,
    SortDirection,
    SortField,
    SortSpec,
)
from koffer.repositories._sqlite import as_entity_id, row_count


def sample_query_to_json(query: SampleQuery) -> str:
    """Serialize SampleQuery to the versioned docs/17 JSON shape."""
    filters = query.filters
    payload: dict[str, Any] = {
        "version": query.version,
        "text": query.text,
        "filters": {
            "sample_type": list(filters.sample_type),
            "instrument_source": list(filters.instrument_source),
            "musical_role": list(filters.musical_role),
            "genre_style": list(filters.genre_style),
            "character": list(filters.character),
            "bpm": {"min": filters.bpm.min, "max": filters.bpm.max},
            "duration_ms": {"min": filters.duration_ms.min, "max": filters.duration_ms.max},
            "extensions": list(filters.extensions),
            "availability": [str(item) for item in filters.availability],
            "source_ids": [str(item) for item in filters.source_ids],
            "collection_ids": [str(item) for item in filters.collection_ids],
            "favorite": filters.favorite,
            "previewed_only": filters.previewed_only,
            "channels": list(filters.channels),
            "keys": list(filters.keys),
        },
        "sort": {"field": str(query.sort.field), "direction": str(query.sort.direction)},
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def sample_query_from_json(raw: str) -> SampleQuery:
    """Parse versioned query_json into SampleQuery."""
    data = json.loads(raw)
    version = int(data.get("version", 1))
    if version != 1:
        msg = f"unsupported SampleQuery version: {version}"
        raise ValueError(msg)
    filters_raw = data.get("filters") or {}
    bpm_raw = filters_raw.get("bpm") or {}
    duration_raw = filters_raw.get("duration_ms") or {}
    sort_raw = data.get("sort") or {}
    availability = tuple(
        SampleAvailability(str(item)) for item in (filters_raw.get("availability") or ())
    )
    return SampleQuery(
        version=version,
        text=str(data.get("text") or ""),
        filters=SampleFilters(
            sample_type=tuple(str(item) for item in (filters_raw.get("sample_type") or ())),
            instrument_source=tuple(
                str(item) for item in (filters_raw.get("instrument_source") or ())
            ),
            musical_role=tuple(str(item) for item in (filters_raw.get("musical_role") or ())),
            genre_style=tuple(str(item) for item in (filters_raw.get("genre_style") or ())),
            character=tuple(str(item) for item in (filters_raw.get("character") or ())),
            bpm=NumericRange(
                min=_optional_float(bpm_raw.get("min")),
                max=_optional_float(bpm_raw.get("max")),
            ),
            duration_ms=NumericRange(
                min=_optional_float(duration_raw.get("min")),
                max=_optional_float(duration_raw.get("max")),
            ),
            extensions=tuple(str(item) for item in (filters_raw.get("extensions") or ())),
            availability=availability,
            source_ids=tuple(EntityId(str(item)) for item in (filters_raw.get("source_ids") or ())),
            collection_ids=tuple(
                EntityId(str(item)) for item in (filters_raw.get("collection_ids") or ())
            ),
            favorite=_optional_bool(filters_raw.get("favorite")),
            previewed_only=bool(filters_raw.get("previewed_only", False)),
            channels=tuple(int(item) for item in (filters_raw.get("channels") or ())),
            keys=tuple(str(item) for item in (filters_raw.get("keys") or ())),
        ),
        sort=SortSpec(
            field=SortField(str(sort_raw.get("field") or SortField.NAME)),
            direction=SortDirection(str(sort_raw.get("direction") or SortDirection.ASC)),
        ),
    )


def _optional_float(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float | str):
        return float(value)
    msg = f"expected numeric JSON value, got {type(value).__name__}"
    raise TypeError(msg)


def _optional_bool(value: object | None) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _from_row(row: sqlite3.Row) -> SavedSearch:
    return SavedSearch(
        id=as_entity_id(row["id"]),
        name=str(row["name"]),
        query=sample_query_from_json(str(row["query_json"])),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


class SavedSearchRepository:
    """CRUD for named saved SampleQuery views."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, saved: SavedSearch) -> None:
        self._conn.execute(
            """
            INSERT INTO saved_searches (id, name, query_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(saved.id),
                saved.name,
                sample_query_to_json(saved.query),
                saved.created_at,
                saved.updated_at,
            ),
        )

    def get(self, saved_id: EntityId) -> SavedSearch | None:
        row = self._conn.execute(
            "SELECT * FROM saved_searches WHERE id = ?",
            (str(saved_id),),
        ).fetchone()
        return None if row is None else _from_row(row)

    def list(self) -> list[SavedSearch]:
        rows = self._conn.execute(
            "SELECT * FROM saved_searches ORDER BY name ASC, id ASC"
        ).fetchall()
        return [_from_row(row) for row in rows]

    def update(self, saved: SavedSearch) -> bool:
        return (
            row_count(
                self._conn,
                """
                UPDATE saved_searches SET
                    name = ?,
                    query_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    saved.name,
                    sample_query_to_json(saved.query),
                    saved.updated_at,
                    str(saved.id),
                ),
            )
            > 0
        )

    def delete(self, saved_id: EntityId) -> bool:
        return (
            row_count(
                self._conn,
                "DELETE FROM saved_searches WHERE id = ?",
                (str(saved_id),),
            )
            > 0
        )
