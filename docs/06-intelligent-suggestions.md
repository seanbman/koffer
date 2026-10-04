# 6. Intelligent Suggestions

Koffer may analyze Samples and propose useful classifications. The system reduces library maintenance rather than making irreversible decisions.

## Evidence sources

### Filename context
Terms such as kick, snr, vox, 808, loop, 120bpm, or Cm can provide useful evidence.

### Folder context
A generic filename such as 07.wav can still be informative when found under a path like Soul / Rhodes / Chords / 90 BPM / 07.wav.

### Embedded metadata
Where available, Koffer may use title, artist, genre, comments, tempo, and musical-key fields.

### Audio properties
Useful signals include duration, transient structure, spectral characteristics, tonal vs percussive content, silence, channel configuration, likely tempo, and likely key.

### Local model inference
Koffer may use on-device audio models to produce semantic labels and audio embeddings.

The current planning direction is to evaluate permissively licensed local models such as PANNs alongside deterministic DSP and path/metadata heuristics.

## Confidence
Suggestions should include confidence where useful.

Example:
- One-shot — 98%
- Drum — 99%
- Kick — 97%
- Electronic — 88%

Confidence communicates uncertainty; it must not imply that a suggestion is fact.

## Review workflow
Users should be able to accept, reject, or edit one suggestion; accept several suggestions together; and apply accepted classification to a batch when appropriate.

## Learning from corrections
A future Koffer version may use user corrections as local evidence for better suggestions.

Any such learning should remain local by default and must not require sending the user's library to a hosted service.

## Privacy
The target behavior is offline inference.

Koffer should not upload audio for classification unless a future optional network feature is deliberately introduced and clearly disclosed.

## Background analysis
Inference should occur outside the primary interaction path.

A newly discovered Sample can appear in the library before deeper analysis is complete. Analysis state should be visible without blocking browsing.
