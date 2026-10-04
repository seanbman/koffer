# 15. UI and Product Acceptance Contract

## Why this exists

This document converts the manual and mockups into a practical contract for implementation agents and reviewers.

An agent does not get to declare a screen complete because widgets exist. A screen is complete when behavior, safety, state handling, keyboard flow, background work, and visual hierarchy match the documented end state.

## Required reading order for UI work

Before implementing a user-visible screen, read:

1. `INDEX.md`
2. `11-end-state-product-spec.md`
3. `12-screen-catalog.md`
4. `13-ui-design-system.md`
5. `14-navigation-and-user-flows.md`
6. this file
7. the relevant domain chapter
8. the matching SVG mockup
9. `AGENTS.md`

## Screen implementation rule

Each screen Order must name:
- Screen ID;
- user goal;
- entry and exit paths;
- data dependencies;
- loading state;
- empty state;
- success state;
- recoverable error state;
- irreversible actions;
- keyboard behavior;
- background Jobs;
- matching mockup.

If these are missing, the Order is underspecified.

## Cross-screen acceptance criteria

Every Koffer-owned screen must:

- preserve the dark visual system;
- use the documented names for core domain objects;
- expose keyboard focus;
- work without network access;
- avoid UI-thread blocking work;
- keep destructive operations explicit;
- report errors without losing context;
- preserve selection/search state when returning to the browser where practical;
- remain usable at the minimum supported desktop window size;
- avoid hidden source-file mutations.

## S00 acceptance

- first launch contains no dead-end;
- adding a Source invokes a native picker;
- dropping a directory is supported;
- safety/local-first promise is visible;
- adding the Source enters S01 immediately;
- scan progress is visible.

## S01 acceptance

- Sample table handles large data sets without rendering all rows at once;
- search can be focused from keyboard;
- selection, playback, favourite, Collection, and Inspector actions are reachable without context loss;
- Inspector can collapse;
- table columns can sort;
- multi-select works with standard desktop modifiers;
- analysis and availability states are visually distinct;
- no scan/analysis task blocks the table.

## S02 acceptance

- active filters are always visible;
- filters can be removed individually and cleared as a set;
- numeric ranges validate user input;
- Save Search captures the actual active query;
- result count updates with query state;
- filter semantics are deterministic and documented.

## S03/S04 acceptance

- Collection membership never copies/moves files;
- deleting a Collection explicitly says audio remains;
- Collection detail reuses browser interaction patterns;
- multi-select add/remove works;
- empty Collection explains how to add Samples.

## S05/S06 acceptance

- online/offline state is clear;
- rescans are background Jobs;
- removing a Source does not delete disk content;
- exclusions preview their effect;
- last successful scan and current scan are distinct;
- issue counts lead to actionable detail.

## S07 acceptance

- all Sample data has provenance: factual, embedded, confirmed, suggested, or user tag;
- waveform/playback remain usable;
- file path and availability are visible;
- preparation recipe presence is visible;
- Edit Metadata and Prepare are separate actions.

## S08 acceptance

- no control writes the source as it is adjusted;
- waveform trim state is visible;
- reset restores recipe without touching source;
- source and recipe are identified;
- preview reflects recipe;
- render/export is a separate explicit workflow.

## S09 acceptance

- Koffer-only vs embeddable metadata is unmistakable;
- unsupported embedded fields cannot silently fail;
- artwork add/replace/remove is visible;
- final write target is explicit;
- batch write shows exceptions before execution;
- writes are verified by rereading metadata.

## S10 acceptance

- confidence and evidence are inspectable;
- accept/reject/edit are keyboard accessible;
- accepted Suggestions become confirmed classifications;
- rejection does not erase provenance/history needed for later analysis quality review;
- batch actions show scope.

## S11 acceptance

- seed Sample is always visible;
- result similarity score is visible;
- metadata filtering does not masquerade as similarity ranking;
- offline results are identifiable;
- preview works directly from the list.

## S12/S13 acceptance

- selected operation is stated in plain language;
- copy/move destination is visible;
- conflicts are enumerated before mutation;
- no default silently overwrites;
- batch conflict rules are explicit;
- partial failure produces an itemized report.

## S14 acceptance

- original and output are visibly different;
- recipe summary is included;
- output technical parameters are explicit;
- metadata carry-over is configurable;
- filename conflict policy is shown;
- render is a background Job.

## S15 acceptance

- offline is not treated as deleted;
- moved vs changed vs permission-denied states are distinct;
- repair action never guesses destructively;
- stale analysis is marked invalid when source content changed.

## S16 acceptance

- running/queued/completed/attention states are distinct;
- progress continues while the center is closed;
- cancel semantics are safe and explicit;
- failure detail includes affected items;
- completed Job history is reviewable.

## S17–S19 acceptance

- settings are grouped by user concept rather than implementation module;
- changes that can apply live do so;
- changes requiring restart say so;
- invalid paths/devices do not strand the user;
- destructive safeguards cannot be globally neutralized.

## S20 acceptance

- backup can be created before rebuild;
- every rebuild names preserved data;
- cache clearing cannot remove user organization;
- database integrity check is non-destructive;
- long work runs as a Job.

## S21 acceptance

- version/build data is copyable;
- licenses are accessible;
- diagnostics bundle excludes audio by default;
- paths and model versions are visible;
- diagnostic export clearly states what is included.

## Visual review checklist

A reviewer compares the implementation with the matching SVG and confirms:

- same primary regions;
- same action hierarchy;
- same dominant control;
- no unexplained navigation additions;
- no critical action moved into an obscure menu;
- no user safety information removed for visual simplicity;
- no web/mobile styling substituted for desktop density.

Pixel-perfect reproduction is not required. Information architecture is.

## Definition of screen done

A screen is done only when:
- visual structure exists;
- keyboard path works;
- data state is real, not placeholder-only;
- loading/empty/error/offline states are implemented where applicable;
- destructive behavior has safety review;
- background work is non-blocking;
- tests cover the critical user path;
- documentation and mockup still describe the implementation truth.
