# 9. UI and Interaction Design

## Status

This chapter defines the intended Koffer desktop interface. It is no longer a loose collection of possible layouts. Detailed screen behavior lives in [12-screen-catalog.md](12-screen-catalog.md), visual rules in [13-ui-design-system.md](13-ui-design-system.md), flows in [14-navigation-and-user-flows.md](14-navigation-and-user-flows.md), and implementation acceptance in [15-ui-acceptance-contract.md](15-ui-acceptance-contract.md).

## Desktop application model

Koffer is a full Linux desktop application. It uses real desktop windows, focus behavior, native file/directory pickers, drag-and-drop, keyboard shortcuts, context menus, clipboard support, persistent window state, and non-blocking background work.

The application is not responsive toward a mobile layout and is not designed as a browser page.

## Primary shell

The default workspace has:
1. a left navigation rail;
2. a central browser/workspace;
3. an optional right Inspector;
4. a persistent bottom transport/status bar;
5. global access to Activity.

The central browser remains the primary surface when the window narrows. The Inspector collapses before the browser becomes unusable.

## Navigation

Primary destinations:
- Library;
- Favourites;
- Recents;
- Review;
- Collections;
- Saved Searches;
- Sources;
- Activity;
- Settings.

Collections and Sources may expand inline. Raw directory trees are not the primary navigation model.

## Library browser

The Library Browser is a compact, high-volume table optimized for tens of thousands of Samples.

It provides:
- dominant search;
- visible filters;
- sortable/resizable columns;
- multi-selection;
- keyboard row navigation;
- playback;
- favourite;
- Collection actions;
- availability state;
- analysis/review state;
- contextual Inspector.

## Inspector

The Inspector displays the selected Sample without replacing the browser.

It shows:
- identity/artwork;
- waveform;
- transport;
- technical facts;
- classifications;
- Suggestions;
- tags;
- file location;
- Collection membership;
- recipe state.

The expanded Sample Detail screen adds full history and metadata editing entry points.

## Focused workspaces

Koffer uses dedicated focused screens for work that requires more room or stronger confirmation:
- Search & Filters;
- Sample Preparation;
- Metadata Editor;
- Suggestions Review;
- Similar Sounds;
- Import / Organize Review;
- Conflicts & Duplicates;
- Render / Export;
- Offline / Missing Recovery;
- Activity;
- Settings;
- Maintenance.

## Playback

Playback remains available during normal browsing and inspection. Moving between metadata screens does not unnecessarily stop the active preview.

The player shows:
- play/pause;
- restart;
- current position and duration;
- loop state;
- preview gain;
- active Sample identity.

## Background work

Scanning, analysis, waveform generation, similarity indexing, file operations, rendering, maintenance, and backups run outside the UI thread.

The user can continue browsing while these Jobs run. Activity state is visible globally and detailed in the Activity Center.

## File safety in the UI

Source-modifying actions use stronger visual treatment than ordinary library actions.

Reference, classification, Collection membership, and preparation recipes are non-destructive.

Move, replace, delete, write-in-place, and overwrite are explicit and reviewed before execution.

## Theme and density

Koffer is dark by default, uses restrained Clay accents, and prioritizes text and waveform contrast.

The UI is dense enough for serious library work but avoids unnecessary chrome. Tables and compact metadata are preferred over large cards for Sample browsing.

## Keyboard behavior

The keyboard is a first-class interaction path.

Core goals:
- focus search instantly;
- traverse results;
- play/stop selection;
- favourite;
- add to Collection;
- open Sample Detail;
- accept/reject Suggestions;
- open Preparation;
- invoke Organize and Metadata actions;
- close focused workspaces and return to prior browser context.

Exact shortcuts are editable in Settings.

## Complete visual reference

The full screen set is in [mockups/](mockups/README.md). Every product-owned screen listed in the Screen Catalog has a corresponding SVG mockup.
