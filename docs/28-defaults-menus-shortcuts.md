# 28. Product Defaults, Menus, and Shortcuts

## Purpose

These defaults remove small UX ambiguities that otherwise cause different agents to invent different Koffer behavior.

## First-run defaults

- recursive Source scan: ON;
- hidden directories: OFF;
- automatic technical probing: ON;
- waveform generation: lazy + background after discovery;
- deterministic analysis: ON;
- semantic model: not installed by default; prompt/setup available, never blocks core use;
- similarity: enabled automatically after model installation, otherwise unavailable with explanation;
- auto-preview on row selection: OFF;
- loop preview: OFF;
- preview gain: -6 dB;
- UI density: Compact;
- Inspector: open;
- theme: Koffer Dark;
- restore last workspace: ON;
- completion notifications: ON;
- reduced motion: OFF.

## Default browser columns

Visible:
1. Name
2. Sample Type
3. Instrument / Source
4. BPM
5. Key
6. Duration
7. Format
8. Review/analysis state

Optional hidden columns:
- Role;
- Genre/Style;
- Character;
- Source;
- Channels;
- Sample Rate;
- Bit Depth;
- File Size;
- Date Discovered;
- Last Previewed.

Column widths/order persist per user.

## Default sorting

All Samples: Name ascending.

Recents: Last Previewed descending.

Recently Added: First Seen descending.

Suggestions Review: attention priority then confidence.

Similar Sounds: similarity descending.

Collections: Name ascending unless manual order selected inside Collection Detail.

## Confirmation policy

No confirmation required:
- favourite;
- Collection add/remove;
- classification/tag edits;
- recipe edits;
- accepting/rejecting Suggestion;
- clearing rebuildable waveform cache after explicit Maintenance action selection.

Review/confirmation required:
- Copy batch;
- Move;
- overwrite/Replace;
- Update Original metadata;
- delete/remove stale library entry where meaning could be confused;
- restore backup;
- destructive cache/model removal if active work may be interrupted.

No global setting may disable overwrite/delete/source-modification confirmations.

## Main menu

### File
- Add Source…
- Organize Selected…
- Export / Render… when applicable
- Settings
- Quit

### Library
- All Samples
- Collections
- Sources
- Suggestions Review
- Activity
- Rescan Current Source when scoped
- Maintenance

### Sample
Enabled when Sample selected:
- Play / Pause
- Open Detail
- Favourite
- Add to Collection…
- Find Similar
- Edit Metadata…
- Prepare…
- Reveal in Files

### View
- Toggle Sidebar
- Toggle Inspector
- Density: Compact / Comfortable
- Reset Pane Layout

### Help
- Documentation / Basics
- About & Diagnostics

## Default keyboard shortcuts

Global:
- Ctrl+F — focus search;
- Ctrl+O — Add Source;
- Ctrl+, — Settings;
- Ctrl+Shift+A — Activity Center;
- Ctrl+Q — Quit;
- Escape — close focused modal/workspace layer or return to prior browser context.

When Sample browser/list has focus:
- Up/Down — change selection;
- Space — play/pause selected/current Sample;
- Enter — open Sample Detail;
- Ctrl+D — toggle Favourite;
- Ctrl+Shift+C — Add to Collection;
- Ctrl+Shift+S — Find Similar;
- Ctrl+M — Edit Metadata;
- Ctrl+P — Prepare;
- Home/End/PageUp/PageDown — standard table navigation.

Suggestions Review:
- A — accept focused Suggestion;
- R — reject focused Suggestion;
- E — edit focused Suggestion;
- Up/Down — move review focus.

Single-letter review shortcuts are active only when a text input is not focused.

Shortcuts are editable in S19. Conflict resolution prevents duplicate active bindings.

## Search behavior

Typing into focused search debounces around 150 ms before query execution.

Enter does not clear filters.

Escape while search field is focused clears current text only if nonempty; a second Escape returns focus to browser.

## Source exclusions

Defaults:
- hidden directories excluded;
- common trash/recycle metadata directories excluded where safely identifiable;
- no arbitrary sample-pack folder names excluded;
- unsupported file types ignored, not treated as errors.

## Managed library defaults

The user chooses the managed audio location on first Copy/Move requiring one if none exists.

Koffer does not silently create a managed audio hierarchy in the user's home directory before needed.

## Naming conflicts

Default conflict action is **Review**, never Replace.

"Keep Both" generates a stable human-readable suffix such as:
`Kick (2).wav`

The exact numbering checks destination atomically before finalize.

## Render defaults

- output format: WAV;
- sample rate: Source;
- bit depth: Source where representable, otherwise 24-bit PCM for WAV;
- channels: Source;
- metadata carry-over: ON;
- artwork carry-over: ON where supported;
- normalize: OFF;
- overwrite: OFF.

## Window defaults

First launch target size: 1440×900 constrained to available screen geometry.

Minimum practical size: approximately 1180×720.

On smaller available desktops, open maximized or fit available geometry rather than creating off-screen content.

## Accessibility defaults

Respect system scale/font settings.

Reduced-motion follows explicit Koffer setting and may initialize from desktop preference when reliably detectable.

Status never uses color alone.
