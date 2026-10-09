# 11. End-State Product Specification

## Status and authority

This document describes **the product Koffer is being built to become**. It is intentionally written as an end-state specification rather than a list of possibilities.

Koffer is a local-first Linux desktop application for discovering, auditioning, organizing, classifying, preparing, and safely maintaining large audio sample libraries. The application is complete when the behavior described here, the screen catalog, interaction guide, mockups, and acceptance contract agree with one another in the running product.

This specification does not authorize implementation by itself. Development still begins only when the project owner explicitly authorizes it.

## Product promise

Koffer gives a producer one reliable place to answer four questions:

1. **What audio do I have?**
2. **Where is the sound I need?**
3. **What is this sound and how is it classified?**
4. **How do I prepare a safe working copy without damaging the source?**

The product does not make the user reorganize an existing filesystem before it becomes useful. It indexes files where they already live, adds a metadata-first organizational layer, and lets the user progressively move selected material into a managed Koffer library when desired.

## Product character

Koffer is:

- a full Linux desktop application;
- local-first and useful offline;
- fast with very large libraries;
- dense but calm;
- keyboard-friendly;
- explicit about filesystem changes;
- non-destructive by default;
- optimistic about automation but conservative about user data;
- transparent about analysis confidence;
- comfortable beside samplers, DAWs, editors, and file managers without trying to replace them.

Koffer is not a DAW, sequencer, mixer, plug-in host, cloud locker, or sample marketplace.

## Core objects

### Source

A Source is a directory the user has authorized Koffer to index. Sources can live on internal disks, external disks, network mounts, or removable media. Source records remain in Koffer when a drive is offline.

### Sample

A Sample is an indexed audio file. A Sample has a stable Koffer identity, a filesystem identity, factual technical properties, embedded descriptive metadata, Koffer classifications, analysis suggestions, Collection membership, history, and optionally a non-destructive preparation recipe.

### Collection

A Collection is an intentional logical group of Samples. A Sample may belong to many Collections without file duplication.

### Saved Search

A Saved Search is a named live query. It is reevaluated against current library data and automatically includes newly discovered matching Samples.

### Suggestion

A Suggestion is machine- or heuristic-generated metadata with evidence and confidence. It is never equivalent to user-confirmed metadata until accepted.

### Preparation Recipe

A Preparation Recipe is a non-destructive set of edits such as trim, fades, gain, normalization, transpose, stretch, reverse, channel conversion, sample-rate conversion, and output format.

### Job

A Job is background work such as scanning, waveform generation, deeper analysis, similarity indexing, copying, moving, rendering, or backup.

## Main application model

The normal Koffer workspace is a single resizable desktop window with five persistent concepts:

- application/navigation rail;
- current workspace or browser surface;
- optional Inspector;
- global transport/player;
- background status/activity access.

The browser remains the primary surface. Specialized workflows open as focused pages or dialogs without replacing the user's library context unnecessarily.

## End-to-end capabilities

### Discover

The user adds Sources with a native directory picker or drag-and-drop. Koffer immediately registers the Source, begins a background scan, and shows discovered files as they arrive.

### Audit

Koffer records format, duration, channel count, sample rate, bit depth when available, file size, modification state, embedded tags, and artwork. Deeper analysis can continue after the Sample is already browseable.

### Find

Search covers filename, path context, user tags, descriptive metadata, classification, BPM, key, duration, technical properties, Collection membership, review state, and analysis state. Search combines naturally with faceted filters and sorting.

### Audition

Selection and playback are tightly connected. The user can move through a result list with the keyboard and audition without opening a separate page.

### Classify

Koffer distinguishes factual metadata, embedded file metadata, user-confirmed classifications, user tags, and machine suggestions. Suggestions can be accepted, rejected, or edited singly or in batches.

### Organize

Samples can be favourited, added to multiple Collections, surfaced through Saved Searches, and found again through recents and similarity search.

### Maintain metadata

Compatible embedded metadata can be edited in place or written to a copy. Koffer always identifies the write target before touching the file. Album artwork is treated as first-class metadata.

### Prepare

The user opens a Sample Preparation workspace to trim, fade, normalize, transpose, stretch, reverse, convert, and preview changes. Edits are recipes until an explicit render/export.

### Render

Rendering creates a new output by default. The render review names destination, format, technical conversion, metadata carry-over, Collection destination, conflicts, and estimated output.

### Recover

Offline drives, missing files, changed files, failed jobs, and interrupted scans remain understandable. Koffer exposes repair actions rather than silently deleting records.

## Non-negotiable safety invariants

1. Browsing never modifies source audio.
2. Classification never modifies source audio.
3. Adding to a Collection never moves or copies a file.
4. Accepting a Suggestion never writes embedded file metadata unless the user separately requests that write.
5. Move, replace, delete, metadata-write-in-place, and overwrite operations are explicit.
6. Destination conflicts never silently overwrite.
7. A failed batch operation reports the exact items that succeeded, failed, or were skipped.
8. A Source removed from Koffer is not deleted from disk.
9. Rebuildable caches can be deleted without losing Collections, confirmed metadata, Saved Searches, or preparation recipes.
10. External changes to a file invalidate stale derived analysis before Koffer presents it as current.

## Performance experience

The UI is designed for libraries containing tens of thousands of Samples and remains usable at 100,000 indexed items on supported hardware.

The finished product targets:

- responsive scrolling and selection under large result sets;
- search feedback that feels immediate after indexing;
- local playback beginning without a perceptible application stall;
- scan and analysis work that never blocks window interaction;
- progressive population of results while long jobs continue;
- cached waveform and analysis reuse when source identity is unchanged;
- lazy loading of artwork, waveforms, and expensive metadata.

These are product experience targets, not permission to hide expensive work or skip correctness.

## Offline and privacy model

Core use requires no account and no network connection.

Audio, filenames, metadata, embeddings, and analysis remain local by default. Future network features must be separately enabled, visibly networked, and incapable of silently changing the local-first behavior.

## Completion test

Koffer is the intended product when a new user can:

1. install and launch it from the Linux desktop;
2. add a Source;
3. watch scanning progress without a frozen UI;
4. search and audition indexed Samples immediately;
5. inspect and confirm classifications;
6. create a Collection and add Samples without copying files;
7. edit metadata with an explicit write target;
8. prepare a Sample non-destructively;
9. render a new copy;
10. disconnect the Source drive and still understand the library state;
11. reconnect it and recover without rebuilding the user's organization.


## Current V1 correction — editing, intelligence, and polish

The finished V1 is not satisfied by a searchable library with placeholder editing/analysis surfaces.

V1 additionally requires:

- direct-manipulation waveform editing through **Edit Sound**;
- persistent non-destructive edit recipes with A/B preview and Export Copy;
- plainly reachable editing of classifications, user tags, supported embedded metadata, and artwork;
- a working local semantic model installation/runtime path;
- automatic model analysis of newly indexed Samples when enabled;
- existing-library semantic backfill;
- mapped, reviewable Suggestions;
- embedding-based Similar Sounds;
- plain-language primary UI with technical evidence behind advanced disclosures;
- the richer visual and action hierarchy defined in docs 30–35.

The application may degrade gracefully when the local model is absent, but a release candidate is not V1-complete until the model-enabled acceptance scenario passes end-to-end.
