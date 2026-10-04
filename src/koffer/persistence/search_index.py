"""FTS5 search projection maintenance for Samples (docs/17 SearchIndexService)."""

from __future__ import annotations

import contextlib
import re
import sqlite3

from koffer.domain.ids import EntityId

_PATH_SPLIT_RE = re.compile(r"[/\\._\-\s]+")
_QUERY_OP_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def path_terms_from_paths(*paths: str) -> str:
    """Normalize path-like strings into FTS-friendly whitespace-separated terms."""
    tokens: list[str] = []
    seen: set[str] = set()
    for path in paths:
        for token in _PATH_SPLIT_RE.split(path.strip().lower()):
            if not token or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return " ".join(tokens)


def _normalize_indexed_text(value: str) -> str:
    """Replace punctuation that FTS5 treats as operators with whitespace."""
    return _QUERY_OP_RE.sub(" ", value).strip()


def _join_terms(values: list[str]) -> str:
    cleaned = [_normalize_indexed_text(value) for value in values if value and value.strip()]
    return " ".join(part for part in cleaned if part)


def sanitize_fts_query(query: str) -> str:
    """Convert free-text input into a safe FTS5 MATCH expression (AND of tokens)."""
    tokens = [token for token in _QUERY_OP_RE.sub(" ", query).split() if token]
    return " ".join(tokens)


class SearchIndexService:
    """Refresh and query the sample_search_fts projection transactionally."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def refresh_sample(self, sample_id: EntityId) -> None:
        """Rebuild the FTS projection row for one Sample from canonical tables."""
        sample_key = str(sample_id)
        row = self._conn.execute(
            """
            SELECT
                s.filename AS filename,
                s.relative_path AS relative_path,
                s.normalized_path_cache AS normalized_path_cache,
                e.title AS title,
                e.artist AS artist,
                e.album AS album,
                e.genre AS genre
            FROM samples AS s
            LEFT JOIN embedded_metadata AS e ON e.sample_id = s.id
            WHERE s.id = ?
            """,
            (sample_key,),
        ).fetchone()
        if row is None:
            self.delete_sample(sample_id)
            return

        classification_rows = self._conn.execute(
            """
            SELECT value FROM classifications
            WHERE sample_id = ?
            ORDER BY dimension ASC, value ASC
            """,
            (sample_key,),
        ).fetchall()
        tag_rows = self._conn.execute(
            """
            SELECT t.display_name AS display_name
            FROM sample_tags AS st
            INNER JOIN user_tags AS t ON t.id = st.tag_id
            WHERE st.sample_id = ?
            ORDER BY t.normalized_name ASC
            """,
            (sample_key,),
        ).fetchall()

        filename = _normalize_indexed_text(str(row["filename"]))
        path_terms = path_terms_from_paths(
            str(row["relative_path"]),
            str(row["normalized_path_cache"]),
        )
        title = "" if row["title"] is None else _normalize_indexed_text(str(row["title"]))
        artist = "" if row["artist"] is None else _normalize_indexed_text(str(row["artist"]))
        album = "" if row["album"] is None else _normalize_indexed_text(str(row["album"]))
        genre = "" if row["genre"] is None else _normalize_indexed_text(str(row["genre"]))
        classification_terms = _join_terms([str(item[0]) for item in classification_rows])
        tag_terms = _join_terms([str(item[0]) for item in tag_rows])

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "DELETE FROM sample_search_fts WHERE sample_id = ?",
                (sample_key,),
            )
            self._conn.execute(
                """
                INSERT INTO sample_search_fts (
                    sample_id, filename, path_terms, title, artist, album, genre,
                    classification_terms, tag_terms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_key,
                    filename,
                    path_terms,
                    title,
                    artist,
                    album,
                    genre,
                    classification_terms,
                    tag_terms,
                ),
            )
            self._conn.execute("COMMIT")
        except Exception:
            with contextlib.suppress(sqlite3.Error):
                self._conn.execute("ROLLBACK")
            raise

    def delete_sample(self, sample_id: EntityId) -> None:
        """Remove a Sample from the FTS projection."""
        self._conn.execute(
            "DELETE FROM sample_search_fts WHERE sample_id = ?",
            (str(sample_id),),
        )

    def search(self, query: str, *, limit: int = 200) -> list[EntityId]:
        """Return Sample IDs matching an FTS5 query, ranked by bm25."""
        cleaned = sanitize_fts_query(query)
        if not cleaned:
            return []
        rows = self._conn.execute(
            """
            SELECT sample_id
            FROM sample_search_fts
            WHERE sample_search_fts MATCH ?
            ORDER BY bm25(sample_search_fts)
            LIMIT ?
            """,
            (cleaned, int(limit)),
        ).fetchall()
        return [EntityId(str(row[0])) for row in rows]

    def rebuild_all(self) -> int:
        """Rebuild the entire FTS projection from samples; returns row count."""
        ids = [
            EntityId(str(row[0]))
            for row in self._conn.execute("SELECT id FROM samples ORDER BY id ASC").fetchall()
        ]
        self._conn.execute("DELETE FROM sample_search_fts")
        for sample_id in ids:
            # refresh_sample opens its own transaction per row.
            self.refresh_sample(sample_id)
        return len(ids)
