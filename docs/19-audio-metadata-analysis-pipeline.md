# 19. Audio, Metadata, and Analysis Pipeline

## Supported file scope

Initial required read/play/index support:
- WAV;
- AIFF/AIF;
- FLAC;
- MP3;
- OGG/Vorbis;
- M4A/AAC where the packaged FFmpeg/Qt backend supports it.

Unsupported media is not indexed as a playable Sample.

## Technical probing

Use ffprobe through an argv-based subprocess wrapper, never shell string interpolation.

Record:
- container;
- codec;
- duration;
- sample rate;
- channels/layout;
- bitrate;
- bit depth when reliably derivable.

Probe failure is visible and does not crash Source scanning.

## Playback

PlaybackService wraps Qt Multimedia.

Required API concepts:
- load(sample/path);
- play;
- pause;
- stop/restart;
- seek milliseconds;
- loop region;
- gain/volume;
- state/position/error signals.

The UI never controls QMediaPlayer directly outside the adapter layer.

If a format probes successfully but cannot play through Qt Multimedia, Koffer reports playback unsupported/error while retaining the indexed Sample.

## Waveform cache

Generate a compact min/max peak envelope from decoded PCM.

Requirements:
- cache key includes source fingerprint + waveform pipeline version;
- lazy generation on demand plus optional background prebuild;
- zoomed preparation view may request a higher-resolution envelope;
- cache corruption causes rebuild, not data loss.

## Preparation recipe

Canonical JSON v1:

~~~json
{
  "version": 1,
  "trim": {"start_ms": 0, "end_ms": null},
  "fade_in_ms": 0,
  "fade_out_ms": 0,
  "gain_db": 0.0,
  "normalize": {"enabled": false, "target_peak_dbfs": -1.0},
  "transpose_semitones": 0.0,
  "fine_cents": 0,
  "time_stretch_ratio": 1.0,
  "reverse": false,
  "channels": "source",
  "sample_rate_hz": "source",
  "bit_depth": "source",
  "output_format": "wav"
}
~~~

A recipe change never modifies source audio.

## Preview strategy

Fast operations can be approximated/precomputed for preview if necessary, but rendered output must use the authoritative render graph.

When exact real-time pitch/stretch preview is unavailable, UI clearly indicates preview quality rather than silently changing the final algorithm.

## Render engine

Use FFmpeg filters/capabilities for stable conversion and render operations where possible.

The render service constructs argv safely from typed recipe values.

Authoritative render order:
1. decode;
2. trim;
3. reverse if enabled;
4. time stretch;
5. pitch shift;
6. fades/envelope;
7. gain/normalize;
8. channel conversion;
9. resample;
10. encode;
11. metadata/artwork write/verify.

If algorithm constraints require a different internal order, add regression tests proving the user-visible recipe semantics remain correct and document the change.

## Metadata reader/writer

Use Mutagen behind a format capability adapter.

Expose normalized fields:
- title;
- artist;
- album;
- album_artist;
- genre;
- date;
- track_number;
- comment;
- composer;
- copyright;
- artwork.

The adapter reports for each selected format:
- readable fields;
- writable fields;
- artwork support;
- limitations.

Never catch a field-write exception and continue silently.

## Metadata targets

### Update Original

Explicitly modifies the existing file. The final confirmation identifies exact file count and paths/scope.

### Write to Copy

Creates or uses a copy/output and modifies that target, preserving source.

Koffer-only tags/classifications do not require an embedded write.

## Deterministic analysis

Pipeline v1 computes, when meaningful:
- filename/path token evidence;
- duration class;
- peak/RMS statistics;
- transient/percussive indicators;
- estimated BPM + confidence;
- estimated key/mode + confidence;
- mono/stereo facts.

Use librosa algorithms for baseline BPM/key features with versioned parameters.

Do not assign BPM/key as factual metadata unless it was embedded or user-confirmed. Estimated values are Suggestions/analysis features.

## Semantic analysis

Default semantic provider contract is PANNs-style local audio tagging with embeddings.

The implementation must support:
- provider disabled/unavailable;
- model artifact download/cache;
- CPU inference;
- optional GPU only if detected and explicitly supported;
- cancellation between items;
- versioned provider/model identity;
- top-k label output;
- embedding output.

The application remains fully usable without the semantic model. In that state:
- deterministic Suggestions continue;
- Similar Sounds explains that semantic embeddings are unavailable and offers model setup.

## PANNs policy

Use official PANNs project/model sources. Code is MIT-licensed; pretrained model redistribution must be separately recorded before any weight is bundled. Until redistribution approval is documented, model weights are downloaded at runtime from the official artifact source and verified against a manifest checksum.

Do not commit model weights to Git.

## Evidence fusion

A Suggestion stores evidence rather than one opaque model score.

Example:
~~~json
{
  "filename": {"label": "kick", "score": 0.98},
  "folder": {"label": "drums", "score": 0.85},
  "semantic": {"label": "Bass drum", "score": 0.93},
  "dsp": {"percussive": 0.91}
}
~~~

Fusion rules are deterministic and versioned.

Suggested classification confidence is calibrated product confidence, not raw neural probability.

## Label mapping

AudioSet/PANNs labels do not directly become Koffer taxonomy.

Maintain a versioned mapping file:
`src/koffer/analysis/label_maps/panns_v1.json`

Examples:
- Bass drum -> Instrument/Source: Kick;
- Snare drum -> Snare;
- Hi-hat -> Hi-hat;
- Singing -> Vocal;
- Synthesizer -> Synth.

Unmapped labels may remain diagnostic evidence but are not surfaced as taxonomy values.

## Similarity

Use semantic embedding vectors from the configured provider.

Store vector files in cache as float32 with a small manifest containing:
- sample_id;
- model_version;
- source fingerprint;
- dimensions;
- checksum.

Build hnswlib cosine index per model version.

Search:
1. obtain seed embedding;
2. query HNSW top N;
3. remove seed;
4. apply metadata/availability filters;
5. return similarity score + Sample IDs.

Changing model version invalidates/rebuilds the similarity index without touching Collections or confirmed metadata.

## Source change invalidation

A source fingerprint change invalidates:
- waveform;
- deterministic analysis;
- semantic output;
- embedding;
- similarity membership.

It does not invalidate:
- Collection membership;
- user tags;
- confirmed classifications unless user explicitly chooses to reset them;
- audit history.

## Analysis acceptance

Before final release, fixtures must include:
- short one-shot;
- loop with known BPM;
- tonal sample with known key;
- silence;
- malformed media;
- stereo/mono;
- metadata-rich MP3/FLAC;
- unsupported file;
- semantic provider missing;
- semantic provider success;
- similarity query with known synthetic ranking invariants.
