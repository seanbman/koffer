# 33. Koffer User Manual

## What Koffer is

Koffer is a Linux desktop application for people who work with large collections of audio samples.

It helps you:

- find sounds quickly;
- hear them immediately;
- understand what they are;
- organize them without duplicating files unnecessarily;
- edit their descriptive information;
- prepare and reshape audio non-destructively;
- export new versions;
- discover similar sounds;
- recover safely when files or drives move.

Koffer is not a multitrack DAW. It is a sample library and sample-preparation workstation.

## First launch

On first launch, Koffer opens to the Welcome screen.

The main action is **Add Source**.

A Source is a folder Koffer is allowed to scan. Adding a Source does not move, copy, delete, or rewrite the audio in that folder.

You can add a Source by:

- clicking Add Source and choosing a directory;
- dragging a directory onto the Welcome screen.

After you add the Source, Koffer begins indexing in the background and opens the Library. You can start using discovered Samples while indexing continues.

## The main window

Koffer has four persistent regions.

### Navigation

The left side gives access to:

- Library;
- Favourites;
- Recents;
- Review;
- Collections;
- Saved Searches;
- Sources;
- Activity;
- Settings.

### Main workspace

The center changes depending on what you are doing.

Most of the time it is the Library table.

### Inspector

The right side shows details about the currently selected Sample.

You can collapse it when you need more room.

### Transport

The bottom strip controls preview playback.

It shows the current Sample, play/pause, restart, seek position, duration, loop state, and preview gain.

## Adding and scanning Sources

Open **Sources** to see every indexed directory.

A Source shows:

- online/offline state;
- indexed Sample count;
- pending analysis;
- issue count;
- last successful scan;
- current scan status.

### Rescan

Use Rescan when files were added or changed outside Koffer.

Scanning runs in the background.

### Disable

Disabling a Source keeps its Koffer records but stops normal scanning/analysis until re-enabled.

### Remove from Koffer

Removing a Source removes Koffer's index records for that Source.

It does not delete the audio folder from disk.

Koffer must show a clear confirmation explaining this.

### Exclusions

A Source can exclude files/folders by rules.

Before Koffer applies changed rules it previews how many supported files would be excluded.

Exclusions affect indexing, not the files themselves.

## Browsing the Library

The Library is designed for thousands or tens of thousands of Samples.

Each row can show useful columns such as:

- name;
- Sample Type;
- Instrument / Source;
- duration;
- BPM;
- key;
- format;
- availability;
- analysis/review status.

Click a column heading to sort.

Select rows with normal desktop selection behavior.

### Search

Use the search field to find names, paths, tags, classifications, and indexed metadata.

### Filters

Open Filters when you need structured criteria.

You can combine filters such as:

- Sample Type;
- Instrument / Source;
- Role;
- Genre / Style;
- Character;
- BPM;
- key;
- duration;
- format;
- Collection;
- tags;
- analysis state.

### Saved Search

A Saved Search stores the current query/filter definition, not a frozen list of files.

When you open it later, Koffer runs the query against the current library.

### Favourites

Mark frequently used Samples as favourites.

### Recents

Recents reflects Samples you recently previewed or used in Koffer.

## Previewing Samples

Select a Sample and press Play.

The global transport remains available while you browse.

Useful playback actions:

- Play/Pause;
- Restart;
- seek;
- Preview Loop;
- preview gain;
- optional auto-preview if enabled in Settings.

Playback is for auditioning. It does not change the audio file.

## The Sample screen

Double-click a Sample or choose Open Sample.

The Sample screen is designed around what a musician wants to know.

At a glance it should show:

- filename/title;
- artwork when available;
- large waveform;
- availability;
- duration and core technical facts;
- confirmed classifications;
- pending Suggestions;
- BPM/key when known;
- tags;
- Collection membership;
- whether sound edits are saved.

Primary actions:

- **Edit Sound**;
- **Edit Info**;
- **Find Similar**;
- **Add to Collection**.

