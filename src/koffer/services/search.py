"""SearchService: SampleQuery FTS + structured filters, sort, paging (docs/04, 17, 27)."""

from __future__ import annotations

import sqlite3
from typing import Any

from koffer.domain.enums import SampleAvailability
from koffer.domain.errors import ValidationError
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.query import (
    Page,
    PageRequest,
    SampleQuery,
    SampleRow,
    SavedSearch,
    SortDirection,
    SortField,
)
from koffer.domain.timestamps import utc_now_iso
from koffer.persistence.connection import ConnectionFactory
from koffer.persistence.search_index import sanitize_fts_query
from koffer.repositories._sqlite import as_optional_entity_id, int_to_bool, optional_str
from koffer.repositories.saved_searches import SavedSearchRepository

_CLASSIFICATION_FILTERS: tuple[tuple[str, str], ...] = (
    ("sample_type", "sample_type"),
    ("instrument_source", "instrument_source"),
    ("musical_role", "musical_role"),
    ("genre_style", "genre_style"),
    ("character", "character"),
)

_SORT_SQL: dict[SortField, str] = {
    SortField.NAME: "s.filename",
    SortField.SAMPLE_TYPE: "sample_type",
    SortField.INSTRUMENT_SOURCE: "instrument_source",
    SortField.BPM: "bpm_value",
    SortField.KEY: "key_value",
    SortField.DURATION: "tm.duration_ms",
    SortField.EXTENSION: "s.extension",
    SortField.AVAILABILITY: "s.availability",
    SortField.DATE_DISCOVERED: "s.first_seen_at",
    SortField.LAST_USED: "s.last_previewed_at",
    SortField.FILE_SIZE: "s.size_bytes",
    SortField.ANALYSIS_CONFIDENCE: "analysis_confidence",
}


class SearchService:
    """Paged Sample browser queries over FTS + SQL predicates."""

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._factory = connection_factory

    def search(self, query: SampleQuery, page: PageRequest) -> Page[SampleRow]:
        """Return one page of SampleRow results for the query."""
        self._validate_query(query)
        conn = self._factory.get_connection()
        where_sql, where_params = _build_where(query)
        order_sql = _build_order(query)
        select_sql = f"""
            SELECT
                s.id AS id,
                s.filename AS name,
                s.extension AS extension,
                s.availability AS availability,
                s.favorite AS favorite,
                s.size_bytes AS size_bytes,
                s.first_seen_at AS first_seen_at,
                s.source_id AS source_id,
                s.last_previewed_at AS last_previewed_at,
                tm.duration_ms AS duration_ms,
                (
                    SELECT c.value FROM classifications AS c
                    WHERE c.sample_id = s.id AND c.dimension = 'sample_type'
                    ORDER BY c.value ASC LIMIT 1
                ) AS sample_type,
                (
                    SELECT c.value FROM classifications AS c
                    WHERE c.sample_id = s.id AND c.dimension = 'instrument_source'
                    ORDER BY c.value ASC LIMIT 1
                ) AS instrument_source,
                (
                    SELECT CAST(json_extract(af.value_json, '$') AS REAL)
                    FROM analysis_runs AS ar
                    INNER JOIN analysis_features AS af ON af.analysis_run_id = ar.id
                    WHERE ar.sample_id = s.id AND af.name = 'bpm'
                    ORDER BY ar.completed_at DESC NULLS LAST, ar.started_at DESC
                    LIMIT 1
                ) AS bpm_value,
                (
                    SELECT json_extract(af.value_json, '$')
                    FROM analysis_runs AS ar
                    INNER JOIN analysis_features AS af ON af.analysis_run_id = ar.id
                    WHERE ar.sample_id = s.id AND af.name = 'key'
                    ORDER BY ar.completed_at DESC NULLS LAST, ar.started_at DESC
                    LIMIT 1
                ) AS key_value,
                (
                    SELECT COUNT(*) FROM collection_samples AS cs
                    WHERE cs.sample_id = s.id
                ) AS collection_count,
                (
                    SELECT COUNT(*) FROM suggestions AS sg
                    WHERE sg.sample_id = s.id AND sg.status = 'pending'
                ) AS pending_suggestion_count,
                (
                    SELECT MAX(sg.confidence) FROM suggestions AS sg
                    WHERE sg.sample_id = s.id AND sg.status = 'pending'
                ) AS analysis_confidence
            FROM samples AS s
            LEFT JOIN technical_metadata AS tm ON tm.sample_id = s.id
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
        """
        params = (*where_params, int(page.limit), int(page.offset))
        rows = conn.execute(select_sql, params).fetchall()
        total = self._count_with_conn(conn, query)
        items = tuple(_row_to_sample_row(row) for row in rows)
        return Page(items=items, total=total, offset=page.offset, limit=page.limit)

    def count(self, query: SampleQuery) -> int:
        """Return total matching Sample count for the query."""
        self._validate_query(query)
        conn = self._factory.get_connection()
        return self._count_with_conn(conn, query)

    def list_saved_searches(self) -> list[SavedSearch]:
        """Return persisted dynamic library views in display-name order."""
        return SavedSearchRepository(self._factory.get_connection()).list()

    def get_saved_search(self, saved_id: EntityId) -> SavedSearch | None:
        """Return one saved library view by id."""
        return SavedSearchRepository(self._factory.get_connection()).get(saved_id)

    def save_search(self, name: str, query: SampleQuery) -> SavedSearch:
        """Persist a named dynamic SampleQuery view."""
        cleaned = name.strip()
        if not cleaned:
            raise ValidationError("Saved search name is required")
        self._validate_query(query)
        now = utc_now_iso()
        saved = SavedSearch(
            id=new_entity_id(),
            name=cleaned,
            query=query,
            created_at=now,
            updated_at=now,
        )
        conn = self._factory.get_connection()
        SavedSearchRepository(conn).create(saved)
        return saved

    def _count_with_conn(self, conn: sqlite3.Connection, query: SampleQuery) -> int:
        where_sql, where_params = _build_where(query)
        sql = f"SELECT COUNT(*) FROM samples AS s WHERE {where_sql}"
        row = conn.execute(sql, where_params).fetchone()
        return int(row[0]) if row is not None else 0

    def _validate_query(self, query: SampleQuery) -> None:
        if query.version != 1:
            raise ValidationError(
                "Unsupported SampleQuery version",
                detail=f"version={query.version}",
            )


