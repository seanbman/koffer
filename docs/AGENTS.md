# Koffer Development Instructions

This file defines the operating rules for any human or software agent contributing to Koffer.

Koffer is currently in **planning**. No implementation work should begin unless the project owner explicitly authorizes development.

The documentation in this directory is the current source of truth for product behavior and design intent.

## 1. Product identity

Koffer is a **full-fledged Linux desktop application** for discovering, organizing, searching, previewing, classifying, preparing, and maintaining metadata for audio samples.

Koffer is an audio sample library and preparation environment.

Koffer is **not a DAW**.

Do not introduce song arrangement, multitrack sequencing, full project mixing, MIDI sequencing, automation lanes, plug-in hosting as a primary workflow, or unrelated production features unless the product documentation is deliberately revised first.

Koffer must remain useful as a standalone desktop application without requiring:
- a browser;
- a manually started local web server;
- a terminal as the normal user interface;
- a network connection for core library features.

## 2. Documentation is authoritative

Before implementing or modifying user-visible behavior, read the relevant files in `/docs`.

Start with:
- `INDEX.md`
- `01-product-overview.md`
- `09-ui-and-interaction-design.md`
- `10-technical-planning-notes.md`

Then read the chapter associated with the feature being changed.

The living manual is the product contract.

If implementation and documentation disagree, do not silently choose one. Determine whether:
1. the implementation is wrong;
2. the documentation is outdated;
3. the behavior is genuinely undecided.

Update documentation when user-visible behavior changes.

Do not rewrite documentation merely to justify an implementation shortcut.

## 3. Planning vs development

The repository may contain planning material before code exists.

When the project is in planning:
- do not scaffold an application;
- do not create placeholder architecture for its own sake;
- do not select libraries permanently without documenting the tradeoff;
- do not create database schemas unless explicitly requested;
- do not convert provisional technical notes into commitments.

Planning work should improve:
- product behavior;
- terminology;
- workflows;
- interaction design;
- safety rules;
- technical evaluation criteria;
- testable acceptance criteria.

Once development is explicitly authorized, implementation must follow these instructions.

## 4. Current technical direction

The current preferred direction is:

- Python
- PySide6 / Qt
- SQLite
- local filesystem indexing
- local audio analysis
- local ML inference
- non-destructive sample preparation
- background workers for expensive operations

These are the current design choices, but they are not immutable.

A different technical choice must have a clear product or engineering reason and must be documented before broad adoption.

Do not replace the desktop architecture with Electron, a browser shell, a hosted web app, or a local web frontend merely because those approaches are familiar.

## 5. Linux desktop requirements

Koffer must behave like a proper Linux desktop application.

Implementation should account for:
- standard application launchers;
- application icon and desktop entry;
- native window lifecycle;
- keyboard focus;
- standard shortcuts;
- context menus where appropriate;
- drag-and-drop;
- clipboard behavior;
- native file and directory selection;
- persistent window geometry and pane state;
- HiDPI scaling;
- Wayland;
- X11 where practical;
- removable storage;
- inaccessible or temporarily offline paths;
- XDG configuration, data, and cache locations;
- desktop audio backends such as PipeWire and PulseAudio, with ALSA considerations where necessary.

Do not assume a single Linux distribution unless the supported-platform policy explicitly says so.

Do not assume the user has a developer environment installed.

## 6. Core domain model

Use the language defined by the manual.

Important concepts include:

### Source
A filesystem directory authorized for scanning.

### Sample
An audio file known to Koffer.

### Collection
A user-defined logical grouping of Samples that does not require duplicate audio files.

### Metadata
Information describing a Sample, including technical, descriptive, and musical information.

### Suggestion
A classification proposed by Koffer analysis that has not yet been confirmed by the user.

Keep these concepts distinct in code and UI.

Do not use raw filesystem folders as a substitute for Collections.

Do not treat AI Suggestions as confirmed user metadata.

## 7. Sample-domain terminology

Use domain language appropriate to music production.

Primary classification dimensions include:
- Sample Type
- Instrument / Source
- Musical Role
- Genre / Style
- Character
- BPM
- Key
- mode
- user tags

