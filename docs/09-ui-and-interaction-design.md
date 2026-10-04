# 9. UI and Interaction Design

This chapter documents the initial interaction model. It is planning material, not a frozen visual specification.

## Desktop-first interaction model

Koffer is designed as a full Linux desktop application.

The UI should follow desktop interaction expectations rather than mobile or web conventions. This includes real window management, strong keyboard navigation, context menus where appropriate, drag-and-drop, native file pickers, persistent window state, and dense data views suitable for large libraries.

The application should feel comfortable alongside other Linux desktop tools used by musicians and producers.

## Overall layout
The primary desktop window uses three functional regions:
1. Navigation / Library sidebar
2. Sample browser
3. Inspector

A persistent player/status area may sit along the bottom.

See the [Library Browser mockup](mockups/library-browser.svg).

## Navigation sidebar
Initial destinations:
- All Samples
- One-shots
- Loops
- Phrases
- Tracks
- Instruments
- Genres / Styles
- Collections
- Favourites
- Sources

Collections and Sources may expand inline.

The sidebar should communicate library structure, not expose the raw filesystem as the only navigation model.

## Sample browser
The center pane is optimized for high-volume browsing.

It includes prominent search, filter chips/facets, sortable results, multi-selection, clear playback affordance, analysis/suggestion state, and quick Collection/favourite actions.

The browser should remain useful with tens of thousands of indexed files.

## Inspector
The right pane displays the selected Sample.

It includes waveform, playback controls, technical metadata, musical metadata, suggestions, tags, file location, Collection membership, and editable embedded metadata where supported.

The Inspector can expand into the preparation view for detailed waveform editing.

See the [Sample Inspector mockup](mockups/sample-inspector.svg).

## Import review
When users choose Copy or Move, Koffer should provide a review surface rather than performing the operation immediately.

The same review pattern can surface suggested classifications for newly discovered material.

See the [Import and Suggestion Review mockup](mockups/import-review.svg).

## Native desktop behaviors

Koffer should support, where appropriate:
- multi-selection with standard Shift/Ctrl behavior;
- drag-and-drop of folders and audio files into the library;
- drag-and-drop of Samples into Collections;
- context menus for file/library actions;
- system clipboard;
- keyboard traversal between panes;
- familiar open/save/directory dialogs;
- remembering window size, position, pane widths, and view preferences;
- multiple windows or auxiliary dialogs only where they materially improve workflow.

## Keyboard workflow
The application should be pleasant to use without constant mouse travel.

Planning goals:
- focus search quickly;
- move through results with arrow keys;
- play/stop selected Sample;
- favourite;
- add to Collection;
- open Inspector;
- accept/reject suggestions;
- invoke common file and metadata actions.

Exact shortcuts will be documented after workflow design stabilizes.

## Long-running work

Scanning, waveform generation, metadata extraction, and inference should never make the desktop window feel frozen.

The UI should provide progress, status, pause/cancel where technically reasonable, and useful recovery information when a task fails.

## Dark theme
Koffer is dark-themed by default.

Design priorities:
- strong text contrast;
- restrained surfaces;
- clear selected/focused states;
- waveform visibility;
- metadata hierarchy;
- accents used for status rather than decoration.

## Density
This is a desktop library tool and can be information-dense, but should not become visually noisy.

The browser favors rows and compact metadata. The Inspector provides detail on demand.

## Window behavior
The three-pane layout should degrade gracefully when the window narrows:
- Inspector can collapse;
- sidebar can narrow or hide;
- browser remains primary.

No mobile UI is planned. Koffer is a Linux desktop application.