def _build_where(query: SampleQuery) -> tuple[str, tuple[Any, ...]]:
    clauses: list[str] = ["1=1"]
    params: list[Any] = []
    fts = sanitize_fts_query(query.text)
    if fts:
        clauses.append(
            "s.id IN (SELECT sample_id FROM sample_search_fts WHERE sample_search_fts MATCH ?)"
        )
        params.append(fts)

    filters = query.filters
    for attr_name, dimension in _CLASSIFICATION_FILTERS:
        values = getattr(filters, attr_name)
        if not values:
            continue
        placeholders = ", ".join("?" for _ in values)
        clauses.append(
            f"""
            EXISTS (
                SELECT 1 FROM classifications AS c
                WHERE c.sample_id = s.id
                  AND c.dimension = ?
                  AND c.value IN ({placeholders})
            )
            """
        )
        params.append(dimension)
        params.extend(values)

    _append_range_exists(
        clauses,
        params,
        feature_name="bpm",
        numeric_range=filters.bpm,
        cast_as="REAL",
    )
    if not filters.duration_ms.is_empty():
        clauses.append(
            "EXISTS (SELECT 1 FROM technical_metadata AS tm "
            "WHERE tm.sample_id = s.id"
            + (" AND tm.duration_ms >= ?" if filters.duration_ms.min is not None else "")
            + (" AND tm.duration_ms <= ?" if filters.duration_ms.max is not None else "")
            + ")"
        )
        if filters.duration_ms.min is not None:
            params.append(float(filters.duration_ms.min))
        if filters.duration_ms.max is not None:
            params.append(float(filters.duration_ms.max))

    if filters.extensions:
        placeholders = ", ".join("?" for _ in filters.extensions)
        clauses.append(f"lower(s.extension) IN ({placeholders})")
        params.extend(ext.lower().lstrip(".") for ext in filters.extensions)

    if filters.availability:
        placeholders = ", ".join("?" for _ in filters.availability)
        clauses.append(f"s.availability IN ({placeholders})")
        params.extend(str(item) for item in filters.availability)

    if filters.source_ids:
        placeholders = ", ".join("?" for _ in filters.source_ids)
        clauses.append(f"s.source_id IN ({placeholders})")
        params.extend(str(item) for item in filters.source_ids)

    if filters.collection_ids:
        placeholders = ", ".join("?" for _ in filters.collection_ids)
        clauses.append(
            f"""
            EXISTS (
                SELECT 1 FROM collection_samples AS cs
                WHERE cs.sample_id = s.id AND cs.collection_id IN ({placeholders})
            )
            """
        )
        params.extend(str(item) for item in filters.collection_ids)

    if filters.favorite is not None:
        clauses.append("s.favorite = ?")
        params.append(1 if filters.favorite else 0)

    if filters.previewed_only:
        clauses.append("s.last_previewed_at IS NOT NULL")

    if filters.channels:
        placeholders = ", ".join("?" for _ in filters.channels)
        clauses.append(
            f"""
            EXISTS (
                SELECT 1 FROM technical_metadata AS tm
                WHERE tm.sample_id = s.id AND tm.channels IN ({placeholders})
            )
            """
        )
        params.extend(int(item) for item in filters.channels)

    if filters.keys:
        placeholders = ", ".join("?" for _ in filters.keys)
        clauses.append(
            f"""
            EXISTS (
                SELECT 1 FROM analysis_runs AS ar
                INNER JOIN analysis_features AS af ON af.analysis_run_id = ar.id
                WHERE ar.sample_id = s.id
                  AND af.name = 'key'
                  AND json_extract(af.value_json, '$') IN ({placeholders})
            )
            """
        )
        params.extend(filters.keys)

    return " AND ".join(clauses), tuple(params)