Sample Type includes concepts such as:
- One-shot
- Loop
- Phrase
- Stem
- Track
- Texture
- Ambience
- SFX

Do not collapse all classification into one rigid taxonomy.

A Sample can have multiple meaningful attributes at once.

## 8. Filesystem safety

Filesystem safety is a core requirement.

Koffer supports:
- Reference
- Copy
- Move

These operations must remain semantically distinct.

### Reference
Leaves the source file in place.

### Copy
Creates another file while preserving the source.

### Move
Relocates the original file.

Never turn Reference into Copy or Move as a hidden side effect.

Never silently overwrite an existing file.

Never silently delete a source file.

Never perform destructive cleanup based only on duplicate detection.

Batch file operations must expose conflicts before destructive changes are committed.

Operations that alter user files must produce useful errors and recover cleanly from interruption.

## 9. Metadata editing

Koffer may read and write metadata embedded in supported audio formats.

Relevant fields may include:
- title;
- artist / author;
- album;
- album artist;
- genre;
- date / year;
- track number;
- comment / description;
- composer;
- copyright;
- embedded cover artwork.

Metadata capabilities vary by format.

Do not pretend unsupported fields can be written safely.

Koffer must distinguish between:

### Update Original
Write supported metadata to the existing file.

### Write to Copy
Write metadata to a copied or rendered file while leaving the original untouched.

A library-only classification change must never automatically rewrite an audio file.

Embedded artwork and external artwork must be distinguishable.

## 10. Non-destructive audio preparation

Sample preparation should be non-destructive by default.

The application may store a preparation recipe containing operations such as:
- trim start/end;
- fades;
- attack;
- decay or release;
- gain;
- normalization;
- pitch shift;
- target key;
- time stretch;
- reverse;
- channel conversion;
- sample-rate conversion;
- bit-depth conversion;
- output format.

The source file should remain unchanged until the user explicitly chooses a write or render operation.

Do not mutate source audio merely to provide preview behavior.

## 11. Audio playback and responsiveness

Playback must feel immediate.

Long-running work must not block playback or freeze the UI.

Scanning, metadata extraction, waveform generation, BPM analysis, key analysis, ML inference, and embedding generation should be designed as background work.

The main UI thread must remain responsive.

Background jobs should expose:
- current state;
- progress where measurable;
- failure state;
- retry or safe rebuild behavior;
- cancellation or pause where technically reasonable.

A partially analyzed Sample should still be browsable.

## 12. Local inference

Koffer's intelligent classification should be local-first.

The planned inference system combines:
1. filename evidence;
2. directory-path evidence;
3. embedded metadata;
4. deterministic audio features;
5. semantic audio-model output;
6. confidence/evidence fusion;
7. user review.

PANNs is currently an evaluation candidate, not a mandatory dependency.

Any chosen model must be reviewed for:
- license;
- redistribution rights;
- commercial compatibility;
- disk footprint;
- memory use;
- CPU performance;
- optional GPU behavior;
- inference quality;
- packaging complexity.

Do not add cloud inference for core classification.

Do not upload user audio without an explicit future product decision and clear user-facing consent.

## 13. Suggestions are not facts

The UI and data model must distinguish:
- factual technical metadata;
- embedded file metadata;
- inferred Suggestions;
- user-confirmed classification;
- user-created tags.

A confidence score is not proof.

Users must be able to:
- accept a Suggestion;
- reject it;
- edit it;
- ignore it;
- review batches of Suggestions.

Do not overwrite confirmed user metadata with later model output.

## 14. Search and library scale

Koffer is expected to handle large libraries.

Design search, filtering, and indexing for libraries containing at least tens of thousands of files.

Search should support combinations of:
- text;
- Sample Type;
- Instrument / Source;
- Role;
- Genre / Style;
- Character;
- BPM;
- Key;
- duration;
- file format;
- technical properties;
- Collections;
- user tags;
- suggestion state.

Avoid architectural decisions that require loading the entire library into UI memory for routine browsing.

Search and filter results should be incremental and responsive.

## 15. Similarity search

Audio embeddings may support "Find Similar".

