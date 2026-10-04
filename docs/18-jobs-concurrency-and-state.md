# 18. Jobs, Concurrency, and State

## Goal

All expensive or side-effecting work is represented as a Job. The UI remains responsive and always knows what is happening.

## Main-thread rule

The Qt main thread may:
- update widgets/models;
- submit Jobs;
- consume progress signals;
- perform tiny in-memory transformations.

It may not:
- recursively scan directories;
- hash large files;
- call FFmpeg synchronously;
- run librosa/PANNs inference;
- perform bulk database rebuilds;
- copy/move batches;
- write metadata batches;
- build similarity indexes;
- create backups.

## Job scheduler

Implement one `JobScheduler` with bounded executors.

Suggested lanes:
- IO lane: 4 workers default;
- analysis lane: min(2, max(1, CPU/2)) default;
- mutation lane: 1–2 workers, serialized by destination/source locks;
- render lane: 1 worker default;
- maintenance lane: exclusive when database-wide.

Settings may reduce concurrency.

## Database connections

Every Job execution context obtains its own SQLite connection from a connection factory and closes it when done.

Never pass a live sqlite3 Connection object from UI thread to a worker.

## Job states

- queued;
- running;
- pause_requested;
- paused;
- cancel_requested;
- cancelled;
- completed;
- completed_with_errors;
- failed.

Only supported Jobs expose pause. Cancellation is cooperative.

## Job progress contract

Each Job publishes:
- job_id;
- state;
- stage;
- current;
- total nullable;
- message;
- active_item nullable;
- succeeded;
- failed;
- skipped.

Progress events are throttled so thousands of files do not flood the Qt event queue.

## Job types

Required:
- source_scan;
- technical_probe;
- waveform_build;
- deterministic_analysis;
- semantic_analysis;
- similarity_index_build;
- copy_files;
- move_files;
- metadata_write;
- render;
- backup;
- restore;
- rebuild_filesystem_index;
- rebuild_waveforms;
- rebuild_analysis;
- rebuild_similarity;
- cache_clear;
- database_verify.

## Scan pipeline

Source scan stages:
1. validate Source/mount;
2. enumerate paths;
3. apply exclusions;
4. classify supported file extensions;
5. compare known file state;
6. insert/update discovery records in batches;
7. mark previously known unseen items as missing only after successful enumeration;
8. queue probes/analysis for new or changed files;
9. commit scan summary.

If enumeration fails due to an offline Source, do **not** mark all files missing.

## File mutation locking

Mutating operations acquire logical locks for affected source/destination paths.

Rules:
- no two Jobs may write the same destination file concurrently;
- move and metadata-write cannot target the same file concurrently;
- playback/read may continue where OS/filesystem permits;
- a render output is written to a temporary sibling and atomically renamed when possible.

## Copy transaction pattern

For each item:
1. validate source exists/readable;
2. resolve destination and conflict policy;
3. copy to temporary destination;
4. fsync/close where practical;
5. verify size and optionally hash according to risk;
6. atomic rename temp -> final;
7. index destination if applicable;
8. record job_item complete.

On failure, remove temp artifact if safe. Original remains untouched.

## Move transaction pattern

Prefer same-filesystem atomic rename.

Cross-filesystem move:
1. verified copy using Copy pattern;
2. only after successful destination verification, delete source;
3. verify source deletion;
4. update library identity/path;
5. record audit event.

If source deletion fails after copy, state becomes completed_with_errors and both paths are reported. Never pretend it was a clean move.

## Metadata write pattern

Per item:
1. inspect format capability;
2. create backup/temp copy when writer requires;
3. write requested fields;
4. close file;
5. reread tags;
6. compare requested supported fields;
7. refresh embedded_metadata;
8. report verified success.

Failure must identify whether source bytes changed.

For Update Original, prefer safe temp-replace mechanisms supported by the metadata library/container.

## Render pattern

1. validate source and recipe;
2. render to temp output;
3. ffprobe output;
4. verify duration/format/expected basic properties;
5. apply metadata/artwork when requested;
6. reread metadata;
7. resolve final destination conflict policy;
8. atomic finalization where possible;
9. index output if it belongs to managed library;
10. record provenance/audit event.

## Cancellation

Pure derived Jobs can cancel between files/analysis stages.

Mutation Jobs cancel between items. Never abort in the middle of a critical rename/delete sequence unless the underlying operation is safely interruptible.

The Activity Center explains completed side effects after cancellation.

## Retry

Automatic retry is limited to clearly transient conditions such as temporary database busy or short-lived file lock, with bounded exponential backoff.

Permission errors, unsupported formats, conflicts, and invalid recipes require user/logic resolution, not endless retry.

## Crash recovery

Jobs persisted as running at previous process termination are marked interrupted on next launch.

Recovery:
- pure derived Jobs can be requeued;
- file mutation Jobs inspect job_items/temp files before retry;
- never blindly replay a delete/move step;
- Activity Center exposes interrupted Jobs.

## UI state

The UI subscribes to a JobStore/model and does not own Job truth.

Closing a screen does not cancel its Job.

## Testing concurrency

Tests must prove:
- UI remains responsive during a synthetic slow scan;
- separate workers do not reuse one SQLite connection;
- cancel stops future items while preserving completed item records;
- two Jobs cannot overwrite same destination;
- offline Source scan does not mass-mark missing;
- cross-filesystem move partial failure is truthful;
- app restart recognizes interrupted Jobs.
