# 32. Local ML Classification and Analysis Specification

## Product decision

Local machine learning is not a speculative future feature. It is a required V1 capability.

Koffer may run in degraded mode when the model is not installed, but a release candidate cannot be declared complete until the model-enabled path is proven end-to-end.

## User promise

The user adds a messy Sample folder and Koffer helps answer:

- What kind of sample is this?
- What instrument/source is heard?
- Is it a one-shot, loop, phrase, texture, ambience, stem, track, or SFX?
- What musical role does it serve?
- What styles/characteristics are plausible?
- What BPM/key information can be estimated?
- What other sounds are sonically similar?

The system proposes answers. It does not pretend the model is infallible.

## Analysis stack

V1 combines:

1. filename/path heuristics;
2. embedded metadata;
3. deterministic DSP;
4. local semantic audio model;
5. evidence fusion;
6. user review;
7. embeddings for Similar Sounds.

No cloud audio upload is required.

## Semantic provider

Current canonical V1 semantic provider remains PANNs-compatible Cnn14 at 32 kHz as defined in `19-audio-metadata-analysis-pipeline.md` and `23-dependencies-models-and-licensing.md`.

Codex must not replace the provider casually. A change to ONNX or another model requires a documented migration preserving the provider interface and measured classification/similarity quality.

## Model setup UX

Settings → Analysis contains a Local AI card.

States:

### Not installed

Shows:

- “Local AI model not installed”;
- what it does;
- approximate download/disk size from manifest;
- privacy statement “Runs on this computer”;
- Install Model button.

### Downloading

Shows:

- progress bytes/percent;
- source host;
- Cancel;
- checksum verification state.

### Installed, disabled

Shows Enable Local AI.

### Enabled

Shows:

- provider/model friendly name;
- version;
- disk usage;
- CPU/GPU mode;
- last successful inference;
- embedding index state;
- Analyze Existing Library;
- Rebuild Suggestions;
- Rebuild Similarity Index;
- Uninstall Model.

### Error

Shows an actionable message and Retry/Repair.

Do not show a naked model path or Python exception as the main copy.

## First-run behavior

Koffer does not silently download a large model without user action.

After the first Source is added, an unobtrusive prompt may explain:

“Want Koffer to identify sounds automatically? Install the local AI model. Audio stays on this computer.”

The prompt can be dismissed. Model installation remains accessible from Settings.

## Automatic scheduling

When Local AI is installed and enabled:

- newly discovered playable Samples automatically queue deterministic analysis;
- semantic analysis queues after technical probe as resources permit;
- embeddings queue from the same semantic pass;
- UI shows analysis progress;
- duplicate unchanged content should reuse valid derived data when identity/fingerprint policy allows;
- editing tags/classification does not require re-running the model;
- changed source audio invalidates derived analysis.

The user should not have to manually press “Analyze” on every new file.

## Backfill

“Analyze Existing Library” queues all eligible Samples missing valid semantic output for the active model version.

Before start, show:

- sample count;
- model;
- estimated workload category (small/medium/large), not fake exact ETA;
- CPU usage preference if supported;
- Pause/Cancel behavior.

Activity Center shows progress.

## Resource controls

Settings should offer pragmatic controls:

- Enable Local AI;
- Analyze new Samples automatically;
- background analysis intensity: Low / Normal / High;
- pause analysis on battery if detectable;
- optional GPU toggle only when supported;
- rebuild controls.

Do not let inference freeze playback or browsing.

## Provider output

For each Sample, semantic inference returns:

- top-k AudioSet-style labels and probabilities;
- 2048-d embedding;
- provider/model/version;
- source fingerprint;
- analysis timestamp.

Raw labels are evidence, not final taxonomy.

## Taxonomy mapping

Use versioned `panns_v1.json`.

Mappings may produce one or more Koffer proposals.

Examples:

- Bass drum → Instrument/Source: Kick; broader Drum;
- Snare drum → Snare; Drum;
- Hi-hat → Hi-hat; Percussion;
- Cymbal → Cymbal;
- Drum → Drum kit/Percussion where appropriate;
- Singing → Vocal;
- Speech → Vocal/Speech-style tag if taxonomy supports it;
- Acoustic guitar → Guitar; Acoustic;
- Electric guitar → Guitar; Electronic/Electric character only where mapping is semantically defensible;
- Piano → Piano; Keys;
- Organ → Organ; Keys;
- Synthesizer → Synth; Electronic;
- Bass guitar → Bass; Guitar;
- Violin/Fiddle → Strings;
- Brass instrument labels → Brass;
- Wind labels → Woodwind where specific;
- Water/rain/wind/nature events → Field recording/Ambience evidence depending other context;
- Foley-like events → Foley/SFX evidence.

Do not map unrelated AudioSet labels just to fill every classification dimension.

## Structural Sample Type

PANNs does not directly solve one-shot vs loop reliably. Fuse deterministic evidence.

