# Koffer icon set

This directory contains the approved Koffer application identity developed during product planning.

## Files

- `koffer-app-icon.svg` — primary application icon with the KOFFER wordmark.
- `koffer-mark.svg` — compact application mark without the wordmark for smaller launcher sizes.
- `koffer-symbolic.svg` — single-colour symbolic form for status/tray or monochrome desktop contexts.

## Visual language

- Background: near-black `#0B0B0B`.
- Primary mark: warm clay / terracotta `#C97845`.
- Vessel: geometric ancient-clay-pot silhouette.
- Audio reference: restrained waveform etching rather than a record/groove motif.
- Wordmark: heavy, blocky, uppercase.

The artwork intentionally uses minimal shading so the mark remains legible at desktop-icon scale.

## Usage guidance

Use the full application icon where the wordmark remains legible. Use the compact mark for small launcher/icon-grid sizes. Use the symbolic variant where the Linux desktop environment expects a monochrome icon.

These files are planning/design assets only. Their presence does not authorize application implementation; Koffer remains in the planning phase until the project owner explicitly starts development.

## Raster export targets

When packaging begins, export the compact mark or full icon as appropriate at:

- 16×16
- 24×24
- 32×32
- 48×48
- 64×64
- 128×128
- 256×256
- 512×512
- 1024×1024

Do not independently redesign the icon during raster export.
