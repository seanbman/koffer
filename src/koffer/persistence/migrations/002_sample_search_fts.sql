-- Migration 002: FTS5 searchable projection for Samples (docs/17).
-- Append-only; does not alter released migration 001.
-- Projection rows are maintained by SearchIndexService (not content= sync).

CREATE VIRTUAL TABLE sample_search_fts USING fts5(
    sample_id UNINDEXED,
    filename,
    path_terms,
    title,
    artist,
    album,
    genre,
    classification_terms,
    tag_terms
);
