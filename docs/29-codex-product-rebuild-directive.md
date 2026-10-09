# 29. Codex Product Rebuild Directive

## Purpose

This document exists because the previous implementation proved that a screen can be “implemented” while still being unpleasant or useless. Koffer must now be evaluated as a product used by a musician, not as a collection of Qt widgets.

This is the current remediation directive. Codex must use it to audit and rebuild the existing `dev` implementation. Existing code is not presumed correct merely because tests pass.

## Product outcome

A user with a folder full of badly named audio Samples should be able to:

1. add the folder as a Source;
2. immediately browse and audition Samples;
3. see analysis start in the background;
4. have local ML and deterministic analysis propose useful classifications;
5. understand suggestions without reading model internals;
6. accept/edit/reject those suggestions;
7. open any Sample and directly manipulate its waveform non-destructively;
8. trim, fade, gain, normalize, reverse, transpose, stretch, loop, and convert it;
9. edit library classifications and supported embedded metadata;
10. add or replace artwork where supported;
11. save a non-destructive editing recipe;
12. render/export a new file when desired;
13. organize Samples into Collections or filesystem destinations;
14. find sonically similar Samples;
15. recover safely when storage goes offline or files move;
16. do all of this in a coherent, colorful, professional Linux desktop UI.

If those tasks are not obvious and pleasant, the product is not complete.

## P0 remediation items

The following are release-blocking:

### P0-1 — Sample editing is genuinely usable

“Edit Sound” must open the waveform workbench described in `31-sample-workbench-waveform-editor.md`.

The workbench must provide direct manipulation and audible preview. Numeric spin boxes alone do not satisfy this requirement.

### P0-2 — Sample information is genuinely editable

The user must be able to edit:

- Sample Type;
- Instrument / Source;
- Musical Role;
- Genre / Style;
- Character;
- user tags;
- supported embedded fields;
- artwork where supported.

The UI distinguishes Koffer library metadata from embedded file metadata. The user should not need to infer which is which from provenance jargon.

### P0-3 — Local ML actually runs

The semantic provider must be installable/configurable and executable on local audio. When installed and enabled:

- new Samples queue semantic analysis automatically;
- an existing library can be backfilled;
- Suggestions include mapped Koffer taxonomy labels;
- evidence includes semantic results;
- embeddings are generated;
- Similar Sounds works;
- Activity reports progress/failure;
- model state is visible in Settings.

A class, interface, manifest, or disabled placeholder does not count.

### P0-4 — UI hierarchy is rebuilt

No screen may use an arbitrary line of buttons simply because actions exist.

Every screen gets:

- a clear title/context zone;
- one obvious primary action where applicable;
- secondary actions grouped together;
- destructive actions separated visually;
- content grouped into meaningful cards/panes;
- consistent spacing;
- consistent color semantics;
- empty/loading/error states.

### P0-5 — Debug-looking information is removed from primary surfaces

Do not show raw:

- JSON evidence;
- provider payloads;
- hashes;
- internal enum strings;
- object IDs;
- model implementation names;
- SQLite concepts;
- raw filesystem fingerprints;

in the normal user path.

Translate them into user-facing content. Advanced technical detail lives behind “Analysis Details”, “File Details”, or Diagnostics.

## P1 remediation items

P1 items must be resolved before release candidate:

- richer color treatment across all screens;
- consistent iconography;
- polished hover/focus/selected/disabled states;
- contextual tooltips;
- plain-language analysis state;
- obvious install/manage-model flow;
- obvious backfill analysis flow;
- inline classification chips;
- editable tag chips;
- collection membership editing;
- waveform zoom and keyboard controls;
- A/B before/after preview;
- undo/reset recipe controls;
- explicit dirty state;
- output/render summary;
- visual QA at target sizes;
- AppImage validation with FFmpeg/model strategy.

## Product language corrections

Use these user-facing terms:

| Avoid | Use |
|---|---|
| Prepare | Edit Sound |
| Preparation Recipe | Edit Recipe, or Recipe in secondary/advanced copy |
| Technical provenance | File Details |
| Suggested provenance | Suggestions |
| Confirmed provenance | Classification |
| Evidence JSON | Analysis Details |
| Semantic provider unavailable | Local AI model not installed / unavailable |
| Execute Plan | Apply / Copy / Move / Export, whichever the user is actually doing |
| Sample Detail foundations | Sample |
| Analysis run | Analysis, except in Activity/diagnostics |

Engineering docs may retain precise internal terminology.

## Required Codex campaign order

Codex must execute in this order unless a dependency forces a small local inversion:

1. visual token and shell cleanup;
2. Sample Detail information hierarchy;
3. Sample Workbench waveform editor;
4. classification/tag editor;
5. embedded metadata editor simplification;
6. local ML installation/runtime;
7. automatic analysis scheduling;
8. Suggestions UX;
9. Similar Sounds UX;
10. browser/Inspector visual integration;
11. remaining S00–S21 visual pass;
12. packaging and clean AppImage smoke;
13. full acceptance matrix.

Do not jump to cosmetic polishing while P0 editing/ML functionality is absent.

## Audit method

For each screen, Codex records:

- what the screen is for;
- current implementation path;
- current service dependencies;
- actions that are real;
- actions that are dead or misleading;
- raw/debug content visible to user;
- layout defects;
- missing states;
- missing keyboard path;
- missing tests;
- remediation change;
- proof.

Do not preserve a bad layout merely because replacing it touches more code.

## Product-complete rule

A green QA run proves the implementation is internally consistent. It does not prove the product is useful.

Koffer is product-complete only when a fresh user can follow `33-user-manual.md` without encountering an absent workflow, engineering-only terminology, or a control that does not produce the documented result.