Similarity search is distinct from metadata search.

Embeddings should be treated as rebuildable derived data.

Do not make Collections, user tags, or confirmed metadata dependent on the continued existence of a particular embedding model.

If models change, Koffer should be able to regenerate similarity indexes.

## 16. Persistence and database design

SQLite is the current local-state candidate.

Persistent user-authored data must be distinguishable from rebuildable derived data.

Examples of user-authored or valuable state:
- Sources;
- Collections;
- confirmed metadata;
- user tags;
- preparation recipes;
- preferences.

Examples of rebuildable state:
- waveform caches;
- derived spectral features;
- some inference outputs;
- embeddings;
- temporary renders.

Do not design cache deletion so that it removes valuable user organization.

Schema migrations must be explicit once persistence is implemented.

Never rely on destructive schema recreation as a normal upgrade path.

## 17. Error handling

Errors should be actionable.

Do not:
- swallow filesystem errors;
- silently skip failed metadata writes;
- hide failed analysis;
- continue destructive batch work after an unrecoverable conflict without telling the user.

Prefer messages that explain:
- what operation failed;
- which file or Source was affected;
- whether user data changed;
- what the user can do next.

Logs may contain technical detail, but user-facing errors should remain understandable.

## 18. Performance principles

Optimize for perceived responsiveness first.

Important expectations:
- UI remains interactive during scans;
- playback starts promptly;
- search returns quickly;
- cached analysis is reused;
- unchanged files are not reanalyzed unnecessarily;
- large Sources are processed incrementally;
- expensive inference can be throttled or deferred.

Do not prematurely optimize obscure code paths while blocking basic desktop usability.

Measure before optimizing.

## 19. UI implementation principles

The current design uses:
- navigation sidebar;
- central Sample browser;
- right-side Inspector;
- persistent playback/status area.

Respect the current information architecture unless documentation is intentionally changed.

UI should be:
- dark by default;
- high contrast;
- information-dense but readable;
- keyboard friendly;
- usable with large datasets;
- clear about selected and focused state.

Do not introduce mobile-first navigation patterns.

Do not make important workflows depend on hover alone.

## 20. Accessibility and input

Support keyboard operation for routine library work.

Maintain:
- visible focus;
- readable contrast;
- usable control sizes;
- semantic labels for controls;
- predictable tab order.

Do not assume a mouse is always used.

Do not break Linux accessibility tooling through unnecessary custom-drawn controls when standard Qt controls can satisfy the design.

## 21. Testing expectations

Once development begins, tests should cover behavior with real failure modes rather than only happy paths.

Required test areas should include:

### Library and Sources
- recursive scanning;
- exclusions;
- changed files;
- missing files;
- removable storage disappearance;
- duplicate Source handling.

### File operations
- Reference;
- Copy;
- Move;
- destination conflicts;
- interrupted operations;
- permission failures;
- batch behavior.

### Metadata
- read supported tags;
- write supported tags;
- preserve unsupported content where practical;
- artwork handling;
- Update Original;
- Write to Copy;
- format-specific limitations.

### Audio preparation
- non-destructive recipes;
- trim boundaries;
- render output;
- pitch/time transformations;
- format conversion;
- source preservation.

### Search
- filename search;
- combined facets;
- large result sets;
- Collection filters;
- metadata filters.

### Inference
- suggestion persistence;
- accept/reject/edit;
- model failure;
- missing model;
- confidence display;
- reanalysis without overwriting confirmed data.

### Desktop behavior
- background work does not freeze the UI;
- window state persists;
- keyboard navigation;
- drag-and-drop;
- common Wayland/X11 behavior where testable.

Prefer deterministic unit and integration tests around core services.

UI tests should focus on critical workflows rather than attempting to snapshot every pixel.

## 22. Test data

Never rely on a developer's personal sample library for automated tests.

Use:
- generated audio fixtures;
- small openly licensed fixtures;
- synthetic metadata cases;
- temporary directories.

Keep fixtures small enough for fast local and CI execution.

Do not commit copyrighted commercial sample packs.

## 23. Dependencies

Every significant dependency must earn its place.

