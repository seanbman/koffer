# 34. Screen-by-Screen Remediation Specification

## How to use this document

Codex audits every screen against this specification.

For each screen, implementation must match the stated purpose, hierarchy, primary actions, and prohibited patterns.

A screen is not accepted merely because its class exists.

---

## S00 — Welcome

### Goal

Get a new user into a real library immediately.

### Layout

- Koffer identity;
- concise “local sample library” explanation;
- large Add Source primary action;
- drag-and-drop zone;
- three concise promises:
  - audio stays where it is;
  - analysis runs locally;
  - edits are non-destructive.

### Avoid

- engineering architecture copy;
- empty window;
- multiple equal-weight buttons;
- generic “Get Started” without explaining Source.

---

## S01 — Library

### Goal

Browse, search, audition, classify, and select Samples quickly.

### Header

- dominant search;
- Filters;
- sort state;
- result count;
- view/column menu.

### Table

Important default columns:

- favourite;
- name;
- type;
- instrument/source;
- duration;
- BPM;
- key;
- format;
- analysis/review status.

### Inspector

Selected Sample shows:

- compact artwork/identity;
- waveform;
- confirmed classification chips;
- top Suggestions;
- tags;
- Collections;
- edit summary;
- file summary.

### Primary contextual actions

- Play;
- Edit Sound;
- Edit Info;
- Add to Collection.

### Avoid

- raw provenance blocks;
- developer IDs;
- vertical paragraphs of metadata;
- hidden edit functions.

---

## S02 — Search & Filters

### Goal

Build a precise reusable query.

### Layout

Use grouped facets, not a giant generic form.

Groups:

- Classification;
- Music;
- Duration/technical;
- Location/Collection;
- Analysis status.

Active filters appear as removable chips at top.

Primary action: Apply.

Secondary: Save Search, Clear All.

---

## S03 — Collections

### Goal

See and manage logical groups.

### Collection cards/rows

Show:

- name;
- Sample count;
- optional artwork/color;
- description snippet;
- last modified where useful.

Primary action: New Collection.

Actions such as Rename/Duplicate/Delete live in context/overflow.

Delete confirmation explicitly says audio remains.

---

## S04 — Collection Detail

### Goal

Use a Collection like a scoped Library.

Reuse Library table/Inspector patterns.

Header:

- Collection name;
- description;
- count;
- Add Samples;
- collection menu.

Do not create a second incompatible browser interaction model.

---

## S05 — Sources

### Goal

Understand storage/index health.

Rows show:

- Source name/path;
- online/offline state;
- Sample count;
- pending analysis;
- issues;
- last scan.

Color/status is meaningful.

Primary: Add Source.

---

## S06 — Source Detail

### Goal

Manage one Source safely.

Sections:

- status/path;
- scan controls;
- indexing summary;
- exclusions;
- issues;
- recent jobs;
- indexed Sample access.

Do not display full file dumps as the dominant UI if a proper Sample table can be reused.

Danger zone contains Disable/Remove with plain safety copy.

---

## S07 — Sample

### Goal

Understand and act on one Sample.

### Required order

1. identity/artwork;
2. large waveform;
3. playback/edit actions;
4. confirmed classifications;
5. Suggestions;
6. tags/Collections;
7. edit summary;
8. File Details;
9. Analysis Details.

### Primary actions

- Edit Sound — Clay;
- Edit Info — secondary;
- Find Similar — Blue;
- Add to Collection — Teal.

Organize/Reveal live in overflow.

### Classification

Editable chips or an obvious Edit Classification affordance.

### Suggestions

Friendly cards/chips.

Raw evidence is hidden by default.

---

## S08 — Edit Sound / Sample Workbench

Defined exhaustively in `31-sample-workbench-waveform-editor.md`.

This is the most important remediation screen.

Form-only implementation is rejected.

---

## S09 — Edit Info

### Goal

Edit human-readable Sample information safely.

Tabs/sections:

### Library

- Sample Type;
- Instrument / Source;
- Role;
- Genre / Style;
- Character;
- user tags.

Changes save to Koffer immediately or through a clear Save button.

### File Metadata

- title;
- artist;
- album;
- album artist;
- genre;
- date;
- track;
- comment;
- composer;
- copyright;
- artwork.

Show format capability inline.

### Write target

Before embedded write:

- Update Original;
- Write to Copy.

Do not mix Koffer-only classification into a file-write confirmation.

### Avoid

- disabled mystery fields with no explanation;
- raw capability maps;
- model/provider data.

---

## S10 — Review

### Goal

Review machine Suggestions efficiently.

### Three-column ideal

- queue;
- selected Sample waveform/identity;
- Suggestions/Why.

### Filter

- confidence range;
- dimension;
- provider/state only if genuinely useful;
- “Needs attention” preset for low-confidence/contradictory items.

