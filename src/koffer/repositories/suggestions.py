"""Typed Suggestion repository for machine-proposed classifications."""

from __future__ import annotations

import sqlite3

from koffer.domain.enums import SuggestionStatus
from koffer.domain.ids import EntityId
from koffer.domain.models import Suggestion
from koffer.repositories._sqlite import as_entity_id, optional_str, row_count


def _from_row(row: sqlite3.Row) -> Suggestion:
    return Suggestion(
        id=as_entity_id(row["id"]),
        sample_id=as_entity_id(row["sample_id"]),
        dimension=str(row["dimension"]),
        proposed_value=str(row["proposed_value"]),
        confidence=float(row["confidence"]),
        status=SuggestionStatus(str(row["status"])),
        evidence_json=str(row["evidence_json"]),
        provider=str(row["provider"]),
        provider_version=str(row["provider_version"]),
        analysis_run_id=as_entity_id(row["analysis_run_id"]),
        created_at=str(row["created_at"]),
        reviewed_at=optional_str(row["reviewed_at"]),
    )


class SuggestionRepository:
    """CRUD for Suggestions awaiting or completing user review."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, suggestion: Suggestion) -> None:
        self._conn.execute(
            """
            INSERT INTO suggestions (
                id, sample_id, dimension, proposed_value, confidence, status,
                evidence_json, provider, provider_version, analysis_run_id,
                created_at, reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(suggestion.id),
                str(suggestion.sample_id),
                suggestion.dimension,
                suggestion.proposed_value,
                suggestion.confidence,
                str(suggestion.status),
                suggestion.evidence_json,
                suggestion.provider,
                suggestion.provider_version,
                str(suggestion.analysis_run_id),
                suggestion.created_at,
                suggestion.reviewed_at,
            ),
        )

    def get(self, suggestion_id: EntityId) -> Suggestion | None:
        row = self._conn.execute(
            "SELECT * FROM suggestions WHERE id = ?",
            (str(suggestion_id),),
        ).fetchone()
        return None if row is None else _from_row(row)

    def list_for_sample(
        self,
        sample_id: EntityId,
        *,
        status: SuggestionStatus | None = None,
    ) -> list[Suggestion]:
        if status is None:
            rows = self._conn.execute(
                """
                SELECT * FROM suggestions
                WHERE sample_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (str(sample_id),),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM suggestions
                WHERE sample_id = ? AND status = ?
                ORDER BY created_at ASC, id ASC
                """,
                (str(sample_id), str(status)),
            ).fetchall()
        return [_from_row(row) for row in rows]

    def list_by_status(
        self,
        status: SuggestionStatus,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[Suggestion]:
        rows = self._conn.execute(
            """
            SELECT * FROM suggestions
            WHERE status = ?
            ORDER BY confidence DESC, created_at ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            (str(status), int(limit), int(offset)),
        ).fetchall()
        return [_from_row(row) for row in rows]

    def count_by_status(self, status: SuggestionStatus) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM suggestions WHERE status = ?",
            (str(status),),
        ).fetchone()
        return int(row["n"]) if row is not None else 0

    def supersede_pending_for_sample(
        self,
        sample_id: EntityId,
        *,
        reviewed_at: str,
        dimensions: set[str] | None = None,
    ) -> int:
        """Mark pending Suggestions superseded. Optional dimension filter."""
        if dimensions is None:
            return row_count(
                self._conn,
                """
                UPDATE suggestions
                SET status = ?, reviewed_at = ?
                WHERE sample_id = ? AND status = ?
                """,
                (
                    str(SuggestionStatus.SUPERSEDED),
                    reviewed_at,
                    str(sample_id),
                    str(SuggestionStatus.PENDING),
                ),
            )
        if not dimensions:
            return 0
        placeholders = ", ".join("?" for _ in dimensions)
        return row_count(
            self._conn,
            f"""
            UPDATE suggestions
            SET status = ?, reviewed_at = ?
            WHERE sample_id = ? AND status = ? AND dimension IN ({placeholders})
            """,
            (
                str(SuggestionStatus.SUPERSEDED),
                reviewed_at,
                str(sample_id),
                str(SuggestionStatus.PENDING),
                *sorted(dimensions),
            ),
        )

    def update(self, suggestion: Suggestion) -> bool:
        return (
            row_count(
                self._conn,
                """
                UPDATE suggestions SET
                    sample_id = ?,
                    dimension = ?,
                    proposed_value = ?,
                    confidence = ?,
                    status = ?,
                    evidence_json = ?,
                    provider = ?,
                    provider_version = ?,
                    analysis_run_id = ?,
                    reviewed_at = ?
                WHERE id = ?
                """,
                (
                    str(suggestion.sample_id),
                    suggestion.dimension,
                    suggestion.proposed_value,
                    suggestion.confidence,
                    str(suggestion.status),
                    suggestion.evidence_json,
                    suggestion.provider,
                    suggestion.provider_version,
                    str(suggestion.analysis_run_id),
                    suggestion.reviewed_at,
                    str(suggestion.id),
                ),
            )
            > 0
        )

    def delete(self, suggestion_id: EntityId) -> bool:
        return (
            row_count(
                self._conn,
                "DELETE FROM suggestions WHERE id = ?",
                (str(suggestion_id),),
            )
            > 0
        )
