# 22. Implementation Roadmap

## Purpose

This is the canonical order of construction. Dreadnought decomposes each phase into bounded Orders and continues automatically through later phases after phase gates pass.

Do not implement screens as static mockups before the services/data they depend on exist unless the roadmap explicitly calls for shell work.

## Phase 0 — Bootstrap and guardrails

Deliver:
- pyproject + uv lock;
- src layout;
- Makefile;
- application entry point;
- logging/config paths;
- empty PySide6 window;
- test harness;
- Ruff/mypy/pytest;
- initial GitHub Actions QA;
- packaging skeleton;
- Dreadnought/Grapher campaign initialized.

Gate:
- app launches;
- tests/quality commands run;
- no product feature placeholders claimed complete.

## Phase 1 — Domain and persistence

Deliver:
- domain types/enums;
- database connection factory;
- migrations framework;
- migration 001 with core schema;
- repositories;
- FTS5 search projection;
- backup primitive.

Gate:
- migration tests;
- CRUD repository tests;
- thread-local connection test;
- backup restore roundtrip.

## Phase 2 — Sources and scanning

Screens: S00, S05, S06 foundations.

Deliver:
- Source add/remove/disable;
- native picker/drop;
- exclusions;
- recursive scanner;
- supported extension detection;
- technical probe queue;
- offline Source handling;
- Activity Job representation.

Gate:
- first Source flow works on generated fixture tree;
- offline scan does not delete records;
- UI stays responsive.

## Phase 3 — Browser, search, Inspector, playback

Screens: S01, S02, Inspector portion of S07.

Deliver:
- paged Sample table;
- search/FTS;
- structured filters/sort;
- saved searches;
- PlaybackService;
- waveform cache;
- Inspector;
- favourites/recents;
- column persistence.

Gate:
- flow B works;
- 100k synthetic table/query baseline measured;
- playback works for required fixtures;
- scan can continue while browsing.

## Phase 4 — Collections

Screens: S03, S04.

Deliver:
- Collection CRUD;
- membership/batch membership;
- collection browser;
- no filesystem side effects;
- drag Sample -> Collection.

Gate:
- flow D;
- deleting Collection leaves files/Samples intact.

## Phase 5 — Sample detail and metadata read

Screen: S07.

Deliver:
- expanded Sample detail;
- technical metadata;
- embedded metadata snapshot;
- classifications/tags;
- file availability/path;
- history view.

Gate:
- provenance categories visually distinct;
- malformed/unsupported files handled.

## Phase 6 — Job system and Activity hardening

Screen: S16.

Deliver:
- scheduler lanes;
- persistent Jobs/job_items;
- cancellation;
- interrupted Job recovery;
- progress throttling;
- Activity Center.

Gate:
- concurrency regression suite;
- app restart with interrupted synthetic job.

## Phase 7 — File organization and conflict resolution

Screens: S12, S13.

Deliver:
- Reference semantics;
- safe Copy;
- safe same/cross-filesystem Move;
- duplicate awareness;
- conflicts;
- operation review;
- per-item results/audit.

Gate:
- flow E;
- original hash safety tests;
- partial failure truthful.

## Phase 8 — Metadata editing

Screen: S09.

Deliver:
- normalized format capability;
- editor;
- artwork;
- Update Original;
- Write to Copy;
- batch exception review;
- reread verification.

Gate:
- flow F;
- format fixture matrix;
- unsupported fields cannot silently fail.

## Phase 9 — Sample preparation and render

Screens: S08, S14.

Deliver:
- preparation recipe;
- waveform trim/zoom;
- gain/fades/reverse;
- pitch/time stretch;
- channel/rate/bit-depth/output controls;
- preview;
- FFmpeg render;
- render verification;
- output provenance.

Gate:
- flow G;
- source hashes unchanged;
- render fixture matrix.

## Phase 10 — Deterministic analysis and Suggestions

Screen: S10.

Deliver:
- path/filename heuristics;
- BPM/key estimation;
- evidence model;
- Suggestion storage;
- accept/reject/edit;
- batch review;
- no overwrite of confirmed metadata.

Gate:
- flow C without semantic model;
- reanalysis safety.

## Phase 11 — Semantic model and similarity

Screen: S11 plus Settings model controls.

Deliver:
- model manifest/downloader;
- checksum verification;
- local PANNs provider;
- mapping;
- semantic Suggestions;
- embeddings;
- hnswlib index;
- Find Similar;
- rebuild lifecycle.

Gate:
- model-disabled behavior works;
- model-enabled smoke works;
- flow H;
- model version change rebuilds derived data only.

## Phase 12 — Recovery, settings, maintenance, diagnostics

Screens: S15, S17–S21.

Deliver:
- missing/offline/changed repair;
- Settings pages;
- cache/model controls;
- backup/restore;
- index/analysis rebuilds;
- database verify;
- About;
- diagnostics bundle.

Gate:
- flows I/J;
- diagnostics contains no audio;
- backup/restore preserves user state.

## Phase 13 — UX completion and performance

All screens.

Deliver:
- keyboard shortcuts;
- focus/a11y;
- drag/drop coverage;
- context menus;
- persisted geometry/panes;
- narrow-window collapse behavior;
- HiDPI;
- error/empty/loading states;
- performance tuning from measurements.

Gate:
- S00–S21 acceptance contract green;
- 100k benchmark targets met or documented with corrected implementation.

## Phase 14 — Packaging and release

Deliver:
- final PyInstaller bundle;
- AppDir;
- AppImage;
- icons/desktop integration;
- license manifest/SBOM;
- release CI;
- clean-environment smoke;
- RC defect burn-down;
- final docs reconciliation.

Gate:
- `21-packaging-ci-and-release.md` checklist complete;
- zero P0/P1;
- release candidate accepted by automated/manual evidence.

## Cross-phase rules

At the end of every phase:
1. run full tests plus phase-specific gates;
2. update docs only if implementation discovered a legitimate product detail;
3. do not weaken requirements to make gate green;
4. record Grapher evidence;
5. report token consumption;
6. continue to next phase automatically unless a hard block exists.

## Scope discipline

Later-phase features may create interfaces/stubs earlier when required for architecture, but no stub counts as product completion.

Do not prematurely implement Phase 11 model complexity before the library/search/file safety foundation is green.


## Current remediation campaign before release progression

The existing implementation reached broad automated coverage before meeting product usability. Before treating phases as complete, execute the remediation contract in docs 29–35.

Required remediation sequence:

1. visual token/shell/action-hierarchy cleanup;
2. S07 Sample hierarchy and plain-language classification/Suggestions;
3. S08 Edit Sound direct waveform workbench;
4. S09 classification/tag/embedded-metadata editing cleanup;
5. real local semantic model install/runtime;
6. automatic semantic scheduling + existing-library backfill;
7. S10 friendly Suggestions review;
8. S11 real embedding-backed Similar Sounds;
9. S00–S21 visual/state pass;
10. packaging with FFmpeg/model setup validation;
11. docs 35 acceptance scenarios.

Phase labels are not proof. Re-run the gates against actual current behavior.
