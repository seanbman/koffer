-- Migration 001: core library schema (docs/17).
-- Timestamp convention: UTC ISO-8601 text with explicit offset (+00:00).
-- Durable IDs: UUIDv4 text generated in application code.
-- FTS5 search projection intentionally deferred (Order exclude / later phase).

CREATE TABLE sources (
    id TEXT PRIMARY KEY NOT NULL,
    display_name TEXT NOT NULL,
    root_path TEXT NOT NULL,
    storage_fingerprint TEXT,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    recursive INTEGER NOT NULL CHECK (recursive IN (0, 1)),
    status TEXT NOT NULL,
    last_scan_started_at TEXT,
    last_scan_completed_at TEXT,
    last_seen_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE source_exclusions (
    id TEXT PRIMARY KEY NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    pattern TEXT NOT NULL,
    pattern_type TEXT NOT NULL CHECK (
        pattern_type IN ('glob', 'relative_path', 'hidden_policy')
    ),
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1))
);

CREATE INDEX idx_source_exclusions_source_id ON source_exclusions(source_id);

CREATE TABLE samples (
    id TEXT PRIMARY KEY NOT NULL,
    source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
    relative_path TEXT NOT NULL,
    normalized_path_cache TEXT NOT NULL,
    filename TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    device_id INTEGER,
    inode INTEGER,
    quick_hash TEXT,
    content_hash TEXT,
    availability TEXT NOT NULL,
    favorite INTEGER NOT NULL CHECK (favorite IN (0, 1)),
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_previewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_samples_source_id ON samples(source_id);
CREATE INDEX idx_samples_availability ON samples(availability);
CREATE INDEX idx_samples_source_relative_path ON samples(source_id, relative_path);

CREATE TABLE technical_metadata (
    sample_id TEXT PRIMARY KEY NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    container_format TEXT NOT NULL,
    codec TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    sample_rate_hz INTEGER NOT NULL,
    bit_depth INTEGER,
    channels INTEGER NOT NULL,
    channel_layout TEXT,
    bitrate INTEGER,
    probe_version TEXT NOT NULL,
    probed_at TEXT NOT NULL
);

CREATE TABLE embedded_metadata (
    sample_id TEXT PRIMARY KEY NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    title TEXT,
    artist TEXT,
    album TEXT,
    album_artist TEXT,
    genre TEXT,
    date_text TEXT,
    track_number TEXT,
    composer TEXT,
    copyright TEXT,
    comment TEXT,
    artwork_present INTEGER NOT NULL CHECK (artwork_present IN (0, 1)),
    artwork_mime TEXT,
    raw_capability_json TEXT NOT NULL,
    reader_version TEXT NOT NULL,
    read_at TEXT NOT NULL
);

CREATE TABLE classifications (
    id TEXT PRIMARY KEY NOT NULL,
    sample_id TEXT NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL CHECK (
        source IN ('user', 'accepted_suggestion', 'import')
    ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (sample_id, dimension, value)
);

CREATE INDEX idx_classifications_sample_id ON classifications(sample_id);

CREATE TABLE user_tags (
    id TEXT PRIMARY KEY NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE sample_tags (
    sample_id TEXT NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    tag_id TEXT NOT NULL REFERENCES user_tags(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (sample_id, tag_id)
);

CREATE TABLE analysis_runs (
    id TEXT PRIMARY KEY NOT NULL,
    sample_id TEXT NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    pipeline_version TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    state TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_code TEXT
);

CREATE INDEX idx_analysis_runs_sample_id ON analysis_runs(sample_id);

CREATE TABLE analysis_features (
    id TEXT PRIMARY KEY NOT NULL,
    analysis_run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    value_json TEXT NOT NULL,
    provider_version TEXT NOT NULL
);

CREATE INDEX idx_analysis_features_run_id ON analysis_features(analysis_run_id);

CREATE TABLE suggestions (
    id TEXT PRIMARY KEY NOT NULL,
    sample_id TEXT NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    proposed_value TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'accepted', 'rejected', 'superseded')
    ),
    evidence_json TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_version TEXT NOT NULL,
    analysis_run_id TEXT NOT NULL REFERENCES analysis_runs(id),
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);

CREATE INDEX idx_suggestions_sample_id ON suggestions(sample_id);
CREATE INDEX idx_suggestions_status ON suggestions(status);

CREATE TABLE collections (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT,
    artwork_path TEXT,
    sort_mode TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Membership table name follows docs/17 (collection_samples).
CREATE TABLE collection_samples (
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    sample_id TEXT NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    manual_position INTEGER,
    added_at TEXT NOT NULL,
    PRIMARY KEY (collection_id, sample_id)
);

CREATE INDEX idx_collection_samples_sample_id ON collection_samples(sample_id);

CREATE TABLE saved_searches (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    query_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE preparation_recipes (
    id TEXT PRIMARY KEY NOT NULL,
    sample_id TEXT NOT NULL UNIQUE REFERENCES samples(id) ON DELETE CASCADE,
    recipe_version INTEGER NOT NULL,
    recipe_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE model_registry (
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    artifact_sha256 TEXT,
    installed_path TEXT,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    installed_at TEXT,
    PRIMARY KEY (provider, model_name, model_version)
);

CREATE TABLE jobs (
    id TEXT PRIMARY KEY NOT NULL,
    type TEXT NOT NULL,
    state TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    progress_current INTEGER NOT NULL,
    progress_total INTEGER,
    stage TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error_code TEXT,
    summary_json TEXT
);

CREATE INDEX idx_jobs_state ON jobs(state);

CREATE TABLE job_items (
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    item_key TEXT NOT NULL,
    sample_id TEXT REFERENCES samples(id) ON DELETE SET NULL,
    source_path TEXT,
    destination_path TEXT,
    state TEXT NOT NULL,
    error_code TEXT,
    detail_json TEXT,
    PRIMARY KEY (job_id, item_key)
);

CREATE TABLE audit_events (
    id TEXT PRIMARY KEY NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    detail_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_audit_events_created_at ON audit_events(created_at);

-- Application settings key/value store (optional settings export companion).
CREATE TABLE settings (
    key TEXT PRIMARY KEY NOT NULL,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
