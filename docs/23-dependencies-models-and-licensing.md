# 23. Dependencies, Models, and Licensing

## Policy

Koffer source is MIT. Every distributed dependency/artifact must have a recorded license and distribution rationale.

A dependency lock is required. No agent may casually replace a core dependency because another library is familiar.

## Required production dependencies

The intended stack is:

| Capability | Dependency / tool | Role |
|---|---|---|
| Desktop UI | PySide6 / Qt 6 | windows, models, widgets, Qt Multimedia |
| XDG paths | platformdirs | config/data/cache resolution |
| Metadata | mutagen | audio tag/artwork read/write |
| Numeric DSP | numpy | arrays/features/waveforms |
| Music analysis | librosa | BPM/key baseline and DSP |
| Audio file helper | soundfile where useful | fixture/read helpers; FFmpeg remains broad codec layer |
| Semantic inference | torch + panns-inference/provider adapter | local PANNs CPU inference |
| ANN similarity | hnswlib | cosine embedding index |
| Packaging | PyInstaller | self-contained Python/Qt bundle |
| Test | pytest, pytest-qt, coverage | quality |
| Static | ruff, mypy | lint/format/types |

The standard library provides SQLite, hashing, JSON, subprocess, pathlib, logging, concurrency primitives.

## External binary capability

FFmpeg/ffprobe are the authoritative broad codec/probe/render tools.

Pin/document the build used for releases.

Invoke with argv arrays and `shell=False`.

## Dependency manager

Use `uv`.

Commit:
- `pyproject.toml`;
- `uv.lock`.

CI uses frozen lock installs.

Runtime users do not need uv.

## Version constraints

During initial implementation:
- constrain compatible major/minor ranges in pyproject;
- lock exact transitive versions in uv.lock;
- update dependencies through explicit maintenance Orders with tests.

Do not hand-edit lock resolution.

## PANNs

The official PANNs/audio tagging project code is MIT licensed.

Policy for pretrained weights:
- do not assume code license automatically settles weight redistribution;
- do not commit weights to Git;
- before bundling weights, record source, license/terms, checksum, and redistribution decision;
- until that record is complete, download weights from official artifact source at runtime;
- verify SHA256 from a checked-in manifest;
- allow uninstall/re-download;
- keep Koffer usable when model is absent.

Model manifest fields:
~~~json
{
  "provider": "panns",
  "model": "Cnn14",
  "version": "upstream-artifact-version",
  "source_url": "official artifact URL",
  "sha256": "...",
  "size_bytes": 0,
  "license_note": "see THIRD_PARTY_NOTICES"
}
~~~

## Model runtime size

PANNs/PyTorch can make packaging large. Product correctness outranks package minimalism.

If later measurement justifies converting the provider to ONNX Runtime, do that as an explicit architecture Order while preserving the SemanticProvider interface and validating output quality. Do not silently swap model behavior during unrelated work.

## FFmpeg licensing

FFmpeg licensing depends on build configuration.

Release documentation records:
- exact version;
- source;
- configure flags/build provenance;
- whether GPL components are enabled;
- applicable license obligations.

Preferred bundled build avoids unnecessary GPL/nonfree components. If product-required codecs force different obligations, resolve before release.

## Fonts and icons

Prefer Qt/system fonts to avoid font redistribution complexity.

Koffer-owned icons/assets must have source provenance. Third-party icon sets require license attribution.

Do not commit font binaries merely to match mockups unless explicitly approved and licensed.

## Test audio

Generated synthetic fixtures are preferred.

Any recorded/open audio fixture must include:
- source;
- license;
- attribution requirements.

Commercial sample packs never enter the repository.

## License inventory

Add a generated `THIRD_PARTY_NOTICES.txt` at packaging time.

CI should fail if a direct production dependency lacks an allowed/known license record.

## Security maintenance

Dependency update Orders inspect:
- upstream security notices;
- breaking changes;
- native binary changes;
- package-size delta;
- AppImage smoke.

Avoid automatic major-version upgrades without verification.
