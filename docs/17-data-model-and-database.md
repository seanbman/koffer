# 17. Data Model and Database Contract

## Database location and mode

Default database:

`$XDG_DATA_HOME/koffer/library.sqlite3`

Fallback follows `platformdirs`.

SQLite settings:
- foreign keys ON;
- WAL journal mode;
- busy timeout configured;
- explicit transactions for writes;
- no cross-thread connection reuse.

## Identifiers

Durable domain entities use UUIDv4 text IDs generated in application code.

Do not expose SQLite rowids as product identity.

Timestamps are stored as UTC ISO-8601 text or integer Unix microseconds consistently across the schema. Pick one representation in migration 001 and never mix conventions.

## Migration system

Migrations live in:

`src/koffer/persistence/migrations/NNN_description.sql`

Required tables:
- `schema_migrations(version, applied_at, checksum)`.

Migration rules:
- append-only migration history;
- never edit an already released migration;
- migration runs inside transaction where SQLite allows;
- startup refuses to run against a newer unsupported schema;
- migration failure leaves previous schema usable;
- CI tests every migration chain from retained fixtures.

## Canonical tables

### sources

Purpose: authorized scan roots.

Required fields:
- id;
- display_name;
- root_path;
- storage_fingerprint nullable;
- enabled;
- recursive;
- status;
- last_scan_started_at;
- last_scan_completed_at;
- last_seen_at;
- created_at;
- updated_at.

Source status enum:
- online;
- offline;
- permission_denied;
- disabled;
- scanning;
- error.

### source_exclusions

- id;
- source_id;
- pattern;
- pattern_type: glob | relative_path | hidden_policy;
- enabled.

### samples

One row per indexed audio file identity.

Required fields:
- id;
- source_id nullable only for managed/orphan recovery cases;
- relative_path;
- normalized_path_cache;
- filename;
- extension;
- size_bytes;
- mtime_ns;
- device_id nullable;
- inode nullable;
- quick_hash nullable;
- content_hash nullable;
- availability;
- favorite;
- first_seen_at;
- last_seen_at;
- last_previewed_at nullable;
- created_at;
- updated_at.

Availability enum:
- online;
- source_offline;
- missing;
- changed;
- permission_denied;
- unsupported.

A scan identifies likely unchanged files with source + relative path + size + mtime. Content hash is calculated lazily when required for duplicate certainty or mutation verification.

### technical_metadata

One-to-one with Sample:
- sample_id PK/FK;
- container_format;
- codec;
- duration_ms;
- sample_rate_hz;
- bit_depth nullable;
- channels;
- channel_layout nullable;
- bitrate nullable;
- probe_version;
- probed_at.

### embedded_metadata

One-to-one snapshot of what is actually in the file:
- sample_id;
- title;
- artist;
- album;
- album_artist;
- genre;
- date_text;
- track_number;
- composer;
- copyright;
- comment;
- artwork_present;
- artwork_mime nullable;
- raw_capability_json;
- reader_version;
- read_at.

Do not merge this table with user-confirmed Koffer classifications.

### classifications

Confirmed library classifications.

Fields:
- id;
- sample_id;
- dimension;
- value;
- source: user | accepted_suggestion | import;
- created_at;
- updated_at.

Dimensions:
- sample_type;
- instrument_source;
- musical_role;
- genre_style;
- character.

Unique constraint on sample_id + dimension + normalized value.

### user_tags

- id;
- normalized_name unique;
- display_name;
- created_at.

### sample_tags

- sample_id;
- tag_id;
- created_at;
- PK(sample_id, tag_id).

### suggestions

Fields:
- id;
- sample_id;
- dimension;
- proposed_value;
- confidence real 0..1;
- status: pending | accepted | rejected | superseded;
- evidence_json;
- provider;
- provider_version;
- analysis_run_id;
- created_at;
- reviewed_at nullable.

Accepted Suggestion causes a separate classification row; the Suggestion record remains for provenance.

