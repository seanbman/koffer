# 35. Definition of Done and Acceptance Matrix

## Why this document exists

Koffer previously reached green CI while remaining unsatisfactory as a product.

Therefore “tests pass” is no longer synonymous with “done”.

This document adds product acceptance gates on top of automated QA.

## Completion levels

### Level 0 — Exists

A class/widget/service exists.

This has no product-completion value by itself.

### Level 1 — Wired

The action reaches real service/domain behavior.

Still not sufficient.

### Level 2 — Tested

Critical behavior has deterministic automated tests.

Still not sufficient for user-facing completion.

### Level 3 — Usable

A user can discover and complete the workflow without implementation knowledge.

### Level 4 — Polished

Visual hierarchy, copy, states, keyboard behavior, error handling, and performance satisfy the product contract.

A V1 user-facing feature requires Level 4.

## Mandatory global gates

### G1 — Source safety

Pass if:

- Reference does not copy/move;
- Copy preserves source;
- Move is explicit;
- no silent overwrite;
- metadata write target explicit;
- edit recipe does not mutate source;
- source hash regression tests pass.

### G2 — Sample editability

Pass if:

- Edit Sound reachable from Library/Sample;
- direct waveform trim works;
- fade handles work;
- zoom/seek works;
- gain/normalize works;
- pitch works;
- stretch works;
- reverse works;
- A/B works;
- Save Recipe persists;
- Export Copy produces edited file;
- source remains byte-identical.

### G3 — Classification editability

Pass if:

- all five classification families editable;
- tags editable;
- confirmed values appear in Library/Sample;
- edits persist/reload;
- machine Suggestions never overwrite confirmed values.

### G4 — Embedded metadata

Pass if:

- supported fields editable;
- unsupported fields explained;
- artwork add/replace/remove;
- Update Original explicit;
- Write to Copy explicit;
- reread verification after writes.

### G5 — Local ML

Pass only with model-enabled evidence:

- install;
- checksum verify;
- enable;
- automatic new-Sample analysis;
- existing-library backfill;
- mapped Suggestions;
- evidence;
- embeddings;
- Similar Sounds;
- cancellation/failure;
- privacy/no audio upload.

### G6 — Human-readable UI

Pass if primary workflows contain no default raw:

- JSON;
- hashes;
- UUIDs;
- provider internals;
- enum serialization;
- debug text areas.

Advanced disclosures may contain technical details.

### G7 — Visual quality

Pass if all S00–S21 meet `30-visual-product-redesign.md` and `34-screen-by-screen-remediation.md`.

### G8 — Desktop responsiveness

Pass if:

- UI remains interactive during scan;
- playback remains usable during analysis;
- waveform editing remains interactive during preview render;
- background work visible in Activity;
- minimum window layout is usable.

### G9 — Packaging

Pass if:

- AppImage built from clean CI/release environment;
- no Python/uv required on target;
- Qt runtime works;
- FFmpeg strategy works on target;
- model setup path works on target;
- desktop entry/icon valid.

## Feature acceptance matrix

| Area | Required proof |
|---|---|
| Add Source | picker + drop + background scan |
| Library | large paged data, search, sorting, multi-select |
| Playback | play/pause/restart/seek/loop/gain |
| Inspector | waveform + human-readable summary |
| Sample | classification/Suggestions/edit actions |
| Edit Sound | direct-manipulation waveform scenario |
| Edit Info | library + embedded metadata paths |
| Collections | logical membership, no file copy |
| Organize | reviewed Reference/Copy/Move |
| Conflicts | no silent overwrite, real resolutions |
| Analysis | deterministic + semantic states |
| Review | accept/edit/reject + Why |
| Similar | real embedding similarity |
| Activity | truthful background state |
| Recovery | offline/missing/changed distinct |
| Settings | model/audio/appearance usable |
| Maintenance | preserved-data statements |
| Diagnostics | no audio in bundle by default |
| Package | clean AppImage launch |

## Exact acceptance scenarios

### Scenario A — Messy sample pack

Given a Source containing files such as:

- `KCK_01.wav`;
- `snr-dry.wav`;
- `120_Dm_synth_loop.wav`;
- `vox_phrase_07.wav`;
- generic filenames nested under useful folders.

Expected:

1. add Source;
2. rows appear before deep analysis completes;
3. deterministic analysis starts;
4. local AI starts when enabled;
5. classifications/Suggestions become visible;
6. Review provides understandable reasons;
7. accepted values persist;
8. search/filter can find by accepted classification.

### Scenario B — Edit a bad kick

Given a kick with leading silence and long tail:

1. open Edit Sound;
2. trim visually;
3. add fades;
4. normalize;
5. transpose;
6. A/B compare;
7. save recipe;
8. close/reopen;
9. export copy;
10. original hash unchanged;
11. output audibly/technically reflects recipe.

### Scenario C — Edit information

1. change Sample Type and Instrument;
2. add tags;
3. change title/artwork on supported file;
4. choose Write to Copy;
5. verify copy tags/artwork;
6. original embedded metadata unchanged;
7. library classifications persist independently.

### Scenario D — Local AI fresh install

1. install model;
2. verify checksum;
3. add Source;
4. semantic analysis queues automatically;
5. mapped Suggestions appear;
6. accept one;
7. Similar Sounds returns results;
8. disable model;
9. core library still works.

### Scenario E — Filesystem conflict

1. Copy Sample to destination containing same filename;
2. review shows conflict;
3. Execute disabled;
4. Choose Destination to unused path;
5. plan becomes executable;
6. copy succeeds;
7. source remains.

### Scenario F — Offline drive

1. Source disappears;
2. Source becomes Offline, not deleted;
3. Samples remain searchable with unavailable state;
4. reconnect/recheck restores availability;
5. Collections/classifications remain.

## Visual review rubric

Score each screen 0–2 on:

- hierarchy;
- spacing;
- color;
- readability;
- action grouping;
- state clarity;
- keyboard/focus;
- plain language;
- empty/error states;
- minimum-size layout.

0 = unacceptable.

1 = functional but visibly rough.

2 = polished.

No screen may contain a 0.

Release candidate target: at least 18/20 for each primary screen S01, S07, S08, S09, S10, S11.

## P0 defects

Examples:

- cannot edit audio despite Edit Sound;
- ML never actually executes;
- source mutation without explicit user action;
- dead primary button;
- raw exception instead of recoverable state on normal path;
- corrupt/delete user organization;
- packaged app lacks required render dependency.

Zero P0 allowed.

## P1 defects

Examples:

- workflow technically works but is confusing;
- important action hidden;
- severe visual inconsistency;
- primary screen uses debug-style content;
- missing keyboard path;
- inability to complete documented task at minimum window size.

Zero P1 allowed at release.

## Codex campaign completion report

Before proposing merge to `main`, Codex produces:

~~~text
Koffer V1 acceptance
DEV HEAD:
QA:
PACKAGE:
P0:
P1:
SCREENS LEVEL 4:
ML MODEL-ENABLED PROOF:
EDIT SOUND PROOF:
METADATA PROOF:
SOURCE SAFETY PROOF:
100K PERF:
WAYLAND/X11:
DOCUMENTATION:
KNOWN P2/P3:
~~~

Every line requires evidence.

## Final rule

If the manual says a user can do something and the current build cannot do it pleasantly and truthfully, the implementation is incomplete even if every existing test passes.
