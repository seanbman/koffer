# Koffer Documentation Index

Koffer is a dark-themed Linux desktop application for discovering, organizing, searching, previewing, classifying, and preparing audio samples.

This documentation is the living product manual and primary design authority during planning. Koffer is **not yet in development**.

## Product principles
- Koffer is an **audio sample library**, not a DAW.
- Existing files remain safe unless the user explicitly chooses to move or replace them.
- Library organization is metadata-first rather than dependent on one rigid filesystem hierarchy.
- Suggestions made by local analysis or AI are always reviewable suggestions.
- Core library use should remain useful offline.
- The desktop experience is designed primarily for Linux and a dark UI.

## Manual chapters

### 1. [Product Overview](01-product-overview.md)
Purpose, audience, product boundary, core vocabulary, user journey, and non-destructive philosophy.

### 2. [Library and Sources](02-library-and-sources.md)
Adding directories, recursive scanning, removable storage, rescanning, exclusions, missing files, and Source status.

### 3. [Import and File Management](03-import-and-file-management.md)
Reference, Copy, Move, conflicts, duplicate awareness, destination handling, batch operations, and safety.

### 4. [Browsing, Search, and Collections](04-browsing-search-and-collections.md)
Filename and metadata search, filters, sorting, saved searches, Collections, favourites, recents, and similar-sound discovery.

### 5. [Sample Classification and Metadata](05-classification-and-metadata.md)
Sample Type, Instrument/Source, Role, Genre/Style, Character, tempo, key, technical metadata, and user tags.

### 6. [Intelligent Suggestions](06-intelligent-suggestions.md)
Inference from filenames, folder context, metadata, audio properties, local models, confidence, review, corrections, and privacy.

### 7. [Playback and Sample Preparation](07-playback-and-sample-preparation.md)
Preview, waveform navigation, trim, fades, envelope, gain, normalization, pitch, key, stretch, reverse, conversion, and rendering.

### 8. [Safety, Settings, and Library Maintenance](08-safety-settings-and-maintenance.md)
Library location, cache, analysis controls, file-operation safeguards, changed files, backups, and offline behavior.

## Design documentation

### 9. [UI and Interaction Design](09-ui-and-interaction-design.md)
Three-pane desktop layout, sidebar, results browser, Inspector, player, import review, keyboard workflow, and dark-theme principles.

### 10. [Technical Planning Notes](10-technical-planning-notes.md)
Provisional direction: Python, PySide6/Qt, SQLite, local analysis, local ML inference, non-destructive edit recipes, and background indexing.

These are planning choices, not implementation commitments.

## UI mockups
Low-fidelity mockups are stored in [mockups/](mockups/README.md).

- [Library Browser](mockups/library-browser.svg)
- [Sample Inspector / Preparation View](mockups/sample-inspector.svg)
- [Import and Suggestion Review](mockups/import-review.svg)

The mockups show structure and workflow rather than final branding, iconography, spacing, or polish.

## Documentation rules
1. User-visible behavior should be documented here before implementation.
2. When behavior changes, the relevant chapter should be updated.
3. The manual describes user experience, not internal code structure.
4. Technical planning stays separate and must not quietly redefine user behavior.
5. Koffer should not acquire DAW features unless the product boundary is deliberately reconsidered.
6. Destructive file operations must remain explicit.
7. AI or analysis results must remain distinguishable from user-confirmed metadata.
