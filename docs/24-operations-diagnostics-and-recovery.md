# 24. Operations, Diagnostics, and Recovery

## Goal

Koffer should be repairable without asking users to delete their database or lose organization.

## Application startup sequence

1. resolve XDG paths;
2. initialize logging;
3. validate writable config/data/cache locations;
4. open database;
5. run migrations;
6. mark abandoned running Jobs interrupted;
7. load settings;
8. initialize services/scheduler;
9. initialize playback;
10. open shell;
11. asynchronously refresh Source availability and pending maintenance.

If database open/migration fails, open a recovery error surface; do not create a fresh database over the failed one.

## Graceful shutdown

- persist window geometry/state;
- stop accepting new Jobs;
- request cancellation for cancellable transient Jobs;
- wait bounded time for critical filesystem commit sections;
- persist interrupted state for unfinished Jobs;
- stop playback;
- close DB connections/logs.

Do not force-delete temp files that may be needed to diagnose/recover a mutation Job.

## Logs

Default local rotating logs:
`$XDG_STATE_HOME/koffer/logs/` where available, otherwise platformdirs-compatible state/data path.

Levels:
- INFO normal lifecycle/Job summaries;
- WARNING recoverable anomalies;
- ERROR failed user operation;
- DEBUG opt-in diagnostic detail.

Paths may appear in local logs because repair sometimes requires them, but diagnostics export should offer path redaction.

## Diagnostics bundle

ZIP contents:
- version/build;
- OS/kernel/session type;
- Qt/Python versions;
- audio backend/device summary;
- resolved XDG paths;
- schema version;
- Source status summary with optional/redacted paths;
- model manifest/version;
- recent sanitized logs;
- recent failed Job summaries;
- dependency/package inventory.

Excluded by default:
- audio files;
- waveform cache;
- embeddings;
- cover art;
- database content;
- full filenames/paths when redaction mode is selected.

UI lists bundle contents before export.

## Database integrity

Maintenance offers:
- `PRAGMA quick_check` routine;
- `PRAGMA integrity_check` deeper verification;
- backup before invasive repair.

Never "fix" corruption by silently deleting the database.

## Backup

Use SQLite online backup API into a versioned backup file plus manifest.

Backup destination can be user-chosen.

Restore:
1. validate manifest;
2. verify backup database integrity;
3. close active app DB access;
4. back up current DB automatically;
5. restore to temp path;
6. migrate if needed;
7. integrity check;
8. atomic replace;
9. reopen;
10. show summary.

## Source recovery

### Source offline

Keep Samples and metadata. Disable playback/file operations. Recheck mount periodically/on user request.

### File missing

Allow:
- locate exact file;
- locate Source root;
- leave unresolved;
- remove stale library entry.

### File changed

Show old vs new basic fingerprint. Invalidate derived analysis. User-authored organization remains.

### File moved externally

"Locate file" can reconnect the existing Sample identity when confidence is high and user confirms. Do not create duplicates silently.

### Permission denied

Preserve state and expose path/permission error. Do not reinterpret as missing.

## Temp file recovery

Mutation/render temp names include Job ID.

On startup, inspect known interrupted Jobs and matching temp artifacts.

Actions are operation-specific:
- safe orphan temp may be deleted after user/system validation;
- completed verified destination may allow Job reconciliation;
- ambiguous move/delete state requires explicit repair UI, never automatic destructive cleanup.

## Cache recovery

Waveform/embedding/similarity cache corruption:
- log;
- discard affected derived artifact;
- queue rebuild;
- never affect durable organization.

## Model recovery

Checksum mismatch:
- reject artifact;
- delete/quarantine failed download;
- keep provider disabled;
- offer retry.

Inference crash:
- mark analysis item failed;
- do not crash app;
- provider may be disabled after repeated process-level failures;
- deterministic features remain usable.

## Safe mode

Implement a diagnostic startup flag:
`koffer --safe-mode`

Safe mode:
- does not auto-resume analysis;
- disables semantic provider;
- avoids nonessential background maintenance;
- opens library read/browse capabilities where database is valid.

Also support:
- `--diagnostics`;
- `--version`;
- `--data-dir PATH` for tests only or documented advanced use.

## Troubleshooting map

| Symptom | First checks | Safe response |
|---|---|---|
| App will not open | logs, schema, Qt plugin | safe mode / diagnostics |
| Source vanished | mount/status | keep records, reconnect |
| Scan stuck | Activity Job stage | cancel/retry, inspect path |
| Playback fails | probe vs playback backend | report format/backend |
| Metadata write failed | Job item + capability | preserve/report target |
| Model unavailable | manifest/path/checksum | disable model, retry |
| Search stale | FTS health | rebuild search projection |
| Similarity stale | model/index version | rebuild derived index |
| DB concern | quick/integrity check | backup then repair/restore |

## Never advise as first-line recovery

Do not tell a user to:
- delete `~/.local/share/koffer`;
- wipe the database;
- remove original audio;
- reinstall without preserving library state.

Recovery should preserve intent first.