def _append_range_exists(
    clauses: list[str],
    params: list[Any],
    *,
    feature_name: str,
    numeric_range: Any,
    cast_as: str,
) -> None:
    if numeric_range.is_empty():
        return
    parts = [
        "EXISTS (",
        "SELECT 1 FROM analysis_runs AS ar",
        "INNER JOIN analysis_features AS af ON af.analysis_run_id = ar.id",
        "WHERE ar.sample_id = s.id",
        "AND af.name = ?",
    ]
    params.append(feature_name)
    if numeric_range.min is not None:
        parts.append(f"AND CAST(json_extract(af.value_json, '$') AS {cast_as}) >= ?")
        params.append(float(numeric_range.min))
    if numeric_range.max is not None:
        parts.append(f"AND CAST(json_extract(af.value_json, '$') AS {cast_as}) <= ?")
        params.append(float(numeric_range.max))
    parts.append(")")
    clauses.append(" ".join(parts))


def _build_order(query: SampleQuery) -> str:
    expr = _SORT_SQL[query.sort.field]
    direction = "ASC" if query.sort.direction is SortDirection.ASC else "DESC"
    # NULLs last for optional technical/analysis columns; stable tie-break on id.
    nulls = "NULLS LAST"
    return f"{expr} {direction} {nulls}, s.id ASC"


def _row_to_sample_row(row: sqlite3.Row) -> SampleRow:
    bpm_raw = row["bpm_value"]
    confidence_raw = row["analysis_confidence"]
    duration_raw = row["duration_ms"]
    return SampleRow(
        id=EntityId(str(row["id"])),
        name=str(row["name"]),
        extension=str(row["extension"]),
        availability=SampleAvailability(str(row["availability"])),
        favorite=int_to_bool(row["favorite"]),
        size_bytes=int(row["size_bytes"]),
        first_seen_at=str(row["first_seen_at"]),
        sample_type=optional_str(row["sample_type"]),
        instrument_source=optional_str(row["instrument_source"]),
        bpm=None if bpm_raw is None else float(bpm_raw),
        key=optional_str(row["key_value"]),
        duration_ms=None if duration_raw is None else int(duration_raw),
        source_id=as_optional_entity_id(row["source_id"]),
        last_previewed_at=optional_str(row["last_previewed_at"]),
        collection_count=int(row["collection_count"] or 0),
        pending_suggestion_count=int(row["pending_suggestion_count"] or 0),
        analysis_confidence=None if confidence_raw is None else float(confidence_raw),
    )


__all__ = ["SearchService"]
