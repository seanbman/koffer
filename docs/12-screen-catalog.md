# 12. Screen Catalog

## Purpose

This catalog is the complete inventory of Koffer-owned product surfaces. Each screen has a stable identifier used by documentation, mockups, tests, and development Orders.

Native Linux file/directory pickers are deliberately not redesigned by Koffer. They are invoked from the appropriate screen.

## Screen inventory

| ID | Screen | Purpose | Primary entry |
|---|---|---|---|
| S00 | Welcome / First Run | Explain Koffer and add the first Source | First launch |
| S01 | Library Browser | Main All Samples workspace | App launch after setup |
| S02 | Search & Filters | Deep query/facet editing and Saved Search creation | Search bar / filter button |
| S03 | Collections | Browse and manage all Collections | Sidebar: Collections |
| S04 | Collection Detail | Browse one Collection and manage membership | Open Collection |
| S05 | Sources | Source health, storage state, scan control | Sidebar: Sources |
| S06 | Source Detail | Inspect one Source, exclusions, jobs, files | Open Source |
| S07 | Sample Detail | Expanded Inspector for one Sample | Open Sample |
| S08 | Sample Preparation | Non-destructive audio preparation | Prepare |
| S09 | Metadata Editor | Edit descriptive/embedded metadata and artwork | Edit Metadata |
| S10 | Suggestions Review | Review machine suggestions at scale | Review badge / sidebar |
| S11 | Similar Sounds | Audio-similarity result workspace | Find Similar |
| S12 | Import / Organize Review | Review Reference, Copy, or Move operations | Organize / drag-in |
| S13 | Conflicts & Duplicates | Resolve name conflicts and likely duplicates | File operation conflict |
| S14 | Render / Export | Define rendered output and destination | Export Copy / Render |
| S15 | Offline / Missing Recovery | Repair unavailable paths and changed files | Offline badge / Source issue |
| S16 | Activity Center | Inspect background jobs and failures | Global activity button |
| S17 | Settings: General | Startup, behavior, paths, notifications | Settings |
| S18 | Settings: Library & Analysis | Scan, cache, inference, similarity policy | Settings |
| S19 | Settings: Audio & Interface | Playback device, preview, UI, keyboard | Settings |
| S20 | Maintenance & Backup | Backup, restore, rebuild, cache maintenance | Settings / Library menu |
| S21 | About & Diagnostics | Version, licenses, paths, diagnostics export | Help > About |
| S22 | Screen Map | Visual navigation map for agents | Documentation only |

## S00 — Welcome / First Run

The first-run screen is sparse and confidence-building. It explains that Koffer indexes existing files without moving them and that core analysis is local.

Primary actions:
- **Add First Source**
- **Open Sample Folder** if a user drops a folder onto the window
- **Learn the Basics**

The screen also shows three promises: files stay where they are, scanning happens in the background, and Koffer works offline.

Success exits directly into S01 while the first scan runs.

## S01 — Library Browser

This is the default workspace and the most important screen in Koffer.

Regions:
- navigation rail;
- search/filter header;
- sortable Sample table;
- right Inspector;
- bottom transport;
- activity indicator.

Primary actions:
- search;
- filter;
- sort;
- play;
- favourite;
- add to Collection;
- open Sample Detail;
- Find Similar;
- Prepare;
- Organize;
- multi-select for batch actions.

The Inspector never steals selection from the table. Playback follows the selected row only when auto-preview is enabled.

## S02 — Search & Filters

This screen expands query construction without forcing the user to learn query syntax.

Filter groups:
- Sample Type;
- Instrument / Source;
- Musical Role;
- Genre / Style;
- Character;
- BPM;
- Key / mode;
- duration;
- format;
- channel layout;
- Source;
- Collection;
- analysis/review state;
- availability;
- date discovered / modified / used.

Filters combine with AND across groups and OR within a multi-select group unless the UI explicitly says otherwise.

The current query can be named and saved as a Saved Search.

## S03 — Collections

Collections are shown as compact cards/list rows with name, count, optional artwork/color, last modified time, and a short description.

Actions:
- New Collection;
- rename;
- duplicate definition without duplicating audio;
- delete Collection;
- export membership list;
- pin favourite Collections.

Deleting a Collection never deletes audio.

## S04 — Collection Detail

This is a browser scoped to one Collection. It reuses the S01 result table and Inspector, adds Collection title/description controls, and exposes membership actions.

The page supports manual ordering only when the Collection is explicitly switched from automatic sort to manual order.

## S05 — Sources

The Sources page is a health dashboard.

Each Source shows:
- display name;
- path;
- online/offline;
- enabled/disabled;
- indexed file count;
- pending analysis;
- last successful scan;
- current job;
- issue count.

Primary actions:
- Add Source;
- Rescan;
- Pause;
- Disable;
- Open in file manager;
- Remove from Koffer.

## S06 — Source Detail

Source Detail shows status, path, storage identity, inclusion/exclusion rules, last scan summary, current and recent jobs, detected issues, and files discovered under the Source.

Exclusion rules are previewable before they remove files from the active index.

## S07 — Sample Detail

This is the expanded version of the Inspector.

Sections:
- artwork and identity;
- waveform and transport;
- classifications;
- technical facts;
- descriptive metadata;
- embedded metadata state;
- Suggestions with evidence/confidence;
- Collections;
- file path and availability;
- preparation recipe summary;
- history.

