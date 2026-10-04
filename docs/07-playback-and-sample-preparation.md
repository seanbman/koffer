# 7. Playback and Sample Preparation

Koffer provides focused tools for auditioning and preparing individual audio files. These tools should not evolve into a multitrack DAW.

## Playback
Any supported Sample should be playable directly from the browser.

Playback controls should include play/pause, restart, scrub, loop preview, output level, and optional auto-play while browsing.

## Waveform
The Inspector should show a waveform for the selected Sample.

The waveform supports seeking, zoom, start/end selection, trim preview, and loop preview.

## Trim
Users may set non-destructive start and end points.

Trim state is part of the Sample's preparation recipe until rendered.

## Attack, decay, and fades
Koffer may provide a simple amplitude envelope appropriate to sample preparation:
- attack;
- decay/release behavior;
- fade-in;
- fade-out.

Controls should remain intentionally simpler than synthesizer or DAW automation systems.

## Gain and normalization
Users may adjust gain, preview the result, normalize to a supported target, and render/export when ready.

## Pitch and key
Koffer may support transpose by semitone, fine adjustment in cents, source key display, and target key selection where key is known.

Pitch controls should clearly distinguish pitch shifting from playback-speed changes.

## Time/stretch
Loops and phrases may be time-stretched independently of pitch where supported.

This is a preparation feature, not a sequencing feature.

## Reverse
A Sample may be previewed or rendered in reverse.

## Format preparation
Useful export preparation may include mono/stereo conversion, sample-rate conversion, bit-depth conversion, and target file format.

## Non-destructive edit recipe
Preparation settings should be stored separately from the original audio whenever possible.

Example recipe:
- trim start: 174 ms;
- trim end: 2.84 s;
- transpose: -2 semitones;
- fade-out: 35 ms;
- normalize: enabled.

## Render/export
The user explicitly chooses when to produce a modified audio file.

Possible actions:
- Export Copy
- Render to Collection
- Render to Managed Library

Overwriting an original should not be the normal workflow and must require explicit confirmation if supported at all.
