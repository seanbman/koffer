# Koffer — Codex Execution Contract

This file is intentionally at repository root so Codex sees it before touching code.

## Mission

Build the complete Koffer Linux desktop product described in `docs/`. Do not optimize for “widgets exist”, “tests pass”, or “screen is reachable”. Optimize for a musician being able to import a library, understand it, edit it, hear changes, classify it with local ML, organize it, and export useful samples without reading engineering jargon.

The current remediation mandate is defined by:

1. `docs/29-codex-product-rebuild-directive.md`
2. `docs/30-visual-product-redesign.md`
3. `docs/31-sample-workbench-waveform-editor.md`
4. `docs/32-local-ml-classification-spec.md`
5. `docs/33-user-manual.md`
6. `docs/34-screen-by-screen-remediation.md`
7. `docs/35-definition-of-done-and-acceptance.md`

These files clarify and strengthen the older product documents. They do not authorize weakening filesystem safety, privacy, provenance, or Linux desktop requirements.

## Non-negotiable product corrections

- “Prepare” is not an acceptable vague primary workflow. User-facing copy uses **Edit Sound** and opens the Sample Workbench.
- A Sample can be edited non-destructively by manipulating its waveform directly: trim handles, fades, loop region, gain, normalize, reverse, pitch, time stretch, channel/rate/bit-depth/output preparation.
- Metadata/classification editing must be plainly reachable. The user must be able to revise Koffer classifications, tags, and supported embedded metadata.
- Local semantic ML is a V1 completion requirement. Koffer may remain usable when the model is absent, but V1 is not complete until the model can be installed, runs locally, automatically analyzes new Samples, backfills existing Samples, produces mapped Suggestions, and powers Similar Sounds.
- Raw JSON, evidence blobs, hashes, provider internals, and provenance diagnostics do not belong in the normal primary UI. Put them behind **Analysis Details**, diagnostics, tooltips, or an advanced disclosure.
- The interface must look like a deliberate music-production utility. Use the richer color system and layout hierarchy in `30-visual-product-redesign.md`.
- Buttons are grouped by intent and frequency. Do not scatter actions across headers, footers, arbitrary rows, and unrelated panes.
- Every user-facing action must either work end-to-end or not exist yet. No decorative buttons.
- Never mutate source audio simply because the waveform editor changed. Edits are recipes until the user explicitly renders/exports or chooses an explicit supported in-place metadata write.
- Never auto-confirm ML output. Machine output is a Suggestion until accepted or edited by the user.

## Required execution behavior

Before coding, read `docs/INDEX.md`, `docs/INSTRUCTIONS.md`, and all seven remediation documents above. Then inspect the current implementation rather than assuming the documentation is already satisfied.

Work from current `dev`. Keep `main` untouched until the release gate.

For every cohesive repair:

1. identify the user-visible defect;
2. cite the relevant screen and acceptance requirement;
3. implement real service/domain behavior before or with UI wiring;
4. remove obsolete UI rather than leaving both old and new workflows;
5. add focused tests;
6. run `make repo-guard`, lint, strict mypy, and relevant pytest;
7. run the full QA suite before declaring the repair accepted;
8. update docs/mockups when the visual or behavioral contract changes;
9. continue automatically to the next P0/P1 item.

Routine engineering decisions do not require owner approval. Stop only for a genuine hard block described in `docs/INSTRUCTIONS.md`.

## Visual verification rule

Passing automated tests is necessary and insufficient.

For S00–S21, Codex must perform a visual review at 1440×900 and at the minimum supported desktop size. Verify:

- no clipped or overlapping controls;
- no giant empty panels;
- no random button rows;
- no debug-looking text areas;
- no raw JSON in the default path;
- primary action is visually obvious;
- action groups match the screen goal;
- color communicates information without becoming noisy;
- waveform editing handles are obvious and usable;
- selected, focused, playing, analyzing, suggested, confirmed, warning, and error states are visually distinguishable.

A screen that is technically wired but visually incoherent is not done.

## Finish line

Do not stop at a green CI checkpoint. The finish line is the release contract in `docs/35-definition-of-done-and-acceptance.md` plus the existing release requirements.
