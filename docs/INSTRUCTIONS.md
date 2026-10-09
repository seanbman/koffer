# Koffer End-to-End Implementation Instructions

## Mission

Build **the complete Koffer product described by this repository**.

The mission starts at the current documentation-only state and ends when a new Linux user can install a release AppImage, launch Koffer from the desktop, add real audio Sources, search and audition them, organize them, edit supported metadata safely, prepare audio non-destructively, render outputs, use local Suggestions and similarity features, recover from missing/offline storage, maintain the library, and complete every screen acceptance contract without requiring a developer environment.

Do not stop because the application launches. Do not stop because the database exists. Do not stop because a few screens work. Do not stop because unit tests pass. The finish line is the complete documented product and release artifact.

## Authorization

Development is authorized.

This authorization is intentionally broad enough to complete the documented product without routine approval gates. It does **not** authorize changing the product into something else, weakening data-safety requirements, uploading private audio, or bypassing Dreadnought.

## Control-plane rule

Dreadnought is the canonical execution authority.

The host agent/orchestrator may:
- read canonical Koffer;
- read these instructions;
- decompose work into bounded Orders;
- seed and refresh scratch workspaces;
- dispatch Cursor Project Arms/minions;
- inspect returned changes;
- run independent verification;
- promote accepted work;
- update Grapher/evaluation records;
- report progress and token use.

The host agent/orchestrator must **not** implement product code directly into canonical Koffer.

Cursor Project Arms implement Orders in scratch only.

Canonical mutation follows this sequence:

~~~text
documentation / mission
        ↓
Dreadnought decomposes bounded Order
        ↓
scratch workspace seeded from current dev
        ↓
Cursor Project Arm implements + tests
        ↓
Arm returns evidence
        ↓
Dreadnought independently verifies
        ↓
accepted change promoted to canonical dev
        ↓
Grapher + evaluation + token telemetry recorded
        ↓
next Order
~~~

If Dreadnought tooling changes names, preserve the protocol even if command names differ.

## Autonomous completion rule

After bootstrap, continue through the implementation roadmap without asking the owner to approve ordinary engineering choices.

Resolve reversible implementation details using:
1. this instruction set;
2. the end-state product docs;
3. the technical contracts;
4. the safest conventional Linux/Python/Qt choice.

Record the choice when it materially affects future work.

Only stop for a true hard block:
- required repository/tool permission is unavailable;
- a required external credential cannot be replaced by a local/test substitute;
- a licensing conflict would make distribution unlawful and no documented fallback exists;
- two canonical requirements directly contradict each other on data safety or product identity;
- continuing would require an irreversible action outside the repository that the owner did not authorize.

A failing test, difficult dependency, packaging bug, model problem, or implementation mistake is **not** a reason to stop. Diagnose, revise strategy, and continue.

## Required reading before decomposition

Dreadnought must ingest, in this order:

1. `README.md`
2. `docs/INSTRUCTIONS.md`
3. `docs/INDEX.md`
4. `docs/AGENTS.md`
5. `docs/11-end-state-product-spec.md`
6. `docs/12-screen-catalog.md`
7. `docs/13-ui-design-system.md`
8. `docs/14-navigation-and-user-flows.md`
9. `docs/15-ui-acceptance-contract.md`
10. `docs/16-system-architecture.md`
11. `docs/17-data-model-and-database.md`
12. `docs/18-jobs-concurrency-and-state.md`
13. `docs/19-audio-metadata-analysis-pipeline.md`
14. `docs/20-testing-fixtures-and-quality.md`
15. `docs/21-packaging-ci-and-release.md`
16. `docs/22-implementation-roadmap.md`
17. `docs/23-dependencies-models-and-licensing.md`
18. `docs/24-operations-diagnostics-and-recovery.md`
19. `docs/25-order-template.md`
20. `docs/26-command-reference.md`
21. `docs/29-codex-product-rebuild-directive.md`
22. `docs/30-visual-product-redesign.md`
23. `docs/31-sample-workbench-waveform-editor.md`
24. `docs/32-local-ml-classification-spec.md`
25. `docs/33-user-manual.md`
26. `docs/34-screen-by-screen-remediation.md`
27. `docs/35-definition-of-done-and-acceptance.md`
28. relevant domain chapters 01–10 and matching SVG mockups.

## Branch contract

- `main` is release/stable.
- `dev` is the canonical integration branch during development.
- Dreadnought seeds scratch from current `dev`.
- Arms never push directly to `main`.
- Arms never treat a stale scratch state as authoritative.
- Promotion to `dev` occurs only after Dreadnought verification.
- Release promotion from `dev` to `main` happens only after the release gate in `21-packaging-ci-and-release.md`.

## Grapher persistence boundary

Grapher is part of the Dreadnought control plane, but its working brain is **not Koffer source**.

- `.grapher/**` stays local and untracked.
- "record Grapher/evaluation" means use Grapher's own local mutation/recording path after verification.
- Do not copy or export Grapher's whole `config`, history, knowledge, vector, cache, or derived state into a Koffer commit.
- Do not force-add ignored Grapher files.
- If an Order requires durable repository evidence, commit only the smallest repo-native artifact that proves that specific acceptance criterion and is useful without Grapher. A focused benchmark report or release manifest is acceptable; a Grapher brain dump is not.
- Dreadnought must run `make repo-guard` before canonical promotion. Any tracked `.grapher/**` path fails promotion.