### One-shot evidence

- short duration;
- strong onset;
- rapid decay;
- filename tokens one-shot, hit, stab;
- drum semantic labels.

### Loop evidence

- filename BPM/loop tokens;
- stable repeating onset pattern;
- duration close to plausible musical bar lengths at estimated BPM;
- tempo confidence.

### Phrase/Stem/Track

Use duration, folder context, embedded metadata, and path tokens. Avoid overconfident classification.

## BPM and key

BPM/key are deterministic/feature-analysis outputs unless embedded or user-confirmed.

They can appear as Suggestions:

- “BPM 124 · 82%”
- “Key C minor · 71%”

User confirmation upgrades status.

## Character/style

Character and genre/style may be uncertain. Use conservative fusion:

- filename/folder/embedded genre carry meaningful weight;
- semantic labels can support acoustic/electronic/vocal/instrumental traits;
- spectral DSP can support bright/dark, clean/noisy, transient/sustained only when calibrated.

Do not fabricate high confidence for subjective labels.

## Evidence fusion

Every final Suggestion stores explainable evidence.

Default presentation is plain-language “Why?” bullets, not JSON.

Example:

**Kick · 94%**

Why:
- Local AI strongly detected bass drum.
- Filename contains “kick”.
- The sound is short and strongly percussive.

Advanced Analysis Details may expose the structured record.

## Confidence bands

Until calibrated by a fixture corpus, use conservative UI bands:

- 0.85–1.00: Strong suggestion;
- 0.65–0.849: Likely;
- 0.45–0.649: Possible;
- below 0.45: normally keep as diagnostic evidence rather than cluttering the review queue.

These are product presentation bands, not claims of statistical calibration.

Never auto-confirm based on confidence alone.

## Suggestion review

The user can:

- Accept;
- Edit & Accept;
- Reject;
- leave pending;
- batch accept a clearly scoped set.

Accepted classification becomes confirmed Koffer metadata.

Rejected Suggestion remains in review history/provenance and should not immediately reappear unchanged after reanalysis unless model/version/evidence materially changed.

## Sample screen presentation

Classification card shows confirmed chips.

Suggestions card shows 1–5 most relevant pending suggestions with confidence.

Example:

- Kick — Strong — 94%
- One-shot — Strong — 91%
- Percussive — Likely — 83%
- Electronic — Possible — 62%

Buttons: Accept, Edit, Reject, Review All.

No raw provider text on this card.

## Similar Sounds

Embeddings generated during semantic analysis feed the HNSW index.

Similar Sounds requires:

- seed visible;
- score visible;
- direct preview;
- filter by classifications/availability;
- explain if index is stale/building;
- rebuild after model version changes.

Do not call metadata filtering “similarity”.

## Analysis Details disclosure

Advanced details may show:

- semantic top-k labels;
- raw probabilities;
- deterministic feature summary;
- filename/path evidence;
- mapping version;
- provider/model version;
- source fingerprint;
- analysis timestamp.

This information is not the default user surface.

## Failure behavior

One bad file must not stop library analysis.

Record itemized failures:

- decode failed;
- unsupported format;
- model missing;
- model load failed;
- inference failed;
- cancelled.

User can Retry Failed.

## Privacy

No audio, embeddings, filenames, paths, or metadata leave the machine for core ML operation.

Model download may contact the official artifact host. The UI distinguishes downloading model software from uploading user audio.

## Performance and concurrency

- inference runs in background worker lane;
- model loads once per worker/process strategy;
- cap concurrent semantic inference conservatively;
- playback/UI remain responsive;
- cancellation occurs between items;
- avoid loading full Source library into RAM;
- persist progress.

## Required tests

### Provider

- model absent;
- manifest valid/invalid;
- checksum failure;
- model load;
- inference on generated/open fixture;
- stable output shape;
- embedding dimension;
- cancellation.

### Mapping

- representative AudioSet labels;
- unknown labels;
- one label mapping to multiple classifications;
- version change invalidation.

### Scheduling

- new scan auto-queues when enabled;
- does not queue semantic when disabled;
- backfill;
- restart recovery;
- unchanged Samples do not churn.

### Suggestions

- evidence saved;
- confidence bands;
- accept/edit/reject;
- confirmed metadata not overwritten;
- rejected history preserved.

### Similarity

- embeddings persisted;
- index build/query;
- seed excluded from results;
- model version invalidates/rebuilds index.

## Mandatory release proof

Release candidate evidence must include:

1. clean install;
2. install local model;
3. add a Source containing test audio;
4. semantic Jobs run automatically;
5. at least one mapped Suggestion appears;
6. user accepts/edits a Suggestion;
7. confirmed classification appears in Library/Sample;
8. embedding index builds;
9. Similar Sounds returns and previews results;
10. no network request contains user audio.

Without this proof, local ML is not implemented.
