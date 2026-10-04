# Koffer Documentation Index

Koffer is a **full-fledged, dark-themed Linux desktop application** for discovering, organizing, searching, previewing, classifying, preparing, and maintaining audio sample libraries.

**Development is authorized through Dreadnought.** This documentation is the complete product and engineering handoff. The canonical branch for accepted development work is `dev`; Cursor Project Arms implement bounded Orders in scratch and Dreadnought verifies/promotes them.

## Start here

1. [End-to-End Implementation Instructions](INSTRUCTIONS.md)
2. [Development Instructions](AGENTS.md)
3. [End-State Product Specification](11-end-state-product-spec.md)
4. [Screen Catalog](12-screen-catalog.md)
5. [UI Design System](13-ui-design-system.md)
6. [Navigation and User Flows](14-navigation-and-user-flows.md)
7. [UI and Product Acceptance Contract](15-ui-acceptance-contract.md)
8. [System Architecture](16-system-architecture.md)
9. [Data Model and Database Contract](17-data-model-and-database.md)
10. [Jobs, Concurrency, and State](18-jobs-concurrency-and-state.md)
11. [Audio, Metadata, and Analysis Pipeline](19-audio-metadata-analysis-pipeline.md)
12. [Testing, Fixtures, and Quality Gates](20-testing-fixtures-and-quality.md)
13. [Packaging, CI, and Release](21-packaging-ci-and-release.md)
14. [Implementation Roadmap](22-implementation-roadmap.md)
15. [Dependencies, Models, and Licensing](23-dependencies-models-and-licensing.md)
16. [Operations, Diagnostics, and Recovery](24-operations-diagnostics-and-recovery.md)
17. [Dreadnought Order Template](25-order-template.md)
18. [Command Reference](26-command-reference.md)
19. [Service and Interface Contracts](27-service-interfaces.md)
20. [Product Defaults, Menus, and Shortcuts](28-defaults-menus-shortcuts.md)

Then read the relevant domain manual chapter and matching SVG mockup for the Order.

## Domain manual

### 1. [Product Overview](01-product-overview.md)
Product identity, audience, desktop expectations, vocabulary, journey, and non-destructive philosophy.

### 2. [Library and Sources](02-library-and-sources.md)
Source authorization, scanning, exclusions, removable storage, rescans, missing files, and Source status.

### 3. [Import and File Management](03-import-and-file-management.md)
Reference, Copy, Move, explicit metadata targets, conflicts, duplicates, managed storage, and batch safety.

### 4. [Browsing, Search, and Collections](04-browsing-search-and-collections.md)
Search, facets, sorting, Saved Searches, Collections, favourites, recents, and Similar Sounds.

### 5. [Sample Classification and Metadata](05-classification-and-metadata.md)
Classification dimensions, embedded/descriptive metadata, artwork, technical facts, BPM/key, and user tags.

### 6. [Intelligent Suggestions](06-intelligent-suggestions.md)
Evidence, deterministic/local semantic inference, confidence, review, provenance, background analysis, and privacy.

### 7. [Playback and Sample Preparation](07-playback-and-sample-preparation.md)
Preview, waveform, trim, fades, gain, normalization, pitch, stretch, reverse, conversion, and render.

### 8. [Safety, Settings, and Library Maintenance](08-safety-settings-and-maintenance.md)
Source safety, XDG/library paths, cache, analysis settings, rebuilds, changed files, backup, and networking policy.

## Product/UI authority

### 9. [UI and Interaction Design](09-ui-and-interaction-design.md)
Desktop shell, browser, Inspector, focused workspaces, playback, Jobs, safety, density, and keyboard behavior.

### 10. [Technical Product Contract](10-technical-planning-notes.md)
Concise technical contract. Chapters 16–28 provide the detailed engineering specification.

### 11. [End-State Product Specification](11-end-state-product-spec.md)
Definitive description of what the finished product is and the non-negotiable safety/performance/completion rules.

### 12. [Screen Catalog](12-screen-catalog.md)
S00–S22 screen inventory and behavior.

### 13. [UI Design System](13-ui-design-system.md)
Geometry, color tokens, typography, controls, tables, waveforms, focus, accessibility, and motion.

### 14. [Navigation and User Flows](14-navigation-and-user-flows.md)
Critical flows A–J and screen navigation.

### 15. [UI and Product Acceptance Contract](15-ui-acceptance-contract.md)
Screen-by-screen implementation acceptance.

## Engineering authority

### 16. [System Architecture](16-system-architecture.md)
Repository layout, module boundaries, dependency direction, composition, error/config/logging model.

### 17. [Data Model and Database Contract](17-data-model-and-database.md)
SQLite schema, FTS, migrations, identity, cache, backup, and invariants.

### 18. [Jobs, Concurrency, and State](18-jobs-concurrency-and-state.md)
Main-thread rule, scheduler lanes, connection ownership, file mutation transactions, cancellation, retry, crash recovery.

### 19. [Audio, Metadata, and Analysis Pipeline](19-audio-metadata-analysis-pipeline.md)
Supported formats, playback, waveform, recipes, FFmpeg render, Mutagen, deterministic/PANNs analysis, evidence, similarity.

### 20. [Testing, Fixtures, and Quality Gates](20-testing-fixtures-and-quality.md)
Unit/integration/UI/E2E/package tests, fixture generation, coverage, performance, safety regressions, defect severity.

### 21. [Packaging, CI, and Release](21-packaging-ci-and-release.md)
Self-contained AppImage, PyInstaller/AppDir, FFmpeg/model policy, Actions workflows, versioning, release checklist.

### 22. [Implementation Roadmap](22-implementation-roadmap.md)
Phases 0–14, their deliverables, screens, and gates.

### 23. [Dependencies, Models, and Licensing](23-dependencies-models-and-licensing.md)
Locked V1 stack, uv policy, PANNs/model artifact rules, FFmpeg review, fixtures/assets notices.

### 24. [Operations, Diagnostics, and Recovery](24-operations-diagnostics-and-recovery.md)
Startup/shutdown, logs, diagnostics, backup/restore, Source recovery, interrupted Job/temp recovery, safe mode.

### 25. [Dreadnought Order Template](25-order-template.md)
Required format and verification evidence for every Cursor Project Arm Order.

### 26. [Command Reference](26-command-reference.md)
Required local/CI run, QA, tests, package, model, and database commands.

### 27. [Service and Interface Contracts](27-service-interfaces.md)
Stable service operations and UI/service boundaries.

### 28. [Product Defaults, Menus, and Shortcuts](28-defaults-menus-shortcuts.md)
Default settings, columns, sort, confirmations, menu tree, keyboard shortcuts, render/window behavior.

## Complete UI mockups

[mockups/README.md](mockups/README.md) indexes the full S00–S22 SVG set.

## Authority and conflict resolution

If two documents appear to disagree:
1. `INSTRUCTIONS.md` governs execution/control-plane behavior.
2. Product/end-state and acceptance docs govern user-visible behavior and safety.
3. Engineering chapters 16–28 govern implementation mechanics.
4. A domain chapter governs feature-specific details.
5. Mockups govern layout/hierarchy, not hidden behavior.

Do not silently rewrite a higher-authority requirement to match existing code.

## Documentation maintenance rule

Implementation agents update docs only when implementation reveals a legitimate missing detail or a deliberate product/architecture change has been made. Documentation is not rewritten to excuse incomplete implementation.