### Suggestion card

Shows:

- proposed value;
- dimension;
- confidence band;
- percentage;
- plain-language Why.

Actions:

- Accept;
- Edit & Accept;
- Reject.

Batch actions show exact scope.

---

## S11 — Similar Sounds

### Goal

Discover sonically related audio.

Header shows seed Sample.

Each result shows:

- preview button;
- similarity score;
- name;
- key classifications;
- availability.

The user can preview without opening another screen.

If model/index unavailable, show exactly what to do.

Do not show an internal provider line as the main status.

---

## S12 — Organize Review

### Goal

Review what Reference/Copy/Move will do.

Use plain language.

Summary card:

- operation;
- item count;
- destination;
- conflict count.

List/table shows source → destination.

Primary button label matches operation: Reference / Copy / Move.

Avoid “Execute Plan”.

---

## S13 — Conflicts

### Goal

Resolve destination conflicts before mutation.

Each conflict shows:

- source;
- existing destination;
- relevant comparison facts;
- chosen action.

Actions only appear when implemented.

Currently required:

- Keep Both;
- Skip;
- Replace;
- Choose Destination.

Compare and Use Existing Indexed Sample are required before V1 only after their service semantics/tests exist; never add fake buttons first.

---

## S14 — Export Copy

### Goal

Render the current edit into a new file.

Summary:

- original Sample;
- edit summary;
- output format;
- technical conversion;
- metadata/artwork carry-over;
- destination;
- filename;
- conflict policy.

Primary: Export Copy.

Show background progress in Activity.

---

## S15 — Recovery

### Goal

Repair storage/file problems without guessing.

Filter/group by:

- Source offline;
- file missing;
- file changed;
- permission denied;
- mount/source problem.

Actions depend on condition.

Missing file:

- Locate File;
- Leave Unresolved;
- Remove Stale Entry.

Changed file:

- Accept Changed File;
- leave unresolved.

Source offline:

- Recheck Source;
- Locate/Reconnect Source when implemented.

Raw enum values should be translated into labels.

---

## S16 — Activity

### Goal

Understand and control background work.

Groups:

- Running;
- Queued;
- Needs Attention;
- Completed.

Each Job shows:

- friendly name;
- progress;
- current stage;
- affected Source/Sample count;
- pause/cancel where safe;
- failure summary.

Advanced job IDs belong in details.

---

## S17 — General Settings

### Goal

Application-level behavior.

Group settings by concept.

Avoid long path/debug panels in the primary view.

Data paths may have a compact Advanced section.

---

## S18 — Library & Analysis Settings

### Goal

Control scanning and intelligent analysis.

Must include Local AI card from `32-local-ml-classification-spec.md`.

Also:

- automatic deterministic analysis;
- automatic local AI analysis;
- analysis intensity;
- model install/manage;
- Analyze Existing Library;
- rebuild actions.

This is not complete if it only exposes booleans for a model that never runs.

---

## S19 — Audio & Appearance

### Goal

Preview and interface preferences.

Sections:

- Audio output;
- Preview;
- Waveform;
- Appearance;
- Accessibility/keyboard.

Appearance includes:

- density;
- Inspector default;
- reduced motion;
- theme/accent policy if configurable.

---

## S20 — Maintenance

### Goal

Safe repair/rebuild operations.

Use clear cards:

- Backup & Restore;
- Library Index;
- Waveforms;
- Analysis;
- Similarity;
- Cache;
- Database Health.

Each action says what is preserved.

---

## S21 — About & Diagnostics

### Goal

Support/debug information without cluttering normal workflows.

Shows:

- app version;
- build;
- licenses;
- model version/state;
- XDG paths;
- create diagnostics bundle.

This is where technical implementation detail belongs.

---

## Cross-screen action placement

### Header

Context + one primary action max.

### Main content

Task-specific controls.

### Inspector

Selection-specific information/actions.

### Overflow/context menu

Low-frequency actions:

- Reveal in Files;
- Organize;
- duplicate;
- technical details;
- reset/rebuild where not primary.

### Danger zone

Destructive actions only.

---

## Raw text policy

A QTextEdit/QPlainTextEdit is acceptable for:

- actual comments/descriptions;
- editable exclusion rule text if a structured editor is not yet practical;
- logs/diagnostics in advanced surfaces.

It is not acceptable as the default presentation for:

- classifications;
- Suggestions;
- evidence;
- metadata;
- technical facts;
- model state;
- collections;
- job state.

Use structured UI.

## Visual QA evidence

For every screen Codex records at least:

- 1440×900 screenshot or equivalent inspected rendering;
- minimum-size rendering;
- empty state;
- populated state;
- error/offline state when applicable;
- keyboard focus path.

The repository need not retain every screenshot permanently, but the campaign must record review evidence.
