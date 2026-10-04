# 9. UI and Interaction Design

This chapter documents the initial interaction model. It is planning material, not a frozen visual specification.

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

It includes waveform, playback controls, technical metadata, musical metadata, suggestions, tags, file location, and Collection membership.

The Inspector can expand into the preparation view for detailed waveform editing.

See the [Sample Inspector mockup](mockups/sample-inspector.svg).

## Import review
When users choose Copy or Move, Koffer should provide a review surface rather than performing the operation immediately.

The same review pattern can surface suggested classifications for newly discovered material.

See the [Import and Suggestion Review mockup](mockups/import-review.svg).

## Keyboard workflow
The application should be pleasant to use without constant mouse travel.

Planning goals:
- focus search quickly;
- move through results with arrow keys;
- play/stop selected Sample;
- favourite;
- add to Collection;
- open Inspector;
- accept/reject suggestions.

Exact shortcuts will be documented after workflow design stabilizes.

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

No mobile UI is planned; Koffer is a desktop application.