### collections

- id;
- name;
- description nullable;
- color nullable;
- artwork_path nullable;
- sort_mode;
- created_at;
- updated_at.

### collection_samples

- collection_id;
- sample_id;
- manual_position nullable;
- added_at;
- PK(collection_id, sample_id).

Deleting a Collection cascades membership only, never Samples/files.

### saved_searches

- id;
- name;
- query_json;
- created_at;
- updated_at.

The query JSON is versioned:
~~~json
{"version":1,"text":"kick","filters":{"sample_type":["One-shot"],"bpm":{"min":null,"max":null}},"sort":{"field":"name","direction":"asc"}}
~~~

### preparation_recipes

One active recipe per Sample for V1:
- id;
- sample_id unique;
- recipe_version;
- recipe_json;
- updated_at.

Recipe JSON contains only non-destructive parameters and references no temp file paths.

### analysis_runs

- id;
- sample_id;
- pipeline_version;
- source_fingerprint;
- state;
- started_at;
- completed_at nullable;
- error_code nullable.

### analysis_features

Small derived scalar features/provenance:
- id;
- analysis_run_id;
- name;
- value_json;
- provider_version.

Large waveforms/embeddings remain in rebuildable cache files.

### model_registry

- provider;
- model_name;
- model_version;
- artifact_sha256 nullable;
- installed_path nullable;
- enabled;
- installed_at nullable;
- PK(provider, model_name, model_version).

### jobs

- id;
- type;
- state;
- scope_json;
- progress_current;
- progress_total nullable;
- stage nullable;
- created_at;
- started_at nullable;
- completed_at nullable;
- error_code nullable;
- summary_json nullable.

### job_items

For batch side effects:
- job_id;
- item_key;
- sample_id nullable;
- source_path nullable;
- destination_path nullable;
- state;
- error_code nullable;
- detail_json nullable;
- PK(job_id, item_key).

### audit_events

User-relevant durable history:
- id;
- event_type;
- entity_type;
- entity_id;
- summary;
- detail_json;
- created_at.

Use for metadata writes, moves, renders, restores, and repair actions—not every UI click.

## Search index

Use SQLite FTS5.

`sample_search_fts` contains searchable projections:
- sample_id UNINDEXED;
- filename;
- path_terms;
- title;
- artist;
- album;
- genre;
- classification_terms;
- tag_terms.

A SearchIndexService refreshes affected rows transactionally after relevant changes.

Structured filters such as BPM, key, duration, availability, Source, Collection, and suggestion state remain SQL predicates rather than FTS text.

## Query pagination

Browser queries use stable keyset or bounded offset pagination through a Qt table model. Never instantiate 100,000 full Sample objects just to show the first screen.

Default page fetch target: 200 rows. Prefetch adjacent pages based on scroll.

## File identity

Identity tiers:
1. Source + normalized relative path.
2. size + mtime for cheap change detection.
3. quick hash for likely duplicate/change confirmation.
4. full content hash for definitive duplicate/mutation verification.

Do not hash every large library file eagerly.

## Cache layout

Under `$XDG_CACHE_HOME/koffer/`:

~~~text
waveforms/<pipeline-version>/<sample-id>.bin
embeddings/<model-version>/<sample-id>.f32
similarity/<model-version>/index.bin
renders/tmp/
thumbnails/
~~~

All of these are rebuildable.

## Backup

Use SQLite online backup API, not raw copying of a live database file.

Backup includes:
- database;
- manifest with Koffer/schema version;
- optional settings export.

It does not include user audio by default.

## Data invariants

- confirmed classification survives reanalysis;
- Collection membership survives cache clearing/reanalysis;
- removing a Source never deletes Source files;
- Source offline never deletes Sample rows;
- changed source content invalidates derived analysis;
- a metadata write refreshes embedded_metadata after verification;
- a file move updates path only after filesystem success;
- partial batch operations preserve per-item truth;
- migrations never silently recreate the library.
