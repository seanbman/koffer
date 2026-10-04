# 1. Product Overview

## What Koffer is
Koffer is a **full-fledged Linux desktop application** for maintaining an audio sample library.

It is intended to behave like a real desktop program rather than a browser app, web wrapper, or lightweight utility. Koffer should install, launch, integrate with the desktop environment, access local and removable storage with clear permissions, maintain persistent local state, and remain useful offline.

It helps users:
- discover audio files stored across selected directories;
- preview and search those files;
- organize useful sounds into Collections;
- classify samples using music-production terminology;
- receive local suggestions about what a sample may contain;
- edit compatible embedded metadata such as artist, album, genre, and artwork;
- perform focused sample preparation such as trimming, fading, pitch changes, and conversion;
- find related material without remembering its original folder structure.

Koffer is intended for musicians, producers, beatmakers, samplers, sound designers, DJs, and anyone with a substantial collection of audio material.

## Desktop application requirements

Koffer should provide the expectations of a mature Linux desktop application, including:
- an installable application package;
- a normal application launcher entry and icon;
- proper desktop windowing and keyboard focus behavior;
- native file and directory selection;
- drag-and-drop where useful;
- clipboard support;
- keyboard shortcuts;
- persistent preferences and window state;
- background indexing and analysis without blocking the interface;
- notifications or in-app status for long-running operations;
- safe handling of removable and unavailable storage;
- clear error reporting and recovery;
- offline-first operation for core library features.

Koffer's primary V1 distribution is a self-contained x86_64 Linux AppImage. End users do not require Python, a development environment, uv, a source checkout, or a terminal to use Koffer normally. Additional package formats may follow without changing the product architecture.

## What Koffer is not
Koffer is not a digital audio workstation.

It does not aim to provide song arrangement, multitrack production timelines, a project mixer, MIDI sequencing, automation lanes, plug-in hosting as a primary workflow, or full project composition.

Koffer prepares and organizes the material used by those tools.

## Core concepts

### Source
A directory the user has authorized Koffer to scan.

### Sample
An audio file known to Koffer. A Sample may remain at its original location or live in a Koffer-managed library.

### Collection
A user-defined group of Samples. Collections are organizational and do not require duplicate audio files.

### Metadata
Information describing a Sample, including technical properties and musical classification.

### Suggestion
A classification proposed by Koffer's analysis system. Suggestions are not treated as user-confirmed metadata until accepted.

## Core journey
1. Launch Koffer from the Linux desktop.
2. Add one or more Sources using normal desktop file/directory selection.
3. Let Koffer scan supported audio files in the background.
4. Browse, search, preview, and filter the discovered material.
5. Review suggested classifications.
6. Keep files where they are, copy them, or move selected files into a managed library.
7. Add useful Samples to Collections.
8. Prepare a Sample non-destructively.
9. Render or export a prepared copy when needed.

## Non-destructive principle
Koffer should preserve source audio by default.

Editing controls describe a preparation recipe until the user deliberately renders or exports a new file. Moving, replacing, deleting, or rewriting metadata on source material must never happen as a side effect of browsing, tagging, previewing, or accepting library-only classifications.
