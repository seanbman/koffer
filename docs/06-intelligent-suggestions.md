# 6. Intelligent Suggestions

Koffer analyzes Samples and proposes useful classifications. The system reduces library maintenance without making irreversible classification decisions.

## Evidence sources

### Filename context
Terms such as kick, snr, vox, 808, loop, 120bpm, or Cm can provide useful evidence.

### Folder context
A generic filename such as 07.wav can still be informative when found under a path like Soul / Rhodes / Chords / 90 BPM / 07.wav.

### Embedded metadata
Where available, Koffer uses title, artist, genre, comments, tempo, and musical-key fields as evidence.

### Audio properties
Useful signals include duration, transient structure, spectral characteristics, tonal vs percussive content, silence, channel configuration, likely tempo, and likely key.

### Local model inference
Koffer supports on-device semantic audio inference and embeddings through a local provider. The V1 provider is PANNs-compatible and operates alongside deterministic DSP plus path/metadata heuristics. The application remains usable when the semantic model is not installed; model installation and licensing behavior are defined in `23-dependencies-models-and-licensing.md`.

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
V1 records user accept/reject/edit outcomes as local review history and provenance. It does not retrain a model from those corrections. Any future adaptive learning remains local by default and requires a deliberate product/version decision.

## Privacy
Semantic inference is local and offline after required model artifacts are installed.

Koffer should not upload audio for classification unless a future optional network feature is deliberately introduced and clearly disclosed.

## Background analysis
Inference should occur outside the primary interaction path.

A newly discovered Sample can appear in the library before deeper analysis is complete. Analysis state should be visible without blocking browsing.
