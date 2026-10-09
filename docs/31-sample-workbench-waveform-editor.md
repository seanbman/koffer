# 31. Sample Workbench and Waveform Editor

## Product decision

Koffer must provide a real, direct-manipulation Sample editor.

The user-facing action is **Edit Sound**. The implementation may continue to store a non-destructive `PreparationRecipe`, but the user should experience an audio editor, not a recipe form.

This screen replaces the current form-heavy interpretation of S08. Internal Screen ID S08 may remain for compatibility.

## Core safety rule

Editing the waveform does not alter the source file.

Every edit changes an in-memory/persisted non-destructive recipe. Source bytes change only through a separate explicit render/export action. Embedded metadata writes remain a separate workflow.

## Entry paths

Edit Sound is reachable from:

- Library row/context menu;
- Inspector;
- Sample screen;
- Collection Detail;
- keyboard shortcut;
- optionally Suggestions/Similar results via context menu.

Opening Edit Sound must preserve the browser context so Back returns the user to the same search/selection.

## Screen anatomy

### Header

Left:

- Back;
- Sample filename;
- optional Collection/path context.

Center/right:

- Saved / Unsaved Changes badge;
- Undo;
- Redo;
- Reset;
- A/B Original vs Edited.

Primary output action is **Export Copy**.

Do not put destructive source overwrite in the main toolbar.

### Main waveform

The waveform occupies roughly 45–60% of usable screen height at 1440×900.

It must support:

- click to seek;
- drag playhead;
- wheel/pinch-equivalent zoom where feasible;
- horizontal pan when zoomed;
- Fit button;
- zoom in/out buttons;
- time ruler;
- current playhead time;
- duration;
- selection readout.

### Trim handles

Left/right draggable handles define retained audio.

Behavior:

- drag left handle changes trim start;
- drag right handle changes trim end;
- excluded audio dims;
- retained region stays vivid;
- handles snap optionally to zero crossing/transient;
- modifier key disables snap;
- numeric trim values update live;
- numeric edits move handles;
- invalid crossing is prevented;
- double-click/Reset Trim restores full file.

Keyboard:

- Left/Right nudges playhead;
- Shift+Left/Right adjusts selected trim handle;
- configurable coarse/fine nudge.

### Loop region

Loop preview can be enabled independently of trim.

The loop region:

- defaults to retained trim;
- may have its own handles when unlocked;
- repeats during preview;
- never implies the final export loops forever;
- is clearly labeled “Preview Loop”.

### Fade handles

Fade-in and fade-out are drawn as envelope curves over the waveform.

The user can drag fade duration handles.

Controls show exact ms values and allow keyboard entry.

Fade curves must remain visible at a glance.

### Gain and normalize

Provide:

- gain slider with dB readout;
- Reset 0 dB;
- Normalize toggle;
- target peak control when Normalize enabled;
- peak/clipping warning on preview/render estimate where available.

Changing gain is previewable and non-destructive.

### Pitch

Provide:

- semitone step control;
- fine cents control;
- source key if estimated/confirmed;
- optional target-key helper;
- Reset.

Use Magenta accent.

Pitch shift must not be mislabeled as playback speed.

### Time stretch

Provide:

- ratio or target duration;
- for loops with BPM, optional Source BPM → Target BPM control;
- preserve pitch by default;
- Reset.

If exact preview has rendering latency, show “Rendering preview…” without blocking the UI.

### Reverse

Provide a clear Reverse toggle with immediately understandable visual state.

### Channel/output preparation

Secondary Output panel:

- source → mono/stereo;
- sample rate;
- bit depth;
- output format;
- filename;
- destination;
- metadata/artwork carry-over.

These are export settings, not dominant editing controls.

## Preview pipeline

The editor must support audible before/after comparison.

### A/B

A = original source.

B = current edit recipe.

Switching A/B should preserve approximately the same playhead region where technically practical.

The state is obvious in the transport.

### Preview render

For operations that cannot be applied by the realtime playback adapter, render a temporary preview in the background.

Requirements:

- cancel superseded preview renders;
- do not queue dozens of stale previews while a slider is dragged;
- debounce expensive operations;
- cache by source fingerprint + recipe fingerprint;
- visually indicate stale/rendering/ready;
- never modify source.

### Playhead and recipe preview

Playback must follow trim/loop boundaries while previewing edited audio.

Seeking on the waveform updates the shared playback service.

## Undo/redo

User-facing edit operations must participate in a local command history:

- trim;
- fade;
- gain;
- normalize;
- pitch;
- stretch;
- reverse;
- loop region;
- channel/output settings where appropriate.

At minimum, maintain an editor-session undo/redo stack. Persisted global edit history may be future work.

## Dirty/saved state

The screen distinguishes:

- Original — no recipe changes;
- Unsaved Changes — recipe differs from persisted recipe;
- Saved — current recipe persisted;
- Preview Rendering;
- Preview Ready;
- Export Running;
- Export Complete/Failed.

Leaving with unsaved recipe changes prompts Save / Discard / Cancel unless autosave is deliberately enabled in product settings.

## Save Recipe

Save Recipe persists Koffer edit state only.

It does not render a new file and does not modify source bytes.

After save, Sample Detail shows a concise badge such as:

“Edited · Trim + Normalize + -2 st”

## Export Copy

Export Copy opens a focused output sheet or S14.

It summarizes:

- original;
- applied edits;
- output technical settings;
- destination;
- filename;
- metadata/artwork carry-over;
- conflict policy.

The primary button is “Export Copy”.

## Waveform implementation requirements

The waveform widget must expose a testable model separate from paint code.

Suggested concepts:

- `WaveformViewport`: duration, visible start/end;
- `EditSelection`: trim start/end, loop start/end;
- `EnvelopeOverlay`: fade in/out, gain indication;
- signals for seek/trim/loop/fade changes;
- keyboard commands;
- accessible names and numeric alternatives.

Do not bury recipe mutations directly in `paintEvent` or mouse handlers. UI gestures call controller/model methods.

## Accessibility

Every direct manipulation has a non-pointer alternative.

Examples:

- trim start/end numeric controls;
- fade durations numeric controls;
- zoom buttons;
- playhead time field;
- reset commands;
- keyboard shortcuts.

Focus handles must be visible.

## Performance

Opening Edit Sound should show a usable waveform rapidly from cache.

Higher-resolution waveform data may load progressively.

UI must remain responsive while:

- preview renders;
- waveform cache builds;
- analysis runs;
- source scan runs.

## Required tests

### Unit

- trim constraints;
- snap behavior;
- recipe serialization;
- recipe fingerprint;
- undo/redo;
- output validation.

### Integration

- recipe save/load;
- source hash unchanged after all editor operations;
- preview render reflects trim/gain/reverse/pitch/stretch;
- stale preview cancellation;
- export copy produces output and preserves source.

### UI

- waveform handles move recipe;
- numeric edits move handles;
- A/B state changes transport;
- dirty/save/reset state;
- Back unsaved prompt;
- keyboard trim/fade commands;
- Export Copy summary.

## Acceptance scenario

Given a 3-second kick Sample:

1. open Edit Sound;
2. drag trim start to remove silence;
3. shorten tail with trim end;
4. add a 10 ms fade-in and 80 ms fade-out;
5. normalize;
6. transpose -2 semitones;
7. press B and hear edited preview;
8. press A and hear original;
9. save recipe;
10. return to Sample;
11. see concise edit summary;
12. reopen editor and see exact saved state;
13. Export Copy;
14. verify source hash is identical;
15. verify output contains the audible edits.

If this scenario is not smooth, S08 is not complete.
