# 1. Product Overview

## What Koffer is
Koffer is a Linux desktop application for maintaining an audio sample library.

It helps users:
- discover audio files stored across selected directories;
- preview and search those files;
- organize useful sounds into Collections;
- classify samples using music-production terminology;
- receive local suggestions about what a sample may contain;
- perform focused sample preparation such as trimming, fading, pitch changes, and conversion;
- find related material without remembering its original folder structure.

Koffer is intended for musicians, producers, beatmakers, samplers, sound designers, DJs, and anyone with a substantial collection of audio material.

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
1. Add one or more Sources.
2. Let Koffer scan supported audio files.
3. Browse, search, preview, and filter the discovered material.
4. Review suggested classifications.
5. Keep files where they are, copy them, or move selected files into a managed library.
6. Add useful Samples to Collections.
7. Prepare a Sample non-destructively.
8. Render or export a prepared copy when needed.

## Non-destructive principle
Koffer should preserve source audio by default.

Editing controls describe a preparation recipe until the user deliberately renders or exports a new file. Moving, replacing, or deleting source material must never happen as a side effect of browsing, tagging, or previewing.