Primary actions:
- Prepare;
- Edit Metadata;
- Find Similar;
- Add to Collection;
- Organize;
- Reveal in Files.

## S08 — Sample Preparation

Preparation is a focused single-Sample workspace, not a DAW.

The waveform dominates the page. Controls are grouped into:
- trim;
- fades/envelope;
- gain/normalization;
- pitch;
- time stretch;
- reverse;
- channel conversion;
- sample rate;
- bit depth;
- output format.

The original file is always identified. The current recipe is visibly marked **Non-destructive**.

Primary actions:
- Reset Recipe;
- Save Recipe;
- Export Copy;
- Render to Managed Library;
- Render to Collection.

## S09 — Metadata Editor

The Metadata Editor separates Koffer-only metadata from embeddable file metadata.

Tabs/sections:
- Descriptive;
- Musical;
- Artwork;
- Koffer Tags;
- Write Target.

The final write step must identify **Update Original** or **Write to Copy**. Unsupported embedded fields are disabled with a format explanation rather than silently discarded.

## S10 — Suggestions Review

This page is an inbox for unreviewed analysis.

It supports:
- grouping by confidence;
- grouping by suggestion type;
- quick accept/reject;
- edit-before-accept;
- batch acceptance;
- evidence inspection;
- keyboard review.

The user can filter to low-confidence or contradictory suggestions to focus attention where it matters.

## S11 — Similar Sounds

Similar Sounds keeps the seed Sample pinned at the top and ranks results by audio similarity.

Metadata filters can further narrow the results, but they do not replace the similarity score. Each row shows similarity, key metadata, and availability.

## S12 — Import / Organize Review

This screen appears before Reference, Copy, or Move operations.

It shows:
- selected Samples;
- chosen operation;
- source paths;
- destination when applicable;
- filename conflicts;
- duplicate warnings;
- metadata-write behavior;
- post-operation Collection assignment.

No filesystem mutation happens until the user executes the reviewed plan.

## S13 — Conflicts & Duplicates

This screen resolves ambiguous file operations.

Per-item options:
- Keep Both;
- Skip;
- Choose Destination;
- Replace;
- Compare;
- Use Existing Indexed Sample.

Batch rules can be applied only after the user chooses them explicitly.

## S14 — Render / Export

The Render / Export screen summarizes the non-destructive recipe and defines the output.

Controls:
- destination;
- filename;
- output format;
- sample rate;
- bit depth;
- channel mode;
- metadata/artwork carry-over;
- Collection assignment;
- conflict policy.

The screen displays the original and output as separate files.

## S15 — Offline / Missing Recovery

This page distinguishes:
- Source offline;
- file missing;
- file moved;
- file changed;
- permission denied;
- mount identity changed.

Recovery actions include reconnect, locate file, locate Source, rescan, accept changed file, remove stale entry, or leave unresolved.

## S16 — Activity Center

Jobs are grouped as Running, Queued, Completed, and Needs Attention.

Each Job reports:
- type;
- Source/Sample scope;
- progress;
- started time;
- current stage;
- items succeeded/failed/skipped;
- cancel/pause where safe;
- retry/reveal details.

Closing the Activity Center does not cancel work.

## S17 — Settings: General

Contains:
- launch behavior;
- restore last workspace;
- notifications;
- default managed library path;
- database path;
- temporary render path;
- update policy;
- confirmation preferences for non-destructive actions.

Destructive confirmation safeguards cannot all be globally disabled.

## S18 — Settings: Library & Analysis

Contains:
- recursive scanning;
- hidden-folder policy;
- automatic analysis;
- analysis concurrency;
- idle-only deep analysis;
- waveform cache;
- similarity indexing;
- local model enable/disable;
- model storage;
- cache limits;
- exclusions defaults.

## S19 — Settings: Audio & Interface

Contains:
- output device;
- preview gain;
- auto-preview;
- loop preview default;
- waveform behavior;
- UI density;
- Inspector default;
- theme;
- keyboard shortcut editor;
- reduced motion.

## S20 — Maintenance & Backup

Contains:
- Back Up Library;
- Restore Library;
- Rebuild Filesystem Index;
- Rebuild Waveforms;
- Rebuild Analysis;
- Rebuild Similarity Index;
- Clear Rebuildable Cache;
- verify database integrity;
- show storage usage.

Every maintenance action states what is preserved and what is rebuilt.

## S21 — About & Diagnostics

Contains:
- Koffer version;
- build identifier;
- Python/Qt/runtime versions;
- package format;
- license and third-party notices;
- XDG data/config/cache locations;
- model versions;
- audio backend;
- Create Diagnostics Bundle.

The diagnostics bundle excludes audio content by default.

## Dialogs and transient states

The following are not separate top-level pages, but their behavior is part of the product contract:

- new/rename Collection;
- destructive confirmation;
- native Source directory picker;
- Collection chooser;
- artwork picker;
- keyboard shortcut conflict resolver;
- error detail sheet;
- job cancellation confirmation when partial side effects are possible.

## Mockup mapping

Each screen above has a matching SVG in `docs/mockups/`. The SVG establishes layout, hierarchy, labels, and action placement. The written catalog governs behavior when a detail cannot be expressed visually.
