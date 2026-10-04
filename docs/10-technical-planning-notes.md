# 10. Technical Planning Notes

**Status: planning only. No development has begun.**

This file records the current technical direction so product documentation and future implementation can converge without treating early choices as permanent.

## Application class

Koffer must be delivered as a **full-fledged Linux desktop application**.

The implementation should not depend on a browser being open, a local web server being manually started, or the user launching the program through a terminal as the normal workflow.

The target product should have:
- installable desktop packaging;
- application launcher integration;
- its own process lifecycle;
- local persistent storage;
- desktop-native file interaction;
- background workers for scanning and analysis;
- proper application settings and cache locations;
- offline operation for core features;
- recoverable handling of crashes, unavailable files, and interrupted background work.

## Proposed application stack

### Python
Python is currently favored because Koffer's difficult problems are strongly represented in the Python ecosystem: audio analysis, metadata processing, DSP, machine-learning inference, and filesystem tooling.

### PySide6 / Qt
PySide6 is the current desktop UI candidate.

Reasons:
- native desktop application model;
- mature Linux support;
- strong table/list/tree widgets;
- native windowing and desktop interaction;
- audio-library workflows fit conventional desktop interaction;
- avoids depending on a browser runtime.

This should still be validated with a small prototype before implementation is considered committed.

### SQLite
SQLite is the current candidate for local library state.

Likely data includes Sources, Samples, file identity/state, confirmed metadata, suggestions, Collections, preparation recipes, analysis state, and embeddings or references to embedding storage.

## Desktop integration questions

Planning must eventually resolve:
- XDG config/data/cache locations;
- desktop launcher and icon packaging;
- file/directory picker behavior;
- drag-and-drop;
- MIME/file associations, if useful;
- notifications;
- crash/error logging;
- autostart only if a future background-service use case justifies it;
- Wayland and X11 behavior;
- HiDPI/scaling;
- PipeWire/PulseAudio/ALSA playback compatibility.

## Audio I/O and DSP
The exact library set is not yet selected.

Capabilities to evaluate:
- robust decode support;
- waveform generation;
- duration and channel inspection;
- BPM estimation;
- key estimation;
- pitch shifting;
- time stretching;
- resampling;
- normalization;
- render/export;
- embedded metadata read/write;
- embedded artwork read/write.

FFmpeg may provide broad decode/encode compatibility, while Python audio libraries can provide analysis and transformations.

## Local inference
The inference layer should be modular.

Initial candidate architecture:
1. filename/path heuristics;
2. embedded metadata;
3. deterministic audio features;
4. local semantic model;
5. evidence fusion;
6. suggestion confidence;
7. user review.

PANNs is an early candidate for semantic audio inference and embeddings, but model licensing, packaging size, CPU performance, and output quality must be evaluated before selection.

## Background work
Scanning and inference must not freeze the UI.

Likely background tasks include filesystem scan, waveform generation, metadata extraction, BPM/key analysis, ML inference, and embedding indexing.

Background work should expose progress and failure state to the desktop UI and should be designed so interrupted work can be resumed or safely rebuilt.

## Non-destructive preparation
Edits should be stored as parameters rather than immediately rewriting audio.

Rendering creates a new output file.

## Packaging questions to resolve
Before development:
- target Linux distributions;
- AppImage vs Flatpak vs native packages;
- whether multiple package formats are worth supporting;
- bundled vs system FFmpeg;
- model download vs bundled model;
- GPU acceleration policy;
- cache/storage defaults;
- sandbox/file-permission implications;
- application update strategy.

## Deliberately deferred
No codebase, database schema, class hierarchy, API design, or package layout is defined yet.

The next planning work should continue to refine the user manual, workflows, mockups, desktop behavior, and product boundaries before implementation begins.
