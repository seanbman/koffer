# 21. Packaging, CI, and Release

## Supported product artifact

Primary release artifact: x86_64 Linux AppImage.

The application must not require:
- source checkout;
- Python installation;
- uv;
- a virtual environment;
- terminal launch.

Later Flatpak/deb/rpm support may be added without changing app architecture.

## Build approach

1. `uv sync --frozen --all-extras`.
2. run quality/test gates.
3. PyInstaller builds a one-directory self-contained application.
4. stage an AppDir:
   - `usr/bin/koffer`;
   - bundled Python/runtime libraries;
   - Qt plugins;
   - application resources;
   - desktop file;
   - icons;
   - license notices;
   - packaged FFmpeg/ffprobe if approved.
5. create `AppRun` with defensive environment handling.
6. run AppDir smoke.
7. build AppImage with pinned AppImage tooling.
8. run AppImage smoke outside the source tree.
9. generate SHA256.
10. generate dependency/license manifest and SBOM.

Do not create an AppImage launcher that silently falls back to a system `koffer` executable.

## AppRun requirements

- uses paths relative to APPDIR;
- never assumes `PYTHONPATH` exists;
- does not require current working directory;
- preserves user XDG environment;
- exits with a useful nonzero error if runtime files are missing.

## Desktop integration

Ship:
- `io.github.seanbman.Koffer.desktop` or finalized reverse-DNS ID;
- icons at standard sizes;
- application name Koffer;
- Audio/Utility category as appropriate;
- no terminal requirement.

Validate desktop file in CI where validator exists.

## FFmpeg

If FFmpeg binaries are bundled:
- use a build whose license configuration is compatible with Koffer distribution;
- include required license text/notices;
- record version/configuration/source URL;
- do not assume "FFmpeg is LGPL" without inspecting the actual build configuration.

If a compatible bundled build cannot be produced, package capability must explicitly resolve a system FFmpeg and the release gate must test the supported environment. The preferred end state is self-contained.

## Model artifacts

Large semantic weights are not stored in Git.

Default release behavior:
- app includes model provider/runtime support;
- Settings offers install/enable;
- downloader uses HTTPS official source;
- manifest includes model name/version/expected SHA256/size/source/license note;
- download goes to XDG data/cache model directory;
- checksum verified before activation;
- failed download leaves application fully usable.

No model weight is bundled into the AppImage until redistribution is explicitly documented as approved.

## GitHub Actions

Required workflows:

### qa.yml

On PR/push to dev:
- Python 3.12 environment;
- frozen dependency install;
- Ruff lint/format check;
- mypy;
- unit + integration;
- pytest-qt with `QT_QPA_PLATFORM=offscreen`;
- coverage gate;
- license/dependency verification.

### package.yml

On dev and release candidate tags:
- build PyInstaller output;
- stage AppDir;
- build AppImage;
- launch smoke;
- upload CI artifact.

### model-smoke.yml

Scheduled/manual:
- retrieve model artifact;
- verify checksum;
- run one semantic inference;
- build/query one similarity index.

### release.yml

On signed/approved version tag:
- rerun full QA;
- build clean AppImage;
- package smoke;
- produce SHA256;
- produce SBOM/license inventory;
- publish release artifacts.

## CI display/runtime

UI tests run headless through Qt offscreen/Xvfb as required.

Packaging smoke must include at least one environment that approximates a clean supported Linux desktop rather than the development virtualenv.

## Versioning

Use semantic versioning.

Before 1.0:
- 0.x development releases are allowed.
- First feature-complete release candidate may be `v0.9.0-rc.1`.
- `v1.0.0` means the documented V1 product-complete exit criteria are met.

Version source is single-sourced from package metadata.

## Release branch flow

During active development:
- accepted Orders -> `dev`.

Release candidate:
1. freeze scope;
2. full QA and AppImage gate;
3. fix defects through normal Dreadnought Orders;
4. verify docs;
5. merge/promote `dev` -> `main`;
6. tag;
7. release workflow builds/publishes immutable artifacts.

Never build a release from an uncommitted local tree.

## Release checklist

- [ ] all S00–S21 acceptance green;
- [ ] flows A–J green;
- [ ] no P0/P1;
- [ ] migrations tested;
- [ ] backup/restore tested;
- [ ] 100k benchmark acceptable;
- [ ] Wayland smoke;
- [ ] X11 smoke where supported;
- [ ] PipeWire playback smoke;
- [ ] model-disabled smoke;
- [ ] model-enabled smoke;
- [ ] AppImage clean launch;
- [ ] desktop file/icons valid;
- [ ] source safety regression green;
- [ ] dependency licenses reviewed;
- [ ] FFmpeg configuration recorded;
- [ ] model manifest/checksum valid;
- [ ] diagnostics excludes audio;
- [ ] docs match product;
- [ ] CHANGELOG/release notes;
- [ ] SHA256 + SBOM + license notices;
- [ ] Dreadnought/Grapher campaign complete.
