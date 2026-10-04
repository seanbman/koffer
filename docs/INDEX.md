# Koffer Documentation Index

Koffer is a **full-fledged, dark-themed Linux desktop application** for discovering, organizing, searching, previewing, classifying, preparing, and maintaining metadata for audio samples.

The repository is currently in **documentation-first planning**. The product is described optimistically as the finished end state so future agents can implement against a stable contract. No implementation begins until the project owner explicitly authorizes development.

## Canonical reading order

For any future implementation work, read these first:

1. [End-State Product Specification](11-end-state-product-spec.md)
2. [Screen Catalog](12-screen-catalog.md)
3. [UI Design System](13-ui-design-system.md)
4. [Navigation and User Flows](14-navigation-and-user-flows.md)
5. [UI and Product Acceptance Contract](15-ui-acceptance-contract.md)
6. [Development Instructions](AGENTS.md)
7. the relevant domain chapter
8. the matching [UI mockup](mockups/README.md)

## Product principles

- Koffer is an **audio sample library and preparation workbench**, not a DAW.
- Koffer is an installable Linux desktop application, not a web wrapper.
- Existing files remain safe unless the user explicitly chooses to modify, move, replace, or delete them.
- Library organization is metadata-first.
- Embedded metadata and artwork are deliberately editable with explicit write targets.
- Local analysis produces reviewable Suggestions rather than silent truth.
- Core library use works offline.
- Background work never freezes the primary desktop workflow.
- Every major product surface has a documented screen ID and SVG reference.

## Domain manual

### 1. [Product Overview](01-product-overview.md)
Purpose, audience, desktop expectations, core vocabulary, user journey, and non-destructive philosophy.

### 2. [Library and Sources](02-library-and-sources.md)
Sources, scanning, removable storage, rescanning, exclusions, missing files, and Source state.

### 3. [Import and File Management](03-import-and-file-management.md)
Reference, Copy, Move, metadata write targets, conflicts, duplicate awareness, batch operations, and safety.

### 4. [Browsing, Search, and Collections](04-browsing-search-and-collections.md)
Search, filtering, sorting, Saved Searches, Collections, favourites, recents, and similarity.

### 5. [Sample Classification and Metadata](05-classification-and-metadata.md)
Classification dimensions, embedded metadata, artwork, tempo/key, technical facts, and user tags.

### 6. [Intelligent Suggestions](06-intelligent-suggestions.md)
Evidence, local inference, confidence, review, corrections, background analysis, and privacy.

### 7. [Playback and Sample Preparation](07-playback-and-sample-preparation.md)
Preview, waveform, trim, fades, gain, normalization, pitch, stretch, reverse, conversion, and rendering.

### 8. [Safety, Settings, and Library Maintenance](08-safety-settings-and-maintenance.md)
Safeguards, paths, cache, analysis settings, rebuilds, changed files, backup, and local-first behavior.

## Product and design authority

### 9. [UI and Interaction Design](09-ui-and-interaction-design.md)
Desktop shell, browser, Inspector, focused workspaces, playback, background work, safety, density, and keyboard behavior.

### 10. [Technical Product Contract](10-technical-planning-notes.md)
Target runtime, PySide6/Qt, SQLite, workers, audio/metadata boundaries, local analysis, XDG paths, AppImage packaging, diagnostics, and tests.

### 11. [End-State Product Specification](11-end-state-product-spec.md)
Definitive description of what the finished Koffer product is.

### 12. [Screen Catalog](12-screen-catalog.md)
Complete inventory S00–S22 with entry points, purpose, regions, actions, and state expectations.

### 13. [UI Design System](13-ui-design-system.md)
Reference geometry, colors, typography, controls, tables, Inspector, waveforms, focus, accessibility, and motion.

### 14. [Navigation and User Flows](14-navigation-and-user-flows.md)
Screen map and full user journeys for discovery, search, classification, organization, metadata, preparation, recovery, and maintenance.

### 15. [UI and Product Acceptance Contract](15-ui-acceptance-contract.md)
Agent-facing completion rules and screen-by-screen acceptance criteria.

## Development instructions

### [AGENTS.md](AGENTS.md)
Mandatory operating rules for humans and agents. Documentation remains authoritative, the repository remains in planning until explicitly authorized, and future implementation must use the documented product contracts.

## Complete UI mockups

The complete structural mockup set is indexed in [mockups/README.md](mockups/README.md).

The set covers:
- first run;
- library/search;
- Collections;
- Sources;
- Sample detail and preparation;
- metadata;
- Suggestions;
- similarity;
- file operations and conflicts;
- rendering;
- recovery;
- Activity;
- all Settings surfaces;
- maintenance;
- diagnostics;
- navigation map.

## Documentation rules

1. User-visible behavior is documented before implementation.
2. The end-state docs describe what Koffer **is**, not what it might someday be.
3. Product behavior outranks implementation convenience.
4. Mockups and Screen IDs provide a stable cross-reference for Orders, tests, and reviews.
5. Technical architecture must serve the documented product and safety model.
6. Destructive/source-modifying operations remain explicit.
7. Suggestions remain distinguishable from user-confirmed metadata.
8. Any implementation deviation requires a documentation decision, not silent drift.