Less common actions such as Organize and Reveal in Files live in a secondary/context menu.

### File Details

File Details includes factual properties such as:

- path;
- file type;
- codec/container;
- sample rate;
- bit depth;
- channels;
- size.

This information is normally collapsed or secondary.

### Analysis Details

Analysis Details explains how Koffer reached Suggestions.

You do not need this section for normal use.

## Editing classifications

Koffer classifications are library metadata.

They do not automatically rewrite the audio file.

You can edit:

### Sample Type

Examples:

- One-shot;
- Loop;
- Phrase;
- Stem;
- Track;
- Texture;
- Ambience;
- SFX.

### Instrument / Source

Examples:

- Kick;
- Snare;
- Hi-hat;
- Percussion;
- Bass;
- Guitar;
- Piano;
- Synth;
- Vocal;
- Foley.

A Sample can have more than one useful label.

### Musical Role

Examples:

- Percussive;
- Rhythmic;
- Melodic;
- Harmonic;
- Atmospheric;
- Transitional;
- Vocal;
- Effect.

### Genre / Style

Multiple values can apply.

### Character

Examples:

- Dark;
- Bright;
- Warm;
- Cold;
- Clean;
- Dirty;
- Lo-fi;
- Acoustic;
- Electronic;
- Distorted;
- Dry;
- Wet.

### Tags

Tags are free-form personal labels.

## Local AI analysis

Koffer can use a local AI model to help identify sounds.

The model runs on your computer.

Your audio is not uploaded for classification.

### Install the local model

Open:

**Settings → Analysis**

If the model is not installed, Koffer explains what it does and offers **Install Model**.

The model download is software/model data coming to your computer. It is not your audio being uploaded.

### Automatic analysis

When the model is installed and Local AI is enabled, Koffer can analyze newly discovered Samples automatically.

You can control automatic analysis in Settings.

### Analyze an existing library

Choose **Analyze Existing Library** from Settings → Analysis.

Koffer queues missing analysis in the background.

Activity shows progress.

### What Koffer suggests

Depending on the sound and available evidence, Suggestions may include:

- Kick;
- Snare;
- Drum;
- Vocal;
- Guitar;
- Synth;
- One-shot;
- Loop;
- Percussive;
- Melodic;
- likely BPM;
- likely key;
- character/style hints.

Suggestions are not treated as confirmed facts.

### Reviewing Suggestions

Open **Review**.

You can:

- Accept;
- Edit & Accept;
- Reject;
- leave pending.

Accepted classifications become green/confirmed library metadata.

Rejected Suggestions remain in history so Koffer does not pretend they never happened.

### Why?

Open **Why this suggestion?** when you want the explanation.

Koffer should use plain language such as:

- “The local AI model strongly detected bass drum.”
- “The filename contains ‘kick’.”
- “The sound is short and strongly percussive.”

Advanced technical evidence is available under Analysis Details.

## Editing a sound

Choose **Edit Sound**.

This opens the Sample Workbench.

The editor is non-destructive.

Moving controls changes an edit recipe and preview. It does not rewrite the source audio.

### Waveform

Use the large waveform to:

- seek;
- zoom;
- pan;
- set trim start/end;
- set a preview loop;
- adjust fades.

### Trim

Drag the left/right trim handles.

The dimmed regions are excluded from the edited version.

### Fade

Drag fade handles or enter exact fade times.

### Gain

Adjust level in dB.

### Normalize

Enable Normalize and choose the target when needed.

### Pitch

Transpose by semitones and fine cents.

Pitch shifting is independent of time stretch.

### Time stretch

Adjust duration/tempo while preserving pitch when supported.

For loops, Koffer may let you enter Source BPM and Target BPM.

### Reverse

Toggle Reverse to preview/render the Sample backwards.

### A/B

Use A/B to compare:

- A — original;
- B — current edit.

### Save Recipe

Save Recipe stores the non-destructive edit settings in Koffer.