Before adding one, evaluate:
- license;
- maintenance status;
- Linux support;
- package size;
- transitive dependency burden;
- native-system requirements;
- Flatpak/AppImage implications;
- whether it materially simplifies the product.

Avoid duplicate libraries that solve the same problem unless there is a clear reason.

Pin or constrain dependencies appropriately once implementation begins.

## 24. Licensing

Koffer is currently under the MIT license.

Do not introduce dependencies, models, codecs, assets, or bundled content whose licensing conflicts with the intended distribution model.

Pay special attention to:
- pretrained model licenses;
- non-commercial restrictions;
- copyleft obligations;
- FFmpeg codec/build configuration;
- artwork/icons/fonts;
- sample audio used for demos or tests.

A technically excellent dependency is not acceptable if its license is incompatible with Koffer's distribution goals.

## 25. Security and privacy

Treat local audio libraries as private user data.

Do not collect or transmit:
- filenames;
- directory paths;
- metadata;
- embeddings;
- audio content

unless a future feature explicitly requires it and the product documentation has been updated.

Avoid executing or interpreting untrusted file content beyond what is needed for media parsing.

Assume malformed media files exist.

Use libraries and subprocess invocation safely.

Never construct shell commands through unsafe string interpolation with user-controlled paths.

## 26. Git and change discipline

Keep commits focused.

A change should not mix unrelated refactors, feature work, and documentation cleanup.

Before completing a change:
1. review the relevant manual chapter;
2. update documentation if behavior changed;
3. run applicable tests;
4. inspect the diff for accidental scope growth;
5. verify no source-file safety rule was weakened.

Do not commit generated caches, local databases, model downloads, virtual environments, temporary renders, or personal library paths.

## 27. Documentation discipline

When implementing a documented feature:
- preserve the terminology used in the manual;
- add concrete behavior details discovered during implementation;
- note intentional limitations;
- update mockups when workflow structure materially changes.

Documentation should describe the user's experience.

Internal architecture documentation may explain implementation separately, but it must not replace the user manual.

## 28. Architecture boundaries

Prefer clear separation between:
- UI;
- library/indexing services;
- filesystem operations;
- metadata services;
- audio playback;
- audio processing;
- inference;
- persistence;
- background job orchestration.

Do not put destructive filesystem logic directly inside UI event handlers.

Do not make UI widgets responsible for database transactions or model inference.

Keep domain behavior testable without launching the full desktop application.

## 29. Future-proofing

Koffer should be able to evolve without tying the library permanently to one:
- ML model;
- audio-analysis library;
- filesystem layout;
- packaging format;
- search implementation.

Persist durable user intent, not unnecessary implementation details.

Treat derived data as replaceable whenever practical.

## 30. Things agents must not do

Do not:
- begin implementation while the project is explicitly still planning;
- turn Koffer into a DAW;
- replace the desktop product with a web application;
- make cloud services mandatory for core use;
- silently move, delete, overwrite, or rewrite user files;
- treat model Suggestions as confirmed metadata;
- overwrite confirmed user classification during reanalysis;
- assume every audio format supports the same tags;
- block the main UI during analysis;
- commit large ML weights without a deliberate packaging decision;
- add dependencies without checking licenses;
- commit private sample libraries or copyrighted sample packs;
- change user-visible behavior without updating the manual;
- invent new product requirements merely to complete a coding task.

## 31. When requirements are unclear

If a requirement is missing but implementation can proceed safely with a conservative internal choice, keep the choice reversible and document it.

If a choice changes user-visible behavior, data safety, file formats, privacy, or the product boundary, do not silently decide it.

Record the unresolved decision in documentation and request product direction before committing to irreversible behavior.

## 32. Definition of done

A development change is not complete merely because the code runs.

For applicable work, "done" means:
- behavior matches the manual;
- user files remain safe;
- UI remains responsive;
- errors are surfaced appropriately;
- tests cover the important behavior;
- documentation is current;
- dependencies and licensing are acceptable;
- Linux desktop behavior has been considered;
- no unrelated scope was introduced.

Koffer should become powerful through disciplined library management and sample preparation, not through uncontrolled feature accumulation.
