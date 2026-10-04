# 20. Testing, Fixtures, and Quality Gates

## Philosophy

Tests prove the safety and user contract, not just line execution.

No Order is accepted with knowingly failing tests in its affected scope.

## Test layers

### Unit

Pure domain, query parsing, recipe validation, mapping, conflict policy, error types.

Target: fast, no Qt event loop unless necessary, no network.

### Integration

SQLite repositories, migrations, filesystem services, Mutagen, ffprobe/FFmpeg wrappers, backup/restore.

Use temporary directories and generated fixtures.

### UI

pytest-qt:
- navigation;
- table/Inspector binding;
- keyboard focus;
- screen state;
- loading/error states;
- dialog safety copy;
- Job progress presentation.

### End-to-end

Launch real app against temporary XDG directories and fixture library.

Critical flows correspond to flows A–J in `14-navigation-and-user-flows.md`.

### Packaging smoke

Launch packaged AppImage in a clean Linux environment/container/VM with no source checkout or virtualenv.

## Test fixture generator

Create `scripts/generate_test_audio.py` to generate deterministic small files using Python/FFmpeg.

Fixtures include:
- mono WAV sine, 1 second;
- stereo WAV;
- click track at 120 BPM;
- click track at 90 BPM;
- C major tonal fixture;
- A minor tonal fixture;
- silence;
- short impulse;
- 10-second noise/texture;
- files with supported metadata/artwork;
- deliberately malformed/truncated file;
- duplicate byte-identical pair;
- same filename/different-content pair.

Generated fixture source parameters are checked into tests; generated binary fixture size stays small.

## Filesystem failure fixtures

Tests simulate:
- read-only destination;
- missing Source;
- Source disappears during scan;
- permission denied;
- destination exists;
- cross-filesystem move abstraction;
- interrupted copy temp file;
- rename failure;
- metadata writer failure after temp creation.

No test requires the developer's personal sample collection.

## Database migration fixtures

For each released schema version, retain a minimal compressed fixture.

CI:
1. opens fixture;
2. runs all later migrations;
3. verifies invariants and representative data;
4. confirms user-authored state survives.

## Coverage policy

Coverage is a signal, not the only gate.

Minimum:
- domain/services/persistence/filesystem/metadata/jobs: 85% line coverage;
- safety-critical mutation policy modules: 95%;
- UI coverage is behavior-based rather than a raw line target.

A lower threshold requires an explicit documented reason.

## Static gates

Required:
- `ruff check .`;
- `ruff format --check .`;
- `mypy src/koffer`;
- dependency/license verification;
- no secret/private-path scan;
- Markdown link check for docs where practical.

## Safety regression suite

Must always include:
- scan does not move files;
- Collection membership does not copy files;
- accepting Suggestion does not write embedded metadata;
- offline Source does not delete Samples;
- file conflict does not overwrite by default;
- Update Original writes only after explicit target selection;
- Write to Copy preserves original hash;
- render preserves original hash;
- cross-filesystem Move deletes source only after verified copy;
- cache clear preserves Collections/classifications/recipes;
- reanalysis never overwrites confirmed classification.

## Threading regression suite

Prove:
- worker has independent SQLite connection;
- UI timer continues during slow scan;
- progress signals are throttled;
- cancellation works between items;
- UI widgets are only changed on main thread.

## Performance fixture

Create a generated database/filesystem manifest representing 100,000 Samples without storing 100,000 real audio files.

Targets on a reasonable contemporary desktop, measured and recorded:
- app initial usable shell: <= 2 seconds excluding first database creation/model setup;
- common indexed text/filter query: p95 <= 250 ms;
- first 200 browser rows after query: <= 400 ms;
- scrolling does not instantiate entire corpus;
- UI event loop remains responsive during scans/analysis.

These are release targets. If hardware makes exact timing noisy, CI uses relative regression thresholds and a local benchmark report records reference hardware.

## Audio verification

Render tests compare:
- output probe properties;
- expected duration tolerance;
- channel/sample-rate settings;
- source hash unchanged;
- metadata carry-over.

DSP tests use tolerances, not byte equality.

## Metadata verification

For each supported writable container:
1. create fixture;
2. write normalized field;
3. close;
4. reread through independent reader path;
5. assert expected value;
6. assert audio payload remains decodable.

## Model tests

Do not download large weights in normal unit CI.

Use:
- fake semantic provider for contract tests;
- one opt-in model integration job/cache in CI or scheduled workflow;
- checksum manifest test;
- mapping/evidence fusion tests.

Release candidate must run real local model smoke before publication.

## Defect severity

P0:
- data loss/corruption;
- silent overwrite/delete;
- source modified by non-destructive flow;
- app cannot launch;
- package unusable.

P1:
- critical documented flow impossible;
- repeated crash;
- offline recovery corrupts state;
- metadata/render materially wrong;
- UI freezes during normal large-library operations.

P2:
- noncritical feature malfunction with workaround.

P3:
- polish/cosmetic issue.

Release requires zero open P0/P1.

## Order acceptance evidence

Every implementation Order records:
- tests added;
- exact commands run;
- pass/fail count;
- relevant screenshot or structured UI assertion where needed;
- performance measurement if affected;
- original-file hash proof for mutation-sensitive features.