This boundary is deliberate: Git records product source and intentional audit artifacts; Grapher records evolving agent/control-plane knowledge.

## Order sizing

An Order is bounded around one cohesive outcome that can be independently verified.

Good Orders:
- establish application/package skeleton and launch smoke test;
- implement schema migrations and repository layer;
- implement Source registration + recursive scanner;
- implement S01 browser shell against real repository data;
- implement metadata write-to-copy with verification;
- implement AppImage staging and launch smoke test.

Bad Orders:
- "build the whole backend";
- "implement all UI";
- "finish audio";
- "fix whatever is left".

Each Order must cite:
- roadmap phase;
- Screen IDs if user-facing;
- affected architecture modules;
- acceptance criteria;
- tests to run;
- files it may touch;
- files/behavior it must not change.

Use `25-order-template.md`.

## Definition of a successful Order

An Order returns:
- focused diff;
- tests added/updated;
- tests executed;
- command results;
- acceptance evidence;
- known limitations that remain inside later roadmap scope;
- token usage;
- no hidden canonical mutation;
- `make repo-guard` passes and no Grapher control-plane state is tracked.

Dreadnought independently reruns the relevant verification before promotion.

## Token telemetry and runaway prevention

Every completed or failed Order reports:

~~~text
ORDER:
STATUS:
PROGRESS:
TOKENS INPUT:
TOKENS OUTPUT:
TOKENS TOTAL:
TOKENS CUMULATIVE CAMPAIGN:
TESTS:
ACCEPTANCE:
NEXT ORDER:
~~~

Behavioral thresholds:
- at ~70% of an agent context budget, compact state and avoid rereading irrelevant files;
- at ~85%, finish the current bounded proof, summarize, and hand off rather than opening new exploratory branches;
- at ~95%, do not begin expensive new reasoning paths;
- after three materially similar failed attempts, change strategy before another attempt;
- repeated dependency/build failures require root-cause evidence, not blind retries.

Token thresholds are reporting/strategy controls, not routine pause gates.

## Progress reporting

Dreadnought should be able to produce a compact campaign status at any time:

~~~text
PHASE: 4 / 14 — Browser + Playback
ORDERS: 3 accepted / 1 active / 7 remaining in phase
SCREENS GREEN: S00, S01 shell
TESTS: 184 passed
PACKAGE SMOKE: not yet required
TOKENS THIS ORDER: 21,400
TOKENS CAMPAIGN: 312,600
BLOCKERS: none
NEXT: S01 real search model + Inspector binding
~~~

## Current remediation mandate

Before resuming ordinary roadmap completion, repair the current `dev` implementation according to docs 29–35.

The following are P0 until proven complete:

- a direct-manipulation Edit Sound waveform workbench;
- plainly reachable classification/tag/embedded-metadata editing;
- model installation plus actual local semantic inference;
- automatic semantic analysis for new Samples when enabled;
- existing-library semantic backfill;
- mapped Suggestions and real embedding-based Similar Sounds;
- removal of raw/debug evidence from primary user surfaces;
- coherent action hierarchy and richer semantically colored visual design.

A green QA run does not waive these requirements.

## Product-complete exit criteria

The mission is complete only when all of the following are true:

- S00–S21 satisfy `15-ui-acceptance-contract.md`;
- all critical flows in `14-navigation-and-user-flows.md` pass end-to-end tests;
- all data-safety invariants in `11-end-state-product-spec.md` hold;
- schema migrations work from a new database and from every retained migration fixture;
- 100k-library performance fixture meets documented responsiveness targets;
- filesystem jobs survive partial failure with itemized state;
- metadata writes are reread and verified;
- rendered audio is verified and source content remains unchanged;
- model-disabled mode still provides a fully usable library;
- model-enabled Suggestions and Similar Sounds work locally;
- offline/missing Source recovery works;
- backup/restore and cache rebuild behavior works;
- diagnostics bundle excludes audio by default;
- CI is green;
- release AppImage launches on supported clean Linux test environments;
- desktop entry/icon integration is valid;
- release contains license notices and checksums;
- no P0/P1 defects remain;
- documentation reflects actual behavior;
- Dreadnought campaign record and Grapher evidence are complete.

Then cut a release candidate, run the release gate, promote to `main`, tag the version, and publish the AppImage/checksum artifacts.

## What not to do

Do not:
- substitute a web UI;
- create a toy demo and call it V1;
- leave buttons wired to placeholders;
- silently disable documented screens;
- implement destructive filesystem logic inside Qt event handlers;
- reuse a UI-thread SQLite connection in workers;
- swallow metadata/file errors;
- silently overwrite files;
- treat Suggestions as confirmed metadata;
- upload user audio;
- bundle unreviewed model weights;
- let a Cursor host agent bypass Dreadnought because it is "faster";
- rewrite documentation to rationalize an implementation shortcut.

## Final principle

The documentation exists so the agent does not need product invention privileges.

Build what is written. Where low-level implementation details remain reversible, choose the safe conventional solution, record it, test it, and keep moving until Koffer is a real finished desktop application.