It does not create a new audio file.

### Reset

Reset restores the editor to the original/default recipe.

### Export Copy

Export Copy creates a new audio file with the chosen edits.

Before export, Koffer shows:

- source;
- edits;
- output format;
- sample rate;
- bit depth;
- channels;
- destination;
- filename;
- metadata/artwork carry-over;
- conflict policy.

The source file remains unchanged.

## Editing file information

Choose **Edit Info**.

Koffer separates:

### Library information

Koffer-only classifications/tags.

These are safe to change and do not rewrite audio.

### Embedded metadata

Where the file format supports it, Koffer can edit fields such as:

- title;
- artist;
- album;
- genre;
- year/date;
- comment;
- composer;
- copyright;
- artwork.

Koffer must tell you when the format cannot safely store a field.

### Update Original

Writes supported metadata into the selected existing file.

This changes the file and is explicitly identified.

### Write to Copy

Writes metadata to a new/copy output while preserving the original.

## Artwork

For supported formats you can:

- view embedded artwork;
- add/replace artwork;
- remove artwork;
- carry artwork into rendered copies.

External artwork found near a file is visually distinguished from artwork embedded in the file.

## Collections

Collections are logical groups inside Koffer.

Adding a Sample to a Collection does not copy the audio.

Use Collections for things like:

- Favourite Kicks;
- Drum Breaks;
- Dark Textures;
- Project X;
- Live Set.

You can add/remove multiple Samples.

Deleting a Collection leaves the audio files intact.

## Organizing files

Koffer supports three distinct operations.

### Reference

Keep the file where it is.

### Copy

Create another file at a destination while keeping the original.

### Move

Relocate the original file.

Copy/Move show a review before filesystem mutation.

### Conflicts

If the destination already has a file, Koffer never silently overwrites it.

Available resolutions may include:

- Keep Both;
- Skip;
- Replace;
- Choose Destination.

Future/advanced conflict actions appear only when fully implemented.

## Find Similar

Choose **Find Similar** on a Sample.

When semantic embeddings are available, Koffer shows nearby sounds ranked by audio similarity.

You can preview results directly.

Filters can narrow results, but the ranking remains audio-similarity ranking.

## Activity

Activity shows work running in the background:

- Source scans;
- waveform builds;
- deterministic analysis;
- local AI analysis;
- similarity indexing;
- copy/move;
- metadata writes;
- renders;
- maintenance.

Closing Activity does not stop Jobs.

## Missing/offline files

Koffer treats offline storage differently from deletion.

Open Recovery when you see missing/offline state.

Depending on the problem you may:

- recheck Source;
- locate a missing file;
- accept a changed file;
- leave unresolved;
- remove a stale Koffer index entry.

Removing a stale entry removes only Koffer's record. It does not delete disk content.

## Settings

### General

Application behavior and workspace preferences.

### Library / Analysis

Source/index/analysis behavior, including Local AI.

### Audio & Appearance

Preview gain, auto-preview, loop behavior, UI density, visual preferences, and audio output where available.

## Maintenance

Maintenance actions must state what they preserve.

Examples:

- backup;
- restore;
- rebuild filesystem index;
- rebuild waveforms;
- rebuild analysis;
- rebuild similarity index;
- clear rebuildable cache;
- database integrity check.

Maintenance must never silently erase Collections, user tags, confirmed classifications, or saved edit recipes.

## Diagnostics

About & Diagnostics provides:

- Koffer version/build;
- data/cache/config paths;
- model version/state;
- dependency/license access;
- diagnostic export.

Diagnostic export excludes audio by default.

## Safety summary

Koffer follows these rules:

- adding a Source does not move files;
- classification changes do not rewrite audio;
- editing sound is non-destructive until Export Copy;
- model analysis does not auto-confirm classifications;
- copy/move conflicts are reviewed;
- Collection deletion does not delete audio;
- offline does not mean deleted;
- diagnostics do not contain audio by default;
- Local AI runs on-device.
