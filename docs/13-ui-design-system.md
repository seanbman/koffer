# 13. UI Design System

## Design intent

Koffer looks like a serious piece of music-production utility software without imitating a DAW.

The interface is dark, dense, geometric, and deliberate. Clay/amber remains the Koffer brand accent, but Koffer now uses a richer semantic palette for analysis, playback, editing, confirmation, organization, warning, and destructive state. The main content is audio, waveforms, classifications, and user decisions—not raw implementation data.

## Reference canvas

Mockups use a 1440 × 900 reference window.

Supported desktop layout goals:
- comfortable: 1440 × 900 and larger;
- minimum full layout: approximately 1180 × 720;
- compact: Inspector collapses before the Sample browser is compromised;
- no mobile layout.

Reference regions:
- top application bar: 40 px;
- navigation rail: 224 px;
- Inspector: 336 px;
- bottom transport/status: 72 px;
- main browser: flexible remainder.

## Color tokens

| Token | Value | Use |
|---|---|---|
| Canvas | `#0B0D0F` | application background |
| Surface 1 | `#121518` | navigation and panels |
| Surface 2 | `#181C20` | cards, raised groups |
| Surface 3 | `#20252A` | selected/hovered controls |
| Border | `#30363D` | separators and outlines |
| Text | `#F1F4F6` | primary text |
| Muted | `#98A2AD` | secondary text |
| Faint | `#66717C` | low-priority text |
| Clay | `#CF8652` | primary accent / active |
| Clay Bright | `#E7A36F` | hover/focus accent |
| Green | `#67B983` | success / online |
| Yellow | `#D7B65E` | warning / pending review |
| Red | `#D36B6B` | destructive / failure |
| Blue | `#6FA3D8` | informational / analysis |
| Cyan | `#54C6D8` | playback / time / playhead |
| Violet | `#9B7BD8` | non-destructive Edit Sound state |
| Magenta | `#C66AA3` | pitch / key / tonal metadata |
| Teal | `#5FB7A2` | Collections / organization |

Status colors always have an icon, label, or shape difference so color is never the only information carrier.

## Typography

Default UI font: the platform's clean system sans-serif or bundled equivalent.

Hierarchy:
- application/page title: 20–24 px semibold;
- section title: 15–17 px semibold;
- row primary: 13–14 px medium;
- body: 13 px regular;
- metadata/supporting: 11–12 px;
- timecode, BPM, key, hashes, paths: monospaced where alignment matters.

Uppercase is reserved for very small utility labels and column metadata, not headings.

## Geometry

- base spacing unit: 4 px;
- common gaps: 8 / 12 / 16 / 24 px;
- control height: 32 px;
- compact table row: 34 px;
- comfortable table row: 40 px;
- card radius: 6 px;
- button/input radius: 5 px;
- separators: 1 px;
- selected row uses background and a 2 px Clay leading marker.

## Navigation

The navigation rail contains:
- Library;
- Favourites;
- Recents;
- Review;
- Similar history where useful;
- Collections;
- Saved Searches;
- Sources;
- Activity;
- Settings.

Nested Collections and Sources can expand inline. The rail is not a filesystem tree.

## Table behavior

The Sample table is the productivity center.

Requirements:
- virtualized or otherwise scalable rendering;
- resizable columns;
- reorderable optional columns;
- sticky header;
- multi-selection;
- sorting;
- row keyboard navigation;
- context menu;
- inline favourite and play status;
- no horizontal card grid as the default for large result sets.

Artwork is optional in dense rows.

## Inspector behavior

The Inspector is contextual and never becomes a second navigation system.

Collapsed states:
- hidden;
- compact summary;
- full Inspector.

Selection changes update the Inspector without changing the browser's scroll position.

## Waveforms

Waveforms use neutral/Clay contrast and remain legible at low amplitudes.

The preparation waveform shows:
- playhead;
- selected trim region;
- excluded regions;
- loop region;
- transient or beat markers only when useful;
- zoom scale;
- time ruler.

## Buttons

Primary action:
- filled Clay surface;
- one per focused workflow whenever possible.

Secondary:
- Surface 3 with border.

Destructive:
- red text/border, filled red only at final irreversible confirmation.

Icon-only buttons always expose tooltips and accessible names.

## Fields and chips

Search is visually dominant in browsing screens.

Filter chips communicate:
- label;
- selected state;
- optional count;
- clear action where appropriate.

Tags and Suggestions look different:
- confirmed tag: neutral/Clay;
- machine suggestion: Blue with confidence;
- warning/conflict: Yellow;
- rejected/invalid: muted or red depending severity.

## Empty states

Empty states are instructional, not decorative.

Every empty state answers:
1. why the surface is empty;
2. what the user can do next;
3. whether existing audio is safe.

## Loading and progress

Koffer avoids blocking modal spinners for background work.

Preferred patterns:
- inline skeleton for unready content;
- progress badge in global Activity;
- per-Source scan status;
- per-Sample analysis badge;
- non-modal toast for completion/failure.

## Focus and keyboard

Keyboard focus uses a visible Clay Bright outline with sufficient contrast.

Important actions have shortcuts displayed in menus/tooltips. Tab order follows visual reading order. Table arrow navigation does not unexpectedly move focus into the Inspector.

## Accessibility

- text contrast meets modern desktop accessibility expectations;
- all color-coded status has text/icon redundancy;
- reduced-motion mode disables nonessential transitions;
- controls have accessible names;
- minimum pointer targets remain practical even in dense mode;
- waveform operations have keyboard-accessible alternatives where feasible.

## Motion

Motion is restrained:
- 100–160 ms panel transitions;
- no decorative parallax;
- no animated backgrounds;
- waveform playhead movement is functional;
- progress animation communicates actual work.

## Mockup authority

The mockups are visual acceptance references, not screenshots to clone blindly. If implementation must adapt to platform metrics, it preserves information hierarchy, action grouping, density, and pane relationships first.


## Current visual remediation

`30-visual-product-redesign.md` is the detailed current visual contract.

Primary user screens must not present raw JSON, hashes, internal IDs, provider/version strings, or generic diagnostic textareas by default. Such material belongs in Analysis Details, File Details, Activity detail, or Diagnostics.

Buttons are grouped by intent and hierarchy. More than four same-weight actions in a row is presumed a design defect and must be justified or reorganized.

The Sample Workbench makes the waveform visually dominant and uses direct manipulation. A long vertical form of spin boxes is not an acceptable substitute.
