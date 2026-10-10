"""Typed user_tags / sample_tags repository (library-only; never mutates audio)."""

from __future__ import annotations

import sqlite3

from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.timestamps import utc_now_iso
from koffer.repositories._sqlite import as_entity_id, row_count


class TagRepository:
    """CRUD helpers for free-form user tags attached to Samples."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_display_names_for_sample(self, sample_id: EntityId) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT t.display_name AS display_name
            FROM sample_tags AS st
            INNER JOIN user_tags AS t ON t.id = st.tag_id
            WHERE st.sample_id = ?
            ORDER BY t.normalized_name ASC, t.id ASC
            """,
            (str(sample_id),),
        ).fetchall()
        return [str(row["display_name"]) for row in rows]

    def ensure_tag(self, display_name: str) -> EntityId:
        cleaned = display_name.strip()
        if not cleaned:
            raise ValueError("Tag display name is required")
        normalized = cleaned.casefold()
        existing = self._conn.execute(
            "SELECT id FROM user_tags WHERE normalized_name = ?",
            (normalized,),
        ).fetchone()
        if existing is not None:
            return as_entity_id(existing["id"])
        tag_id = new_entity_id()
        self._conn.execute(
            """
            INSERT INTO user_tags (id, normalized_name, display_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(tag_id), normalized, cleaned, utc_now_iso()),
        )
        return tag_id

    def attach(self, sample_id: EntityId, tag_id: EntityId) -> bool:
        """Attach tag; returns True when a new membership row was inserted."""
        return (
            row_count(
                self._conn,
                """
                INSERT OR IGNORE INTO sample_tags (sample_id, tag_id, created_at)
                VALUES (?, ?, ?)
                """,
                (str(sample_id), str(tag_id), utc_now_iso()),
            )
            > 0
        )

    def replace_for_sample(self, sample_id: EntityId, display_names: tuple[str, ...]) -> None:
        """Replace one Sample's library tags without touching its media file."""
        self._conn.execute("DELETE FROM sample_tags WHERE sample_id = ?", (str(sample_id),))
        seen: set[str] = set()
        for display_name in display_names:
            cleaned = display_name.strip()
            normalized = cleaned.casefold()
            if not cleaned or normalized in seen:
                continue
            seen.add(normalized)
            self.attach(sample_id, self.ensure_tag(cleaned))
