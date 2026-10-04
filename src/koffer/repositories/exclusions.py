"""Typed Source exclusion repository. Caller owns the connection/transaction."""

from __future__ import annotations

import contextlib
import sqlite3

from koffer.domain.enums import ExclusionPatternType
from koffer.domain.ids import EntityId
from koffer.domain.models import ExclusionRule
from koffer.repositories._sqlite import as_entity_id, bool_to_int, int_to_bool, row_count


def _from_row(row: sqlite3.Row) -> ExclusionRule:
    return ExclusionRule(
        id=as_entity_id(row["id"]),
        source_id=as_entity_id(row["source_id"]),
        pattern=str(row["pattern"]),
        pattern_type=ExclusionPatternType(str(row["pattern_type"])),
        enabled=int_to_bool(row["enabled"]),
    )


class SourceExclusionRepository:
    """CRUD for per-Source exclusion rules."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_for_source(self, source_id: EntityId) -> list[ExclusionRule]:
        rows = self._conn.execute(
            """
            SELECT * FROM source_exclusions
            WHERE source_id = ?
            ORDER BY pattern ASC, id ASC
            """,
            (str(source_id),),
        ).fetchall()
        return [_from_row(row) for row in rows]

    def replace_for_source(
        self, source_id: EntityId, rules: list[ExclusionRule]
    ) -> list[ExclusionRule]:
        """Replace all exclusion rows for a Source with ``rules`` (atomic)."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "DELETE FROM source_exclusions WHERE source_id = ?",
                (str(source_id),),
            )
            stored: list[ExclusionRule] = []
            for rule in rules:
                row = ExclusionRule(
                    id=rule.id,
                    source_id=source_id,
                    pattern=rule.pattern,
                    pattern_type=rule.pattern_type,
                    enabled=rule.enabled,
                )
                self._conn.execute(
                    """
                    INSERT INTO source_exclusions (
                        id, source_id, pattern, pattern_type, enabled
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(row.id),
                        str(row.source_id),
                        row.pattern,
                        str(row.pattern_type),
                        bool_to_int(row.enabled),
                    ),
                )
                stored.append(row)
            self._conn.execute("COMMIT")
        except Exception:
            with contextlib.suppress(sqlite3.Error):
                self._conn.execute("ROLLBACK")
            raise
        return stored

    def delete_for_source(self, source_id: EntityId) -> int:
        return row_count(
            self._conn,
            "DELETE FROM source_exclusions WHERE source_id = ?",
            (str(source_id),),
        )
