# 16. System Architecture

## Architectural objective

Koffer is a single-user, local-first Linux desktop application with explicit separation between UI, durable state, filesystem mutation, audio operations, analysis, and background orchestration.

The architecture is deliberately boring. It optimizes for safety, testability, recoverability, and bounded Dreadnought Orders.

## Runtime baseline

- Python: 3.12 baseline.
- UI: PySide6 / Qt 6.
- Package metadata and dependency lock: `pyproject.toml` + `uv.lock`.
- Durable database: SQLite.
- Desktop config: XDG locations via `platformdirs`.
- Metadata: Mutagen.
- Audio decode/render/inspection: FFmpeg / ffprobe capability layer.
- Playback: Qt Multimedia, isolated behind a PlaybackService.
- Numerical analysis: NumPy + librosa where deterministic DSP is needed.
- Local semantic backend: Koffer-owned PANNs Cnn14 (32 kHz) provider adapter based on the audited official MIT implementation; model weights remain outside Git.
- Similarity index: hnswlib over versioned local embeddings.
- Tests: pytest + pytest-qt.
- Static quality: Ruff + mypy.
- Packaging: PyInstaller onedir staged into AppDir, then AppImage tooling.

Dependency and licensing policy is authoritative in `23-dependencies-models-and-licensing.md`.

## Target repository layout

~~~text
koffer/
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── Makefile
├── .gitignore
├── .github/
│   └── workflows/
├── packaging/
│   ├── koffer.desktop
│   ├── AppRun
│   ├── icons/
│   └── appimage/
├── scripts/
│   ├── build_appimage.sh
│   ├── smoke_appimage.sh
│   ├── generate_test_audio.py
│   └── verify_licenses.py
├── src/
│   └── koffer/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── config/
│       ├── domain/
│       ├── persistence/
│       │   └── migrations/
│       ├── repositories/
│       ├── services/
│       ├── jobs/
│       ├── filesystem/
│       ├── metadata/
│       ├── audio/
│       ├── analysis/
│       ├── similarity/
│       ├── ui/
│       │   ├── shell/
│       │   ├── screens/
│       │   ├── widgets/
│       │   ├── models/
│       │   └── resources/
│       └── diagnostics/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── ui/
│   ├── e2e/
│   ├── fixtures/
│   └── performance/
└── docs/
~~~

Do not create a giant `utils.py`, god service, or monolithic MainWindow.

## Layer responsibilities

### domain

Pure application concepts and rules:
- Source;
- Sample;
- Collection;
- Suggestion;
- classification values;
- preparation recipe;
- file operation plan;
- Job state;
- error/result types.

Domain code must be testable without Qt, SQLite, FFmpeg, or filesystem side effects.

### persistence

Owns:
- SQLite connection factory;
- migrations;
- transactions;
- FTS maintenance;
- database backup/restore primitives.

UI code never executes SQL.

### repositories

Typed persistence interfaces for:
- Sources;
- Samples;
- Collections;
- metadata/classifications;
- Suggestions;
- recipes;
- Jobs;
- analysis provenance.

Repositories accept a database context/connection owned by the calling execution context.

### services

Use-case orchestration:
- LibraryService;
- SourceService;
- SearchService;
- CollectionService;
- FileOperationService;
- MetadataService;
- PreparationService;
- AnalysisService;
- SimilarityService;
- MaintenanceService.

Services coordinate domain and repositories. Long-running service calls are invoked as Jobs, not synchronously from UI handlers.

### jobs

Owns:
- JobScheduler;
- cancellation token;
- bounded worker pools;
- progress events;
- Job persistence;
- retry policy;
- Job item results.

### filesystem

Owns normalized safe file operations, path validation, hashing, copy/move staging, conflict detection, and rollback/compensation where practical.

### metadata

Owns embedded tag capability inspection, read/write, artwork, format limitations, and post-write verification.

### audio

Owns:
- technical probing;
- decode helpers;
- waveform generation;
- playback adapter;
- preparation preview;
- render pipeline.

### analysis

Owns:
- filename/path heuristics;
- BPM/key estimation;
- semantic provider interface;
- Suggestion evidence fusion;
- versioning/provenance.

### similarity

Owns embedding persistence/cache and HNSW index lifecycle.

### ui

Qt only:
- screen composition;
- view models/table models;
- interaction state;
- commands to services/jobs;
- progress/error presentation.

UI must not become the source of business truth.

## Application composition

`app.py` constructs one ApplicationContext containing:
- Settings;
- Database;
- repository factory;
- services;
- JobScheduler;
- PlaybackService;
- DiagnosticsService;
- MainWindow.

The composition root is the only location allowed to wire concrete implementations together.

## Dependency direction

~~~text
UI ───────► Services ───────► Domain
             │   │
             │   ├──────────► Repositories ─► Persistence
             │   ├──────────► Filesystem
             │   ├──────────► Metadata
             │   ├──────────► Audio
             │   └──────────► Analysis / Similarity

Jobs ──────► Services
~~~

Lower layers do not import UI.

## Process model

V1 is one desktop process.

CPU-heavy analysis may use a process pool only when measurement proves the GIL or native workload harms responsiveness. Default background work uses Qt/standard worker threads with bounded concurrency.

No local HTTP server is required.

## Error model

Internal operations return typed application errors with:
- stable code;
- user-safe summary;
- technical detail;
- affected entity/path;
- side-effect status;
- retryability.

UI maps typed errors to actionable messages.

Expected error families:
- validation;
- permission;
- path unavailable;
- conflict;
- unsupported format;
- decode;
- metadata write;
- render;
- database;
- model unavailable;
- analysis;
- cancelled;
- internal unexpected.

## Configuration ownership

Use:
- XDG config for application preferences;
- SQLite for library-specific durable state;
- XDG cache for rebuildable waveforms, embeddings, model cache, temp renders;
- XDG data for database, logs needed for support, durable application-managed data.

Never store user configuration beside the executable.

## Logging

Use Python structured logging with rotating local files.

Each Job and Order-relevant operation should carry correlation fields:
- job_id;
- source_id;
- sample_id where applicable;
- operation;
- error_code.

Do not log raw audio bytes.

## Architecture invariants

1. Main Qt thread never performs unbounded disk scan, render, model inference, or bulk metadata work.
2. Worker code never manipulates Qt widgets directly.
3. A SQLite connection belongs to one execution thread/context.
4. Filesystem mutation passes through FileOperationService.
5. Embedded metadata mutation passes through MetadataService.
6. Audio source mutation is not part of preparation preview.
7. Derived caches can be destroyed and rebuilt without losing user-authored organization.
8. The application remains useful if semantic model resources are absent.
9. UI screens depend on documented service contracts, not ad hoc SQL/filesystem access.
