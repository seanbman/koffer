# 10. Technical Product Contract

## Status

This document is an authoritative technical contract for the authorized Koffer implementation. Detailed module boundaries, schema, Job behavior, pipeline, testing, packaging, and execution order are defined in chapters 16–28.

## Runtime and UI

Koffer is a Python 3.12+ desktop application built with PySide6 / Qt 6.

Qt owns:
- windows;
- widgets;
- focus;
- native file/directory dialogs;
- drag-and-drop;
- clipboard;
- menus;
- HiDPI behavior;
- platform integration.

The UI is not an Electron shell and does not depend on a local web server.

## Persistence

SQLite stores durable library state.

The database contains:
- Sources;
- Samples and file identity;
- factual technical metadata;
- embedded descriptive metadata snapshots;
- confirmed classifications;
- Suggestions and review state;
- Collections and membership;
- Saved Searches;
- preparation recipes;
- Job history;
- analysis versions/provenance;
- model/version metadata;
- user preferences that belong with library state.

SQLite uses WAL mode where appropriate. Each worker thread/process owns its own database connection or accesses persistence through an explicitly thread-safe data service. A connection created on the UI thread is never casually reused in a worker.

## XDG filesystem layout

Koffer follows XDG conventions.

Conceptual locations:
- config: `$XDG_CONFIG_HOME/koffer/`;
- durable app data: `$XDG_DATA_HOME/koffer/`;
- cache: `$XDG_CACHE_HOME/koffer/`;
- user-selected managed audio library: independent, configurable location;
- model cache: user-visible/configurable under app data or cache depending model persistence policy.

Exact resolved paths are displayed in About & Diagnostics.

## Audio decoding and rendering

Koffer uses a capability layer rather than scattering codec-specific logic through the UI.

FFmpeg/ffprobe are the authoritative broad compatibility layer for probing and rendering. Release packaging follows `21-packaging-ci-and-release.md` and records the exact distributed build/license configuration.

Rendering is always treated as a Job and produces a new file by default.

## Embedded metadata

Metadata read/write is isolated behind a format-aware service implemented with Mutagen for supported container/tag formats.

A metadata write:
1. validates field support;
2. writes to the chosen target;
3. flushes/closes;
4. rereads the target;
5. reports verified result or explicit failure.

Per-field exceptions are never silently swallowed.

## Playback

Playback is abstracted from browser state. The playback service accepts Sample identity and path, reports position/state, and survives normal screen changes.

The implementation must work with common modern Linux desktop audio stacks, prioritizing PipeWire/PulseAudio compatibility and documenting any ALSA fallback behavior.

## Analysis pipeline

Analysis is modular:

1. path/filename context;
2. embedded metadata;
3. factual technical extraction;
4. deterministic DSP;
5. local semantic inference;
6. embeddings/similarity;
7. evidence fusion;
8. Suggestion generation;
9. user review.

Every derived result carries an analysis version/provenance so stale outputs can be invalidated when algorithms, models, or source content change.

## Local models

Local semantic inference is a required product capability with an optional-at-runtime model installation. The application remains usable when the semantic provider is disabled or its model is absent.

Model requirements:
- permissive distribution or clearly compatible license;
- CPU-capable baseline;
- offline operation;
- versioned weights;
- observable disk usage;
- removable/re-downloadable cache;
- inference cancellation between items;
- no silent upload.

The V1 semantic provider is PANNs-compatible. Its provider interface remains modular so a later documented model migration does not force UI or durable user-state changes.

## Worker architecture

Expensive work never executes directly in an event handler.

Worker domains include:
- scanning;
- metadata extraction;
- waveform generation;
- BPM/key analysis;
- model inference;
- embeddings;
- similarity indexing;
- file copy/move;
- metadata writes;
- rendering;
- backup;
- rebuild/maintenance.

Jobs communicate progress through a bounded event interface. UI updates are marshalled back to the Qt main thread.

## Cancellation and idempotency

Jobs are designed around safe checkpoints.

Pure analysis work can usually be cancelled without side effects.

Filesystem Jobs track each item and record success/failure/skipped state so interrupted batches can be explained and, where safe, resumed.

## Search

Search is database-backed and index-aware. Large tables are paged/virtualized.

Search and filters never require loading the entire Sample corpus into widget memory.

## Packaging

The primary first distribution is a self-contained AppImage.

The AppImage includes:
- Python runtime;
- application code;
- Qt libraries/plugins required by Koffer;
- Python dependencies;
- required codec/runtime helpers such as FFmpeg when licensing permits;
- application icon and desktop metadata.

Large local ML weights are stored separately and versioned so the application package can update without duplicating model storage.

Later packaging can add Flatpak and conventional distro packages without changing the product architecture.

## Updates

Application updates and model updates are conceptually separate.

Koffer remains usable when update services are unreachable. No update check blocks launch.

## Logging and diagnostics

Logs use structured levels and avoid recording raw audio.

Diagnostics can include:
- version/build;
- platform;
- paths;
- Source status;
- Job errors;
- model versions;
- audio backend;
- recent application logs.

The diagnostics export excludes user audio and should minimize personally identifying path content where practical.

## Testing layers

Required test layers:
- pure domain/unit tests;
- persistence/migration tests;
- filesystem integration tests using temporary directories;
- metadata read/write fixtures;
- analysis contract tests;
- Qt widget/UI tests;
- worker/threading tests;
- render verification;
- package launch smoke test;
- large-library performance fixtures.

## Architectural boundary

UI code expresses interaction state; it does not own filesystem mutation, database SQL, codec commands, or model inference directly.

The separation exists to make safety, cancellation, testability, and Dreadnought Order boundaries explicit.
